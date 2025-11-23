# app/views/main_window.py
import os
from typing import Optional, Dict, Any
from PySide6 import QtCore, QtGui, QtWidgets

# Vistas
from app.views.caja_view import CajaView
from app.views.bodega_view import BodegaView
from app.views.admin_view import AdminView

# Monitor de API
from app.servicios.api import ApiClient
from app.servicios.api_monitor import ApiMonitor, LedIndicator

from app.funciones.rol import normalize_role

PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "Administrador": {"caja": True,  "bodega": True,  "admin": True},
    "Cajero":        {"caja": True,  "bodega": False, "admin": False},
    "Bodega":        {"caja": False, "bodega": True,  "admin": False},
}

# Si quieres ver todo sin esconder nada durante desarrollo:
DEV_SHOW_ALL = os.getenv("CLOUDPOS_SHOW_ALL", "0") == "1"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, user: str, role: Any, app_version: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.user = user
        self.role = normalize_role(role, default="Cajero")
        self.app_version = app_version

        self.setWindowTitle(f"CloudPOS — {self.role} [{user}]")
        self.resize(1100, 720)

        # --- Contenido central con páginas ---
        self.stacked = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.page_caja = CajaView(self)
        self.page_bodega = BodegaView(self)
        self.page_admin = AdminView(self)

        self.sections = [
            {"name": "Caja",           "perm": "caja",   "widget": self.page_caja},
            {"name": "Bodega",         "perm": "bodega", "widget": self.page_bodega},
            {"name": "Administración", "perm": "admin",  "widget": self.page_admin},
        ]
        for sec in self.sections:
            self.stacked.addWidget(sec["widget"])

        # --- Navegación lateral (dock) ---
        self.nav = QtWidgets.QListWidget()
        self.nav.setFixedWidth(200)
        self.nav.setObjectName("navList")  # <- para que el style.qss aplique el tema
        for sec in self.sections:
            self.nav.addItem(sec["name"])
        self.nav.currentRowChanged.connect(self.stacked.setCurrentIndex)

        self.nav_dock = QtWidgets.QDockWidget("Navegación", self)
        self.nav_dock.setWidget(self.nav)
        self.nav_dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.nav_dock)

        # --- Barra de estado (texto + LED de API) ---
        self.status = self.statusBar()
        self.status.showMessage(self._status_text())
        self._add_status_right()

        # Ocultamos la barra de menús (más limpio)
        self.menuBar().hide()

        # Aplica permisos y visibilidad según rol
        self._apply_role_permissions()
        self._apply_role_visibility()

        # --- Monitor de API: LED rojo/verde ---
        self._api_monitor = ApiMonitor(ApiClient(), self, interval_ms=15000)  # 15s
        self._api_monitor.onlineChanged.connect(self.api_led.set_state)
        self._api_monitor.start(run_immediately=True)

    # ---------------- Helpers UI ----------------
    def _status_text(self) -> str:
        ver = f" — Versión {self.app_version}" if self.app_version else ""
        return f"Usuario: {self.user} ({self.role}){ver}"

    def _add_status_right(self):
        right_box = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(right_box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        ver_lbl = QtWidgets.QLabel(f"v{self.app_version}") if self.app_version else QtWidgets.QLabel("")
        self.api_led = LedIndicator(12, self)  # LED de estado (rojo/verde)
        self.api_led.setToolTip("Estado de conexión a la API")

        lay.addWidget(ver_lbl)
        lay.addWidget(self.api_led)
        self.status.addPermanentWidget(right_box)

    # ---------------- Permisos / Visibilidad ----------------
    def _apply_role_permissions(self):
        """Oculta items del menú según permisos por rol (cuando la barra es visible)."""
        if DEV_SHOW_ALL:
            self.nav.setCurrentRow(0)
            return

        perms = PERMISSIONS.get(self.role, PERMISSIONS["Cajero"])
        for i, sec in enumerate(self.sections):
            allowed = bool(perms.get(sec["perm"], False))
            item = self.nav.item(i)
            if item:
                item.setHidden(not allowed)

        # Selecciona la primera sección permitida
        first_index = self._first_allowed_index(perms)
        self.nav.setCurrentRow(first_index if first_index is not None else -1)

    def _apply_role_visibility(self):
        """Muestra/Oculta la barra de navegación completa según rol."""
        if DEV_SHOW_ALL:
            self.nav_dock.show()
            return

        is_admin = self.role.lower() in ("administrador", "admin")
        # Para Cajero/Bodega ocultamos todo el dock lateral
        self.nav_dock.setVisible(is_admin)

    def _first_allowed_index(self, perms: Dict[str, bool]) -> Optional[int]:
        for i, sec in enumerate(self.sections):
            if perms.get(sec["perm"], False):
                return i
        return None

    # ---------------- Eventos de ventana ----------------
    def _about(self):
        QtWidgets.QMessageBox.information(
            self,
            "Acerca de CloudPOS",
            "CloudPOS — UI (solo vistas)\nPySide6/Qt."
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # Detiene el monitor si está activo para liberar recursos
        try:
            if hasattr(self, "_api_monitor") and self._api_monitor:
                self._api_monitor.stop()
        except Exception:
            pass
        super().closeEvent(event)
