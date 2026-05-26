"""
Tesztadatbázis feltöltő script.

Egy havi (31 nap) szintetikus, realisztikus adatot ír egy KÜLÖN tesztadatbázisba
(data/health_tracker_test.db), az éles adatbázist NEM érinti.

Futtatás a projekt gyökeréből:
    python tests/create_pseudo_database.py

Az így létrehozott adatbázissal az alkalmazás elindítható:
    DB_PATH=data/health_tracker_test.db python main.py

Vagy egyszerűen a config.toml-ban átmenetileg átírható:
    [database]
    path = "data/health_tracker_test.db"
"""

import random
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Tesztadatbázis — külön fájl, az éles DB-t nem érinti
# ---------------------------------------------------------------------------

TEST_DB_PATH = PROJECT_ROOT / "data" / "health_tracker_test.db"


def _init_test_db(path: Path):
    import sqlite3
    path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL UNIQUE,
            sleep_start TEXT,
            sleep_end   TEXT,
            sleep_hours REAL,
            mood_morning   INTEGER,
            mood_afternoon INTEGER,
            pain_morning   INTEGER,
            pain_afternoon INTEGER,
            energy_morning   INTEGER,
            energy_afternoon INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weather_date TEXT NOT NULL UNIQUE,
            temperature_avg REAL,
            temperature_min REAL,
            temperature_max REAL,
            pressure_avg  REAL,
            humidity_avg  REAL,
            wind_speed_avg REAL,
            precipitation  REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    return conn


@contextmanager
def _test_conn(path: Path):
    import sqlite3
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Konfiguráció
# ---------------------------------------------------------------------------

DAYS        = 45  # dropna után ~41 sor marad, bőven a min_days_for_ml=30 felett
START_DATE  = date.today() - timedelta(days=DAYS - 1)
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Segédfüggvények
# ---------------------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def walk(current: float, step: float, lo: float, hi: float) -> float:
    return clamp(current + random.uniform(-step, step), lo, hi)


def round_int(value: float) -> int:
    return int(round(value))


# ---------------------------------------------------------------------------
# Adatgenerátor
# ---------------------------------------------------------------------------

def generate_entries(days: int = DAYS) -> list[dict]:
    entries = []

    sleep_start_h = 23.0
    sleep_dur     = 7.5
    mood          = 6.5
    pain          = 3.5
    energy        = 6.5

    for i in range(days):
        current_date = START_DATE + timedelta(days=i)

        sleep_start_h = walk(sleep_start_h, 0.5, 21.5, 25.0)
        sleep_dur     = walk(sleep_dur,     0.4,  5.0,  9.5)

        start_h = int(sleep_start_h) % 24
        start_m = int((sleep_start_h % 1) * 60 / 15) * 15
        sleep_start_str = f"{start_h:02d}:{start_m:02d}"

        end_total_h = sleep_start_h + sleep_dur
        end_h = int(end_total_h) % 24
        end_m = int((end_total_h % 1) * 60 / 15) * 15
        sleep_end_str = f"{end_h:02d}:{end_m:02d}"

        mood   = walk(mood   + (sleep_dur - 7.0) * 0.06, 0.6, 2.0, 9.5)
        pain   = walk(pain   + max(0, (7.0 - sleep_dur) * 0.08), 0.5, 1.0, 9.0)
        energy = walk(energy + (sleep_dur - 7.0) * 0.08, 0.6, 2.0, 9.5)

        def split(base: float, noise: float = 0.5) -> tuple[int, int]:
            return (
                round_int(clamp(base + random.uniform(-noise, noise), 1, 10)),
                round_int(clamp(base + random.uniform(-noise, noise), 1, 10)),
            )

        mood_m,   mood_a   = split(mood)
        pain_m,   pain_a   = split(pain,   noise=0.8)
        energy_m, energy_a = split(energy)

        entries.append(
            {
                "entry_date":       current_date.isoformat(),
                "sleep_start":      sleep_start_str,
                "sleep_end":        sleep_end_str,
                "sleep_hours":      round(sleep_dur, 2),
                "mood_morning":     mood_m,
                "mood_afternoon":   mood_a,
                "pain_morning":     pain_m,
                "pain_afternoon":   pain_a,
                "energy_morning":   energy_m,
                "energy_afternoon": energy_a,
                "notes":            "",
            }
        )

    return entries


def generate_weather(days: int = DAYS) -> list[dict]:
    records = []

    temp     = 12.0
    pressure = 1013.0
    humidity = 68.0
    wind     = 10.0

    for i in range(days):
        current_date = START_DATE + timedelta(days=i)

        temp     = walk(temp,      1.5,  -5.0,  30.0)
        pressure = walk(pressure,  2.0, 990.0, 1035.0)
        humidity = walk(humidity,  4.0,  35.0,  95.0)
        wind     = walk(wind,      2.0,   0.0,  40.0)

        precipitation = round(random.uniform(0, 8) if random.random() < 0.25 else 0.0, 1)
        temp_min = round(temp - random.uniform(2.0, 5.0), 1)
        temp_max = round(temp + random.uniform(2.0, 5.0), 1)

        records.append(
            {
                "weather_date":    current_date.isoformat(),
                "temperature_avg": round((temp_min + temp_max) / 2, 1),
                "temperature_min": temp_min,
                "temperature_max": temp_max,
                "pressure_avg":    round(pressure, 1),
                "humidity_avg":    round(humidity, 1),
                "wind_speed_avg":  round(wind, 1),
                "precipitation":   precipitation,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Főprogram
# ---------------------------------------------------------------------------

def main():
    _init_test_db(TEST_DB_PATH)

    entries = generate_entries(DAYS)
    weather = generate_weather(DAYS)

    with _test_conn(TEST_DB_PATH) as conn:
        for e in entries:
            conn.execute(
                """
                INSERT INTO daily_entries (
                    entry_date, sleep_start, sleep_end, sleep_hours,
                    mood_morning, mood_afternoon,
                    pain_morning, pain_afternoon,
                    energy_morning, energy_afternoon,
                    notes
                ) VALUES (
                    :entry_date, :sleep_start, :sleep_end, :sleep_hours,
                    :mood_morning, :mood_afternoon,
                    :pain_morning, :pain_afternoon,
                    :energy_morning, :energy_afternoon,
                    :notes
                )
                ON CONFLICT(entry_date) DO UPDATE SET
                    sleep_start      = excluded.sleep_start,
                    sleep_end        = excluded.sleep_end,
                    sleep_hours      = excluded.sleep_hours,
                    mood_morning     = excluded.mood_morning,
                    mood_afternoon   = excluded.mood_afternoon,
                    pain_morning     = excluded.pain_morning,
                    pain_afternoon   = excluded.pain_afternoon,
                    energy_morning   = excluded.energy_morning,
                    energy_afternoon = excluded.energy_afternoon,
                    notes            = excluded.notes
                """,
                e,
            )

        for w in weather:
            conn.execute(
                """
                INSERT INTO weather_data (
                    weather_date,
                    temperature_avg, temperature_min, temperature_max,
                    pressure_avg, humidity_avg, wind_speed_avg, precipitation
                ) VALUES (
                    :weather_date,
                    :temperature_avg, :temperature_min, :temperature_max,
                    :pressure_avg, :humidity_avg, :wind_speed_avg, :precipitation
                )
                ON CONFLICT(weather_date) DO UPDATE SET
                    temperature_avg = excluded.temperature_avg,
                    temperature_min = excluded.temperature_min,
                    temperature_max = excluded.temperature_max,
                    pressure_avg    = excluded.pressure_avg,
                    humidity_avg    = excluded.humidity_avg,
                    wind_speed_avg  = excluded.wind_speed_avg,
                    precipitation   = excluded.precipitation
                """,
                w,
            )

    print(f"Kész. {len(entries)} napi bejegyzés, {len(weather)} időjárási rekord.")
    print(f"Tesztadatbázis: {TEST_DB_PATH.resolve()}")
    print()
    print("Az alkalmazás tesztadatbázissal indítható — config.toml-ban:")
    print("  [database]")
    print(f'  path = "{TEST_DB_PATH}"')
    print()
    print(f"  {'Dátum':<12} {'Elalvás':<8} {'Ébredés':<8} {'Alvás':>6}  "
          f"{'Hangulat':>9}  {'Fájdalom':>9}  {'Energia':>8}")
    for e in entries[:7]:
        print(
            f"  {e['entry_date']:<12} {e['sleep_start']:<8} {e['sleep_end']:<8} "
            f"{e['sleep_hours']:>5.1f}h  "
            f"{e['mood_morning']}/{e['mood_afternoon']:<6}  "
            f"{e['pain_morning']}/{e['pain_afternoon']:<6}  "
            f"{e['energy_morning']}/{e['energy_afternoon']}"
        )


if __name__ == "__main__":
    main()
