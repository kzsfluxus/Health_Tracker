"""
Konfigurációs réteg.

Python 3.11+ esetén a tomllib stdlib csomag.
A config.toml a projekt gyökerében keresendő; ha nem található,
az alapértelmezett értékek érvényesek (tesztkörnyezetben is biztonságos).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.toml"


@dataclass
class LocationConfig:
    lat: float = 47.3949
    lon: float = 18.9136
    name: str = "Érd"


@dataclass
class DatabaseConfig:
    path: str = "data/health_tracker.db"


@dataclass
class ModelsConfig:
    storage_dir: str = "data/models"


@dataclass
class WeatherConfig:
    auto_fetch_on_start: bool = True
    initial_fetch_days: int = 30


@dataclass
class ThresholdsConfig:
    bad_sleep_hours: float = 6.0
    min_days_for_ml: int = 30


@dataclass
class AppConfig:
    location:   LocationConfig   = field(default_factory=LocationConfig)
    database:   DatabaseConfig   = field(default_factory=DatabaseConfig)
    models:     ModelsConfig     = field(default_factory=ModelsConfig)
    weather:    WeatherConfig    = field(default_factory=WeatherConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)


def load_config(path: Path = _CONFIG_PATH) -> AppConfig:
    """
    Betölti a config.toml-t. Ha a fájl nem létezik, alapértelmezett
    értékeket ad vissza — teszteléshez és első indításhoz is biztonságos.
    """
    if not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    loc = raw.get("location", {})
    db  = raw.get("database", {})
    mdl = raw.get("models", {})
    wth = raw.get("weather", {})
    thr = raw.get("thresholds", {})

    return AppConfig(
        location=LocationConfig(
            lat=loc.get("lat", 47.3949),
            lon=loc.get("lon", 18.9136),
            name=loc.get("name", "Érd"),
        ),
        database=DatabaseConfig(
            path=db.get("path", "data/health_tracker.db"),
        ),
        models=ModelsConfig(
            storage_dir=mdl.get("storage_dir", "data/models"),
        ),
        weather=WeatherConfig(
            auto_fetch_on_start=wth.get("auto_fetch_on_start", True),
            initial_fetch_days=wth.get("initial_fetch_days", 30),
        ),
        thresholds=ThresholdsConfig(
            bad_sleep_hours=thr.get("bad_sleep_hours", 6.0),
            min_days_for_ml=thr.get("min_days_for_ml", 30),
        ),
    )


# Egyetlen globális példány — a többi modul ebből olvas
config = load_config()
