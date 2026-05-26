"""
database.py egységtesztek.

Teszteli: initialize_database, bejegyzés mentése, felülírás (UPSERT),
weather_data mentése és visszaolvasása.

A visszaolvasás szintén get_connection()-on keresztül történik,
nem a raw in_memory_db-n — így a patch mindkét irányt lefedi.
"""

import pytest
import database
from database import initialize_database


def test_initialize_creates_tables(in_memory_db):
    """Az initialize_database létrehozza a szükséges táblákat."""
    initialize_database()
    with database.get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "daily_entries" in tables
    assert "weather_data"  in tables


def test_insert_daily_entry(in_memory_db):
    """Napi bejegyzés mentése és visszaolvasása."""
    with database.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_entries (
                entry_date, sleep_start, sleep_end, sleep_hours,
                mood_morning, mood_afternoon,
                pain_morning, pain_afternoon,
                energy_morning, energy_afternoon,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2024-01-15", "23:00", "07:00", 8.0, 7, 6, 3, 4, 8, 7, "teszt"),
        )

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_entries WHERE entry_date = '2024-01-15'"
        ).fetchone()

    assert row is not None
    assert row["sleep_hours"] == 8.0
    assert row["mood_morning"] == 7
    assert row["notes"] == "teszt"


def test_upsert_daily_entry(in_memory_db):
    """Ugyanarra a dátumra való újramentés felülírja az előző adatot."""
    for sleep_hours in (6.0, 8.5):
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO daily_entries (entry_date, sleep_hours,
                    mood_morning, mood_afternoon, pain_morning, pain_afternoon,
                    energy_morning, energy_afternoon)
                VALUES (?, ?, 5, 5, 5, 5, 5, 5)
                ON CONFLICT(entry_date) DO UPDATE SET sleep_hours = excluded.sleep_hours
                """,
                ("2024-01-15", sleep_hours),
            )

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT sleep_hours FROM daily_entries WHERE entry_date = '2024-01-15'"
        ).fetchone()
    assert row["sleep_hours"] == 8.5


def test_insert_weather_data(in_memory_db):
    """Időjárási adat mentése és visszaolvasása."""
    with database.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO weather_data (
                weather_date, temperature_avg, temperature_min, temperature_max,
                pressure_avg, humidity_avg, wind_speed_avg, precipitation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2024-01-15", 5.5, 2.0, 9.0, 1015.2, 78.0, 12.3, 0.0),
        )

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM weather_data WHERE weather_date = '2024-01-15'"
        ).fetchone()

    assert row is not None
    assert row["temperature_avg"] == 5.5
    assert row["pressure_avg"]    == 1015.2


def test_weather_upsert(in_memory_db):
    """Időjárási adat felülírása konfliktus esetén."""
    for pressure in (1010.0, 1020.0):
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO weather_data (weather_date, pressure_avg)
                VALUES (?, ?)
                ON CONFLICT(weather_date) DO UPDATE SET pressure_avg = excluded.pressure_avg
                """,
                ("2024-01-15", pressure),
            )

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT pressure_avg FROM weather_data WHERE weather_date = '2024-01-15'"
        ).fetchone()
    assert row["pressure_avg"] == 1020.0
