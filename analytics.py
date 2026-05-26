"""
Analitikai réteg: heti aggregációk, korrelációk, feature engineering.
Az ML pipeline-hoz szükséges feature-öket is itt készítjük elő.
"""

import pandas as pd

from config import config
from database import get_connection


# ---------------------------------------------------------------------------
# Alap lekérdezések
# ---------------------------------------------------------------------------

def load_entries(days: int = 90) -> pd.DataFrame:
    """Betölti az utolsó `days` nap naplóbejegyzéseit."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            f"""
            SELECT *
            FROM daily_entries
            ORDER BY entry_date DESC
            LIMIT {days}
            """,
            conn,
        )
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    return df.sort_values("entry_date").reset_index(drop=True)


def load_weather(days: int = 90) -> pd.DataFrame:
    """Betölti az utolsó `days` nap időjárási adatait."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            f"""
            SELECT *
            FROM weather_data
            ORDER BY weather_date DESC
            LIMIT {days}
            """,
            conn,
        )
    df["weather_date"] = pd.to_datetime(df["weather_date"])
    return df.sort_values("weather_date").reset_index(drop=True)


def load_merged(days: int = 90) -> pd.DataFrame:
    """Naplóbejegyzések és időjárás összefésülve dátum alapján."""
    entries = load_entries(days)
    weather = load_weather(days)

    entries = entries.rename(columns={"entry_date": "date"})
    weather = weather.rename(columns={"weather_date": "date"})

    return pd.merge(entries, weather, on="date", how="left")


# ---------------------------------------------------------------------------
# Heti aggregációk
# ---------------------------------------------------------------------------

def weekly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Heti összesítő a naplóadatokból.
    A df-nek tartalmaznia kell egy 'date' oszlopot.

    Az előző lambda-alapú megközelítés törött volt nem-lineáris indexeknél;
    itt explicit oszlopszámítás történik a groupby előtt.
    """
    if df.empty:
        return pd.DataFrame(
            columns=["week", "avg_sleep", "avg_mood", "avg_pain",
                     "avg_energy", "bad_sleep_days", "days_logged"]
        )

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W")
    df["mood_avg"]   = (df["mood_morning"]   + df["mood_afternoon"])   / 2
    df["pain_avg"]   = (df["pain_morning"]   + df["pain_afternoon"])   / 2
    df["energy_avg"] = (df["energy_morning"] + df["energy_afternoon"]) / 2

    bad_threshold = config.thresholds.bad_sleep_hours

    agg = df.groupby("week", sort=True).agg(
        avg_sleep      =("sleep_hours", "mean"),
        avg_mood       =("mood_avg",    "mean"),
        avg_pain       =("pain_avg",    "mean"),
        avg_energy     =("energy_avg",  "mean"),
        bad_sleep_days =("sleep_hours", lambda x: (x < bad_threshold).sum()),
        days_logged    =("sleep_hours", "count"),
    ).round(2)

    return agg.reset_index()


# ---------------------------------------------------------------------------
# Feature engineering (ML előkészítés)
# ---------------------------------------------------------------------------

def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Elkészíti az ML betanításhoz szükséges feature mátrixot.

    Bemeneti oszlopok (merged df):
      sleep_hours, mood_morning, mood_afternoon,
      pain_morning, pain_afternoon, energy_morning, energy_afternoon,
      temperature_avg, pressure_avg, humidity_avg, precipitation

    Kimenet: feature mátrix + target oszlopok

    Raises:
        ValueError: ha a dropna utáni sorok száma kisebb mint
                    config.thresholds.min_days_for_ml
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    df["mood_avg"]   = (df["mood_morning"]   + df["mood_afternoon"])   / 2
    df["pain_avg"]   = (df["pain_morning"]   + df["pain_afternoon"])   / 2
    df["energy_avg"] = (df["energy_morning"] + df["energy_afternoon"]) / 2

    df["prev_sleep"]     = df["sleep_hours"].shift(1)
    df["sleep_ma3"]      = df["sleep_hours"].rolling(3).mean()
    df["pressure_ma3"]   = df["pressure_avg"].rolling(3).mean()
    df["pressure_delta"] = df["pressure_avg"].diff()

    feature_cols = [
        "sleep_hours", "prev_sleep", "sleep_ma3",
        "temperature_avg", "pressure_avg", "pressure_ma3",
        "pressure_delta", "humidity_avg", "precipitation",
    ]
    target_cols = ["mood_avg", "pain_avg", "energy_avg"]

    result = df[["date"] + feature_cols + target_cols].dropna()

    min_days = config.thresholds.min_days_for_ml
    if len(result) < min_days:
        raise ValueError(
            f"Túl kevés adat az ML pipeline-hoz: {len(result)} nap "
            f"(minimum: {min_days}). Gyűjts több bejegyzést."
        )

    return result


# ---------------------------------------------------------------------------
# Korrelációk
# ---------------------------------------------------------------------------

def weather_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson-korrelációs mátrix az időjárási és közérzeti változók között."""
    weather_cols = ["temperature_avg", "pressure_avg", "humidity_avg", "precipitation"]
    health_cols  = ["sleep_hours", "mood_avg", "pain_avg", "energy_avg"]
    available    = [c for c in weather_cols + health_cols if c in df.columns]
    return df[available].corr()
