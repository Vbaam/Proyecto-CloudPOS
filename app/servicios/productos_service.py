from typing import List
from PySide6 import QtCore
from app.servicios.api import ApiClient
import os

DEBUG = os.getenv("CLOUDPOS_DEBUG", "0") == "1"


class _ProductosWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)

    def __init__(self, client: ApiClient):
        super().__init__()
        self.client = client

    @QtCore.Slot()
    def run(self):
        try:
            data = self.client.get_json("/productos")
            if not isinstance(data, list):
                raise ValueError("Respuesta inesperada al listar productos")
            if DEBUG:
                print(f"[ProductosService] OK, recibidos: {len(data)}")
            self.finished.emit(data, "")
        except Exception as e:
            if DEBUG:
                print(f"[ProductosService] ERROR: {e!r}")
            self.finished.emit([], str(e))


class ProductosService(QtCore.QObject):
    productosCargados = QtCore.Signal(list)
    error = QtCore.Signal(str)
    busy = QtCore.Signal(bool)

    def __init__(self, client: ApiClient | None = None, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.client = client or ApiClient()
        self._thread: QtCore.QThread | None = None
        self._worker: _ProductosWorker | None = None

    def cargar_productos(self):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[ProductosService] carga ya en curso; se omite")
            return
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = _ProductosWorker(self.client)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)

        if DEBUG:
            print("[ProductosService] iniciando hilo de carga…")
        self._thread.start()

    @QtCore.Slot()
    def _clear_refs(self):
        if DEBUG:
            print("[ProductosService] hilo finalizado; limpiando refs")
        self._thread = None
        self._worker = None

    @QtCore.Slot(list, str)
    def _on_finished(self, items: List[dict], err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.productosCargados.emit(items)