import os
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
    
    try:
        base_dir = os.path.dirname(__file__)
        qss_path = os.path.join(base_dir, "assets", "style.qss")
        icons_dir = os.path.join(base_dir, "assets", "icons").replace("\\", "/")
        with open(qss_path, "r", encoding="utf-8") as f:
            qss = f.read().replace("%ICONS%", icons_dir)
        app.setStyleSheet(qss)
    except FileNotFoundError:
        pass

    login = LoginWindow(app_version=APP_VERSION)
    login.show()

    def on_login_success(user, role):
        app.main_window = MainWindow(user=user, role=role, app_version=APP_VERSION)
        if hasattr(app.main_window, "page_caja"):
            app.main_window.page_caja.usuario_actual = user
        elif hasattr(app.main_window, "caja_view"):
            app.main_window.caja_view.usuario_actual = user
        app.main_window.show()
        login.close()

    login.login_success.connect(on_login_success)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
