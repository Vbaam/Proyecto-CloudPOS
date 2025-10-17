from typing import List
from PySide6 import QtCore
from app.servicios.api import ApiClient
from app.funciones.admin import (
    validar_nombre_categoria,
    construir_payload_crear_categoria,
    parsear_respuesta_crear_categoria,
    mapear_categorias_response,
)
import os

DEBUG = os.getenv("CLOUDPOS_DEBUG", "0") == "1"


class _CategoriasWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)

    def __init__(self, client: ApiClient):
        super().__init__()
        self.client = client

    @QtCore.Slot()
    def run(self):
        try:
            data = self.client.get_json("/categorias")
            items = mapear_categorias_response(data)
            if DEBUG:
                print(f"[CategoriasService] OK, recibidas: {len(items)}")
            self.finished.emit(items, "")
        except Exception as e:
            if DEBUG:
                print(f"[CategoriasService] ERROR: {e!r}")
            self.finished.emit([], str(e))


class _CrearCategoriaWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str)  # (mensaje, error)

    def __init__(self, client: ApiClient, nombre: str):
        super().__init__()
        self.client = client
        self.nombre = nombre

    @QtCore.Slot()
    def run(self):
        try:
            err = validar_nombre_categoria(self.nombre)
            if err:
                self.finished.emit("", err)
                return
            payload = construir_payload_crear_categoria(self.nombre)
            res = self.client.post_json("/categorias", payload)
            msg = parsear_respuesta_crear_categoria(res)
            if DEBUG:
                print(f"[CategoriasService] POST /categorias OK -> {msg!r}")
            self.finished.emit(msg, "")
        except Exception as e:
            if DEBUG:
                print(f"[CategoriasService] POST /categorias ERROR: {e!r}")
            self.finished.emit("", str(e))


class CategoriasService(QtCore.QObject):
    categoriasCargadas = QtCore.Signal(list)
    categoriaCreada = QtCore.Signal(str)
    error = QtCore.Signal(str)
    busy = QtCore.Signal(bool)

    def __init__(self, client: ApiClient | None = None, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self.client = client or ApiClient()
        self._thread: QtCore.QThread | None = None
        self._worker: QtCore.QObject | None = None

    def _start_thread(self, worker: QtCore.QObject):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[CategoriasService] operación ya en curso; se omite")
            return False
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        return True

    @QtCore.Slot()
    def _clear_refs(self):
        self._thread = None
        self._worker = None
        if DEBUG:
            print("[CategoriasService] hilo finalizado; refs liberadas")

    def cargar_categorias(self):
        worker = _CategoriasWorker(self.client)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_list_finished)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    @QtCore.Slot(list, str)
    def _on_list_finished(self, items: List[dict], err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.categoriasCargadas.emit(items)

    def crear_categoria(self, nombre: str):
        worker = _CrearCategoriaWorker(self.client, nombre)
        if not self._start_thread(worker):
            return
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._on_create_finished)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.start()

    @QtCore.Slot(str, str)
    def _on_create_finished(self, mensaje: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.categoriaCreada.emit(mensaje)