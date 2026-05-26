"""
models.py egységtesztek.

Szintetikus adaton teszteli a teljes pipeline-t:
betanítás, mentés/betöltés, predikció, SHAP.
A LightGBM-et nem mock-oljuk — valóban lefut, de kis adaton gyors.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from models import (
    FEATURE_COLS,
    TrainResult,
    train_model,
    save_model,
    load_model,
    model_exists,
    predict_next,
    explain_model,
)


# ---------------------------------------------------------------------------
# Tesztadat
# ---------------------------------------------------------------------------

N = 60  # elegendő a CV-hez és a min_days küszöbhöz


def make_feature_matrix(n: int = N) -> pd.DataFrame:
    """Szintetikus feature mátrix, amilyet build_feature_matrix() adna."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")

    sleep   = rng.uniform(5.0, 9.0, n)
    pressure = rng.uniform(1005.0, 1020.0, n)

    df = pd.DataFrame(
        {
            "date":            dates,
            "sleep_hours":     sleep,
            "prev_sleep":      np.roll(sleep, 1),
            "sleep_ma3":       pd.Series(sleep).rolling(3).mean().fillna(sleep.mean()).values,
            "temperature_avg": rng.uniform(-5.0, 30.0, n),
            "pressure_avg":    pressure,
            "pressure_ma3":    pd.Series(pressure).rolling(3).mean().fillna(pressure.mean()).values,
            "pressure_delta":  np.diff(pressure, prepend=pressure[0]),
            "humidity_avg":    rng.uniform(40.0, 90.0, n),
            "precipitation":   rng.uniform(0.0, 10.0, n),
            "mood_avg":        rng.uniform(3.0, 9.0, n),
            "pain_avg":        rng.uniform(1.0, 8.0, n),
            "energy_avg":      rng.uniform(3.0, 9.0, n),
        }
    )
    return df.dropna()


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------

class TestTrainModel:
    def test_returns_train_result(self):
        result = train_model(make_feature_matrix(), target="pain_avg")
        assert isinstance(result, TrainResult)

    def test_target_stored(self):
        result = train_model(make_feature_matrix(), target="mood_avg")
        assert result.target == "mood_avg"

    def test_mae_is_positive(self):
        result = train_model(make_feature_matrix())
        assert result.mae > 0

    def test_rmse_gte_mae(self):
        result = train_model(make_feature_matrix())
        assert result.rmse >= result.mae

    def test_cv_scores_length(self):
        result = train_model(make_feature_matrix())
        assert len(result.cv_scores) == 5

    def test_cv_scores_positive(self):
        result = train_model(make_feature_matrix())
        assert all(s > 0 for s in result.cv_scores)

    def test_invalid_target_raises(self):
        with pytest.raises(ValueError, match="Ismeretlen target"):
            train_model(make_feature_matrix(), target="nem_letezik")

    def test_all_targets_train(self):
        df = make_feature_matrix()
        for target in ("sleep_hours", "pain_avg", "mood_avg", "energy_avg"):
            result = train_model(df, target=target)
            assert result.target == target

    def test_x_test_has_correct_columns(self):
        result = train_model(make_feature_matrix())
        available = [c for c in FEATURE_COLS if c in make_feature_matrix().columns]
        assert list(result.X_test.columns) == available


# ---------------------------------------------------------------------------
# save_model / load_model / model_exists
# ---------------------------------------------------------------------------

class TestModelPersistence:
    @pytest.fixture(autouse=True)
    def tmp_model_dir(self, tmp_path, monkeypatch):
        """Minden teszthez ideiglenes model könyvtár."""
        import config as cfg_module
        original = cfg_module.config.models.storage_dir
        cfg_module.config.models.storage_dir = str(tmp_path / "models")
        yield
        cfg_module.config.models.storage_dir = original

    def test_model_not_exists_before_save(self):
        assert model_exists("pain_avg") is False

    def test_save_creates_file(self):
        result = train_model(make_feature_matrix())
        path   = save_model(result)
        assert path.exists()

    def test_model_exists_after_save(self):
        result = train_model(make_feature_matrix())
        save_model(result)
        assert model_exists("pain_avg") is True

    def test_load_after_save(self):
        result = train_model(make_feature_matrix())
        save_model(result)
        loaded = load_model("pain_avg")
        assert loaded is not None

    def test_load_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            load_model("pain_avg")

    def test_loaded_model_predicts(self):
        df     = make_feature_matrix()
        result = train_model(df)
        save_model(result)
        loaded = load_model("pain_avg")
        # load_model lgb.Booster-t ad vissza — annak predict() metódusa
        # DataFrame helyett numpy array-t vár
        preds = loaded.predict(result.X_test.values)
        assert len(preds) == len(result.X_test)


# ---------------------------------------------------------------------------
# predict_next
# ---------------------------------------------------------------------------

class TestPredictNext:
    def test_returns_float(self):
        result = train_model(make_feature_matrix())
        latest = result.X_test.iloc[[-1]]
        pred   = predict_next(result.model, latest)
        assert isinstance(pred, float)

    def test_prediction_in_range(self):
        result = train_model(make_feature_matrix())
        latest = result.X_test.iloc[[-1]]
        pred   = predict_next(result.model, latest)
        assert 1.0 <= pred <= 10.0

    def test_clamp_applies(self):
        """Ha a modell 1–10 kívüli értéket adna, azt clampeljük."""
        result = train_model(make_feature_matrix())
        latest = result.X_test.iloc[[-1]].copy()

        # Szokatlanul extrém input — a clamp véd
        for col in latest.columns:
            latest[col] = 9999.0

        pred = predict_next(result.model, latest)
        assert 1.0 <= pred <= 10.0


# ---------------------------------------------------------------------------
# explain_model
# ---------------------------------------------------------------------------

class TestExplainModel:
    def test_returns_tuple(self):
        result = train_model(make_feature_matrix())
        shap_values, explainer = explain_model(result)
        assert shap_values is not None
        assert explainer is not None

    def test_shap_shape_matches_test_set(self):
        result = train_model(make_feature_matrix())
        shap_values, _ = explain_model(result)
        assert shap_values.shape == result.X_test.shape


# ---------------------------------------------------------------------------
# build_feature_matrix validáció (analytics integrációs teszt)
# ---------------------------------------------------------------------------

class TestFeatureMatrixValidation:
    def test_too_few_rows_raises(self, monkeypatch):
        """Ha kevés az adat, build_feature_matrix ValueError-t dob."""
        import config as cfg_module
        monkeypatch.setattr(cfg_module.config.thresholds, "min_days_for_ml", 100)

        from analytics import build_feature_matrix
        # make_merged_df() adja a build_feature_matrix() által várt nyers formátumot
        # (mood_morning/afternoon stb. oszlopokkal), 14 sor < 100 küszöb
        from tests.test_analytics import make_merged_df

        with pytest.raises(ValueError, match="Túl kevés adat"):
            build_feature_matrix(make_merged_df(14))
