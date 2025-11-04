from PySide6 import QtCore
from app.servicios.api import ApiClient
import hashlib


class _ListarUsuariosWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)  # (usuarios, error)

    def __init__(self, client: ApiClient):
        super().__init__()
        self.client = client

    @QtCore.Slot()
    def run(self):
        try:
            res = self.client.get_json("/usuarios")
            if isinstance(res, dict) and "usuario" in res:
                usuarios = res.get("usuario") or []
                self.finished.emit(usuarios, "")
                return
            if isinstance(res, list):
                self.finished.emit(res, "")
                return
            self.finished.emit([], "Formato de respuesta inesperado.")
        except Exception as e:
            self.finished.emit([], str(e))


class _CrearUsuarioWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str)

    def __init__(self, client: ApiClient, payload: dict):
        super().__init__()
        self.client = client
        self.payload = payload

    @QtCore.Slot()
    def run(self):
        try:
            pwd = self.payload.get("contrasena") or ""
            if pwd:
                self.payload["contrasena"] = hashlib.md5(pwd.encode("utf-8")).hexdigest()
            res = self.client.post_json("/usuario", self.payload)
            if isinstance(res, dict) and (res.get("error") or int(res.get("status", 200)) >= 400):
                msg = res.get("detail") or res.get("message") or "No se pudo crear el usuario."
                self.finished.emit("", msg)
            else:
                self.finished.emit("Usuario creado correctamente.", "")
        except Exception as e:
            self.finished.emit("", str(e))


class _ActualizarNombreUsuarioWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str)

    def __init__(self, client: ApiClient, user_id: int, nombre: str):
        super().__init__()
        self.client = client
        self.user_id = user_id
        self.nombre = nombre

    @QtCore.Slot()
    def run(self):
        try:
            res = self.client.put_json(f"/usuarios/{self.user_id}/nombre", {"nombre": self.nombre})
            if isinstance(res, dict) and (res.get("error") or int(res.get("status", 200)) >= 400):
                msg = res.get("detail") or res.get("message") or "No se pudo actualizar el nombre."
                self.finished.emit("", msg)
            else:
                self.finished.emit("Nombre actualizado.", "")
        except Exception as e:
            self.finished.emit("", str(e))


class _ActualizarContrasenaUsuarioWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str)

    def __init__(self, client: ApiClient, user_id: int, contrasena: str):
        super().__init__()
        self.client = client
        self.user_id = user_id
        self.contrasena = contrasena

    @QtCore.Slot()
    def run(self):
        try:
            hashed = hashlib.md5(self.contrasena.encode("utf-8")).hexdigest()
            res = self.client.put_json(
                f"/usuarios/{self.user_id}/contrasena",
                {"contrasena": hashed}
            )
            if isinstance(res, dict) and (res.get("error") or int(res.get("status", 200)) >= 400):
                msg = res.get("detail") or res.get("message") or "No se pudo actualizar la contraseña."
                self.finished.emit("", msg)
            else:
                self.finished.emit("Contraseña actualizada.", "")
        except Exception as e:
            self.finished.emit("", str(e))


class UsuariosService(QtCore.QObject):
    usuariosListados = QtCore.Signal(list)
    usuarioCreado = QtCore.Signal(str)
    usuarioActualizado = QtCore.Signal(str)
    error = QtCore.Signal(str)
    busy = QtCore.Signal(bool)

    def __init__(self, client: ApiClient | None = None, parent=None):
        super().__init__(parent)
        self.client = client or ApiClient()
        self._thread: QtCore.QThread | None = None
        self._worker: QtCore.QObject | None = None 

    def _start_thread(self, worker: QtCore.QObject) -> bool:
        # si ya hay un hilo corriendo, no lanzamos otro
        if self._thread and self._thread.isRunning():
            return False
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.finished.connect(self._thread.deleteLater)
        # limpiar referencias cuando termine
        self._thread.finished.connect(self._clear_thread)
        return True

    @QtCore.Slot()
    def _clear_thread(self):
        self._thread = None
        self._worker = None

    # -------- operaciones públicas --------
    def listar(self):
        worker = _ListarUsuariosWorker(self.client)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_listado)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    def crear(self, payload: dict):
        worker = _CrearUsuarioWorker(self.client, payload)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_creado)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    def actualizar_nombre(self, user_id: int, nuevo_nombre: str):
        worker = _ActualizarNombreUsuarioWorker(self.client, user_id, nuevo_nombre)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_actualizado)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    def actualizar_contrasena(self, user_id: int, nueva_contrasena: str):
        worker = _ActualizarContrasenaUsuarioWorker(self.client, user_id, nueva_contrasena)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_actualizado)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    # -------- handlers --------
    @QtCore.Slot(list, str)
    def _on_listado(self, usuarios: list, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.usuariosListados.emit(usuarios)

    @QtCore.Slot(str, str)
    def _on_creado(self, msg: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.usuarioCreado.emit(msg or "Usuario creado.")

    @QtCore.Slot(str, str)
    def _on_actualizado(self, msg: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.usuarioActualizado.emit(msg or "Usuario actualizado.")
