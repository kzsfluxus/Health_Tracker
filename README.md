# Alvás–Időjárás–Közérzet Követő

Offline-first személyes egészségnapló PyQt6 + SQLite alapon.
Automatikusan letölti az időjárási adatokat (Open-Meteo API),
és összekapcsolja azokat az alvás, hangulat, ízületi fájdalom
és energiaszint napi bejegyzéseivel.

**Jelenlegi verzió: v0.3**

---

## Funkciók

- Napi beviteli űrlap: elalvás (előző este), ébredés, hangulat, fájdalom, energia (1–10 skála), megjegyzések
- Heti táblázat heti átlagokkal + soronkénti módosítás gomb
- Grafikonok: alvás, hangulat, fájdalom, időjárás (hőmérséklet + légnyomás)
- ML fül: LightGBM betanítás TimeSeriesSplit CV-vel, MAE/RMSE, holnapi becslés
- SHAP fül: feature importance bar chart, megmutatja mi befolyásolja legjobban a közérzetet
- Időjárás automatikus letöltése indításkor, ha a mai adat hiányzik
- Konfigurációs fájl: koordináták, küszöbértékek, model storage útvonal

---

## Rendszerkövetelmények

- Python 3.11+
- Linux (Debian/Ubuntu ajánlott), macOS, Windows

---

## Telepítés

```bash
git clone <repo>
cd health_tracker

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -r requirements.txt

python main.py
```

Az adatbázis (`data/health_tracker.db`) az első indításkor automatikusan létrejön.
Az időjárási adatok az első indításkor automatikusan letöltődnek (ha hálózat elérhető).

---

## Konfiguráció

A `config.toml` fájl szerkeszthető a projekt gyökerében:

```toml
[location]
lat  = 47.3949
lon  = 18.9136
name = "Érd"

[database]
path = "data/health_tracker.db"

[weather]
auto_fetch_on_start = true   # automatikus frissítés indításkor
initial_fetch_days  = 30     # hány napra visszamenőleg töltse le az első futáskor

[thresholds]
bad_sleep_hours = 6.0        # ennyi óránál kevesebb számít "rossz" napnak
min_days_for_ml = 30         # minimum adat az ML pipeline-hoz (v0.3)
```

---

## Tesztek futtatása

```bash
pytest tests/ -v
```

A tesztek in-memory SQLite-ot és mock hálózati hívásokat használnak —
nincs szükség hálózatra vagy valódi adatbázisra.

---

## Tesztadatbázis generálása

Ha az ML fület és a grafikonokat valódi adattal szeretnéd kipróbálni az éles DB
érintése nélkül:

```bash
python scripts/create_pseudo_database.py
```

A script 31 nap szintetikus adatot ír a `data/health_tracker_test.db` fájlba —
a projekt gyökeréhez képest, függetlenül attól honnan futtatod. Az éles
`health_tracker.db`-t nem érinti.

Az alkalmazás ezután a tesztadatbázissal indítható — a `config.toml`-ban
átmenetileg:

```toml
[database]
path = "data/health_tracker_test.db"
```

Tesztelés után visszaírni az eredetire:

```toml
[database]
path = "data/health_tracker.db"
```

---

## Projektstruktúra

```
health_tracker/
├── main.py                        # Belépési pont
├── config.toml                    # Felhasználói konfiguráció
├── config.py                      # Typed config loader
├── database.py                    # SQLite kapcsolat, séma inicializáció
├── weather_api.py                 # Open-Meteo fetch + parse + auto-fetch
├── analytics.py                   # Aggregációk, feature engineering, korrelációk
├── models.py                      # LightGBM pipeline: train, save, load, predict, SHAP
├── requirements.txt
│
├── ui/
│   ├── main_window.py             # Főablak, fülek, auto-fetch indításkor
│   ├── daily_entry_widget.py      # Napi beviteli űrlap
│   ├── weekly_view_widget.py      # Heti táblázat + módosítás gomb soronként
│   └── charts_widget.py           # Grafikonok + ML fül + SHAP fül
│
├── scripts/
│   └── create_pseudo_database.py  # 31 nap szintetikus adat → health_tracker_test.db
│
├── tests/
│   ├── conftest.py                # Megosztott fixture-ök (in-memory DB)
│   ├── test_database.py           # CRUD, upsert tesztek
│   ├── test_weather_api.py        # parse, fetch, auto-fetch tesztek
│   ├── test_analytics.py          # weekly_summary, feature matrix, korreláció
│   └── test_models.py             # train, CV, save/load, predict, SHAP tesztek
│
├── data/
│   ├── health_tracker.db          # Éles adatbázis (gitignore-ba kerül)
│   ├── health_tracker_test.db     # Tesztadatbázis (gitignore-ba kerül)
│   └── models/                    # Mentett LightGBM modellek (.txt)
│
└── development_plan/
    └── fejlesztesi_terv.md        # Tervezett fázisok szélesebb felhasználáshoz
```

---

## Adatmodell

Két tábla:

**`daily_entries`** — napi naplóbejegyzések
(dátum, alvás kezdete/vége/hossza, hangulat/fájdalom/energia délelőtt+délután, megjegyzések)

**`weather_data`** — napi időjárás
(dátum, hőmérséklet avg/min/max, légnyomás, páratartalom, szélsebesség, csapadék)

Ugyanarra a dátumra többször menthető bejegyzés — az utolsó felülírja az előzőt (`ON CONFLICT DO UPDATE`).

---

## Fejlesztési terv

A `development_plan/fejlesztesi_terv.md` tartalmazza a tervezett fázisokat,
ha a projekt személyes eszközből szélesebb felhasználású rendszerré bővül
(PostgreSQL, FastAPI, Flutter mobilkliens, produkciós deployment, GDPR).
