import pytest

from src.tools.calculator import emi, foir, ltv


def test_emi_known_value():
    # 100k @ 12% p.a. for 12 months -> textbook EMI 8884.88
    assert emi(100000, 0.12, 12) == pytest.approx(8884.88, abs=0.01)


def test_emi_zero_rate():
    assert emi(120000, 0.0, 12) == pytest.approx(10000.0)


def test_emi_scales_with_principal():
    assert emi(200000, 0.12, 12) == pytest.approx(2 * emi(100000, 0.12, 12), rel=1e-9)


def test_emi_invalid_inputs():
    with pytest.raises(ValueError):
        emi(0, 0.12, 12)
    with pytest.raises(ValueError):
        emi(100000, 0.12, 0)
    with pytest.raises(ValueError):
        emi(100000, -0.01, 12)


def test_foir_known_value():
    assert foir(10000, 5000, 50000) == pytest.approx(0.30)


def test_foir_no_obligations():
    assert foir(8000, 0, 40000) == pytest.approx(0.20)


def test_foir_invalid_income():
    with pytest.raises(ValueError):
        foir(8000, 0, 0)


def test_ltv_known_value():
    assert ltv(80000, 100000) == pytest.approx(0.80)


def test_ltv_unsecured_is_none():
    assert ltv(500000, None) is None


def test_ltv_invalid():
    with pytest.raises(ValueError):
        ltv(80000, 0)
