import pytest
from app.scenarios.math import compute_scenarios, _project


def test_project_year_zero_equals_capital():
    result = _project(10000, 0, 5, 0.035)
    assert result[0] == 10000.0


def test_project_grows_over_time():
    result = _project(10000, 0, 5, 0.035)
    assert result[5] > result[0]


def test_project_zero_pmt_compound_only():
    # 1 anno a 3.5% composto mensile: ~10350
    result = _project(10000, 0, 1, 0.035)
    assert 10340 < result[1] < 10360


def test_monthly_pmt_increases_final_value():
    no_pmt = _project(10000, 0, 10, 0.05)
    with_pmt = _project(10000, 500, 10, 0.05)
    assert with_pmt[-1] > no_pmt[-1]


def test_compute_scenarios_returns_all_keys():
    data = compute_scenarios(10000, 500, 15)
    assert set(data.keys()) == {"sicuro", "bilanciato", "crescita", "inflazione", "labels"}
    assert len(data["labels"]) == 16  # anno 0..15
    assert data["labels"] == list(range(16))


def test_crescita_beats_bilanciato_beats_sicuro():
    data = compute_scenarios(10000, 500, 15)
    assert data["crescita"][-1] > data["bilanciato"][-1] > data["sicuro"][-1]


def test_inflazione_only_compounds_capital_no_pmt():
    # inflazione = capital * (1.025)^t, no versamento mensile
    data = compute_scenarios(10000, 0, 15)
    expected = round(10000 * (1.025 ** 15), 2)
    assert abs(data["inflazione"][15] - expected) < 1


def test_sicuro_beats_inflazione_at_zero_pmt():
    # 3.5% > 2.5% quindi sicuro batte inflazione anche senza versamenti
    data = compute_scenarios(10000, 0, 10)
    assert data["sicuro"][-1] > data["inflazione"][-1]
