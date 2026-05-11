"""
Main event loop — BTC Predictor v4.0 Orchestrator.
Coordinates: data assembly → pre-filter → specialist agents → Governor → execution.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog

from config import constants as C
from config.constants import ANTHROPIC_API_KEY
from src.alerts.telegram_alerts import TelegramAlerts
from src.agents.advisor import AdvisorAgent, AdvisorOpinion
from src.agents.base.base_agent import AgentSignal
from src.agents.governor.governor import DIMENSION_WEIGHTS, GovernorAgent, GovernorDecision
from src.agents.specialists.quant_master import QuantMaster
from src.agents.specialists.flow_master import FlowMaster
from src.agents.specialists.macro_monarch import MacroMonarch
from src.agents.specialists.sentiment_scout import SentimentScout
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
    Main orchestrator for the BTC 15m Direction Predictor v4.0.

    Flow per 15m cycle:
      1. Wait for Binance WS kline_15m close event
      2. Assemble MarketState (parallel data fetch)
      3. Run PreFilter (hard rules)
      4. If passed: run all 5 specialists + Advisor in parallel
      5. Governor reconciles → final call
      6. If ENTER: open session, place bet
      7. Wait for C2/C3/C4 close → resolve bets
      8. Log outcome, run reflection, repeat
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.running = False
        self._shutdown = asyncio.Event()

        # Components
        self.binance: Optional[BinanceClient] = None
        self.assembler: Optional[MarketStateAssembler] = None
        self.session_mgr = SessionManager()
        self.logger = PredictionLogger()
        self.polymarket: Optional[PolymarketClient] = None
        self.alerts: Optional[TelegramAlerts] = None

        # Agents
        self.advisor: Optional[AdvisorAgent] = None
        self.governor: Optional[GovernorAgent] = None
        self.quant: Optional[QuantMaster] = None
        self.flow_master: Optional[FlowMaster] = None
        self.macro_monarch: Optional[MacroMonarch] = None
        self.sentiment_scout: Optional[SentimentScout] = None

        # State
        self._analysis_count = 0
        self._uuid_counter = 0
        self._current_decision: Optional[GovernorDecision] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self):
        """Start the predictor — connect all data sources and agents."""
        log.info("BTC Predictor v4.0 starting...", dry_run=self.dry_run)

        self.binance = BinanceClient()
        await self.binance.__aenter__()
        self.assembler = MarketStateAssembler(self.binance)

        self.polymarket = PolymarketClient(
            wallet_key=C.POLYMARKET_WALLET_KEY if not self.dry_run else ""
        )

        if C.TELEGRAM_BOT_TOKEN and C.TELEGRAM_CHAT_ID:
            self.alerts = TelegramAlerts()

        if ANTHROPIC_API_KEY:
            # Start all agents
            self.advisor = AdvisorAgent()
            await self.advisor.__aenter__()

            self.governor = GovernorAgent()
            await self.governor.__aenter__()

            self.quant = QuantMaster()
            await self.quant.__aenter__()

            self.flow_master = FlowMaster()
            await self.flow_master.__aenter__()

            self.macro_monarch = MacroMonarch()
            await self.macro_monarch.__aenter__()

            self.sentiment_scout = SentimentScout()
            await self.sentiment_scout.__aenter__()

        self.running = True

        # Resume any active session
        state = await self.session_mgr.load()
        if state.is_active:
            log.info(f"Resuming active session: {state.summary()}")

        log.info("BTC Predictor v4.0 started. Waiting for 15m candle close...")

    async def stop(self):
        """Graceful shutdown."""
        log.info("BTC Predictor shutting down...")
        self.running = False
        self._shutdown.set()

        for agent in [self.quant, self.flow_master, self.macro_monarch,
                       self.sentiment_scout, self.advisor, self.governor]:
            if agent:
                try:
                    await agent.__aexit__(None, None, None)
                except Exception:
                    pass

        if self.binance:
            await self.binance.__aexit__(None, None, None)

        if self.polymarket:
            await self.polymarket.__aexit__(None, None, None)

    # ── Main Loop ───────────────────────────────────────────────────────

    async def run(self):
        """Main run loop — subscribes to Binance 15m kline WS stream."""
        await self.start()

        # Seed trade buffer
        try:
            recent_trades = await self.binance.fetch_recent_trades(limit=500)
            self.binance.seed_trade_buffer(recent_trades)
            log.info(f"Trade buffer seeded with {len(recent_trades)} trades")
        except Exception as e:
            log.warning(f"Failed to seed trade buffer: {e}")

        kline_q = await self.binance.subscribe_kline("15m")

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
        """Called on every 15m candle close (C1)."""
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
            await self._alert_skipped(pf_result, analysis_id, state)
            return

        # ── Step 4: Parallel specialist + advisor analysis ───────────────────
        specialist_signals = await self._run_specialists(state, reflection)

        # ── Step 5: Governor decision ────────────────────────────────────────
        decision = await self._run_governor(state, specialist_signals, reflection)

        # ── Step 6: Apply confidence gate + execute ─────────────────────────
        if decision.call == "SKIP":
            log.info(f"Governor SKIP — confidence={decision.weighted_confidence:.2f}")
            await self._log_analysis(analysis_id, decision, state, reflection, pf_result, specialist_signals)
            return

        # ── Step 7: Enter session ──────────────────────────────────────────
        await self._enter_session(analysis_id, state, decision, reflection, pf_result, specialist_signals)

    # ── Specialist Agents ────────────────────────────────────────────────

    async def _run_specialists(
        self,
        state: MarketState,
        reflection: dict,
    ) -> dict[str, AgentSignal]:
        """Run all specialist agents in parallel."""
        specialists = [
            ("quant", self.quant),
            ("flow_master", self.flow_master),
            ("macro_monarch", self.macro_monarch),
            ("sentiment_scout", self.sentiment_scout),
        ]

        tasks = {}
        for name, agent in specialists:
            if agent:
                tasks[name] = asyncio.create_task(agent.analyze(state, reflection))

        results = {}
        for name, task in tasks.items():
            try:
                signal = await task
                results[name] = signal
                log.debug(f"  {name.upper()}: score={signal.score:.3f} conf={signal.confidence:.2f}")
            except Exception as e:
                log.warning(f"  {name.upper()} failed: {e}")
                results[name] = AgentSignal(
                    dimension=name,
                    score=0.5,
                    confidence=0.0,
                    regime="UNKNOWN",
                    key_signals=[f"Agent failed: {e}"],
                )

        # Fallback: if no specialists ran, use LLM reasoning engine directly
        if not results:
            log.warning("No specialists available — using fallback reasoning")
            return await self._fallback_reasoning(state, reflection)

        return results

    async def _fallback_reasoning(
        self,
        state: MarketState,
        reflection: dict,
    ) -> dict[str, AgentSignal]:
        """Fallback when no specialist agents are available."""
        from src.reasoning_prompt import build_reasoning_prompt, parse_reasoning_output
        import anthropic

        if not ANTHROPIC_API_KEY:
            return {
                "fallback": AgentSignal(
                    dimension="fallback",
                    score=0.5,
                    confidence=0.0,
                    regime="UNKNOWN",
                    key_signals=["No reasoning engine available"],
                )
            }

        try:
            client = anthropic.AsyncAnthropic(
                api_key=ANTHROPIC_API_KEY,
                base_url=C.ANTHROPIC_BASE_URL,
            )
            system_prompt, user_prompt = build_reasoning_prompt(state, reflection)
            resp = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            await client.aclose()

            raw = ""
            for block in resp.content:
                if block.type == "text":
                    raw += block.text

            output = parse_reasoning_output(raw)
            return {
                "momentum": AgentSignal("momentum", output.signal_scores.get("momentum", 0.5), 0.6, "UNKNOWN"),
                "trend": AgentSignal("trend", output.signal_scores.get("trend", 0.5), 0.6, "UNKNOWN"),
                "orderflow": AgentSignal("orderflow", output.signal_scores.get("orderflow", 0.5), 0.6, "UNKNOWN"),
                "smart_money": AgentSignal("smart_money", output.signal_scores.get("smart_money", 0.5), 0.6, "UNKNOWN"),
                "sentiment": AgentSignal("sentiment", output.signal_scores.get("sentiment", 0.5), 0.6, "UNKNOWN"),
                "macro": AgentSignal("macro", output.signal_scores.get("macro", 0.5), 0.6, "UNKNOWN"),
            }
        except Exception as e:
            log.error(f"Fallback reasoning failed: {e}")
            return {}

    # ── Governor ────────────────────────────────────────────────────────

    async def _run_governor(
        self,
        state: MarketState,
        specialist_signals: dict[str, AgentSignal],
        reflection: dict,
    ) -> GovernorDecision:
        """Run Governor decision process."""
        t0 = asyncio.get_event_loop().time()

        if not self.governor:
            # Fallback: simple weighted average
            return self._simple_decision(specialist_signals)

        try:
            decision = await self.governor.make_decision(
                state, specialist_signals, reflection
            )
            latency = (asyncio.get_event_loop().time() - t0) * 1000
            decision.latency_ms = latency
            self._current_decision = decision
            return decision
        except Exception as e:
            log.error(f"Governor decision failed: {e}")
            return self._simple_decision(specialist_signals)

    def _simple_decision(self, signals: dict[str, AgentSignal]) -> GovernorDecision:
        """Simple weighted average fallback."""
        total = 0.0
        for dim, weight in DIMENSION_WEIGHTS.items():
            if dim in signals:
                total += signals[dim].score * weight
            else:
                total += 0.5 * weight

        conf = round(total, 3)
        bucket = "HIGH" if conf >= C.CONFIDENCE_HIGH else "MEDIUM" if conf >= C.CONFIDENCE_MEDIUM else "LOW"
        call = "SKIP" if bucket == "LOW" else ("GREEN" if conf > 0.52 else "RED")

        return GovernorDecision(
            call=call,
            weighted_confidence=conf,
            confidence_bucket=bucket,
            signal_scores={dim: s.score for dim, s in signals.items()},
            advisor_reconciliation={"advisor_call": "SKIP", "agreed": True},
            regime="UNKNOWN",
            analysis={},
            contradictions=[],
            key_signals=[],
            risk_factors=[],
        )

    # ── Session Entry ───────────────────────────────────────────────────

    async def _enter_session(
        self,
        analysis_id: str,
        state: MarketState,
        decision: GovernorDecision,
        reflection: dict,
        pf_result: PreFilterResult,
        specialist_signals: dict[str, AgentSignal],
    ):
        """Open a new session and place the first bet."""
        direction = decision.call
        confidence = decision.weighted_confidence

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
        bet_size = self.polymarket.compute_bet_size(
            confidence=confidence,
            market_price=market_price,
            bankroll=1000.0,
        ) if self.polymarket else 1.0

        # Place bet
        result = None
        try:
            async with PolymarketClient() as pm:
                result = await pm.place_order(
                    market=market,
                    direction=direction,
                    size=bet_size,
                    market_price=market_price,
                )
        except Exception as e:
            log.warning(f"Bet placement failed: {e}")

        # Record bet
        await self.session_mgr.place_bet(
            candle_label="C2",
            direction=direction,
            confidence=confidence,
            market_price=(result.filled_price or market_price) if result else market_price,
            bet_amount=(result.filled_size or bet_size) if result else bet_size,
        )

        # Log analysis
        await self._log_analysis(analysis_id, decision, state, reflection, pf_result, specialist_signals)

        # Alert
        if self.alerts:
            rationale = " | ".join(f"{k}: {v:.2f}" for k, v in decision.signal_scores.items())
            await self.alerts.session_started(
                direction=direction,
                confidence=confidence,
                rationale=rationale,
                market_url=market_url,
                regime=reflection.get("regime", "UNKNOWN"),
            )
            if result:
                await self.alerts.bet_placed(
                    candle="C2",
                    direction=direction,
                    price=result.filled_price or market_price,
                    size=result.filled_size or bet_size,
                    market_url=market_url,
                    bet_number=1,
                )

        # Schedule C2 resolution
        asyncio.create_task(self._wait_and_resolve_candle("C2"))

    # ── Candle Resolution ────────────────────────────────────────────────

    async def _wait_and_resolve_candle(self, label: str):
        """Wait for target candle to close, then resolve."""
        candle_map = {"C2": 1, "C3": 2, "C4": 3}
        wait_for = candle_map.get(label, 1)
        await asyncio.sleep(8)  # Buffer for WS latency

        try:
            candles = await self.binance.fetch_klines(limit=5)
            if len(candles) >= wait_for + 1:
                target = candles[-wait_for]
                await self._resolve_candle(label, target)
        except Exception as e:
            log.error(f"Failed to fetch {label}: {e}")

    async def _resolve_candle(self, label: str, candle: Candle):
        """Resolve a bet on a candle."""
        session_state = await self.session_mgr.load()
        if not session_state.is_active:
            return

        direction = session_state.current_direction
        is_green = candle.is_green
        won = (direction == "GREEN" and is_green) or (direction == "RED" and not is_green)

        log.info(f"{label} RESOLVED: {'GREEN' if is_green else 'RED'} "
                 f"→ {'✅ WIN' if won else '❌ LOSS'} (bet={direction})")

        await self.session_mgr.resolve_bet(won=won, close_price=candle.close)

        if self.alerts:
            await self.alerts.bet_resolved(
                candle=label,
                won=won,
                close_price=candle.close,
                bets_remaining=session_state.bets_remaining,
                session_pnl=session_state.total_pnl,
            )

        if won:
            await self._handle_session_won(candle, session_state)
        elif session_state.bets_remaining > 0:
            await self._check_flip_and_continue(candle, session_state)
        else:
            await self._handle_session_lost(candle, session_state)

    async def _check_flip_and_continue(self, candle: Candle, session_state):
        """After a loss, evaluate flip conditions."""
        try:
            state = await self.assembler.assemble(f"flip_check_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        except Exception as e:
            log.warning(f"Flip check failed: {e}")
            asyncio.create_task(self._wait_and_resolve_candle(session_state.next_candle))
            return

        flip_eval = evaluate_flip(
            original_direction=session_state.locked_direction,
            loss_candle=session_state.next_candle,
            loss_reason=f"{session_state.next_candle} loss",
            original_confidence=session_state.bets[-1].confidence if session_state.bets else 0.60,
            counter_signal_strength=0.55,
            advisor_flip_confidence=0.50,
            vpin=state.vpin,
            cvd_diverging=(state.cvd > 0) if session_state.current_direction == "RED" else (state.cvd < 0),
            funding_reversal=False,
            new_technical_breakdown=False,
        )

        if flip_eval.decision == "FLIP":
            await self.session_mgr.flip_direction(
                new_direction=flip_eval.flip_direction,
                reason=flip_eval.trigger_reason,
                confidence=0.60,
            )
            log.warning(f"DIRECTION FLIPPED: {session_state.current_direction} → {flip_eval.flip_direction}")
            if self.alerts:
                await self.alerts.send_message(
                    f"⚠️ DIRECTION FLIPPED: {session_state.current_direction} → {flip_eval.flip_direction}\n"
                    f"Reason: {flip_eval.trigger_reason}"
                )

        asyncio.create_task(self._wait_and_resolve_candle(session_state.next_candle))

    async def _handle_session_won(self, winning_candle: Candle, session_state):
        """Handle a won session."""
        bets = session_state.bets
        won_bet = next((b for b in reversed(bets) if b.won), bets[-1])
        market_price = won_bet.market_price if won_bet else 0.50
        bet_amount = won_bet.bet_amount if won_bet else 1.0
        pnl = bet_amount / max(market_price, 0.01) - bet_amount

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
        """Handle a lost session."""
        total_loss = sum(b.bet_amount for b in session_state.bets)

        await self.logger.log_session_outcome(
            analysis_id=session_state.analysis_id,
            session_won=False,
            session_lost=True,
            winning_candle="",
            total_bets=len(session_state.bets),
            total_pnl=-total_loss,
            winning_candles=[],
            losing_candles=[b.candle_label for b in session_state.bets],
            flip_occurred=session_state.flip_occurred,
        )

        stats = await self.logger.compute_stats()
        if self.alerts:
            if stats.get("consecutive_losses", 0) >= 3:
                await self.alerts.circuit_breaker(
                    consecutive_losses=stats["consecutive_losses"],
                    reason="3 consecutive losses",
                    edge_required="$0.05",
                )
            await self.alerts.session_lost(
                total_loss=total_loss,
                direction=session_state.locked_direction,
                all_bets=[{"candle": b.candle_label, "won": bool(b.won),
                           "close_price": b.close_price or 0.0} for b in session_state.bets],
            )

        await self.session_mgr.reset()

    async def _handle_active_session(self, candle: Candle, session_state):
        """Handle incoming candle during active session."""
        log.debug(f"Candle during active session: {session_state.summary()}")

    async def _alert_skipped(self, pf_result, analysis_id, state):
        if self.alerts:
            await self.alerts.analysis_skipped(
                reason=pf_result.reason.value if pf_result.reason else "unknown",
                confidence=0.0,
                candle_id=analysis_id,
            )

    async def _log_analysis(
        self,
        analysis_id: str,
        decision: GovernorDecision,
        state: MarketState,
        reflection: dict,
        pf_result: PreFilterResult,
        specialist_signals: dict[str, AgentSignal],
    ):
        advisor_call = "N/A"
        advisor_confidence = 0.0
        advisor_strength = "N/A"
        if decision.advisor_reconciliation:
            advisor_call = decision.advisor_reconciliation.get("advisor_call", "N/A")
            advisor_confidence = decision.advisor_reconciliation.get("advisor_confidence", 0.0)
            advisor_strength = decision.advisor_reconciliation.get("advisor_strength", "N/A")

        await self.logger.log_analysis(
            analysis_id=analysis_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            direction=decision.call,
            confidence=decision.weighted_confidence,
            confidence_bucket=decision.confidence_bucket,
            signal_scores=decision.signal_scores,
            advisor_call=advisor_call,
            advisor_confidence=advisor_confidence,
            advisor_strength=advisor_strength,
            locked_direction=decision.call,
            current_direction=decision.call,
            pre_filter_reason=pf_result.reason.value if pf_result.reason else "PASSED",
            reasoning_json=decision.analysis,
            market_price=0.0,
            market_url="",
            c1_price=state.current_price,
            c1_pattern=state.c1.candle_pattern if state.c1 else "N/A",
            rsi_14=state.technical.rsi_14 if state.technical else 0.0,
            vpin=state.vpin,
            cvd=state.cvd,
            funding_rate=state.smart_money.funding_rate_pct if state.smart_money else 0.0,
            fear_greed=state.sentiment.fear_greed_index if state.sentiment else 50,
            regime=reflection.get("regime", "UNKNOWN"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    """Run the BTC Predictor."""
    import argparse
    parser = argparse.ArgumentParser(description="BTC 15m Direction Predictor v4.0")
    parser.add_argument("--live", action="store_true", help="Enable live trading")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    predictor = BTCPredictor(dry_run=not args.live)

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
