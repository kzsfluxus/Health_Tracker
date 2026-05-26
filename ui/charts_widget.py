"""
Grafikon fülek: Alvás, Hangulat, Fájdalom, Időjárás, ML/SHAP.

Az ML és SHAP fülek csak akkor aktívak, ha elegendő adat áll rendelkezésre
(config.thresholds.min_days_for_ml). Ha kevés az adat, tájékoztató üzenetet
mutat, nem dob hibát.
"""

import pandas as pd

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QLabel,
    QComboBox,
)
from PyQt6.QtCore import Qt

import database
from config import config


class _ChartTab(QWidget):
    """Egy matplotlib vászon egy fülön belül, frissítés gombbal."""

    def __init__(self, plot_fn):
        super().__init__()
        self._plot_fn = plot_fn

        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)
        toolbar = NavigationToolbar2QT(self.canvas, self)

        refresh_btn = QPushButton("Frissítés")
        refresh_btn.clicked.connect(self.refresh)

        layout = QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(refresh_btn)
        self.setLayout(layout)

        self.refresh()

    def refresh(self):
        self.figure.clear()
        self._plot_fn(self.figure)
        self.canvas.draw()


class _MLTab(QWidget):
    """
    ML betanítás, értékelés és predikció fül.
    Csak akkor aktív, ha elegendő adat van.
    """

    TARGET_LABELS = {
        "sleep_hours": "Alvás (időjárás hatása)",
        "pain_avg":    "Fájdalom",
        "mood_avg":    "Hangulat",
        "energy_avg":  "Energia",
    }

    def __init__(self):
        super().__init__()
        self._result = None

        # Célváltozó választó
        self._target_combo = QComboBox()
        for key, label in self.TARGET_LABELS.items():
            self._target_combo.addItem(label, key)

        train_btn   = QPushButton("Betanítás")
        predict_btn = QPushButton("Holnapi becslés")
        train_btn.clicked.connect(self._train)
        predict_btn.clicked.connect(self._predict)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Célváltozó:"))
        btn_row.addWidget(self._target_combo)
        btn_row.addWidget(train_btn)
        btn_row.addWidget(predict_btn)
        btn_row.addStretch()

        self._status = QLabel("Még nincs betanított modell.")
        self._status.setWordWrap(True)

        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)

        layout = QVBoxLayout()
        layout.addLayout(btn_row)
        layout.addWidget(self._status)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self._check_data()

    def _check_data(self):
        """Ellenőrzi, hogy elegendő adat áll-e rendelkezésre."""
        from analytics import load_merged
        try:
            df = load_merged()
            n  = len(df.dropna(subset=["pressure_avg"]))
            min_days = config.thresholds.min_days_for_ml
            if n < min_days:
                self._status.setText(
                    f"Kevés adat: {n} nap érhető el időjárással együtt "
                    f"(minimum: {min_days}). Gyűjts több bejegyzést."
                )
        except Exception:
            pass

    def _target(self) -> str:
        return self._target_combo.currentData()

    def _train(self):
        from analytics import load_merged, build_feature_matrix
        from models import train_model, save_model

        try:
            df     = load_merged()
            matrix = build_feature_matrix(df)
        except ValueError as exc:
            self._status.setText(str(exc))
            return

        try:
            result       = train_model(matrix, target=self._target())
            self._result = result
            path         = save_model(result)

            cv_mean = sum(result.cv_scores) / len(result.cv_scores)
            self._status.setText(
                f"Betanítva: {self.TARGET_LABELS[result.target]} | "
                f"MAE: {result.mae:.2f} | RMSE: {result.rmse:.2f} | "
                f"CV MAE (5-fold): {cv_mean:.2f} | "
                f"Mentve: {path}"
            )
            self._plot_predictions(result)
        except Exception as exc:
            self._status.setText(f"Hiba a betanítás során: {exc}")

    def _predict(self):
        from analytics import load_merged, build_feature_matrix
        from models import load_model, predict_next

        target = self._target()
        try:
            model = load_model(target)
        except FileNotFoundError:
            self._status.setText(
                "Nincs mentett modell. Először futtasd a betanítást."
            )
            return

        try:
            df     = load_merged()
            matrix = build_feature_matrix(df)
            latest = matrix.iloc[[-1]]
            pred   = predict_next(model, latest, target)
            label  = self.TARGET_LABELS[target]
            self._status.setText(
                f"Holnapi {label} becslés: {pred:.1f} / 10"
            )
        except Exception as exc:
            self._status.setText(f"Hiba a predikció során: {exc}")

    def _plot_predictions(self, result):
        """Tényleges vs. becsült értékek a teszt halmazon."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        y_true = result.y_test.values
        y_pred = result.model.predict(result.X_test)

        ax.plot(y_true, label="Valós", marker="o", linewidth=1.5)
        ax.plot(y_pred, label="Becsült", marker="s", linewidth=1.5, linestyle="--")
        ax.set_title(f"{self.TARGET_LABELS[result.target]} — teszt halmaz")
        ax.set_xlabel("Minta")
        ax.set_ylabel("Érték (1–10)")
        ax.set_ylim(0, 11)
        ax.legend()
        self.figure.tight_layout()
        self.canvas.draw()


class _SHAPTab(QWidget):
    """SHAP feature importance és summary plot."""

    def __init__(self):
        super().__init__()

        self._target_combo = QComboBox()
        for key, label in _MLTab.TARGET_LABELS.items():
            self._target_combo.addItem(label, key)

        explain_btn = QPushButton("SHAP elemzés futtatása")
        explain_btn.clicked.connect(self._run)

        self._status = QLabel("Válassz célváltozót és kattints a gombra.")

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Célváltozó:"))
        btn_row.addWidget(self._target_combo)
        btn_row.addWidget(explain_btn)
        btn_row.addStretch()

        self.figure = Figure(figsize=(10, 5))
        self.canvas = FigureCanvasQTAgg(self.figure)

        layout = QVBoxLayout()
        layout.addLayout(btn_row)
        layout.addWidget(self._status)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def _run(self):
        from analytics import load_merged, build_feature_matrix
        from models import train_model, explain_model

        try:
            import shap
        except ImportError:
            self._status.setText("A 'shap' csomag nincs telepítve.")
            return

        try:
            df     = load_merged()
            matrix = build_feature_matrix(df)
        except ValueError as exc:
            self._status.setText(str(exc))
            return

        target = self._target_combo.currentData()
        try:
            result           = train_model(matrix, target=target)
            shap_values, _   = explain_model(result)

            self.figure.clear()
            ax = self.figure.add_subplot(111)

            # Bar chart: átlagos |SHAP| értékek feature-önként
            mean_abs = pd.Series(
                abs(shap_values).mean(axis=0),
                index=result.X_test.columns,
            ).sort_values()

            mean_abs.plot(kind="barh", ax=ax, color="#4C72B0")
            ax.set_title(
                f"SHAP feature fontosság — {_MLTab.TARGET_LABELS[target]}"
            )
            ax.set_xlabel("Átlagos |SHAP érték|")
            self.figure.tight_layout()
            self.canvas.draw()

            self._status.setText("SHAP elemzés kész.")
        except Exception as exc:
            self._status.setText(f"Hiba: {exc}")


class ChartsWidget(QWidget):
    def __init__(self):
        super().__init__()

        tabs = QTabWidget()
        tabs.addTab(_ChartTab(self._plot_sleep),   "Alvás")
        tabs.addTab(_ChartTab(self._plot_mood),    "Hangulat")
        tabs.addTab(_ChartTab(self._plot_pain),    "Fájdalom")
        tabs.addTab(_ChartTab(self._plot_weather), "Időjárás")
        tabs.addTab(_MLTab(),                      "ML")
        tabs.addTab(_SHAPTab(),                    "SHAP")

        layout = QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Adatbetöltés
    # ------------------------------------------------------------------

    def _load_entries(self) -> pd.DataFrame:
        with database.get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM daily_entries ORDER BY entry_date", conn
            )
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        return df

    def _load_weather(self) -> pd.DataFrame:
        with database.get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM weather_data ORDER BY weather_date", conn
            )
        df["weather_date"] = pd.to_datetime(df["weather_date"])
        return df

    # ------------------------------------------------------------------
    # Plot függvények
    # ------------------------------------------------------------------

    def _plot_sleep(self, fig: Figure):
        df = self._load_entries()
        ax = fig.add_subplot(111)
        if df.empty:
            ax.text(0.5, 0.5, "Nincs adat", ha="center", va="center")
            return
        ax.plot(df["entry_date"], df["sleep_hours"], marker="o", linewidth=1.5, color="#4C72B0")
        ax.axhline(7, color="gray", linestyle="--", linewidth=0.8, label="7 h ajánlott")
        ax.set_title("Alvásórák")
        ax.set_xlabel("Dátum")
        ax.set_ylabel("Óra")
        ax.legend()
        fig.autofmt_xdate()

    def _plot_mood(self, fig: Figure):
        df = self._load_entries()
        ax = fig.add_subplot(111)
        if df.empty:
            ax.text(0.5, 0.5, "Nincs adat", ha="center", va="center")
            return
        ax.plot(df["entry_date"], df["mood_morning"],   marker="o", label="Délelőtt", linewidth=1.5)
        ax.plot(df["entry_date"], df["mood_afternoon"], marker="s", label="Délután",   linewidth=1.5)
        ax.set_title("Hangulat (1–10)")
        ax.set_xlabel("Dátum")
        ax.set_ylabel("Értékelés")
        ax.set_ylim(0, 11)
        ax.legend()
        fig.autofmt_xdate()

    def _plot_pain(self, fig: Figure):
        df = self._load_entries()
        ax = fig.add_subplot(111)
        if df.empty:
            ax.text(0.5, 0.5, "Nincs adat", ha="center", va="center")
            return
        ax.fill_between(df["entry_date"], df["pain_morning"],   alpha=0.4, label="Délelőtt")
        ax.fill_between(df["entry_date"], df["pain_afternoon"], alpha=0.4, label="Délután")
        ax.set_title("Ízületi fájdalom (1–10)")
        ax.set_xlabel("Dátum")
        ax.set_ylabel("Intenzitás")
        ax.set_ylim(0, 11)
        ax.legend()
        fig.autofmt_xdate()

    def _plot_weather(self, fig: Figure):
        df = self._load_weather()
        if df.empty:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Nincs időjárási adat", ha="center", va="center")
            return

        ax1 = fig.add_subplot(211)
        ax1.plot(df["weather_date"], df["temperature_avg"], color="#e07b39", linewidth=1.5)
        ax1.set_title("Hőmérséklet (°C)")
        ax1.set_ylabel("°C")
        fig.autofmt_xdate()

        ax2 = fig.add_subplot(212)
        ax2.plot(df["weather_date"], df["pressure_avg"], color="#5c7e99", linewidth=1.5)
        ax2.set_title("Légnyomás (hPa)")
        ax2.set_ylabel("hPa")
        fig.autofmt_xdate()

        fig.tight_layout()
