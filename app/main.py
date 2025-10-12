import sys
from PySide6 import QtWidgets
from app.views.login_window import LoginWindow
from app.views.main_window import MainWindow

APP_VERSION = "0.1.0"


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("CloudPOS")
    app.setOrganizationName("CloudPOS")
    app.setStyle("Fusion")

    # Carga de estilos (opcional)
    try:
        with open("app/assets/style.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass

    login = LoginWindow(app_version=APP_VERSION)
    login.show()

    def on_login_success(user, role):
        # Mantén una referencia viva a la ventana principal
        app.main_window = MainWindow(user=user, role=role, app_version=APP_VERSION)
        app.main_window.show()
        login.close()

    login.login_success.connect(on_login_success)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()