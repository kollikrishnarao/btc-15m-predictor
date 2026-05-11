"""
Tests for dynamic flip logic.
"""
import pytest

from src.dynamic_flip import evaluate_flip, FlipDecision


class TestFlipDecision:
    def test_hold_when_vpin_toxic(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C2",
            loss_reason="C2 loss",
            original_confidence=0.72,
            counter_signal_strength=0.75,
            advisor_flip_confidence=0.70,
            vpin=0.80,          # Toxic!
        )
        assert result.decision == FlipDecision.HOLD

    def test_flip_when_advisor_approves_and_confidence_gap(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C2",
            loss_reason="C2 loss",
            original_confidence=0.70,
            counter_signal_strength=0.85,  # Gap > 0.15
            advisor_flip_confidence=0.70,
            vpin=0.30,
            cvd_diverging=True,
            funding_reversal=True,
            new_technical_breakdown=True,
        )
        assert result.decision == FlipDecision.FLIP

    def test_cannot_flip_on_c4(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C4",    # No bets remain!
            loss_reason="C4 loss",
            original_confidence=0.70,
            counter_signal_strength=0.90,
            advisor_flip_confidence=0.80,
            vpin=0.30,
        )
        assert result.decision == FlipDecision.HOLD

    def test_hold_low_counter_confidence(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C2",
            loss_reason="C2 loss",
            original_confidence=0.75,
            counter_signal_strength=0.77,   # Only 0.02 gap — not enough
            advisor_flip_confidence=0.60,    # Below 0.65 threshold
            vpin=0.30,
            cvd_diverging=False,
            funding_reversal=False,
            new_technical_breakdown=False,
        )
        assert result.decision == FlipDecision.HOLD

    def test_flip_disabled(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C2",
            loss_reason="C2 loss",
            original_confidence=0.70,
            counter_signal_strength=0.95,
            advisor_flip_confidence=0.80,
            vpin=0.20,
            flip_allowed=False,
        )
        assert result.decision == FlipDecision.HOLD
        assert "disabled" in result.trigger_reason.lower()

    def test_flip_direction_correct(self):
        result = evaluate_flip(
            original_direction="GREEN",
            loss_candle="C2",
            loss_reason="C2 loss",
            original_confidence=0.70,
            counter_signal_strength=0.90,
            advisor_flip_confidence=0.75,
            vpin=0.20,
            cvd_diverging=True,
            funding_reversal=True,
            new_technical_breakdown=True,
        )
        assert result.flip_direction == "RED"

        result2 = evaluate_flip(
            original_direction="RED",
            loss_candle="C3",
            loss_reason="C3 loss",
            original_confidence=0.68,
            counter_signal_strength=0.85,
            advisor_flip_confidence=0.70,
            vpin=0.25,
            cvd_diverging=True,
            funding_reversal=True,
            new_technical_breakdown=True,
        )
        assert result2.flip_direction == "GREEN"
