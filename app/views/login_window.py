from __future__ import annotations
from typing import Optional, Any
from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork
import hashlib
import json
from datetime import datetime

from app.servicios.api import ApiClient
from app.servicios.api_monitor import ApiMonitor, LedIndicator
from app.funciones.rol import normalize_role


class LoginWindow(QtWidgets.QMainWindow):
    login_success = QtCore.Signal(str, str)  # username, role normalized
    DEFAULT_ROLE = "Cajero"

    def __init__(self, app_version: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._app_version = app_version
        self.setWindowTitle("CloudPOS — Inicio de sesión")
        self.setMinimumSize(520, 420)

        if not QtCore.QCoreApplication.organizationName():
            QtCore.QCoreApplication.setOrganizationName("CloudPOS")
        if not QtCore.QCoreApplication.applicationName():
            QtCore.QCoreApplication.setApplicationName("CloudPOS")
        if self._app_version:
            QtCore.QCoreApplication.setApplicationVersion(self._app_version)

        # Token de vinculación (para /login). No persistente.
        self.link_token: Optional[str] = None

        # --- Red asíncrona para login ---
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

        # Mensaje de error
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)

        # Botones (Vincular a la izquierda)
        btn_row = QtWidgets.QHBoxLayout()
        self.link_btn = QtWidgets.QPushButton("Vincular")
        self.link_btn.setToolTip("Vincular cliente mediante correo y código")
        self.link_btn.clicked.connect(self._on_link_clicked)
        btn_row.addWidget(self.link_btn) 

        btn_row.addStretch(1)
        self.exit_btn = QtWidgets.QPushButton("Salir")
        self.exit_btn.clicked.connect(self.close)
        self.login_btn = QtWidgets.QPushButton("Ingresar")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login_clicked)
        btn_row.addWidget(self.exit_btn)
        btn_row.addWidget(self.login_btn)

        inner_layout = QtWidgets.QVBoxLayout()
        inner_layout.addWidget(form_card)
        inner_layout.addWidget(self.error_label)
        inner_layout.addLayout(btn_row)
        root.addLayout(inner_layout)

        # Barra inferior (versión + LED estado + texto)
        status_bar = QtWidgets.QHBoxLayout()
        status_bar.addStretch(1)

        version_label = QtWidgets.QLabel(f"Versión {self._app_version}") if self._app_version else QtWidgets.QLabel("")
        self.api_led = LedIndicator(12, self)
        self.api_led.setToolTip("Estado de conexión a la API")
        self.status_text = QtWidgets.QLabel("Desconectado")

        status_bar.addWidget(version_label)
        status_bar.addSpacing(12)
        status_bar.addWidget(self.api_led)
        status_bar.addWidget(self.status_text)
        root.addStretch(1)
        root.addLayout(status_bar)

        # Atajos
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, self.on_login_clicked)
        QtGui.QShortcut(QtGui.QKeySequence("Enter"), self, self.on_login_clicked)
        QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

        # Persistencia: limpiar cred guardadas si cambia de versión
        self._init_link_persistence()

        # Monitor de API (LED)
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

    # ---------- Persistencia de Vincular (QSettings) ----------
    def _init_link_persistence(self):
        """Al cambiar la versión de la app, borra correo/código guardados."""
        settings = QtCore.QSettings()
        stored_version = settings.value("app/version", "", type=str)
        current_version = self._app_version or "dev"
        if stored_version and stored_version != current_version:
            settings.remove("link")
        settings.setValue("app/version", current_version)

    def _load_link_saved(self) -> tuple[str, str]:
        """Lee correo y código guardados (si existen)."""
        settings = QtCore.QSettings()
        email = settings.value("link/email", "", type=str) or ""
        code = settings.value("link/code", "", type=str) or ""
        return email, code

    def _save_link_saved(self, correo: str, codigo: str, remember: bool):
        """Guarda o limpia correo/código, según el checkbox."""
        settings = QtCore.QSettings()
        if remember:
            settings.setValue("link/email", correo or "")
            settings.setValue("link/code", codigo or "")
        else:
            settings.remove("link/email")
            settings.remove("link/code")

    # ---------- Vincular ----------
    def _on_link_clicked(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Vincular cliente")
        dlg.setModal(True)
        lay = QtWidgets.QFormLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)

        email_edit = QtWidgets.QLineEdit()
        email_edit.setPlaceholderText("correo@ejemplo.com")
        email_edit.setClearButtonEnabled(True)

        code_edit = QtWidgets.QLineEdit()
        code_edit.setPlaceholderText("Código de vinculación")
        code_edit.setClearButtonEnabled(True)
        code_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        remember_chk = QtWidgets.QCheckBox("Guardar correo y código en este equipo")

        # Prellenar si ya estaba guardado
        saved_email, saved_code = self._load_link_saved()
        if saved_email:
            email_edit.setText(saved_email)
            remember_chk.setChecked(True)
        if saved_code:
            code_edit.setText(saved_code)
            remember_chk.setChecked(True)

        lay.addRow("Correo:", email_edit)
        lay.addRow("Código:", code_edit)
        lay.addRow("", remember_chk)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=dlg
        )
        btns.button(QtWidgets.QDialogButtonBox.Ok).setText("Aceptar")
        btns.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addRow(btns)

        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        correo = email_edit.text().strip()
        codigo = code_edit.text().strip()
        if not correo or not codigo:
            QtWidgets.QMessageBox.information(self, "Vincular", "Debes ingresar Correo y Código.")
            return

        # Guarda/limpia según el checkbox
        self._save_link_saved(correo, codigo, remember_chk.isChecked())

        payload = {
            "correo": correo,
            "codigo": codigo,
            "fecha": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }

        client = ApiClient()
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            resp = client.post_json("/vincular", payload)
            if isinstance(resp, dict) and resp.get("error"):
                msg = resp.get("detail") or f"HTTP {resp.get('status', '')}"
                QtWidgets.QMessageBox.warning(self, "Vincular", f"Error al vincular:\n{msg}")
                return

            token = None
            if isinstance(resp, dict):
                token = resp.get("token_vinculacion")
            if not token:
                QtWidgets.QMessageBox.warning(self, "Vincular", "La API no entregó un token de vinculación.")
                return

            # Guardar token de vinculación en memoria (no persistente)
            self.link_token = token
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.setProperty("link_token", token)

            QtWidgets.QMessageBox.information(self, "Vincular", "Vinculación exitosa.\nToken almacenado (memoria).")
        finally:
            try:
                QtWidgets.QApplication.restoreOverrideCursor()
            except Exception:
                pass

    def on_login_clicked(self):
        if self._pending_reply is not None:
            self._show_error("Ya hay una autenticación en curso. Espera un momento…")
            return

        app = QtWidgets.QApplication.instance()
        link_token = None
        if app is not None:
            link_token = app.property("link_token")
        if not link_token:
            link_token = self.link_token

        if not link_token:
            if QtWidgets.QMessageBox.question(
                self, "Token requerido",
                "Debes vincular tu cliente antes de iniciar sesión.\n¿Deseas vincular ahora?"
            ) == QtWidgets.QMessageBox.Yes:
                self._on_link_clicked()
            else:
                self._show_error("Falta token de vinculación. Usa el botón 'Vincular'.")
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

        client = ApiClient()
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(f"{client.base_url}/login"))
        req.setRawHeader(b"Content-Type", b"application/json")
        req.setRawHeader(b"Accept", b"application/json")
        # IMPORTANTE: /login usa el token de vinculación
        req.setRawHeader(b"Authorization", f"Bearer {link_token}".encode("utf-8"))

        payload = {"nombre": user, "contrasena": hashed_pwd}
        reply = self._nam.post(req, json.dumps(payload).encode("utf-8"))
        self._pending_reply = reply

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

            self.login_btn.setEnabled(True)
            self.status_text.setText(prev_status if prev_status else "Desconectado")

            # Errores de red
            if net_err != QtNetwork.QNetworkReply.NetworkError.NoError and status_code not in (400, 401, 403, 422):
                return self._show_error(err_str or "Error de red")

            try:
                res: Any = json.loads(raw.decode("utf-8", errors="ignore"))
            except Exception:
                res = {"detail": raw.decode("utf-8", errors="ignore")}

            # Token inválido/expirado en /login
            if status_code in (401, 403):
                return self._show_error("Token de vinculación inválido o expirado. Vuelve a 'Vincular' e inténtalo nuevamente.")

            # ---- Extraer y guardar el token de sesión del LOGIN ----
            login_token = None
            if isinstance(res, dict):
                keys = ("token", "access_token", "auth_token", "jwt", "bearer", "authorization",
                        "Authorization", "token_login")
                for k in keys:
                    if k in res and res[k]:
                        login_token = str(res[k]); break
                if not login_token:
                    data = res.get("data")
                    if isinstance(data, dict):
                        for k in keys:
                            if k in data and data[k]:
                                login_token = str(data[k]); break

            if not login_token:
                return self._show_error("El inicio de sesión no entregó token de sesión.")

            # Guardar token de sesión en memoria para el resto de la app
            if app is not None:
                app.setProperty("auth_token", login_token)

            # ---- Manejo de código/errores y rol ----
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
                        role_raw = res.get(key); break
                if role_raw is None:
                    userobj = res.get("user") or res.get("usuario") or res.get("data")
                    if isinstance(userobj, dict):
                        for key in ("rol_id", "role_id", "id_rol", "rolid", "rol", "role"):
                            if key in userobj and userobj.get(key) is not None:
                                role_raw = userobj.get(key); break

            role_name = normalize_role(role_raw, default=self.DEFAULT_ROLE)
            self.error_label.setVisible(False)
            self.status_text.setText("Conectado")
            self.login_success.emit(user, role_name)

        reply.finished.connect(_finish)
        timer.start()

    def _abort_reply(self, reply: QtNetwork.QNetworkReply):
        if reply is self._pending_reply and reply.isRunning():
            reply.abort()

    # Limpieza segura al cerrar
    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        try:
            if hasattr(self, "_api_monitor") and self._api_monitor:
                self._api_monitor.stop()
        except Exception:
            pass
        try:
            if getattr(self, "_pending_reply", None) is not None:
                rep = self._pending_reply
                self._pending_reply = None
                if rep.isRunning():
                    rep.abort()
                rep.deleteLater()
        except Exception:
            pass
        super().closeEvent(e)
