from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets


class LoginWindow(QtWidgets.QMainWindow):
    """
    - Usuario y contraseña
    - Mensajes de error
    - Estado de conexión simulado y versión
    Nota: El rol será determinado por backend más adelante.
          Mientras tanto, se emite un rol placeholder ("Cajero").
    """
    login_success = QtCore.Signal(str, str)  # username, role (placeholder)

    DEFAULT_ROLE = "Cajero"  # Placeholder hasta conectar backend

    def __init__(self, app_version: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._app_version = app_version
        self.setWindowTitle("CloudPOS — Inicio de sesión")
        self.setMinimumSize(520, 420)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Encabezado
        title = QtWidgets.QLabel("CloudPOS")
        title.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        subtitle = QtWidgets.QLabel("Sistema de Caja e Inventario")
        subtitle.setAlignment(QtCore.Qt.AlignHCenter)
        subtitle.setStyleSheet("color: #5f6368;")
        root.addWidget(title)
        root.addWidget(subtitle)

        # Tarjeta de formulario
        form_card = QtWidgets.QFrame()
        form_card.setFrameShape(QtWidgets.QFrame.StyledPanel)
        form_card.setProperty("card", True)
        form_layout = QtWidgets.QFormLayout(form_card)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(12)

        self.username = QtWidgets.QLineEdit()
        self.username.setPlaceholderText("Usuario")
        self.username.setClearButtonEnabled(True)

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Contraseña")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setClearButtonEnabled(True)

        form_layout.addRow("Usuario:", self.username)
        form_layout.addRow("Contraseña:", self.password)

        # Mensaje de error
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        # Botones
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.login_btn = QtWidgets.QPushButton("Ingresar")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login_clicked)
        self.exit_btn = QtWidgets.QPushButton("Salir")
        self.exit_btn.clicked.connect(self.close)
        btn_row.addWidget(self.exit_btn)
        btn_row.addWidget(self.login_btn)

        inner_layout = QtWidgets.QVBoxLayout()
        inner_layout.addWidget(form_card)
        inner_layout.addWidget(self.error_label)
        inner_layout.addLayout(btn_row)
        root.addLayout(inner_layout)

        # Barra inferior: versión y estado de conexión
        status_bar = QtWidgets.QHBoxLayout()
        status_bar.addStretch(1)

        version_label = QtWidgets.QLabel(f"Versión {self._app_version}") if self._app_version else QtWidgets.QLabel("")
        self.status_dot = QtWidgets.QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedSize(12, 12)
        self.status_text = QtWidgets.QLabel("Desconectado")

        # Estado inicial
        self._set_connection_status(False)

        status_bar.addWidget(version_label)
        status_bar.addSpacing(12)
        status_bar.addWidget(self.status_dot)
        status_bar.addWidget(self.status_text)
        root.addStretch(1)
        root.addLayout(status_bar)

        # Atajos (QtGui.QShortcut)
        s_return = QtGui.QShortcut(QtGui.QKeySequence("Return"), self)
        s_return.activated.connect(self.on_login_clicked)
        s_enter = QtGui.QShortcut(QtGui.QKeySequence("Enter"), self)
        s_enter.activated.connect(self.on_login_clicked)
        s_esc = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self)
        s_esc.activated.connect(self.close)

        # Simula verificación de conexión
        QtCore.QTimer.singleShot(300, lambda: self._set_connection_status(True))

    # === Lógica UI local (sin backend) ===
    def _set_connection_status(self, ok: bool):
        if not hasattr(self, "status_dot") or not hasattr(self, "status_text"):
            return
        self.status_dot.setProperty("status", "ok" if ok else "bad")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_text.setText("Conectado" if ok else "Desconectado")

    def on_login_clicked(self):
        user = self.username.text().strip()
        pwd = self.password.text()

        ok, msg = self._validate_credentials(user, pwd)
        if not ok:
            return self._show_error(msg)

        self.error_label.setVisible(False)
        # Emitimos un rol placeholder hasta que el backend asigne el real
        self.login_success.emit(user, self.DEFAULT_ROLE)

    def _validate_credentials(self, user: str, pwd: str) -> Tuple[bool, str]:
        if not user:
            return False, "Ingresa tu usuario."
        if not pwd:
            return False, "Ingresa tu contraseña."
        if len(user) < 3:
            return False, "El usuario debe tener al menos 3 caracteres."
        if len(pwd) < 4:
            return False, "La contraseña debe tener al menos 4 caracteres."
        # Regla demo temporal
        if pwd != "1234":
            return False, "Usuario o contraseña incorrectos."
        return True, ""

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.setVisible(True)