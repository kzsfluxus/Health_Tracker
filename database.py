import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import config

DB_PATH = Path(config.database.path)


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
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
            )
            """
        )

        cursor.execute(
            """
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
            )
            """
        )
