from PySide6 import QtGui

def fmt_money(v: int) -> str:
    return f"${v:,}".replace(",", ".")

def parse_money(s: str) -> int:
    return int(s.replace("$", "").replace(".", "").strip())

def total_carrito(model: QtGui.QStandardItemModel) -> int:
    total = 0
    for r in range(model.rowCount()):
        total += parse_money(model.item(r, 4).text())
    return total