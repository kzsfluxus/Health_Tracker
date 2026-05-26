import pandas as pd

import database
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QDialog,
    QVBoxLayout as QVBox,
)
from PyQt6.QtCore import Qt

from ui.daily_entry_widget import DailyEntryWidget


COLUMNS = {
    "entry_date":       "Dátum",
    "sleep_hours":      "Alvás (h)",
    "mood_morning":     "Hangulat D.e.",
    "mood_afternoon":   "Hangulat D.u.",
    "pain_morning":     "Fájdalom D.e.",
    "pain_afternoon":   "Fájdalom D.u.",
    "energy_morning":   "Energia D.e.",
    "energy_afternoon": "Energia D.u.",
}


class _EditDialog(QDialog):
    """Modális dialógus egy meglévő nap szerkesztéséhez."""

    def __init__(self, entry_date: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Bejegyzés módosítása — {entry_date}")
        self.setMinimumWidth(420)

        self._widget = DailyEntryWidget(entry_date=entry_date)

        # A mentés után zárja be a dialógust
        self._widget.findChild(QPushButton).clicked.connect(self._on_saved)

        layout = QVBox()
        layout.addWidget(self._widget)
        self.setLayout(layout)

    def _on_saved(self):
        # Kis késleltetés: a DailyEntryWidget saját save slotja fut le először
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self.accept)


class WeeklyViewWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # +1 oszlop a gombokhoz
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        refresh_btn = QPushButton("Frissítés")
        refresh_btn.clicked.connect(self.load_data)

        layout = QVBoxLayout()
        layout.addWidget(refresh_btn)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.load_data()

    def load_data(self):
        with database.get_connection() as conn:
            df = pd.read_sql_query(
                f"""
                SELECT {', '.join(COLUMNS.keys())}
                FROM daily_entries
                ORDER BY entry_date DESC
                LIMIT 7
                """,
                conn,
            )

        self._fill_table(df)
        self._fill_summary(df)

    def _fill_table(self, df: pd.DataFrame):
        col_count = len(COLUMNS) + 1  # +1 a Módosítás gombnak
        self.table.setRowCount(len(df))
        self.table.setColumnCount(col_count)
        self.table.setHorizontalHeaderLabels(list(COLUMNS.values()) + [""])

        for row in range(len(df)):
            for col, key in enumerate(COLUMNS.keys()):
                val = df.iloc[row, col]
                item = QTableWidgetItem(
                    f"{val:.1f}" if isinstance(val, float) else str(val)
                )
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

            # Módosítás gomb az utolsó oszlopban
            entry_date = df.iloc[row]["entry_date"]
            btn = QPushButton("Módosítás")
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda checked, d=entry_date: self._open_edit(d))
            self.table.setCellWidget(row, len(COLUMNS), btn)

        self.table.resizeColumnsToContents()
        # A gomb oszlop ne nyújtódjön túl
        self.table.setColumnWidth(len(COLUMNS), 100)

    def _open_edit(self, entry_date: str):
        dialog = _EditDialog(entry_date, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _fill_summary(self, df: pd.DataFrame):
        if df.empty:
            self.summary_label.setText("Nincs adat.")
            return

        avg_sleep  = df["sleep_hours"].mean()
        avg_mood   = ((df["mood_morning"] + df["mood_afternoon"]) / 2).mean()
        avg_pain   = ((df["pain_morning"] + df["pain_afternoon"]) / 2).mean()
        avg_energy = ((df["energy_morning"] + df["energy_afternoon"]) / 2).mean()
        bad_sleep  = (df["sleep_hours"] < 6).sum()

        self.summary_label.setText(
            f"Heti átlag — Alvás: {avg_sleep:.1f} h | "
            f"Hangulat: {avg_mood:.1f} | "
            f"Fájdalom: {avg_pain:.1f} | "
            f"Energia: {avg_energy:.1f} | "
            f"Rossz alvásos napok: {bad_sleep}"
        )
