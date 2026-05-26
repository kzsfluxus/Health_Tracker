import sys

from PyQt6.QtWidgets import QApplication

from database import initialize_database
from ui.main_window import MainWindow


def main():
    initialize_database()

    app = QApplication(sys.argv)
    app.setApplicationName("Health Tracker")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
