"""
Tests for Governor reconciliation logic.
Phase 1 Bug 1 fix: _reconcile now derives direction from score, not dimension name.
"""
import pytest

from src.agents.governor.governor import GovernorAgent
from src.agents.advisor import AdvisorOpinion
from src.agents.base.base_agent import AgentSignal


@pytest.fixture
def gov():
    return GovernorAgent()


def make_advisor(call, confidence, advisor_strength=0.7):
    return AdvisorOpinion(
        call=call,
        confidence=confidence,
        reasoning={},
        key_signals=[],
        risk_flags=[],
        advisor_strength=advisor_strength,
        regime="UNKNOWN",
    )


class TestReconcileLogic:
    def test_advisor_agrees_engine_bullish(self, gov):
        advisor = make_advisor("GREEN", 0.65)
        signals = {"momentum": AgentSignal("momentum", 0.72, 0.7, "TRENDING_UP")}
        call, conf = gov._reconcile(0.72, advisor, signals)
        assert call == "GREEN"
        assert conf == 0.72

    def test_advisor_agrees_engine_bearish(self, gov):
        advisor = make_advisor("RED", 0.70)
        signals = {"momentum": AgentSignal("momentum", 0.30, 0.7, "TRENDING_DOWN")}
        call, conf = gov._reconcile(0.30, advisor, signals)
        assert call == "RED"
        assert conf == 0.70

    def test_advisor_skip_always_skips(self, gov):
        advisor = make_advisor("SKIP", 0.99, advisor_strength=0.1)
        signals = {"momentum": AgentSignal("momentum", 0.80, 0.7, "TRENDING_UP")}
        call, conf = gov._reconcile(0.80, advisor, signals)
        assert call == "SKIP"
        assert conf == 0.80

    def test_advisor_disagrees_engine_significantly_more_confident(self, gov):
        advisor = make_advisor("RED", 0.60)
        signals = {"momentum": AgentSignal("momentum", 0.78, 0.7, "TRENDING_UP")}
        call, conf = gov._reconcile(0.78, advisor, signals)
        assert call == "GREEN"
        assert conf == 0.78

    def test_advisor_disagrees_similar_confidence(self, gov):
        advisor = make_advisor("RED", 0.68)
        signals = {"momentum": AgentSignal("momentum", 0.75, 0.7, "TRENDING_UP")}
        call, conf = gov._reconcile(0.75, advisor, signals)
        assert call == "RED"
        assert conf == 0.68

    def test_duplicate_skip_check_removed(self, gov):
        import inspect
        source = inspect.getsource(gov._reconcile)
        count = source.count("advisor.call == \"SKIP\"")
        assert count == 1

    def test_engine_direction_derived_from_score(self, gov):
        advisor = make_advisor("RED", 0.55)
        signals = {"momentum": AgentSignal("momentum", 0.50, 0.7, "RANGING")}
        call, conf = gov._reconcile(0.50, advisor, signals)
        assert call == "RED"
        assert conf == 0.55