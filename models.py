"""
ML pipeline: LightGBM modellek betanítása, értékelése, mentése és predikciója.

Workflow:
  1. analytics.load_merged() + build_feature_matrix() -> feature DataFrame
  2. train_model(df, target) -> TrainResult
  3. save_model(result, target) -> fájl a data/models/ könyvtárba
  4. load_model(target) -> LGBMRegressor
  5. predict_next(model, latest_row) -> float
  6. explain_model(result) -> shap_values
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import config

# Hangulat/fájdalom/energia modelleknél az alvás is feature
FEATURE_COLS_DEFAULT = [
    "sleep_hours",
    "prev_sleep",
    "sleep_ma3",
    "temperature_avg",
    "pressure_avg",
    "pressure_ma3",
    "pressure_delta",
    "humidity_avg",
    "precipitation",
]

# Alvás modellnél csak az időjárás + előző napi alvás szerepel feature-ként —
# a sleep_hours és sleep_ma3 nem lehet egyszerre feature és target
FEATURE_COLS_SLEEP = [
    "prev_sleep",
    "temperature_avg",
    "pressure_avg",
    "pressure_ma3",
    "pressure_delta",
    "humidity_avg",
    "precipitation",
]

FEATURE_COLS_BY_TARGET: dict[str, list[str]] = {
    "sleep_hours": FEATURE_COLS_SLEEP,
    "mood_avg":    FEATURE_COLS_DEFAULT,
    "pain_avg":    FEATURE_COLS_DEFAULT,
    "energy_avg":  FEATURE_COLS_DEFAULT,
}

TARGETS = ("sleep_hours", "mood_avg", "pain_avg", "energy_avg")


# ---------------------------------------------------------------------------
# Eredmény konténer
# ---------------------------------------------------------------------------

@dataclass
class TrainResult:
    model:    object          # LGBMRegressor
    target:   str
    X_train:  pd.DataFrame
    X_test:   pd.DataFrame
    y_train:  pd.Series
    y_test:   pd.Series
    mae:      float
    rmse:     float
    cv_scores: list[float]   # MAE per fold


# ---------------------------------------------------------------------------
# Betanítás
# ---------------------------------------------------------------------------

def train_model(df: pd.DataFrame, target: str = "pain_avg") -> TrainResult:
    """
    LightGBM modell betanítása time-series CV-vel.

    Paraméterek:
        df     -- analytics.build_feature_matrix() kimenete
        target -- célváltozó ('sleep_hours', 'pain_avg', 'mood_avg', 'energy_avg')

    A df már validált (min_days ellenőrzés az analytics rétegben történt).
    Az alvás modellnél külön feature set érvényes (sleep_hours nem lehet
    egyszerre feature és target).
    """
    try:
        import lightgbm as lgb
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import mean_absolute_error, root_mean_squared_error
    except ImportError as e:
        raise ImportError("lightgbm és scikit-learn szükséges") from e

    if target not in TARGETS:
        raise ValueError(f"Ismeretlen target: {target!r}. Válassz egyet: {TARGETS}")

    feature_cols = FEATURE_COLS_BY_TARGET[target]
    available = [c for c in feature_cols if c in df.columns]
    X = df[available].reset_index(drop=True)
    y = df[target].reset_index(drop=True)

    # Time-series CV: az időrend megmarad, nincs data leakage
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores: list[float] = []

    for train_idx, val_idx in tscv.split(X):
        m = lgb.LGBMRegressor(
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=15,
            min_child_samples=5,
            random_state=42,
            verbose=-1,
        )
        m.fit(X.iloc[train_idx], y.iloc[train_idx])
        preds = m.predict(X.iloc[val_idx])
        cv_scores.append(float(mean_absolute_error(y.iloc[val_idx], preds)))

    # Végső modell az összes adaton
    final_model = lgb.LGBMRegressor(
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=15,
        min_child_samples=5,
        random_state=42,
        verbose=-1,
    )

    # Train/test split az utolsó 20%-on (időrendben)
    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    final_model.fit(X_train, y_train)
    preds_test = final_model.predict(X_test)

    mae  = float(mean_absolute_error(y_test, preds_test))
    rmse = float(root_mean_squared_error(y_test, preds_test))

    return TrainResult(
        model=final_model,
        target=target,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        mae=mae,
        rmse=rmse,
        cv_scores=cv_scores,
    )


# ---------------------------------------------------------------------------
# Mentés / betöltés
# ---------------------------------------------------------------------------

def _model_path(target: str) -> Path:
    storage = Path(config.models.storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    return storage / f"lgbm_{target}.txt"


def save_model(result: TrainResult) -> Path:
    """Elmenti a modellt LightGBM natív .txt formátumban."""
    path = _model_path(result.target)
    result.model.booster_.save_model(str(path))
    return path


def load_model(target: str):
    """
    Betölti a mentett modellt lgb.Booster-ként.
    A predict_next() és a charts_widget közvetlenül ezzel dolgozik.

    Raises:
        FileNotFoundError: ha a modell fájl nem létezik.
    """
    try:
        import lightgbm as lgb
    except ImportError as e:
        raise ImportError("lightgbm szükséges") from e

    path = _model_path(target)
    if not path.exists():
        raise FileNotFoundError(
            f"Nincs mentett modell ehhez: {target!r}. "
            "Futtasd le először a betanítást."
        )
    return lgb.Booster(model_file=str(path))


def model_exists(target: str) -> bool:
    """Igaz, ha a mentett modell fájl létezik."""
    return _model_path(target).exists()


# ---------------------------------------------------------------------------
# Predikció
# ---------------------------------------------------------------------------

def predict_next(model, latest_features: pd.DataFrame, target: str) -> float:
    """
    Előrejelzés a következő napra a legfrissebb feature-sor alapján.

    latest_features: egyetlen sor DataFrame a szükséges oszlopokkal.
    target: a célváltozó neve — ebből derül ki melyik feature set érvényes.
    Visszaad: kerekített predikció (1.0–10.0 közé clampelve).
    """
    feature_cols = FEATURE_COLS_BY_TARGET.get(target, FEATURE_COLS_DEFAULT)
    available = [c for c in feature_cols if c in latest_features.columns]
    pred = model.predict(latest_features[available])[0]
    return float(round(np.clip(pred, 1.0, 10.0), 2))


# ---------------------------------------------------------------------------
# SHAP magyarázat
# ---------------------------------------------------------------------------

def explain_model(result: TrainResult) -> tuple:
    """
    SHAP értékek kiszámítása a teszt halmazon.

    Visszaad: (shap_values, explainer) — a UI ezekből rajzol.
    """
    try:
        import shap
    except ImportError as e:
        raise ImportError("shap csomag szükséges") from e

    explainer   = shap.TreeExplainer(result.model)
    shap_values = explainer.shap_values(result.X_test)
    return shap_values, explainer
