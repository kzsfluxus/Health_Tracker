from datetime import datetime, timedelta

import database
from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QPushButton,
    QTextEdit,
    QSpinBox,
    QDateEdit,
    QTimeEdit,
    QMessageBox,
)


class DailyEntryWidget(QWidget):
    def __init__(self, entry_date: str | None = None):
        """
        entry_date: 'yyyy-MM-dd' formátumú string, vagy None (= mai nap).
        Ha meg van adva és létezik az adatbázisban, az űrlap feltöltődik
        a meglévő adatokkal.
        """
        super().__init__()
        self._build_ui()

        if entry_date:
            self._set_date(entry_date)
            self._load_entry(entry_date)
        
    def _build_ui(self):
        layout = QVBoxLayout()
        form = QFormLayout()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())

        self.sleep_start = QTimeEdit()
        self.sleep_end   = QTimeEdit()

        self.mood_morning    = self._scale()
        self.mood_afternoon  = self._scale()

        self.pain_morning    = self._scale()
        self.pain_afternoon  = self._scale()

        self.energy_morning   = self._scale()
        self.energy_afternoon = self._scale()

        self.notes = QTextEdit()
        self.notes.setFixedHeight(80)

        form.addRow("Dátum",                    self.date_edit)
        form.addRow("Elalvás (előző este)",       self.sleep_start)
        form.addRow("Ébredés (ma reggel)",        self.sleep_end)
        form.addRow("Hangulat délelőtt",         self.mood_morning)
        form.addRow("Hangulat délután",           self.mood_afternoon)
        form.addRow("Ízületi fájdalom délelőtt", self.pain_morning)
        form.addRow("Ízületi fájdalom délután",  self.pain_afternoon)
        form.addRow("Energiaszint délelőtt",     self.energy_morning)
        form.addRow("Energiaszint délután",       self.energy_afternoon)
        form.addRow("Megjegyzések",              self.notes)

        save_btn = QPushButton("Mentés")
        save_btn.clicked.connect(self._save_entry)

        layout.addLayout(form)
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def _scale(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 10)
        spin.setValue(5)
        return spin

    def _set_date(self, date_str: str):
        """Beállítja a dátummezőt és zárolja — módosítás esetén a dátum nem változtatható."""
        q_date = QDate.fromString(date_str, "yyyy-MM-dd")
        if q_date.isValid():
            self.date_edit.setDate(q_date)
            self.date_edit.setEnabled(False)

    def _load_entry(self, date_str: str):
        """Betölti a meglévő bejegyzést az adatbázisból és feltölti az űrlapot."""
        with database.get_connection() as conn:
            row = conn.execute(
                """
                SELECT sleep_start, sleep_end,
                       mood_morning, mood_afternoon,
                       pain_morning, pain_afternoon,
                       energy_morning, energy_afternoon,
                       notes
                FROM daily_entries
                WHERE entry_date = ?
                """,
                (date_str,),
            ).fetchone()

        if row is None:
            return

        if row["sleep_start"]:
            t = QTime.fromString(row["sleep_start"], "HH:mm")
            if t.isValid():
                self.sleep_start.setTime(t)

        if row["sleep_end"]:
            t = QTime.fromString(row["sleep_end"], "HH:mm")
            if t.isValid():
                self.sleep_end.setTime(t)

        self.mood_morning.setValue(row["mood_morning"]    or 5)
        self.mood_afternoon.setValue(row["mood_afternoon"] or 5)
        self.pain_morning.setValue(row["pain_morning"]    or 5)
        self.pain_afternoon.setValue(row["pain_afternoon"] or 5)
        self.energy_morning.setValue(row["energy_morning"]   or 5)
        self.energy_afternoon.setValue(row["energy_afternoon"] or 5)
        self.notes.setPlainText(row["notes"] or "")

    def _calc_sleep_hours(self, start_str: str, end_str: str) -> float:
        fmt = "%H:%M"
        start_dt = datetime.strptime(start_str, fmt)
        end_dt   = datetime.strptime(end_str,   fmt)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return round((end_dt - start_dt).total_seconds() / 3600, 2)

    def _save_entry(self):
        date_str    = self.date_edit.date().toString("yyyy-MM-dd")
        sleep_start = self.sleep_start.time().toString("HH:mm")
        sleep_end   = self.sleep_end.time().toString("HH:mm")
        sleep_hours = self._calc_sleep_hours(sleep_start, sleep_end)

        try:
            with database.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO daily_entries (
                        entry_date,
                        sleep_start, sleep_end, sleep_hours,
                        mood_morning, mood_afternoon,
                        pain_morning, pain_afternoon,
                        energy_morning, energy_afternoon,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(entry_date) DO UPDATE SET
                        sleep_start      = excluded.sleep_start,
                        sleep_end        = excluded.sleep_end,
                        sleep_hours      = excluded.sleep_hours,
                        mood_morning     = excluded.mood_morning,
                        mood_afternoon   = excluded.mood_afternoon,
                        pain_morning     = excluded.pain_morning,
                        pain_afternoon   = excluded.pain_afternoon,
                        energy_morning   = excluded.energy_morning,
                        energy_afternoon = excluded.energy_afternoon,
                        notes            = excluded.notes
                    """,
                    (
                        date_str,
                        sleep_start, sleep_end, sleep_hours,
                        self.mood_morning.value(),
                        self.mood_afternoon.value(),
                        self.pain_morning.value(),
                        self.pain_afternoon.value(),
                        self.energy_morning.value(),
                        self.energy_afternoon.value(),
                        self.notes.toPlainText(),
                    ),
                )
            QMessageBox.information(
                self, "Mentés", f"Adatok mentve ({sleep_hours:.1f} óra alvás)"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Hiba", str(exc))
