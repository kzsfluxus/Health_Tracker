from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPushButton,
    QStatusBar,
    QMessageBox,
)

from ui.daily_entry_widget import DailyEntryWidget
from ui.weekly_view_widget import WeeklyViewWidget
from ui.charts_widget import ChartsWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Alvás–Időjárás–Közérzet Követő")
        self.resize(1200, 800)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.tabs = QTabWidget()
        self.tabs.addTab(DailyEntryWidget(), "Napi bevitel")
        self.tabs.addTab(WeeklyViewWidget(), "Heti nézet")
        self.tabs.addTab(ChartsWidget(),     "Grafikonok")

        weather_btn = QPushButton("Időjárás letöltése")
        weather_btn.clicked.connect(self._fetch_weather)

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        top_bar.addWidget(weather_btn)

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_bar)
        main_layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self._auto_fetch_weather()

    # ------------------------------------------------------------------

    def _auto_fetch_weather(self):
        """Indításkor automatikusan frissíti az időjárást, ha szükséges."""
        try:
            from weather_api import auto_fetch_if_needed
            n = auto_fetch_if_needed()
            if n is not None:
                self.status.showMessage(
                    f"Időjárási adatok automatikusan frissítve: {n} nap mentve.", 6000
                )
        except Exception as exc:
            self.status.showMessage(f"Időjárás auto-fetch sikertelen: {exc}", 8000)

    def _fetch_weather(self):
        """Manuális időjárás-frissítés gombra."""
        try:
            from weather_api import fetch_and_store_weather
            n = fetch_and_store_weather()
            self.status.showMessage(
                f"Időjárási adatok frissítve: {n} nap mentve.", 5000
            )
        except Exception as exc:
            QMessageBox.critical(self, "Időjárás hiba", str(exc))
