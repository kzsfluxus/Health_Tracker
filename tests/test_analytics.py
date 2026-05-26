"""
analytics.py egységtesztek.

Fix DataFrame bemeneteken determinisztikus kimenetet ellenőrzünk.
Nem szükséges DB kapcsolat — a függvények DataFrame-et kapnak paraméterként.
"""

import pandas as pd
import pytest

from analytics import weekly_summary, build_feature_matrix, weather_correlations


# ---------------------------------------------------------------------------
# Tesztadatok
# ---------------------------------------------------------------------------

def make_entries_df(n: int = 14) -> pd.DataFrame:
    """n napos szintetikus naplóbejegyzés DataFrame."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "date":            dates,
            "sleep_hours":     [7.5, 6.0, 8.0, 5.5, 7.0, 6.5, 8.5,
                                 7.0, 5.0, 8.0, 6.5, 7.5, 9.0, 6.0][:n],
            "mood_morning":    [7, 5, 8, 4, 7, 6, 8, 7, 4, 8, 6, 7, 9, 5][:n],
            "mood_afternoon":  [6, 5, 7, 4, 6, 6, 7, 6, 4, 7, 6, 7, 8, 5][:n],
            "pain_morning":    [3, 5, 2, 6, 3, 4, 2, 3, 6, 2, 4, 3, 1, 5][:n],
            "pain_afternoon":  [4, 6, 3, 7, 4, 5, 3, 4, 7, 3, 5, 4, 2, 6][:n],
            "energy_morning":  [7, 5, 8, 4, 7, 6, 8, 7, 4, 8, 6, 7, 9, 5][:n],
            "energy_afternoon":[6, 4, 7, 3, 6, 5, 7, 6, 3, 7, 5, 6, 8, 4][:n],
        }
    )


def make_merged_df(n: int = 14) -> pd.DataFrame:
    """Naplóbejegyzések + szintetikus időjárás."""
    df = make_entries_df(n)
    df["temperature_avg"] = [5.0, 4.5, 6.0, 3.0, 7.0, 8.0, 6.5,
                              5.0, 4.0, 3.5, 7.0, 8.5, 9.0, 5.5][:n]
    df["pressure_avg"]    = [1012, 1010, 1015, 1008, 1013, 1016, 1014,
                              1011, 1009, 1007, 1014, 1017, 1018, 1012][:n]
    df["humidity_avg"]    = [70, 75, 65, 80, 68, 62, 67,
                              72, 78, 82, 66, 60, 58, 71][:n]
    df["precipitation"]   = [0, 2, 0, 5, 0, 0, 1,
                              0, 3, 4, 0, 0, 0, 0][:n]
    return df


# ---------------------------------------------------------------------------
# weekly_summary tesztek
# ---------------------------------------------------------------------------

class TestWeeklySummary:
    def test_returns_dataframe(self):
        df = make_entries_df()
        result = weekly_summary(df)
        assert isinstance(result, pd.DataFrame)

    def test_columns_present(self):
        result = weekly_summary(make_entries_df())
        for col in ("avg_sleep", "avg_mood", "avg_pain", "avg_energy",
                    "bad_sleep_days", "days_logged"):
            assert col in result.columns, f"Hiányzó oszlop: {col}"

    def test_two_weeks_of_data_gives_two_rows(self):
        result = weekly_summary(make_entries_df(14))
        assert len(result) == 2

    def test_avg_sleep_is_mean_of_week(self):
        df = make_entries_df(7)
        result = weekly_summary(df)
        expected = round(df["sleep_hours"].mean(), 2)
        assert round(result.iloc[0]["avg_sleep"], 2) == expected

    def test_bad_sleep_days_counts_correctly(self):
        """6 óránál kevesebb alvású napok száma helyes."""
        df = make_entries_df(7)
        result = weekly_summary(df)
        expected = int((df["sleep_hours"] < 6.0).sum())
        assert int(result.iloc[0]["bad_sleep_days"]) == expected

    def test_avg_mood_is_morning_afternoon_average(self):
        df = make_entries_df(7)
        df["mood_avg_manual"] = (df["mood_morning"] + df["mood_afternoon"]) / 2
        result = weekly_summary(df)
        expected = round(df["mood_avg_manual"].mean(), 2)
        assert round(result.iloc[0]["avg_mood"], 2) == expected

    def test_non_linear_index_does_not_break(self):
        """Nem-lineáris index esetén sem törhet az aggregáció."""
        df = make_entries_df(7)
        df.index = [10, 20, 30, 40, 50, 60, 70]
        result = weekly_summary(df)
        assert len(result) == 1

    def test_empty_dataframe_returns_empty(self):
        empty = pd.DataFrame(columns=make_entries_df().columns)
        result = weekly_summary(empty)
        assert result.empty


# ---------------------------------------------------------------------------
# build_feature_matrix tesztek
# ---------------------------------------------------------------------------

class TestBuildFeatureMatrix:
    @pytest.fixture(autouse=True)
    def lower_min_days(self, monkeypatch):
        """A validációs küszöböt 10-re csökkentjük, hogy a 14 soros
        tesztadat ne dobjon ValueError-t."""
        import config as cfg_module
        monkeypatch.setattr(cfg_module.config.thresholds, "min_days_for_ml", 10)

    def test_returns_dataframe(self):
        result = build_feature_matrix(make_merged_df())
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_present(self):
        result = build_feature_matrix(make_merged_df())
        for col in ("sleep_hours", "prev_sleep", "sleep_ma3",
                    "pressure_delta", "mood_avg", "pain_avg", "energy_avg"):
            assert col in result.columns

    def test_no_nan_in_output(self):
        result = build_feature_matrix(make_merged_df(14))
        assert not result.isnull().any().any()

    def test_prev_sleep_is_shifted(self):
        df = make_merged_df(14)
        result = build_feature_matrix(df)
        assert not (result["prev_sleep"] == result["sleep_hours"]).all()

    def test_pressure_delta_is_diff(self):
        df = make_merged_df(14)
        result = build_feature_matrix(df)
        deltas = result["pressure_delta"].values
        pressures = result["pressure_avg"].values
        for i in range(1, len(deltas)):
            assert abs(deltas[i] - (pressures[i] - pressures[i - 1])) < 0.01


# ---------------------------------------------------------------------------
# weather_correlations tesztek
# ---------------------------------------------------------------------------

class TestWeatherCorrelations:
    def test_returns_dataframe(self):
        df = make_merged_df()
        df["mood_avg"]   = (df["mood_morning"] + df["mood_afternoon"]) / 2
        df["pain_avg"]   = (df["pain_morning"] + df["pain_afternoon"]) / 2
        df["energy_avg"] = (df["energy_morning"] + df["energy_afternoon"]) / 2
        result = weather_correlations(df)
        assert isinstance(result, pd.DataFrame)

    def test_diagonal_is_one(self):
        df = make_merged_df()
        df["mood_avg"]   = (df["mood_morning"] + df["mood_afternoon"]) / 2
        df["pain_avg"]   = (df["pain_morning"] + df["pain_afternoon"]) / 2
        df["energy_avg"] = (df["energy_morning"] + df["energy_afternoon"]) / 2
        result = weather_correlations(df)
        for col in result.columns:
            assert abs(result.loc[col, col] - 1.0) < 1e-9

    def test_missing_columns_handled(self):
        """Ha hiányoznak oszlopok, nem dob kivételt."""
        df = pd.DataFrame({"sleep_hours": [7, 8, 6], "temperature_avg": [5, 6, 4]})
        result = weather_correlations(df)
        assert "sleep_hours" in result.columns
        assert "temperature_avg" in result.columns
