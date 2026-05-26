"""
Megosztott pytest fixture-ök.

Az in-memory SQLite adatbázist minden tesztfüggvény frissen kapja,
így a tesztek egymástól teljesen izoláltak.
"""

import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture
def in_memory_db():
    """
    Egy inicializált in-memory SQLite kapcsolatot ad vissza.
    A database modul get_connection()-ját patch-eli, hogy a tesztek
    ne nyúljanak a valódi adatbázis fájlhoz.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript(
        """
        CREATE TABLE daily_entries (
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

        CREATE TABLE weather_data (
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

    @contextmanager
    def _mock_get_connection():
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    with patch("database.get_connection", _mock_get_connection):
        yield conn

    conn.close()
