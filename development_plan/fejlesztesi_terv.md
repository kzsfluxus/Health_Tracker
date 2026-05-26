# Fejlesztési terv — Alvás–Időjárás–Közérzet Követő

> Ez a dokumentum a személyes offline verzióból kiindulva dokumentálja,
> mi szükséges egy szélesebb felhasználói körnek szánt, deployolható rendszerhez.

---

## 1. Jelenlegi állapot (v0.3)

| Komponens          | Állapot                                                        |
|--------------------|----------------------------------------------------------------|
| Adatbázis          | SQLite, lokális fájl, context manager, rollback               |
| UI                 | PyQt6, öt fül (napi bevitel, heti nézet, grafikonok, ML, SHAP)|
| Időjárás           | Open-Meteo, auto-fetch indításkor + manuális gomb             |
| Konfiguráció       | `config.toml` + `config.py` loader                            |
| Analitika          | Heti aggregáció, feature engineering, korrelációk, validáció  |
| ML pipeline        | LightGBM, TimeSeriesSplit CV, mentés/betöltés, predikció      |
| SHAP               | Feature importance bar chart, UI-ba integrálva                |
| Tesztek            | `pytest`: database, weather_api, analytics, models            |
| Deployment         | Nincs — lokális futtatás                                       |
| Autentikáció       | Nincs                                                          |

---

## 2. Fázisok

### 2.1 Fázis — Stabil személyes verzió (v0.2) ✅ KÉSZ

**Cél:** mielőtt bármilyen multi-user logika kerül bele, legyen a core szilárd.

#### Elvégzett munkák

- [x] Egységtesztek: `database.py`, `weather_api.py`, `analytics.py`
  - `pytest` + `pytest-mock`
  - in-memory SQLite izolált fixture-ökkel
- [x] `weather_api.py`: automatikus napi frissítés indításkor, ha a mai adat hiányzik (`auto_fetch_if_needed`)
- [x] `analytics.py`: `weekly_summary()` helyes aggregáció — a lambda-alapú törött megközelítés helyett explicit oszlopszámítás a groupby előtt
- [x] Konfigurációs fájl (`config.toml`): koordináták, DB útvonal, küszöbértékek, auto-fetch beállítás
- [x] `config.py`: typed loader dataclass-okkal, fallback alapértékekel
- [x] `database.py` és `weather_api.py` config-ból olvassa a koordinátákat és az útvonalat
- [x] `__init__.py` fájlok a csomagokhoz

#### Kódminőség (opcionális, személyes verzióhoz nem kötelező)

A következők bevezetése a multi-user fázis előtt javasolt:

- `ruff` linter + `black` formatter
- `mypy` típusellenőrzés (legalább a `database.py` és `analytics.py` rétegre)
- Pre-commit hook

---

### 2.2 Fázis — ML pipeline (v0.3) ✅ KÉSZ

**Cél:** a `models.py` stub-ból működő pipeline legyen.

#### Elvégzett munkák

- [x] `analytics.build_feature_matrix()` validálása: minimális adatmennyiség-ellenőrzés (`config.thresholds.min_days_for_ml`), `ValueError` explicit üzenettel
- [x] LightGBM betanítás `TimeSeriesSplit` (5-fold) CV-vel, MAE/RMSE metrikák
- [x] `TrainResult` dataclass: modell, train/test halmazok, CV scores, MAE, RMSE
- [x] Modell mentése/betöltése LightGBM natív `.txt` formátumban (`data/models/`)
- [x] `predict_next()`: következő napi becslés, 1–10 közé clampelve
- [x] SHAP feature importance bar chart UI-ba integrálva (`_SHAPTab`)
- [x] ML fül: betanítás gomb, célváltozó választó, predikció gomb, teszt halmaz plot
- [x] Adatmennyiség-kapu: ha kevés az adat, tájékoztató üzenet jelenik meg, nem dob hibát
- [x] `config.toml` bővítve: `[models] storage_dir`
- [x] Egységtesztek: `tests/test_models.py` (betanítás, CV, mentés, betöltés, predikció, SHAP, validáció)

---

### 2.3 Fázis — Multi-user előkészítés (v1.0-alpha)

**Cél:** az architektúra legyen képes több felhasználót kezelni.

#### Adatbázis migráció

SQLite → PostgreSQL (vagy MariaDB, ha a meglévő infrastruktúrával konzisztens marad).

```sql
-- Felhasználó tábla
CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    email      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- daily_entries kibővítve
ALTER TABLE daily_entries ADD COLUMN user_id INTEGER REFERENCES users(id);

-- weather_data marad közös (location alapú)
```

Migrációs eszköz: `alembic` (ha SQLAlchemy-t használunk) vagy egyszerű SQL migration scriptek verziószámmal.

#### Autentikáció

- Minimális: lokális felhasználók, bcrypt hash
- Opcionálisan: OAuth2 (Google, GitHub) — csak ha webapp lesz belőle
- Session kezelés: JWT token vagy server-side session

#### API réteg

Ha a Flutter mobilkliens is megjelenik, REST API szükséges:

```
GET  /api/entries?user_id=&from=&to=
POST /api/entries
GET  /api/weather?date=
GET  /api/analytics/weekly?user_id=
GET  /api/ml/predict?user_id=
```

Javasolt stack: **FastAPI** (async, automatikus OpenAPI doc, jól integrálható a meglévő Python kóddal).

---

### 2.4 Fázis — Webapp / mobilkliens (v1.0)

#### Opció A — Web frontend

- FastAPI backend + React vagy HTMX frontend
- A PyQt6 desktop app párhuzamosan megmarad offline módban
- Szinkron: REST API hívások, conflict resolution: last-write-wins vagy timestamp alapú

#### Opció B — Flutter mobilkliens

- Flutter app: iOS + Android
- WiFi szinkron: mDNS discovery + REST API
- QR alapú párosítás az első kapcsolódáshoz
- Offline mód: lokális SQLite (sqflite csomag), háttérszinkron

**Ajánlás:** ha személyes marad (csak saját eszközök), az Opció B egyszerűbb.
Ha mások is használnák, az Opció A skálázhatóbb.

---

### 2.5 Fázis — Produkciós deployment (v1.1)

#### Infrastruktúra

| Komponens        | Megoldás                                      |
|------------------|-----------------------------------------------|
| Backend          | FastAPI, uvicorn + gunicorn                   |
| Adatbázis        | PostgreSQL, managed (pl. Supabase, RDS)       |
| Reverse proxy    | nginx                                         |
| Containerizáció  | Docker + Docker Compose                       |
| Orchestráció     | Kubernetes (ha skálázás szükséges)            |
| CI/CD            | GitHub Actions                                |
| Monitoring       | Prometheus + Grafana, vagy egyszerűbb: Sentry |
| Backup           | Napi pg_dump, S3-ba                           |

#### Időjárás cache

A weather_data tábla már cache-ként funkcionál.
Produkciós környezetben: background task (APScheduler vagy Celery), ami naponta egyszer frissít, nem gombnyomásra.

```python
# FastAPI + APScheduler példa
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=6, minute=0)
async def daily_weather_update():
    fetch_and_store_weather()
```

---

## 3. Adatvédelem és GDPR (ha külső felhasználók vannak)

- Egészségügyi adat különleges kategóriájú személyes adat (GDPR 9. cikk)
- Szükséges: explicit hozzájárulás, adattörlési lehetőség, adathordozhatóság
- Ajánlott: end-to-end encryption a szinkronizált adatokhoz
- Privacy policy és Terms of Service (ha publikus a service)

---

## 4. Bővíthető metrikák (jövőbeli adatmodell)

Az alábbi mezők bevezetésekor a `daily_entries` tábla bővítése szükséges,
vagy külön `health_metrics` tábla javasolt (kevesebb NULL az alaptáblában).

| Metrika           | Típus    | Skála / Egység    |
|-------------------|----------|-------------------|
| Koffein           | INTEGER  | mg / nap          |
| Alkohol           | REAL     | egység / nap      |
| Gyógyszerek       | TEXT     | névlista (JSON)   |
| Stressz           | INTEGER  | 1–10              |
| Migrén            | BOOLEAN  | igen/nem          |
| Vérnyomás sziszt. | INTEGER  | Hgmm              |
| Vérnyomás diasz.  | INTEGER  | Hgmm              |
| Pulzus            | INTEGER  | bpm               |
| SpO2              | REAL     | %                 |
| Lépések           | INTEGER  | db / nap          |

Smartwatch integráció (pl. Garmin Connect IQ, Apple HealthKit, Google Fit):
külön `device_sync` modul, a nyers adatok mappelése a belső sémára.

---

## 5. Vizualizációk (tervezett)

- [ ] Korrelációs heatmap: időjárás ↔ közérzet
- [ ] Időjárás overlay: alvás + légnyomás egy grafikonon, kettős y-tengely
- [ ] SHAP summary plot (integrált a UI-ba)
- [ ] Szezonális mintázatok: havi boxplot
- [ ] Trend: mozgóátlagok, anomália detekció

---

## 6. Tesztelési stratégia

### Egységtesztek (v0.2-ben megvalósítva)
- `database.py`: CRUD műveletek in-memory SQLite-tal, upsert, rollback
- `weather_api.py`: mock `requests` (`pytest-mock`), parse_weather, is_today_fetched, fetch_and_store
- `analytics.py`: fix DataFrame bemenetre determinisztikus kimenet — weekly_summary, build_feature_matrix, weather_correlations

### Integrációs tesztek (v1.0-alpha-tól)
- Teljes pipeline: fake adat → DB → analytics → output
- API végpontok: FastAPI TestClient

### UI tesztek (opcionális)
- `pytest-qt`: widget interakciók szimulálása
- Minimálisan: mentés → visszaolvasás konzisztencia

### Adatminőség-ellenőrzés (v0.3-tól)
- Minimum adatmennyiség az ML-hez
- Outlier detekció: alvás > 14 h, fájdalom hirtelen ugrás

---

## 7. Verziótérkép

| Verzió         | Tartalom                                           | Állapot           |
|----------------|----------------------------------------------------|-------------------|
| v0.1-personal  | Alap UI, SQLite, időjárás fetch, heti nézet        | ✅ Kész           |
| v0.2           | Tesztek, config, auto-fetch, weekly_summary javítva| ✅ Kész           |
| v0.3           | LightGBM + SHAP UI, predikció, CV, modell mentés  | ✅ Kész           |
| v1.0-alpha     | PostgreSQL, FastAPI, multi-user alapok             | 🔲 Tervezett      |
| v1.0           | Web/mobil kliens, szinkron                         | 🔲 Tervezett      |
| v1.1           | Produkciós deployment, monitoring                  | 🔲 Tervezett      |
