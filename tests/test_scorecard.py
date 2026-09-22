from src.tools.scorecard import risk_band, score_application

BASE = dict(cibil=720, foir=0.35, ltv=None, vintage_months=30, worst_dpd_24m=0)


def test_score_bounds():
    best = score_application(cibil=850, foir=0.2, ltv=0.4, vintage_months=60, worst_dpd_24m=0)
    worst = score_application(cibil=300, foir=0.9, ltv=1.2, vintage_months=0, worst_dpd_24m=120)
    assert best["score"] == 900
    assert 300 <= worst["score"] <= 900


def test_monotonic_cibil():
    low = score_application(**{**BASE, "cibil": 640})
    high = score_application(**{**BASE, "cibil": 800})
    assert high["score"] > low["score"]


def test_monotonic_foir():
    low_risk = score_application(**{**BASE, "foir": 0.25})
    high_risk = score_application(**{**BASE, "foir": 0.60})
    assert low_risk["score"] > high_risk["score"]


def test_monotonic_vintage_and_delinquency():
    a = score_application(**{**BASE, "vintage_months": 48, "worst_dpd_24m": 0})
    b = score_application(**{**BASE, "vintage_months": 3, "worst_dpd_24m": 90})
    assert a["score"] > b["score"]


def test_monotonic_ltv():
    low_ltv = score_application(**{**BASE, "ltv": 0.5})
    high_ltv = score_application(**{**BASE, "ltv": 1.1})
    assert low_ltv["score"] > high_ltv["score"]


def test_risk_band_thresholds():
    assert risk_band(900) == "low"
    assert risk_band(750) == "low"
    assert risk_band(749) == "medium"
    assert risk_band(650) == "medium"
    assert risk_band(649) == "high"


def test_breakdown_sums():
    r = score_application(**BASE)
    assert r["score"] == 300 + sum(r["breakdown"].values())
    assert set(r["breakdown"]) == {"cibil", "foir", "ltv", "vintage", "delinquency"}
