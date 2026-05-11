"""
Main event loop — the BTC Predictor orchestrator.
Runs on every 15m candle close from Binance WS.
Coordinates: data assembly → pre-filter → advisor + reasoning (parallel) → decision → execution.
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
import structlog

from config import constants as C
from config.constants import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, BRAINS
from src.alerts.telegram_alerts import TelegramAlerts
from src.agents.advisor import AdvisorAgent, AdvisorOpinion
from src.data_sources.binance_client import BinanceClient, Candle
from src.dynamic_flip import FlipDecision, evaluate_flip
from src.execution.polymarket_client import PolymarketClient
from src.features.market_state import MarketState, MarketStateAssembler
from src.pre_filter import PreFilterResult, run_pre_filter
from src.prediction_logger import PredictionLogger
from src.reasoning_prompt import (
    REASONING_SYSTEM_PROMPT,
    ReasoningOutput,
    build_reasoning_prompt,
    parse_reasoning_output,
)
from src.session import SessionManager, SessionPhase

log = structlog.get_logger(__name__)


class BTCPredictor:
    """
    Main orchestrator for the BTC 15m Direction Predictor.

    Flow per 15m cycle:
      1. Wait for Binance WS kline_15m close event
      2. Assemble MarketState (parallel data fetch)
      3. Run PreFilter (hard rules)
      4. If passed: run Advisor + Reasoning in parallel
      5. Reconcile → final call
      6. If ENTER: open session, place bet
      7. Wait for C2/C3/C4 close → resolve bets
      8. Log outcome, update reflection
      9. Repeat
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.running = False
        self._shutdown = asyncio.Event()

        # Components
        self.binance: Optional[BinanceClient] = None
        self.assembler: Optional[MarketStateAssembler] = None
        self.advisor: Optional[AdvisorAgent] = None
        self.session_mgr: SessionManager = SessionManager()
        self.logger: PredictionLogger = PredictionLogger()
        self.polymarket: Optional[PolymarketClient] = None
        self.alerts: Optional[TelegramAlerts] = None

        # State
        self._current_market: Optional[MarketState] = None
        self._analysis_count = 0
        self._uuid_counter = 0
        self._c2_candle: Optional[Candle] = None
        self._c3_candle: Optional[Candle] = None
        self._c4_candle: Optional[Candle] = None
        self._bet_resolution_tasks: list[asyncio.Task] = []

        # Anthropic client for my reasoning
        self._anthropic: Optional[anthropic.AsyncAnthropic] = None
        if ANTHROPIC_API_KEY:
            self._anthropic = anthropic.AsyncAnthropic(
                api_key=ANTHROPIC_API_KEY,
                base_url=ANTHROPIC_BASE_URL,
            )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self):
        """Start the predictor — connect to all data sources."""
        log.info("BTC Predictor starting...", dry_run=self.dry_run)

        self.binance = BinanceClient()
        self.assembler = MarketStateAssembler(self.binance)

        self.polymarket = PolymarketClient(
            wallet_key=C.POLYMARKET_WALLET_KEY if not self.dry_run else ""
        )

        if C.TELEGRAM_BOT_TOKEN and C.TELEGRAM_CHAT_ID:
            self.alerts = TelegramAlerts()

        if ANTHROPIC_API_KEY and C.ANTHROPIC_ADVISOR_KEY:
            self.advisor = AdvisorAgent()

        self.running = True

        # Load any active session from disk
        state = await self.session_mgr.load()
        if state.is_active:
            log.info(f"Resuming active session: {state.summary()}")

        log.info("BTC Predictor started. Waiting for 15m candle close...")

    async def stop(self):
        """Graceful shutdown."""
        log.info("BTC Predictor shutting down...")
        self.running = False
        self._shutdown.set()
        if self.binance:
            await self.binance.__aexit__(None, None, None)
        if self.polymarket:
            await self.polymarket.__aexit__(None, None, None)
        if self.alerts:
            await self.alerts.__aexit__(None, None, None)

    # ── Main Loop ────────────────────────────────────────────────────────

    async def run(self):
        """Main run loop — subscribes to Binance 15m kline WS stream."""
        await self.start()

        # Seed the trade buffer with recent trades for orderflow metrics
        try:
            recent_trades = await self.binance.fetch_recent_trades(limit=500)
            self.binance.seed_trade_buffer(recent_trades)
            log.info(f"Trade buffer seeded with {len(recent_trades)} recent trades")
        except Exception as e:
            log.warning(f"Failed to seed trade buffer: {e}")

        kline_q = await self.binance.subscribe_kline("15m")

        # Keep polling for candle closes
        while self.running:
            try:
                candle: Candle = await asyncio.wait_for(kline_q.get(), timeout=120)
                if not candle.is_closed:
                    continue
                await self._on_candle_close(candle)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def _on_candle_close(self, candle: Candle):
        """
        Called on every 15m candle close (C1).
        This is the main analysis trigger.
        """
        self._uuid_counter += 1
        analysis_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}_{self._uuid_counter:03d}"
        self._analysis_count += 1

        log.info(f"=== CANDLE CLOSE: {candle.open_time} === "
                 f"O={candle.open:.1f} H={candle.high:.1f} "
                 f"L={candle.low:.1f} C={candle.close:.1f} "
                 f"V={candle.volume:.4f} | {candle.candle_pattern}")

        # ── Step 1: Assemble MarketState ──────────────────────────────────
        try:
            state = await self.assembler.assemble(analysis_id)
        except Exception as e:
            log.error(f"MarketState assembly failed: {e}")
            return

        # ── Step 2: Check for active session ──────────────────────────────
        session_state = await self.session_mgr.load()
        if session_state.is_active:
            await self._handle_active_session(candle, session_state)
            return

        # ── Step 3: Pre-filter ─────────────────────────────────────────────
        reflection = await self.logger.get_reflection_context()
        pf_result = run_pre_filter(
            state=state,
            session_active=False,
            consecutive_losses=reflection.get("consecutive_losses", 0),
            last_direction=None,
        )
        pf_result.log()

        if not pf_result.passed:
            await self._alert_if_needed(
                "analysis_skipped",
                reason=pf_result.reason.value,
                confidence=0.0,
                candle_id=analysis_id,
            )
            return

        # ── Step 4: Parallel reasoning ────────────────────────────────────
        advisor_opinion = None
        reasoning_output = None

        # Run advisor + reasoning in parallel
        tasks = []
        advisor_task = None
        reasoning_task = None

        if self.advisor and self._anthropic:
            advisor_task = asyncio.create_task(
                self.advisor.analyze(state, reflection)
            )
            tasks.append(advisor_task)

        if self._anthropic:
            system_prompt, user_prompt = build_reasoning_prompt(
                state, reflection,
                advisor_opinion=None,  # advisor hasn't responded yet
            )
            reasoning_task = asyncio.create_task(
                self._call_reasoning_engine(system_prompt, user_prompt)
            )
            tasks.append(reasoning_task)

        if not tasks:
            log.error("No reasoning engine configured — set ANTHROPIC_API_KEY")
            return

        # Wait for both to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse results
        if advisor_task and not isinstance(results[0], Exception):
            advisor_opinion = results[0]
        if reasoning_task and not isinstance(results[-1], Exception):
            reasoning_output = results[-1]

        # If advisor finished first, rebuild prompt with advisor's view
        if self.advisor and advisor_task.done() and not advisor_task.exception():
            advisor_opinion = advisor_task.result()
            if reasoning_task and not reasoning_task.done():
                # Restart reasoning with advisor's opinion included
                reasoning_task.cancel()
                system_prompt, user_prompt = build_reasoning_prompt(
                    state, reflection,
                    advisor_opinion={
                        "call": advisor_opinion.call,
                        "confidence": advisor_opinion.confidence,
                        "key_signals": advisor_opinion.key_signals,
                        "risk_flags": advisor_opinion.risk_flags,
                        "advisor_strength": advisor_opinion.advisor_strength,
                        "regime": advisor_opinion.regime,
                    },
                )
                reasoning_output = await self._call_reasoning_engine(system_prompt, user_prompt)

        if not reasoning_output:
            log.error("Reasoning engine failed — skipping this cycle")
            return

        # ── Step 5: Reconcile with advisor ─────────────────────────────────
        reasoning_output = self._reconcile_advisor(reasoning_output, advisor_opinion)

        # ── Step 6: Apply confidence gate ─────────────────────────────────
        call = reasoning_output.call
        confidence = reasoning_output.weighted_confidence
        bucket = reasoning_output.confidence_bucket

        if bucket == "LOW" or confidence < C.CONFIDENCE_MEDIUM:
            log.info(f"Confidence {confidence:.2f} below threshold — SKIP")
            await self.logger.log_analysis(
                analysis_id=analysis_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                direction=call, confidence=confidence,
                confidence_bucket=bucket,
                signal_scores=reasoning_output.signal_scores,
                advisor_call=advisor_opinion.call if advisor_opinion else "N/A",
                advisor_confidence=advisor_opinion.confidence if advisor_opinion else 0.0,
                advisor_strength=advisor_opinion.advisor_strength if advisor_opinion else "N/A",
                locked_direction=call,
                current_direction=call,
                pre_filter_reason=pf_result.reason.value if pf_result.reason else "PASSED",
                reasoning_json=reasoning_output.analysis,
                market_price=0.0,
                market_url="",
                c1_price=state.current_price,
                c1_pattern=state.c1.candle_pattern if state.c1 else "N/A",
                rsi_14=state.technical.rsi_14 if state.technical else 0.0,
                vpin=state.vpin,
                cvd=state.cvd,
                funding_rate=state.smart_money.funding_rate_pct if state.smart_money else 0.0,
                fear_greed=state.sentiment.fear_greed_index if state.sentiment else 50,
                regime=reasoning_output.analysis.get("regime", "UNKNOWN"),
            )
            return

        # ── Step 7: Enter session ──────────────────────────────────────────
        await self._enter_session(
            analysis_id=analysis_id,
            state=state,
            reasoning_output=reasoning_output,
            advisor_opinion=advisor_opinion,
            reflection=reflection,
            pf_result=pf_result,
        )

    # ── Reasoning Engine ──────────────────────────────────────────────────

    async def _call_reasoning_engine(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ReasoningOutput:
        """Call Anthropic to get my reasoning output."""
        if not self._anthropic:
            return ReasoningOutput(
                call="SKIP", confidence=0.50, confidence_bucket="LOW",
                signal_scores={}, dimension_weights={}, weighted_confidence=0.50,
                advisor_reconciliation={}, analysis={},
                contradictions=[], key_bullish_signals=[],
                key_bearish_signals=[], risk_factors=[],
                flip_consideration={},
            )

        model = BRAINS["reasoning"]["model"]
        max_tokens = BRAINS["reasoning"]["max_tokens"]
        temperature = BRAINS["reasoning"]["temperature"]

        try:
            response = await self._anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw = ""
            for block in response.content:
                if block.type == "text":
                    raw += block.text

            return parse_reasoning_output(raw)

        except Exception as e:
            log.error(f"Reasoning engine call failed: {e}")
            return ReasoningOutput(
                call="SKIP", confidence=0.50, confidence_bucket="LOW",
                signal_scores={}, dimension_weights={}, weighted_confidence=0.50,
                advisor_reconciliation={}, analysis={},
                contradictions=[], key_bullish_signals=[],
                key_bearish_signals=[], risk_factors=[],
                flip_consideration={},
                raw_response=f"Error: {e}",
            )

    def _reconcile_advisor(
        self,
        reasoning: ReasoningOutput,
        advisor: Optional[AdvisorOpinion],
    ) -> ReasoningOutput:
        """
        Reconcile my reasoning with the advisor's opinion.
        If advisor disagrees significantly, lean toward the conservative call
        unless my confidence is >0.15 higher.
        """
        if not advisor or advisor.call == "SKIP" or advisor.call == reasoning.call:
            reasoning.advisor_reconciliation = {
                "advisor_called": advisor.call if advisor else "SKIP",
                "advisor_confidence": advisor.confidence if advisor else 0.50,
                "agreed": True,
                "conservative_override": False,
                "override_reason": "",
            }
            return reasoning

        # Disagreement
        conf_gap = reasoning.weighted_confidence - advisor.confidence
        if conf_gap > 0.15:
            # My confidence is significantly higher — stick with my call
            reasoning.advisor_reconciliation = {
                "advisor_called": advisor.call,
                "advisor_confidence": advisor.confidence,
                "agreed": False,
                "conservative_override": False,
                "override_reason": f"My confidence {conf_gap:.2f} higher than advisor",
            }
        else:
            # Advisor disagrees — flip to conservative call
            original_call = reasoning.call
            reasoning.call = advisor.call
            reasoning.advisor_reconciliation = {
                "advisor_called": advisor.call,
                "advisor_confidence": advisor.confidence,
                "agreed": False,
                "conservative_override": True,
                "override_reason": "Advisor disagreed with lower confidence — conservative override",
            }
            log.info(f"Advisor override: {original_call} → {reasoning.call}")

        return reasoning

    # ── Session Entry ───────────────────────────────────────────────────

    async def _enter_session(
        self,
        analysis_id: str,
        state: MarketState,
        reasoning_output: ReasoningOutput,
        advisor_opinion: Optional[AdvisorOpinion],
        reflection: dict,
        pf_result: PreFilterResult,
    ):
        """Open a new session and place the first bet (on C2)."""
        direction = reasoning_output.call
        confidence = reasoning_output.weighted_confidence

        log.info(f"=== ENTER SESSION: {direction} @ {confidence:.2f} ===")

        # Start session
        await self.session_mgr.start(
            analysis_id=analysis_id,
            direction=direction,
            confidence=confidence,
            c1_close_time=state.c1.close_time if state.c1 else 0,
            c1_close_price=state.current_price,
        )

        # Discover Polymarket market
        market = None
        market_price = 0.50
        market_url = ""
        try:
            async with PolymarketClient() as pm:
                market = await pm.find_best_btc_market(direction)
                if market:
                    market_price = market.yes_price if direction == "GREEN" else market.no_price
                    market_url = market.market_url
        except Exception as e:
            log.warning(f"Polymarket market discovery failed: {e}")

        # Compute bet size
        bankroll = 1000.0  # TODO: track actual bankroll
        bet_size = self.polymarket.compute_bet_size(
            confidence=confidence,
            market_price=market_price,
            bankroll=bankroll,
        ) if self.polymarket else 10.0

        # Place bet
        async with PolymarketClient() as pm:
            result = await pm.place_order(
                market=market,
                direction=direction,
                size=bet_size,
                market_price=market_price,
            )

        # Record bet in session
        await self.session_mgr.place_bet(
            candle_label="C2",
            direction=direction,
            confidence=confidence,
            market_price=result.filled_price or market_price,
            bet_amount=result.filled_size or bet_size,
        )

        # Log analysis
        await self.logger.log_analysis(
            analysis_id=analysis_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            direction=direction,
            confidence=confidence,
            confidence_bucket=reasoning_output.confidence_bucket,
            signal_scores=reasoning_output.signal_scores,
            advisor_call=advisor_opinion.call if advisor_opinion else "N/A",
            advisor_confidence=advisor_opinion.confidence if advisor_opinion else 0.0,
            advisor_strength=advisor_opinion.advisor_strength if advisor_opinion else "N/A",
            locked_direction=direction,
            current_direction=direction,
            pre_filter_reason="PASSED",
            reasoning_json=reasoning_output.analysis,
            market_price=result.filled_price or market_price,
            market_url=result.market_url or market_url,
            c1_price=state.current_price,
            c1_pattern=state.c1.candle_pattern if state.c1 else "N/A",
            rsi_14=state.technical.rsi_14 if state.technical else 0.0,
            vpin=state.vpin,
            cvd=state.cvd,
            funding_rate=state.smart_money.funding_rate_pct if state.smart_money else 0.0,
            fear_greed=state.sentiment.fear_greed_index if state.sentiment else 50,
            regime=reflection.get("regime", "UNKNOWN"),
        )

        # Alert
        rationale = " | ".join(
            f"{k}: {v:.2f}" for k, v in reasoning_output.signal_scores.items()
        )
        if self.alerts:
            await self.alerts.session_started(
                direction=direction,
                confidence=confidence,
                rationale=rationale,
                market_url=result.market_url or market_url,
                regime=reflection.get("regime", "UNKNOWN"),
            )
            await self.alerts.bet_placed(
                candle="C2",
                direction=direction,
                price=result.filled_price or market_price,
                size=result.filled_size or bet_size,
                market_url=result.market_url or market_url,
                bet_number=1,
            )

        # Schedule C2 resolution
        asyncio.create_task(self._wait_and_resolve_candle("C2"))

    # ── Candle Resolution ────────────────────────────────────────────────

    async def _wait_and_resolve_candle(self, label: str):
        """Wait for the target candle to close, then resolve the bet."""
        # Wait for the candle to form:
        # C1 close at T → bet placed → wait 15 minutes for C{N} to close
        candle_map = {"C2": 1, "C3": 2, "C4": 3}
        wait_for = candle_map.get(label, 1)
        await asyncio.sleep(5)  # Small buffer for WS latency

        # Get the closed candle from Binance
        try:
            candles = await self.binance.fetch_klines(limit=5)
            if len(candles) >= wait_for + 1:
                target_candle = candles[-(wait_for)]
                await self._resolve_candle(label, target_candle)
        except Exception as e:
            log.error(f"Failed to fetch {label} candle for resolution: {e}")

    async def _resolve_candle(self, label: str, candle: Candle):
        """Resolve the bet on a candle and handle session state."""
        session_state = await self.session_mgr.load()
        if not session_state.is_active:
            return

        # Determine if bet won
        direction = session_state.current_direction
        is_green = candle.is_green
        won = (direction == "GREEN" and is_green) or (direction == "RED" and not is_green)

        log.info(f"{label} RESOLVED: close={candle.close:.1f} "
                 f"open={candle.open:.1f} {'GREEN' if is_green else 'RED'} "
                 f"→ {'✅ WIN' if won else '❌ LOSS'} (bet={direction})")

        # Resolve the bet
        await self.session_mgr.resolve_bet(won=won, close_price=candle.close)

        # Alert
        if self.alerts:
            session_state = await self.session_mgr.load()
            await self.alerts.bet_resolved(
                candle=label,
                won=won,
                close_price=candle.close,
                bets_remaining=session_state.bets_remaining,
                session_pnl=session_state.total_pnl,
            )

        if won:
            # Session WON
            await self._handle_session_won(candle, session_state)
        elif session_state.bets_remaining > 0:
            # Session continues — check for flip
            await self._check_flip_and_continue(candle, session_state)
        else:
            # Session LOST — all 3 bets exhausted
            await self._handle_session_lost(candle, session_state)

    async def _check_flip_and_continue(self, candle: Candle, session_state):
        """After a loss, evaluate whether to flip direction."""
        # Get current market state for counter-signals
        analysis_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        try:
            state = await self.assembler.assemble(analysis_id)
        except Exception as e:
            log.warning(f"MarketState fetch for flip check failed: {e}")
            # Continue with current direction
            asyncio.create_task(self._wait_and_resolve_candle(session_state.next_candle))
            return

        # Evaluate flip
        loss_candle = session_state.next_candle  # The next one to bet on
        advisor_conf = 0.50
        cvd_diverging = state.cvd > 0 if session_state.current_direction == "RED" else state.cvd < 0
        funding_reversal = False  # TODO: detect funding reversal

        flip_eval = evaluate_flip(
            original_direction=session_state.locked_direction,
            loss_candle=loss_candle,
            loss_reason=f"C{len(session_state.bets)} loss",
            original_confidence=session_state.bets[-1].confidence if session_state.bets else 0.60,
            counter_signal_strength=0.55,  # TODO: compute from state
            advisor_flip_confidence=advisor_conf,
            vpin=state.vpin,
            cvd_diverging=cvd_diverging,
            funding_reversal=funding_reversal,
            new_technical_breakdown=False,
        )

        if flip_eval.decision == "FLIP":
            await self.session_mgr.flip_direction(
                new_direction=flip_eval.flip_direction,
                reason=flip_eval.trigger_reason,
                confidence=0.60,
            )
            log.warning(f"DIRECTION FLIPPED: {session_state.current_direction} → {flip_eval.flip_direction}")
        elif flip_eval.decision == "SKIP":
            log.info(f"Flip uncertain — skipping remaining bets")
            await self.session_mgr.end_session(total_pnl=0.0)
            return

        # Place next bet
        next_candle = session_state.next_candle
        if next_candle:
            asyncio.create_task(self._wait_and_resolve_candle(next_candle))

    async def _handle_session_won(self, winning_candle: Candle, session_state):
        """Handle a won session."""
        bets = session_state.bets
        won_bet = next((b for b in bets if b.won), bets[-1])
        market_price = won_bet.market_price if won_bet else 0.50
        bet_amount = won_bet.bet_amount if won_bet else 10.0
        pnl = bet_amount / max(market_price, 0.01) - bet_amount

        session_state.total_pnl = pnl

        # Log outcome
        await self.logger.log_session_outcome(
            analysis_id=session_state.analysis_id,
            session_won=True,
            session_lost=False,
            winning_candle=won_bet.candle_label,
            total_bets=len(bets),
            total_pnl=pnl,
            winning_candles=[won_bet.candle_label],
            losing_candles=[b.candle_label for b in bets if not b.won],
            flip_occurred=session_state.flip_occurred,
        )

        # Alert
        if self.alerts:
            await self.alerts.session_won(
                winning_candle=won_bet.candle_label,
                pnl=pnl,
                total_bets=len(bets),
                confidence=won_bet.confidence,
                flip_occurred=session_state.flip_occurred,
            )

        await self.session_mgr.reset()

    async def _handle_session_lost(self, last_candle: Candle, session_state):
        """Handle a lost session (all 3 bets exhausted)."""
        bets = session_state.bets
        total_loss = sum(b.bet_amount for b in bets)

        # Log outcome
        await self.logger.log_session_outcome(
            analysis_id=session_state.analysis_id,
            session_won=False,
            session_lost=True,
            winning_candle="",
            total_bets=len(bets),
            total_pnl=-total_loss,
            winning_candles=[],
            losing_candles=[b.candle_label for b in bets],
            flip_occurred=session_state.flip_occurred,
        )

        # Check circuit breaker
        stats = await self.logger.compute_stats()
        if self.alerts and stats.get("consecutive_losses", 0) >= 3:
            await self.alerts.circuit_breaker(
                consecutive_losses=stats["consecutive_losses"],
                reason="3 consecutive losses",
                edge_required="$0.05",
            )

        # Alert
        if self.alerts:
            await self.alerts.session_lost(
                total_loss=total_loss,
                direction=session_state.locked_direction,
                all_bets=[{"candle": b.candle_label, "won": bool(b.won),
                           "close_price": b.close_price or 0.0} for b in bets],
            )

        await self.session_mgr.reset()

    async def _handle_active_session(self, candle: Candle, session_state):
        """Handle incoming candle while a session is active."""
        log.debug(f"Candle received during active session: {session_state.summary()}")

    async def _alert_if_needed(self, alert_type: str, **kwargs):
        if self.alerts:
            if alert_type == "analysis_skipped":
                await self.alerts.analysis_skipped(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    """Run the BTC Predictor."""
    import argparse
    parser = argparse.ArgumentParser(description="BTC 15m Direction Predictor")
    parser.add_argument("--live", action="store_true", help="Enable live trading (not paper)")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    predictor = BTCPredictor(dry_run=not args.live)

    # Handle signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(predictor.stop()))

    try:
        await predictor.run()
    except KeyboardInterrupt:
        pass
    finally:
        await predictor.stop()


if __name__ == "__main__":
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    asyncio.run(main())
