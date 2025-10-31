from typing import Optional, Any
from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork
import hashlib
import json

from app.servicios.api import ApiClient
from app.servicios.api_monitor import ApiMonitor, LedIndicator
from app.funciones.rol import normalize_role


class LoginWindow(QtWidgets.QMainWindow):
    login_success = QtCore.Signal(str, str)  # username, role (normalized)
    DEFAULT_ROLE = "Cajero"

    def __init__(self, app_version: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._app_version = app_version
        self.setWindowTitle("CloudPOS — Inicio de sesión")
        self.setMinimumSize(520, 420)

        # --- Red asíncrona ---
        self._nam = QtNetwork.QNetworkAccessManager(self)
        self._nam.authenticationRequired.connect(self._ignore_auth)
        self._pending_reply: Optional[QtNetwork.QNetworkReply] = None

        # ---------- UI ----------
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

        # Tarjeta/formulario
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

        # Mensaje de error (debajo de la tarjeta)
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

        # Barra inferior 
        status_bar = QtWidgets.QHBoxLayout()
        status_bar.addStretch(1)

        version_label = QtWidgets.QLabel(f"Versión {self._app_version}") if self._app_version else QtWidgets.QLabel("")
        self.api_led = LedIndicator(12, self)  # LED rojo/verde
        self.api_led.setToolTip("Estado de conexión a la API")
        self.status_text = QtWidgets.QLabel("Desconectado")

        status_bar.addWidget(version_label)
        status_bar.addSpacing(12)
        status_bar.addWidget(self.api_led)
        status_bar.addWidget(self.status_text)
        root.addStretch(1)
        root.addLayout(status_bar)

        # Atajos (como en tu versión original)
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, self.on_login_clicked)
        QtGui.QShortcut(QtGui.QKeySequence("Enter"), self, self.on_login_clicked)
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        # ---------- Monitor de API ----------
        self._api_monitor = ApiMonitor(ApiClient(), self, interval_ms=15000)
        self._api_monitor.onlineChanged.connect(self.api_led.set_state)
        self._api_monitor.onlineChanged.connect(self._on_api_online_changed)
        self._api_monitor.start(run_immediately=True)

    # ---------- Auxiliares UI ----------
    @QtCore.Slot(bool)
    def _on_api_online_changed(self, ok: bool):
        self.status_text.setText("Conectado" if ok else "Desconectado")

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    @QtCore.Slot(QtNetwork.QNetworkReply, QtNetwork.QAuthenticator)
    def _ignore_auth(self, _reply: QtNetwork.QNetworkReply, authenticator: QtNetwork.QAuthenticator):
        authenticator.setUser("")
        authenticator.setPassword("")

    # ---------- Acción de login ----------
    def on_login_clicked(self):
        # Evitar múltiples solicitudes en paralelo
        if self._pending_reply is not None:
            self._show_error("Ya hay una autenticación en curso. Espera un momento…")
            return

        user = self.username.text().strip()
        pwd = self.password.text() or ""

        if not user:
            return self._show_error("Ingresa tu usuario.")
        if not pwd:
            return self._show_error("Ingresa tu contraseña.")

        try:
            hashed_pwd = hashlib.md5(pwd.encode("utf-8")).hexdigest()
        except Exception:
            return self._show_error("Error al procesar la contraseña.")

        self.error_label.setVisible(False)
        self.login_btn.setEnabled(False)
        prev_status = self.status_text.text()
        self.status_text.setText("Conectando...")

        # Petición HTTP
        client = ApiClient()
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(f"{client.base_url}/login"))
        req.setRawHeader(b"Content-Type", b"application/json")
        req.setRawHeader(b"Accept", b"application/json")

        payload = {"nombre": user, "contrasena": hashed_pwd}
        reply = self._nam.post(req, json.dumps(payload).encode("utf-8"))
        self._pending_reply = reply

        # Timeout de seguridad
        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(max(5000, client.timeout * 1000))
        timer.timeout.connect(lambda: self._abort_reply(reply))

        def _finish():
            if timer.isActive():
                timer.stop()
            timer.deleteLater()

            raw = bytes(reply.readAll())
            status_code = int(reply.attribute(QtNetwork.QNetworkRequest.HttpStatusCodeAttribute) or 0)
            net_err = reply.error()
            err_str = reply.errorString()
            reply.deleteLater()
            self._pending_reply = None

            # Restaurar UI
            self.login_btn.setEnabled(True)
            self.status_text.setText(prev_status if prev_status else "Desconectado")

            # Errores de red “duros” (host caído, timeout, etc.): mostrar tal cual
            if net_err != QtNetwork.QNetworkReply.NetworkError.NoError and status_code not in (400, 401, 403, 422):
                return self._show_error(err_str or "Error de red")

            try:
                res: Any = json.loads(raw.decode("utf-8", errors="ignore"))
            except Exception:
                res = {"detail": raw.decode("utf-8", errors="ignore")}

            # Compatibilidad con ApiClient.post_json
            def _get_status_code(resp: Any) -> int:
                if not isinstance(resp, dict):
                    return status_code or 200
                try:
                    return int(resp.get("status", status_code or 200))
                except Exception:
                    return status_code or 200

            code = _get_status_code(res)
            if isinstance(res, dict) and (res.get("error") or code >= 400):
                err_msg = (
                    (res.get("detail") if isinstance(res.get("detail"), str) else None)
                    or res.get("message")
                    or ("Usuario o contraseña incorrectos." if code in (400, 401, 403) else f"Error HTTP {code}")
                )
                return self._show_error(err_msg)

            # Extraer rol
            role_raw = None
            if isinstance(res, str):
                role_raw = res
            elif isinstance(res, dict):
                for key in ("rol_id", "role_id", "id_rol", "rolid", "role", "rol"):
                    if key in res and res.get(key) is not None:
                        role_raw = res.get(key)
                        break
                if role_raw is None:
                    userobj = res.get("user") or res.get("usuario") or res.get("data")
                    if isinstance(userobj, dict):
                        for key in ("rol_id", "role_id", "id_rol", "rolid", "rol", "role"):
                            if key in userobj and userobj.get(key) is not None:
                                role_raw = userobj.get(key)
                                break

            role_name = normalize_role(role_raw, default=self.DEFAULT_ROLE)

            # Éxito: mostrar estado y emitir señal
            self.error_label.setVisible(False)
            self.status_text.setText("Conectado")
            self.login_success.emit(user, role_name)
            print(f"[Login] Usuario '{user}' autenticado. Rol: {role_name}")

        reply.finished.connect(_finish)
        timer.start()

    def _abort_reply(self, reply: QtNetwork.QNetworkReply):
        if reply is self._pending_reply and reply.isRunning():
            reply.abort()
