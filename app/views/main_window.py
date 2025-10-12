import os
from typing import Optional, Dict
from PySide6 import QtCore, QtGui, QtWidgets
from app.views.caja_view import CajaView
from app.views.bodega_view import BodegaView
from app.views.admin_view import AdminView

# Permisos por rol: qué secciones están habilitadas
PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "Administrador": {"caja": True,  "bodega": True,  "admin": True},
    "Cajero":        {"caja": True,  "bodega": True, "admin": True},
    "Bodega":        {"caja": False, "bodega": True,  "admin": False},
}


DEV_SHOW_ALL = os.getenv("CLOUDPOS_SHOW_ALL", "0") == "1"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, user: str, role: str, app_version: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.user = user
        self.role = role
        self.app_version = app_version

        self.setWindowTitle(f"CloudPOS — {role} [{user}]")
        self.resize(1100, 720)

        self.stacked = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.page_caja = CajaView(self)
        self.page_bodega = BodegaView(self)
        self.page_admin = AdminView(self)

        # Registro de secciones: nombre visible, clave de permiso, widget
        self.sections = [
            {"name": "Caja",            "perm": "caja",   "widget": self.page_caja},
            {"name": "Bodega",          "perm": "bodega", "widget": self.page_bodega},
            {"name": "Administración",  "perm": "admin",  "widget": self.page_admin},
        ]

        # Agregar vistas al stacked según el orden de sections
        for sec in self.sections:
            self.stacked.addWidget(sec["widget"])

        # Navegación lateral
        self.nav = QtWidgets.QListWidget()
        self.nav.setFixedWidth(180)
        for sec in self.sections:
            self.nav.addItem(sec["name"])
        self.nav.currentRowChanged.connect(self.stacked.setCurrentIndex)

        dock = QtWidgets.QDockWidget("Navegación")
        dock.setWidget(self.nav)
        dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

        # Barra de estado
        self.status = self.statusBar()
        self.status.showMessage(self._status_text())
        self._add_status_right()

        # Eliminar barra de menú (sin atajos)
        self.menuBar().hide()

        # Aplicar permisos del rol actual
        self._apply_role_permissions()

    def _status_text(self) -> str:
        ver = f" — Versión {self.app_version}" if self.app_version else ""
        return f"Usuario: {self.user} ({self.role}){ver}"

    def _add_status_right(self):
        right_box = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(right_box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        dot = QtWidgets.QLabel()
        dot.setObjectName("statusDot")
        dot.setFixedSize(12, 12)
        dot.setProperty("status", "ok")
        ver = QtWidgets.QLabel(f"v{self.app_version}") if self.app_version else QtWidgets.QLabel("")
        lay.addWidget(ver)
        lay.addWidget(dot)
        self.status.addPermanentWidget(right_box)

    def _apply_role_permissions(self):
        # En desarrollo, permite todo
        if DEV_SHOW_ALL:
            self.nav.setCurrentRow(0)
            return

        perms = PERMISSIONS.get(self.role, PERMISSIONS["Cajero"])

        # Ocultar/mostrar ítems de navegación según permisos
        for i, sec in enumerate(self.sections):
            allowed = bool(perms.get(sec["perm"], False))
            item = self.nav.item(i)
            if item:
                item.setHidden(not allowed)

        # Seleccionar la primera sección permitida
        first_index = self._first_allowed_index(perms)
        if first_index is not None:
            self.nav.setCurrentRow(first_index)
        else:
            self.nav.setCurrentRow(-1)

    def _first_allowed_index(self, perms: Dict[str, bool]) -> Optional[int]:
        for i, sec in enumerate(self.sections):
            if perms.get(sec["perm"], False):
                return i
        return None

    def _about(self):
        QtWidgets.QMessageBox.information(
            self,
            "Acerca de CloudPOS",
            "CloudPOS — UI (solo vistas)\nPySide6/Qt • Sin backend conectado."
        )