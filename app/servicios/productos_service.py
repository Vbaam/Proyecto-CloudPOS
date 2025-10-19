from __future__ import annotations
from typing import List, Any, Optional
from PySide6 import QtCore
from app.servicios.api import ApiClient
import os

DEBUG = os.getenv("CLOUDPOS_DEBUG", "0") == "1"


def _parse_product_response(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("productos", [])
        return items if isinstance(items, list) else []
    return []


class _ProductosWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)

    def __init__(self, client: ApiClient):
        super().__init__()
        self.client = client

    @QtCore.Slot()
    def run(self):
        try:
            data = self.client.get_json("/muestra_productos")
            items = _parse_product_response(data)
            if DEBUG:
                print(f"[ProductosService] OK: {len(items)} productos")
            self.finished.emit(items, "")
        except Exception as e:
            if DEBUG:
                print(f"[ProductosService] ERROR: {e!r}")
            self.finished.emit([], str(e))


class _CrearProductoWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str)  # (mensaje, error)

    def __init__(self, client: ApiClient, nombre: str, categoria_id: int, precio: int, cantidad: int):
        super().__init__()
        self.client = client
        self.nombre = (nombre or "").strip()
        self.categoria_id = int(categoria_id)
        self.precio = int(precio)
        self.cantidad = int(cantidad)

    @QtCore.Slot()
    def run(self):
        try:
            if not self.nombre:
                self.finished.emit("", "El nombre es obligatorio.")
                return
            if self.categoria_id <= 0:
                self.finished.emit("", "Selecciona una categoría válida.")
                return
            if self.precio <= 0:
                self.finished.emit("", "El precio debe ser mayor a 0.")
                return
            if self.cantidad < 0:
                self.finished.emit("", "La cantidad no puede ser negativa.")
                return

            payload = {
                "nombre": self.nombre,
                "categoria_id": self.categoria_id,
                "precio": self.precio,
                "cantidad": self.cantidad,
            }
            res = self.client.post_json("/producto/", payload)

            if isinstance(res, dict):
                status = int(res.get("status", 200))
                is_error = bool(res.get("error")) or status >= 400
                if is_error:
                    err_msg = (
                        (res.get("detail") if isinstance(res.get("detail"), str) else None)
                        or res.get("message")
                        or f"Error HTTP {status}"
                    )
                    if DEBUG:
                        print(f"[ProductosService] CREATE ERROR: {status} -> {err_msg!r}")
                    self.finished.emit("", err_msg)
                    return

            if isinstance(res, str):
                msg = res or "Producto creado"
            elif isinstance(res, dict):
                msg = res.get("message") or res.get("detail") or "Producto creado"
            else:
                msg = "Producto creado"

            if DEBUG:
                print(f"[ProductosService] POST /producto/ OK -> {msg!r}")
            self.finished.emit(msg, "")
        except Exception as e:
            if DEBUG:
                print(f"[ProductosService] POST /producto/ ERROR: {e!r}")
            self.finished.emit("", str(e))


class _ActualizarProductoWorker(QtCore.QObject):
    finished = QtCore.Signal(int, str, str)  # (producto_id, mensaje, error)

    def __init__(self, client: ApiClient, producto_id: int, precio: int, cantidad: int):
        super().__init__()
        self.client = client
        self.producto_id = int(producto_id)
        self.precio = int(precio)
        self.cantidad = int(cantidad)

    @QtCore.Slot()
    def run(self):
        try:
            if self.producto_id <= 0:
                self.finished.emit(self.producto_id, "", "Producto inválido.")
                return
            if self.precio <= 0:
                self.finished.emit(self.producto_id, "", "El precio debe ser mayor a 0.")
                return
            if self.cantidad < 0:
                self.finished.emit(self.producto_id, "", "La cantidad no puede ser negativa.")
                return

            res = self.client.put_json(f"/producto/{self.producto_id}/", {"precio": self.precio, "cantidad": self.cantidad})
            if isinstance(res, dict):
                status = int(res.get("status", 200))
                is_error = bool(res.get("error")) or status >= 400
                if is_error:
                    err_msg = (
                        (res.get("detail") if isinstance(res.get("detail"), str) else None)
                        or res.get("message")
                        or f"Error HTTP {status}"
                    )
                    if DEBUG:
                        print(f"[ProductosService] PUT producto ERROR: {status} -> {err_msg!r}")
                    self.finished.emit(self.producto_id, "", err_msg)
                    return

            msg = "Producto actualizado"
            if isinstance(res, str):
                msg = res or msg
            elif isinstance(res, dict):
                msg = res.get("message") or res.get("detail") or msg
            if DEBUG:
                print(f"[ProductosService] PUT /producto/{self.producto_id}/ OK -> {msg!r}")
            self.finished.emit(self.producto_id, msg, "")
        except Exception as e:
            if DEBUG:
                print(f"[ProductosService] PUT producto ERROR: {e!r}")
            self.finished.emit(self.producto_id, "", str(e))


class _ActualizarCategoriaWorker(QtCore.QObject):
    finished = QtCore.Signal(int, str, str)  # (producto_id, mensaje, error)

    def __init__(self, client: ApiClient, producto_id: int, categoria_id: int):
        super().__init__()
        self.client = client
        self.producto_id = int(producto_id)
        self.categoria_id = int(categoria_id)

    @QtCore.Slot()
    def run(self):
        try:
            if self.producto_id <= 0:
                self.finished.emit(self.producto_id, "", "Producto inválido.")
                return
            if self.categoria_id <= 0:
                self.finished.emit(self.producto_id, "", "Selecciona una categoría válida.")
                return

            res = self.client.put_json(f"/producto/{self.producto_id}/categoria", {"categoria_id": self.categoria_id})
            if isinstance(res, dict):
                status = int(res.get("status", 200))
                is_error = bool(res.get("error")) or status >= 400
                if is_error:
                    err_msg = (
                        (res.get("detail") if isinstance(res.get("detail"), str) else None)
                        or res.get("message")
                        or f"Error HTTP {status}"
                    )
                    if DEBUG:
                        print(f"[ProductosService] PUT categoria ERROR: {status} -> {err_msg!r}")
                    self.finished.emit(self.producto_id, "", err_msg)
                    return

            msg = "Categoría actualizada"
            if isinstance(res, str):
                msg = res or msg
            elif isinstance(res, dict):
                msg = res.get("message") or res.get("detail") or msg
            if DEBUG:
                print(f"[ProductosService] PUT /producto/{self.producto_id}/categoria OK -> {msg!r}")
            self.finished.emit(self.producto_id, msg, "")
        except Exception as e:
            if DEBUG:
                print(f"[ProductosService] PUT categoria ERROR: {e!r}")
            self.finished.emit(self.producto_id, "", str(e))


class ProductosService(QtCore.QObject):
    productosCargados = QtCore.Signal(list)
    productoCreado = QtCore.Signal(str)
    productoActualizado = QtCore.Signal(int, str)      # (producto_id, mensaje)
    categoriaActualizada = QtCore.Signal(int, str)     # (producto_id, mensaje)
    error = QtCore.Signal(str)
    busy = QtCore.Signal(bool)

    def __init__(self, client: Optional[ApiClient] = None, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.client = client or ApiClient()
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[QtCore.QObject] = None

    def cargar_productos(self):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[ProductosService] carga en curso; se omite")
            return
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = _ProductosWorker(self.client)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_list_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        self._thread.start()

    def crear_producto(self, nombre: str, categoria_id: int, precio: int, cantidad: int):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[ProductosService] operación en curso; se omite crear")
            return
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = _CrearProductoWorker(self.client, nombre, categoria_id, precio, cantidad)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_create_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        self._thread.start()

    def actualizar_producto(self, producto_id: int, precio: int, cantidad: int):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[ProductosService] operación en curso; se omite actualizar producto")
            return
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = _ActualizarProductoWorker(self.client, producto_id, precio, cantidad)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_update_product_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        self._thread.start()

    def actualizar_categoria_producto(self, producto_id: int, categoria_id: int):
        if self._thread and self._thread.isRunning():
            if DEBUG:
                print("[ProductosService] operación en curso; se omite actualizar categoría")
            return
        self.busy.emit(True)
        self._thread = QtCore.QThread(self)
        self._worker = _ActualizarCategoriaWorker(self.client, producto_id, categoria_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_update_cat_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        self._thread.start()

    @QtCore.Slot()
    def _clear_refs(self):
        self._thread = None
        self._worker = None

    @QtCore.Slot(list, str)
    def _on_list_finished(self, items: List[dict], err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.productosCargados.emit(items)

    @QtCore.Slot(str, str)
    def _on_create_finished(self, mensaje: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.productoCreado.emit(mensaje)

    @QtCore.Slot(int, str, str)
    def _on_update_product_finished(self, producto_id: int, mensaje: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.productoActualizado.emit(producto_id, mensaje)

    @QtCore.Slot(int, str, str)
    def _on_update_cat_finished(self, producto_id: int, mensaje: str, err: str):
        self.busy.emit(False)
        if err:
            self.error.emit(err)
        else:
            self.categoriaActualizada.emit(producto_id, mensaje)