from PySide6 import QtCore, QtWidgets, QtGui

def aplicar_filtro(table: QtWidgets.QTableView, model: QtGui.QStandardItemModel, texto: str, categoria: str):
    text = (texto or "").lower().strip()
    for r in range(model.rowCount()):
        code = model.item(r, 0).text().lower()
        name = model.item(r, 1).text().lower()
        cat_row = model.item(r, 2).text()
        match = (text in code or text in name) and (categoria == "Todas" or categoria == cat_row)
        table.setRowHidden(r, not match)

def colorizar_stock(model: QtGui.QStandardItemModel):
    for r in range(model.rowCount()):
        stock = int(model.item(r, 4).text())
        bg = None
        if stock == 0:
            bg = QtGui.QBrush(QtGui.QColor("#ffebee"))
        elif stock <= 5:
            bg = QtGui.QBrush(QtGui.QColor("#fff8e1"))
        for c in range(model.columnCount()):
            model.item(r, c).setBackground(bg if bg else QtGui.QBrush())