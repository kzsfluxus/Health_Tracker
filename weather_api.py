"""
Open-Meteo API kliens.

A temperature_avg-ot manuálisan számoljuk (min+max)/2 alapján,
mert az API csak napi min/max-ot ad vissza daily szinten.
A pressure és humidity hourly mezők — ezeket napira átlagoljuk.
"""

from datetime import date, timedelta

import requests

from config import config

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(
    lat: float | None = None,
    lon: float | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Visszaadja az időjárási adatokat a megadott időintervallumra.
    Ha nincs megadva dátum, az elmúlt 7 napot kéri le.
    Koordináták alapértelmezetten a config.toml-ból jönnek.
    """
    lat = lat if lat is not None else config.location.lat
    lon = lon if lon is not None else config.location.lon

    if start_date is None:
        start_date = date.today() - timedelta(days=7)
    if end_date is None:
        end_date = date.today()

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        ],
        "hourly": [
            "surface_pressure",
            "relative_humidity_2m",
            "wind_speed_10m",
        ],
        "start_date": start_date.isoformat(),
        "end_date":   end_date.isoformat(),
        "timezone":   "auto",
    }

    response = requests.get(BASE_URL, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def parse_weather(raw: dict) -> list[dict]:
    """
    Az API nyers válaszát napi rekordok listájává alakítja.
    """
    daily  = raw.get("daily",  {})
    hourly = raw.get("hourly", {})

    dates         = daily.get("time", [])
    temp_max      = daily.get("temperature_2m_max", [])
    temp_min      = daily.get("temperature_2m_min", [])
    precipitation = daily.get("precipitation_sum",  [])

    hourly_times = hourly.get("time", [])
    pressures    = hourly.get("surface_pressure",      [])
    humidities   = hourly.get("relative_humidity_2m",  [])
    wind_speeds  = hourly.get("wind_speed_10m",        [])

    hourly_by_date: dict[str, dict[str, list]] = {}
    for i, t in enumerate(hourly_times):
        day = t[:10]
        if day not in hourly_by_date:
            hourly_by_date[day] = {"pressure": [], "humidity": [], "wind": []}
        if i < len(pressures)   and pressures[i]   is not None:
            hourly_by_date[day]["pressure"].append(pressures[i])
        if i < len(humidities)  and humidities[i]  is not None:
            hourly_by_date[day]["humidity"].append(humidities[i])
        if i < len(wind_speeds) and wind_speeds[i] is not None:
            hourly_by_date[day]["wind"].append(wind_speeds[i])

    def avg(lst: list) -> float | None:
        return round(sum(lst) / len(lst), 2) if lst else None

    records = []
    for i, day in enumerate(dates):
        t_max = temp_max[i] if i < len(temp_max) else None
        t_min = temp_min[i] if i < len(temp_min) else None
        t_avg = round((t_max + t_min) / 2, 2) if (t_max is not None and t_min is not None) else None

        h = hourly_by_date.get(day, {})
        records.append(
            {
                "weather_date":    day,
                "temperature_avg": t_avg,
                "temperature_min": t_min,
                "temperature_max": t_max,
                "pressure_avg":    avg(h.get("pressure", [])),
                "humidity_avg":    avg(h.get("humidity", [])),
                "wind_speed_avg":  avg(h.get("wind",     [])),
                "precipitation":   precipitation[i] if i < len(precipitation) else None,
            }
        )

    return records


def fetch_and_store_weather(
    lat: float | None = None,
    lon: float | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """
    Letölti és elmenti az időjárási adatokat az adatbázisba.
    Visszaadja a beszúrt/frissített sorok számát.
    """
    from database import get_connection

    raw     = fetch_weather(lat, lon, start_date, end_date)
    records = parse_weather(raw)

    with get_connection() as conn:
        cursor = conn.cursor()
        for r in records:
            cursor.execute(
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
                r,
            )

    return len(records)


def is_today_fetched() -> bool:
    """Igaz, ha a mai nap időjárási adata már szerepel az adatbázisban."""
    from database import get_connection

    today = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM weather_data WHERE weather_date = ?", (today,)
        ).fetchone()
    return row is not None


def auto_fetch_if_needed() -> int | None:
    """
    Ha a config engedélyezi és a mai adat hiányzik, letölti az elmúlt
    `initial_fetch_days` napot. Visszaadja a mentett sorok számát,
    vagy None-t, ha nem volt szükség frissítésre.
    """
    if not config.weather.auto_fetch_on_start:
        return None
    if is_today_fetched():
        return None

    days  = config.weather.initial_fetch_days
    start = date.today() - timedelta(days=days)
    return fetch_and_store_weather(start_date=start, end_date=date.today())
