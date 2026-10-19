from orchestrator.domain.metrics import plan_metrics, compare_metrics
from orchestrator.domain.research import search_local_sources


def test_numbers_are_deterministic():
    a = plan_metrics("A", 100, 35, 5)
    b = plan_metrics("B", 100, 50, 10)
    assert a["gross_margin_pct"] == 65
    assert a["monthly_gross_contribution"] == 325
    result = compare_metrics(a, b)
    assert result["winner_by_margin"] == "A"
    assert result["winner_by_contribution"] == "B"


def test_local_research():
    assert search_local_sources("Starter Growth")
