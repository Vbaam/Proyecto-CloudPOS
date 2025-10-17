from __future__ import annotations
import csv
from PySide6 import QtCore, QtGui, QtWidgets
from typing import Any, Optional

def exportar_csv(model: QtGui.QStandardItemModel, path: str):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        headers = [model.headerData(i, QtCore.Qt.Horizontal) for i in range(model.columnCount())]
        w.writerow(headers)
        for r in range(model.rowCount()):
            row = [
                model.item(r, c).text().replace("$", "").replace(".", "")
                if c >= 2 else model.item(r, c).text()
                for c in range(model.columnCount())
            ]
            w.writerow(row)

def aplicar_filtro_movimientos(table: QtWidgets.QTableView, model: QtGui.QStandardItemModel, texto: str):
    text = (texto or "").lower().strip()
    for r in range(model.rowCount()):
        prod = model.item(r, 2).text().lower()
        table.setRowHidden(r, text not in prod)

def validar_nombre_categoria(nombre: str) -> Optional[str]:
    n = (nombre or "").strip()
    if not n:
        return "La categoría es obligatoria."
    if len(n) > 80:
        return "La categoría no debe exceder 80 caracteres."
    return None


def construir_payload_crear_categoria(nombre: str) -> dict:
    return {"categoria": (nombre or "").strip()}


def parsear_respuesta_crear_categoria(res: Any) -> str:
    if isinstance(res, str):
        return res or "Categoría creada"
    if isinstance(res, dict):
        return (
            res.get("message")
            or res.get("detail")
            or res.get("categoria")
            or "Categoría creada"
        )
    return "Categoría creada"


def mapear_categorias_response(data: Any) -> list[dict]:
    if isinstance(data, dict):
        items = data.get("categorias", [])
    elif isinstance(data, list):
        items = data
    else:
        items = []
    if not isinstance(items, list):
        raise ValueError("Formato inválido: 'categorias' no es lista")
    return items