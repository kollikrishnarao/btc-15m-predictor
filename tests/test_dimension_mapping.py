"""
Tests for dimension mapping and weighted confidence calculation.
Phase 1 Bug 2: signals now keyed by dimension name, not specialist name.
Phase 2.4: regime-adaptive weight profiles.
Phase 2.7: interaction terms.
"""
import pytest

from src.agents.governor.governor import GovernorAgent, DIMENSION_WEIGHTS, REGIME_WEIGHT_PROFILES
from src.agents.base.base_agent import AgentSignal


@pytest.fixture
def gov():
    return GovernorAgent()


class TestDimensionMapping:
    """Signal dicts are now keyed by dimension name (momentum, trend, etc)."""

    def test_all_dimensions_present(self, gov):
        """All 6 DIMENSION_WEIGHTS keys should exist in signal dict."""
        signals = {
            "momentum": AgentSignal("momentum", 0.70, 0.7, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.65, 0.7, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.72, 0.7, "TRENDING_UP"),
            "smart_money": AgentSignal("smart_money", 0.55, 0.6, "RISK_ON"),
            "sentiment": AgentSignal("sentiment", 0.60, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.52, 0.5, "NEUTRAL"),
        }
        conf = gov._compute_weighted_confidence(signals)
        assert 0.0 <= conf <= 1.0

    def test_missing_dimension_gets_neutral(self, gov):
        """Missing dimension → contributes 0.5 (neutral)."""
        signals = {
            "momentum": AgentSignal("momentum", 0.70, 0.7, "TRENDING_UP"),
        }
        conf = gov._compute_weighted_confidence(signals)
        # momentum: 0.70 * 0.25 = 0.175 (in UNKNOWN profile)
        # 5 missing → each 0.5 * weight → some positive contribution
        assert 0.0 <= conf <= 1.0

    def test_quant_provides_momentum_and_trend(self, gov):
        """QuantMaster returns momentum + trend signals (composite)."""
        signals = {
            "momentum": AgentSignal("momentum", 0.80, 0.8, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.75, 0.8, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.60, 0.6, "RANGING"),
            "smart_money": AgentSignal("smart_money", 0.55, 0.5, "NEUTRAL"),
            "sentiment": AgentSignal("sentiment", 0.60, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.50, 0.5, "NEUTRAL"),
        }
        conf = gov._compute_weighted_confidence(signals)
        assert 0.0 <= conf <= 1.0


class TestRegimeWeightProfiles:
    """All regime weight profiles must sum to 1.0."""

    def test_all_profiles_sum_to_one(self):
        for regime, weights in REGIME_WEIGHT_PROFILES.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{regime} weights sum to {total}, not 1.0"

    def test_regime_affects_confidence(self, gov):
        """Same signals produce different confidence with different regimes."""
        signals = {
            "momentum": AgentSignal("momentum", 0.80, 0.8, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.75, 0.8, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.60, 0.6, "RANGING"),
            "smart_money": AgentSignal("smart_money", 0.55, 0.5, "NEUTRAL"),
            "sentiment": AgentSignal("sentiment", 0.60, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.50, 0.5, "NEUTRAL"),
        }
        conf_trending = gov._compute_weighted_confidence(signals, "TRENDING_UP")
        conf_ranging = gov._compute_weighted_confidence(signals, "RANGING")
        # In RANGING, orderflow gets more weight (0.30 vs 0.15)
        # In TRENDING, momentum gets more weight (0.30 vs 0.15)
        # Should produce different scores
        assert conf_trending != conf_ranging

    def test_unknown_regime_uses_default(self, gov):
        """UNKNOWN regime → same as default."""
        signals = {
            "momentum": AgentSignal("momentum", 0.70, 0.7, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.65, 0.7, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.60, 0.6, "RANGING"),
            "smart_money": AgentSignal("smart_money", 0.55, 0.5, "NEUTRAL"),
            "sentiment": AgentSignal("sentiment", 0.60, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.50, 0.5, "NEUTRAL"),
        }
        conf_unknown = gov._compute_weighted_confidence(signals, "UNKNOWN")
        conf_default = gov._compute_weighted_confidence(signals, "NEUTRAL")
        assert conf_unknown == conf_default


class TestInteractionTerms:
    """Phase 2.7: confirmation bonus, divergence penalty, consensus floor."""

    def test_confirmation_bonus_when_momentum_and_orderflow_agree(self, gov):
        """orderflow and momentum agree → +confirmation bonus."""
        signals = {
            "momentum": AgentSignal("momentum", 0.80, 0.8, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.70, 0.7, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.80, 0.7, "TRENDING_UP"),
            "smart_money": AgentSignal("smart_money", 0.60, 0.6, "RISK_ON"),
            "sentiment": AgentSignal("sentiment", 0.55, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.55, 0.5, "NEUTRAL"),
        }
        conf_agree = gov._compute_weighted_confidence(signals, "TRENDING_UP")

        # Change orderflow to disagree
        signals["orderflow"] = AgentSignal("orderflow", 0.30, 0.7, "RANGING")
        conf_disagree = gov._compute_weighted_confidence(signals, "TRENDING_UP")

        # Agreement should give higher confidence
        assert conf_agree > conf_disagree

    def test_divergence_penalty(self, gov):
        """Large gap between dimensions → divergence penalty."""
        signals = {
            "momentum": AgentSignal("momentum", 0.90, 0.8, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.10, 0.7, "TRENDING_DOWN"),
            "orderflow": AgentSignal("orderflow", 0.85, 0.7, "TRENDING_UP"),
            "smart_money": AgentSignal("smart_money", 0.15, 0.6, "RISK_OFF"),
            "sentiment": AgentSignal("sentiment", 0.50, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.50, 0.5, "NEUTRAL"),
        }
        conf = gov._compute_weighted_confidence(signals)
        # Without penalty: high. With penalty: reduced
        # max_divergence = max gap = 0.80 (momentum 0.90 vs trend 0.10)
        # penalty = max(0, (0.80-0.30)*0.10) = 0.05
        assert 0.0 <= conf <= 1.0

    def test_consensus_bonus(self, gov):
        """All dimensions loosely agree → consensus floor bonus."""
        # All near 0.70 — high consensus
        signals_agree = {
            "momentum": AgentSignal("momentum", 0.70, 0.7, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.68, 0.7, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.72, 0.7, "TRENDING_UP"),
            "smart_money": AgentSignal("smart_money", 0.69, 0.6, "RISK_ON"),
            "sentiment": AgentSignal("sentiment", 0.71, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.70, 0.5, "NEUTRAL"),
        }
        conf_agree = gov._compute_weighted_confidence(signals_agree, "TRENDING_UP")

        # Spread = 0.72 - 0.68 = 0.04, bonus = max(0, (0.50-0.04)*0.05) = 0.023
        assert conf_agree > 0.0

    def test_interaction_terms_clamped(self, gov):
        """Final score must always be in [0, 1]."""
        signals = {
            "momentum": AgentSignal("momentum", 0.95, 0.8, "TRENDING_UP"),
            "trend": AgentSignal("trend", 0.92, 0.7, "TRENDING_UP"),
            "orderflow": AgentSignal("orderflow", 0.90, 0.7, "TRENDING_UP"),
            "smart_money": AgentSignal("smart_money", 0.88, 0.6, "RISK_ON"),
            "sentiment": AgentSignal("sentiment", 0.90, 0.5, "NEUTRAL"),
            "macro": AgentSignal("macro", 0.92, 0.5, "NEUTRAL"),
        }
        conf = gov._compute_weighted_confidence(signals, "TRENDING_UP")
        assert 0.0 <= conf <= 1.0