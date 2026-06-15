from typing import TypedDict
from app.constants import SCENARIO_KEYS


RATES: dict[str, float] = {"sicuro": 0.035, "bilanciato": 0.05, "crescita": 0.07}
assert set(RATES) == set(SCENARIO_KEYS), "RATES keys must match SCENARIO_KEYS"
INFLATION_RATE = 0.025


class MathData(TypedDict):
    sicuro: list[float]
    bilanciato: list[float]
    crescita: list[float]
    inflazione: list[float]
    labels: list[int]


def _project(capital: float, monthly_pmt: float, horizon_yrs: int, annual_rate: float) -> list[float]:
    r = (1 + annual_rate) ** (1 / 12) - 1
    result = []
    for year in range(horizon_yrs + 1):
        n = year * 12
        if r == 0:
            v = capital + monthly_pmt * n
        else:
            v = capital * (1 + r) ** n + monthly_pmt * ((1 + r) ** n - 1) / r
        result.append(round(v, 2))
    return result


def compute_scenarios(capital: float, monthly_pmt: float, horizon_yrs: int) -> MathData:
    return {
        "sicuro": _project(capital, monthly_pmt, horizon_yrs, RATES["sicuro"]),
        "bilanciato": _project(capital, monthly_pmt, horizon_yrs, RATES["bilanciato"]),
        "crescita": _project(capital, monthly_pmt, horizon_yrs, RATES["crescita"]),
        "inflazione": [round(capital * (1 + INFLATION_RATE) ** year, 2) for year in range(horizon_yrs + 1)],
        "labels": list(range(horizon_yrs + 1)),
    }
