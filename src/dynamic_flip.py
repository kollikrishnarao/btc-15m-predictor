"""
Dynamic direction flip logic — evaluates whether to flip direction on C2/C3 loss.
Called ONLY after a loss. Returns a FlipDecision.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from config.constants import FLIP_ALLOWED, FLIP_CONFIDENCE_GAP

log = logging.getLogger(__name__)


class FlipDecision(Enum):
    HOLD = "HOLD"           # Keep current direction
    FLIP = "FLIP"           # Flip to opposite direction
    SKIP = "SKIP"            # Flip but skip remaining bets (too uncertain)


@dataclass
class FlipEvaluation:
    decision: FlipDecision
    original_direction: str
    flip_direction: str
    original_signal_strength: float
    counter_signal_strength: float
    trigger_reason: str
    confidence_delta: float
    risk_score: float   # 0=low risk, 1=high risk


def evaluate_flip(
    original_direction: str,
    loss_candle: str,        # "C2" or "C3"
    loss_reason: str,        # Description of why it lost
    original_confidence: float,
    counter_signal_strength: float,
    advisor_flip_confidence: float,
    vpin: float,
    vpin_threshold: float = 0.60,
    cvd_diverging: bool = False,
    funding_reversal: bool = False,
    new_technical_breakdown: bool = False,
    flip_allowed: bool = FLIP_ALLOWED,
    confidence_gap: float = FLIP_CONFIDENCE_GAP,
) -> FlipEvaluation:
    """
    Evaluate whether to flip direction after a C2/C3 loss.

    Rules:
    1. Flip only allowed on C2 or C3 loss (not C4 — no bets remain)
    2. Counter-signal must exceed original by FLIP_CONFIDENCE_GAP (0.15)
    3. VPIN must NOT be in extreme toxicity zone (institutional uncertainty)
    4. Advisor must recommend flip (or counter-signal very strong)
    5. At least 2 of 3 secondary conditions must be met:
       CVD divergence, funding reversal, new technical breakdown

    Returns a FlipEvaluation with decision and reasoning.
    """
    if not flip_allowed:
        return FlipEvaluation(
            decision=FlipDecision.HOLD,
            original_direction=original_direction,
            flip_direction="RED" if original_direction == "GREEN" else "GREEN",
            original_signal_strength=original_confidence,
            counter_signal_strength=counter_signal_strength,
            trigger_reason="Flip disabled in config",
            confidence_delta=0.0,
            risk_score=1.0,
        )

    if loss_candle not in ("C2", "C3"):
        return FlipEvaluation(
            decision=FlipDecision.HOLD,
            original_direction=original_direction,
            flip_direction="RED" if original_direction == "GREEN" else "GREEN",
            original_signal_strength=original_confidence,
            counter_signal_strength=counter_signal_strength,
            trigger_reason=f"Cannot flip on {loss_candle} — only C2 or C3",
            confidence_delta=0.0,
            risk_score=1.0,
        )

    flip_direction = "RED" if original_direction == "GREEN" else "GREEN"

    # ── Condition 1: Confidence gap ──────────────────────────────────────
    confidence_met = counter_signal_strength >= (original_confidence + confidence_gap)
    confidence_delta = counter_signal_strength - original_confidence

    # ── Condition 2: VPIN not toxic ───────────────────────────────────────
    vpin_safe = vpin < vpin_threshold

    # ── Condition 3: Advisor flip recommendation ───────────────────────────
    advisor_approves = advisor_flip_confidence >= 0.65

    # ── Condition 4: At least 2 secondary conditions ───────────────────
    secondary_conditions = sum([
        cvd_diverging,
        funding_reversal,
        new_technical_breakdown,
    ])
    secondary_met = secondary_conditions >= 2

    # ── Decision logic ────────────────────────────────────────────────────
    reasons = []
    risk_flags = []

    if not vpin_safe:
        risk_flags.append(f"VPIN {vpin:.3f} > {vpin_threshold} — institutional uncertainty")

    if not confidence_met:
        risk_flags.append(
            f"Counter-signal {counter_signal_strength:.2f} not strong enough "
            f"(need ≥ original + {confidence_gap:.2f})"
        )

    if advisor_approves:
        reasons.append("✅ Advisor recommends flip")

    if cvd_diverging:
        reasons.append("✅ CVD diverging from original direction")

    if funding_reversal:
        reasons.append("✅ Funding rate reversal detected")

    if new_technical_breakdown:
        reasons.append("✅ New technical breakdown detected")

    # Calculate risk score
    risk_score = 0.0
    if not vpin_safe:
        risk_score += 0.4
    if not secondary_met:
        risk_score += 0.3
    if not confidence_met:
        risk_score += 0.2
    if advisor_approves:
        risk_score -= 0.2
    risk_score = max(0.0, min(1.0, risk_score))

    # Decision tree
    if not vpin_safe:
        decision = FlipDecision.HOLD
        reason = "VPIN toxic — institutional uncertainty, cannot confidently flip"
    elif risk_score >= 0.7:
        decision = FlipDecision.HOLD
        reason = f"High risk score ({risk_score:.2f}) — hold direction"
    elif not secondary_met and not advisor_approves:
        decision = FlipDecision.HOLD
        reason = "Neither advisor approves nor sufficient secondary conditions met"
    else:
        # Either advisor approves or we have strong secondary evidence
        if advisor_approves and confidence_met:
            decision = FlipDecision.FLIP
            reason = " | ".join([f"Advisor approves (conf={advisor_flip_confidence:.2f})"]
                                  + reasons)
        elif secondary_met and confidence_met:
            decision = FlipDecision.FLIP
            reason = " | ".join(reasons)
        elif secondary_met and advisor_approves:
            decision = FlipDecision.FLIP
            reason = f"Secondary conditions met + advisor flip (conf={advisor_flip_confidence:.2f})"
        else:
            # Close call — skip remaining bets
            decision = FlipDecision.SKIP
            reason = "Uncertain flip — skipping remaining bets"

    log.info(f"Flip evaluation: {decision.value} | risk={risk_score:.2f} | "
             f"reason: {reason} | flags: {risk_flags}")

    return FlipEvaluation(
        decision=decision,
        original_direction=original_direction,
        flip_direction=flip_direction,
        original_signal_strength=original_confidence,
        counter_signal_strength=counter_signal_strength,
        trigger_reason=reason,
        confidence_delta=confidence_delta,
        risk_score=risk_score,
    )
