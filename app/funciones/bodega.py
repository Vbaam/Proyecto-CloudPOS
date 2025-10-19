from __future__ import annotations
from typing import List, Any
import os
import json
from urllib import request, error

from PySide6 import QtCore, QtGui, QtWidgets
from app.servicios.api import ApiClient

_client = ApiClient()
DEBUG = os.getenv("CLOUDPOS_DEBUG", "0") == "1"


def aplicar_filtro(table: QtWidgets.QTableView,
                   model: QtGui.QStandardItemModel,
                   texto: str,
                   categoria: str) -> None:
    q = (texto or "").strip().lower()
    cat_filter = (categoria or "").strip()
    cat_lower = cat_filter.lower()
    for r in range(model.rowCount()):
        codigo = (model.item(r, 0).text() if model.item(r, 0) else "").lower()
        nombre = (model.item(r, 1).text() if model.item(r, 1) else "").lower()
        cat_row = (model.item(r, 2).text() if model.item(r, 2) else "").lower()
        match_text = (q in codigo) or (q in nombre) or (q in cat_row) if q else True
        match_cat = True if (not cat_filter or cat_filter == "Todas") else (cat_row == cat_lower)
        table.setRowHidden(r, not (match_text and match_cat))


def colorizar_stock(model: QtGui.QStandardItemModel) -> None:
    for r in range(model.rowCount()):
        try:
            stock = int(model.item(r, 4).text())
        except Exception:
            stock = 0
        item_stock = model.item(r, 4)
        if not item_stock:
            continue
        if stock <= 0:
            item_stock.setBackground(QtGui.QBrush(QtGui.QColor("#e74c3c")))
            item_stock.setForeground(QtGui.QBrush(QtGui.QColor("#ffffff")))
        elif stock <= 5:
            item_stock.setBackground(QtGui.QBrush(QtGui.QColor("#f39c12")))
            item_stock.setForeground(QtGui.QBrush(QtGui.QColor("#000000")))
        else:
            item_stock.setBackground(QtGui.QBrush())
            item_stock.setForeground(QtGui.QBrush())


def _parse_error_body(raw: bytes) -> dict:
    text = raw.decode("utf-8", errors="ignore")
    try:
        return json.loads(text)
    except Exception:
        return {"detail": text or "HTTP error"}


def _put_json(path: str, payload: dict) -> Any:
    base = _client.base_url.rstrip("/")
    url = f"{base}/{path.replace('//','/').lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"accept": "application/json", "content-type": "application/json"},
        method="PUT",
    )
    try:
        with request.urlopen(req, timeout=_client.timeout) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(text)
            except Exception:
                return {"detail": text or "OK", "status": getattr(resp, "status", 200)}
    except error.HTTPError as e:
        body = e.read() or b""
        parsed = _parse_error_body(body) or {}
        return {"error": True, "status": e.code, **parsed}
    except error.URLError as e:
        return {"error": True, "status": 0, "detail": str(getattr(e, "reason", "Error de red"))}


def _extract_list(data: Any, kind: str) -> List[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in (kind, "items", "data", "results"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def listar_productos() -> List[dict]:
    """
    Intenta múltiples rutas conocidas y formatos de respuesta.
    """
    paths = ["/muestra_productos", "/productos", "/producto", "/producto/"]
    last_err: Exception | None = None
    for p in paths:
        try:
            if DEBUG:
                print(f"[bodega.listar_productos] GET {p}")
            data = _client.get_json(p)
            items = _extract_list(data, "productos")
            if items:
                if DEBUG:
                    print(f"[bodega.listar_productos] OK {p} -> {len(items)} items")
                return items
            if isinstance(data, list) and len(data) == 0:
                if DEBUG:
                    print(f"[bodega.listar_productos] OK {p} -> lista vacía")
                return []
            if DEBUG:
                print(f"[bodega.listar_productos] Formato no reconocido en {p}: {type(data)} {data}")
        except Exception as e:
            if DEBUG:
                print(f"[bodega.listar_productos] ERROR {p}: {e}")
            last_err = e
            continue
    if last_err:
        raise RuntimeError(str(last_err))
    raise RuntimeError("No se pudo obtener productos (rutas probadas: " + ", ".join(paths) + ")")


def listar_categorias() -> List[dict]:
    paths = ["/categorias", "/categoria", "/categoria/"]
    last_err: Exception | None = None
    for p in paths:
        try:
            if DEBUG:
                print(f"[bodega.listar_categorias] GET {p}")
            data = _client.get_json(p)
            items = _extract_list(data, "categorias")
            if items:
                if DEBUG:
                    print(f"[bodega.listar_categorias] OK {p} -> {len(items)} items")
                return items
            if isinstance(data, list) and len(data) == 0:
                if DEBUG:
                    print(f"[bodega.listar_categorias] OK {p} -> lista vacía")
                return []
            if DEBUG:
                print(f"[bodega.listar_categorias] Formato no reconocido en {p}: {type(data)} {data}")
        except Exception as e:
            if DEBUG:
                print(f"[bodega.listar_categorias] ERROR {p}: {e}")
            last_err = e
            continue
    if last_err:
        raise RuntimeError(str(last_err))
    raise RuntimeError("No se pudo obtener categorías (rutas probadas: " + ", ".join(paths) + ")")


def crear_producto(nombre: str, categoria_id: int, precio: int, cantidad: int) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise RuntimeError("El nombre es obligatorio.")
    if int(categoria_id) <= 0:
        raise RuntimeError("Selecciona una categoría válida.")
    if int(precio) <= 0:
        raise RuntimeError("El precio debe ser mayor a 0.")
    if int(cantidad) < 0:
        raise RuntimeError("La cantidad no puede ser negativa.")

    payload = {
        "nombre": nombre,
        "categoria_id": int(categoria_id),
        "precio": int(precio),
        "cantidad": int(cantidad),
    }
    if DEBUG:
        print(f"[bodega.crear_producto] POST /producto/ payload={payload}")
    res = _client.post_json("/producto/", payload)

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
                print(f"[bodega.crear_producto] ERROR: {status} -> {err_msg}")
            raise RuntimeError(err_msg)

    if isinstance(res, str):
        return res or "Producto creado"
    if isinstance(res, dict):
        return res.get("message") or res.get("detail") or "Producto creado"
    return "Producto creado"


def actualizar_producto(producto_id: int, precio: int, cantidad: int) -> str:
    if int(producto_id) <= 0:
        raise RuntimeError("Producto inválido.")
    if int(precio) <= 0:
        raise RuntimeError("El precio debe ser mayor a 0.")
    if int(cantidad) < 0:
        raise RuntimeError("La cantidad no puede ser negativa.")

    payload = {"precio": int(precio), "cantidad": int(cantidad)}
    if DEBUG:
        print(f"[bodega.actualizar_producto] PUT /producto/{int(producto_id)}/ payload={payload}")
    res = _put_json(f"/producto/{int(producto_id)}/", payload)

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
                print(f"[bodega.actualizar_producto] ERROR: {status} -> {err_msg}")
            raise RuntimeError(err_msg)

    if isinstance(res, str):
        return res or "Producto actualizado"
    if isinstance(res, dict):
        return res.get("message") or res.get("detail") or "Producto actualizado"
    return "Producto actualizado"


def actualizar_categoria(producto_id: int, categoria_id: int) -> str:
    if int(producto_id) <= 0:
        raise RuntimeError("Producto inválido.")
    if int(categoria_id) <= 0:
        raise RuntimeError("Selecciona una categoría válida.")

    payload = {"categoria_id": int(categoria_id)}
    if DEBUG:
        print(f"[bodega.actualizar_categoria] PUT /producto/{int(producto_id)}/categoria payload={payload}")
    res = _put_json(f"/producto/{int(producto_id)}/categoria", payload)

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
                print(f"[bodega.actualizar_categoria] ERROR: {status} -> {err_msg}")
            raise RuntimeError(err_msg)

    if isinstance(res, str):
        return res or "Categoría actualizada"
    if isinstance(res, dict):
        return res.get("message") or res.get("detail") or "Categoría actualizada"
    return "Categoría actualizada"