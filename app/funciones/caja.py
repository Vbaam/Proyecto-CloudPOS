from PySide6 import QtGui
from datetime import datetime
import json

def fmt_money(v: int) -> str:
    return f"${v:,}".replace(",", ".")

def parse_money(s: str) -> int:
    return int(s.replace("$", "").replace(".", "").strip())

def total_carrito(model: QtGui.QStandardItemModel) -> int:
    total = 0
    for r in range(model.rowCount()):
        total += parse_money(model.item(r, 5).text())
    return total

def generate_sale_json(model: QtGui.QStandardItemModel) -> str:
    items = []
    total = 0
    for r in range(model.rowCount()):
        pid_item = model.item(r, 0)
        producto_item = model.item(r, 1)
        precio_item = model.item(r, 2)
        precio_con_iva_item = model.item(r, 3)
        cantidad_item = model.item(r, 4)
        subtotal_item = model.item(r, 5)

        pid = pid_item.text() if pid_item is not None else ""
        producto = producto_item.text() if producto_item is not None else ""
        precio = parse_money(precio_item.text()) if precio_item is not None else 0
        precio_con_iva = parse_money(precio_con_iva_item.text()) if precio_con_iva_item is not None else 0
        cantidad = int(cantidad_item.text()) if cantidad_item is not None and cantidad_item.text().isdigit() else 0
        subtotal = parse_money(subtotal_item.text()) if subtotal_item is not None else 0

        total += subtotal

        items.append({
            "id": pid,
            "producto": producto,
            "precio": precio,
            "precio_con_iva": precio_con_iva,
            "cantidad": cantidad,
            "subtotal": subtotal,
        })

    now = datetime.now()
    fecha = now.date().isoformat()  # YYYY-MM-DD
    hora = now.time().isoformat(timespec="seconds")  # HH:MM:SS

    payload = {
        "fecha": fecha,
        "hora": hora,
        "total": total,
        "items": items,
    }

    try:
        json_str = json.dumps(payload, ensure_ascii=False)
    except Exception:
        json_str = json.dumps(payload, ensure_ascii=False, default=str)
    return json_str