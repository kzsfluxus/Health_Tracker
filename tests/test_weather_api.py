"""
weather_api.py egységtesztek.

A requests.get hívásokat mock-oljuk, nem indulnak valódi hálózati kérések.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from weather_api import parse_weather, fetch_weather, is_today_fetched, fetch_and_store_weather


# ---------------------------------------------------------------------------
# Tesztadat
# ---------------------------------------------------------------------------

MOCK_API_RESPONSE = {
    "daily": {
        "time": ["2024-01-15", "2024-01-16"],
        "temperature_2m_max": [8.0,  6.0],
        "temperature_2m_min": [2.0, -1.0],
        "precipitation_sum":  [0.0,  2.5],
    },
    "hourly": {
        "time": [
            "2024-01-15T00:00", "2024-01-15T06:00",
            "2024-01-15T12:00", "2024-01-15T18:00",
            "2024-01-16T00:00", "2024-01-16T06:00",
            "2024-01-16T12:00", "2024-01-16T18:00",
        ],
        "surface_pressure":     [1012.0, 1013.0, 1014.0, 1015.0,
                                  1010.0, 1011.0, 1012.0, 1013.0],
        "relative_humidity_2m": [80.0, 75.0, 70.0, 72.0,
                                  85.0, 82.0, 78.0, 80.0],
        "wind_speed_10m":       [10.0, 12.0, 15.0, 11.0,
                                   8.0,  9.0, 11.0, 10.0],
    },
}


# ---------------------------------------------------------------------------
# parse_weather tesztek
# ---------------------------------------------------------------------------

def test_parse_weather_returns_correct_number_of_records():
    records = parse_weather(MOCK_API_RESPONSE)
    assert len(records) == 2


def test_parse_weather_temperature_avg():
    records = parse_weather(MOCK_API_RESPONSE)
    # (8.0 + 2.0) / 2 = 5.0
    assert records[0]["temperature_avg"] == 5.0
    # (6.0 + (-1.0)) / 2 = 2.5
    assert records[1]["temperature_avg"] == 2.5


def test_parse_weather_pressure_avg():
    records = parse_weather(MOCK_API_RESPONSE)
    expected = round((1012.0 + 1013.0 + 1014.0 + 1015.0) / 4, 2)
    assert records[0]["pressure_avg"] == expected


def test_parse_weather_humidity_avg():
    records = parse_weather(MOCK_API_RESPONSE)
    expected = round((80.0 + 75.0 + 70.0 + 72.0) / 4, 2)
    assert records[0]["humidity_avg"] == expected


def test_parse_weather_date_field():
    records = parse_weather(MOCK_API_RESPONSE)
    assert records[0]["weather_date"] == "2024-01-15"
    assert records[1]["weather_date"] == "2024-01-16"


def test_parse_weather_precipitation():
    records = parse_weather(MOCK_API_RESPONSE)
    assert records[0]["precipitation"] == 0.0
    assert records[1]["precipitation"] == 2.5


def test_parse_weather_empty_response():
    records = parse_weather({})
    assert records == []


def test_parse_weather_handles_none_values():
    """None értékek nem okoznak kivételt a temperature_avg számításban."""
    raw = {
        "daily": {
            "time": ["2024-01-15"],
            "temperature_2m_max": [None],
            "temperature_2m_min": [None],
            "precipitation_sum":  [0.0],
        },
        "hourly": {"time": [], "surface_pressure": [],
                   "relative_humidity_2m": [], "wind_speed_10m": []},
    }
    records = parse_weather(raw)
    assert records[0]["temperature_avg"] is None


# ---------------------------------------------------------------------------
# fetch_weather tesztek (mock hálózat)
# ---------------------------------------------------------------------------

def test_fetch_weather_calls_correct_url():
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE

    with patch("weather_api.requests.get", return_value=mock_resp) as mock_get:
        fetch_weather(
            lat=47.39, lon=18.91,
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16),
        )
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "api.open-meteo.com" in call_kwargs[0][0]


def test_fetch_weather_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 500")

    with patch("weather_api.requests.get", return_value=mock_resp):
        with pytest.raises(Exception, match="HTTP 500"):
            fetch_weather()


# ---------------------------------------------------------------------------
# is_today_fetched tesztek
# ---------------------------------------------------------------------------

def test_is_today_fetched_false_when_empty(in_memory_db):
    assert is_today_fetched() is False


def test_is_today_fetched_true_after_insert(in_memory_db):
    today = date.today().isoformat()
    in_memory_db.execute(
        "INSERT INTO weather_data (weather_date) VALUES (?)", (today,)
    )
    in_memory_db.commit()
    assert is_today_fetched() is True


# ---------------------------------------------------------------------------
# fetch_and_store_weather integrációs teszt (mock hálózat + in-memory DB)
# ---------------------------------------------------------------------------

def test_fetch_and_store_inserts_records(in_memory_db):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_API_RESPONSE

    with patch("weather_api.requests.get", return_value=mock_resp):
        n = fetch_and_store_weather()

    assert n == 2
    rows = in_memory_db.execute("SELECT * FROM weather_data").fetchall()
    assert len(rows) == 2
