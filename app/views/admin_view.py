from __future__ import annotations
import csv
from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets


class AdminView(QtWidgets.QWidget):
    """
    Vista de Administración — SOLO UI.
    Sin IVA en reportes: columnas = Periodo, Transacciones, Total.
    Inicia sin datos en todas las pestañas.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.tabs = QtWidgets.QTabWidget(self)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(self.tabs)

        self._init_tab_categorias()
        self._init_tab_reportes()
        self._init_tab_movimientos()

    # ---------------- Categorías ----------------
    def _init_tab_categorias(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        toolbar = QtWidgets.QHBoxLayout()
        self.btn_cat_new = QtWidgets.QPushButton("Nueva")
        self.btn_cat_edit = QtWidgets.QPushButton("Editar")
        self.btn_cat_del = QtWidgets.QPushButton("Eliminar")
        toolbar.addWidget(self.btn_cat_new)
        toolbar.addWidget(self.btn_cat_edit)
        toolbar.addWidget(self.btn_cat_del)
        toolbar.addStretch(1)

        self.cat_table = QtWidgets.QTableView()
        self.cat_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cat_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.cat_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.cat_table.horizontalHeader().setStretchLastSection(True)
        self.cat_table.verticalHeader().setVisible(False)

        v.addLayout(toolbar)
        v.addWidget(self.cat_table, 1)
        self.tabs.addTab(w, "Categorías")

        self.cat_model = QtGui.QStandardItemModel(self)
        self.cat_model.setHorizontalHeaderLabels(["Código", "Nombre", "Descripción"])
        self.cat_table.setModel(self.cat_model)

        self.btn_cat_new.clicked.connect(self._cat_new)
        self.btn_cat_edit.clicked.connect(self._cat_edit)
        self.btn_cat_del.clicked.connect(self._cat_del)
        self.cat_table.doubleClicked.connect(self._cat_edit)

    def _cat_append_row(self, row: Tuple[str, str, str]):
        self.cat_model.appendRow([QtGui.QStandardItem(row[0]), QtGui.QStandardItem(row[1]), QtGui.QStandardItem(row[2])])

    def _cat_find_code(self, code: str) -> Optional[int]:
        for r in range(self.cat_model.rowCount()):
            if self.cat_model.item(r, 0).text() == code:
                return r
        return None

    def _cat_new(self):
        dlg = CategoriaDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            code, name, desc = dlg.values()
            if self._cat_find_code(code) is not None:
                QtWidgets.QMessageBox.warning(self, "Código duplicado", "Ya existe una categoría con ese código.")
                return
            self._cat_append_row((code, name, desc))

    def _cat_edit(self):
        idx = self.cat_table.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        code = self.cat_model.item(r, 0).text()
        name = self.cat_model.item(r, 1).text()
        desc = self.cat_model.item(r, 2).text()
        dlg = CategoriaDialog(self, (code, name, desc), editing=True)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            ncode, nname, ndesc = dlg.values()
            if ncode != code and self._cat_find_code(ncode) is not None:
                QtWidgets.QMessageBox.warning(self, "Código duplicado", "Ya existe una categoría con ese código.")
                return
            self.cat_model.item(r, 0).setText(ncode)
            self.cat_model.item(r, 1).setText(nname)
            self.cat_model.item(r, 2).setText(ndesc)

    def _cat_del(self):
        idx = self.cat_table.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        if QtWidgets.QMessageBox.question(self, "Eliminar", "¿Eliminar categoría?") == QtWidgets.QMessageBox.Yes:
            self.cat_model.removeRow(r)

    # ---------------- Reportes (sin IVA) ----------------
    def _init_tab_reportes(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        top = QtWidgets.QHBoxLayout()
        self.periodo = QtWidgets.QComboBox()
        self.periodo.addItems(["Diario", "Semanal", "Mensual"])
        self.desde = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.hasta = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        for de in (self.desde, self.hasta):
            de.setCalendarPopup(True)
            de.setDisplayFormat("yyyy-MM-dd")
        self.btn_generar = QtWidgets.QPushButton("Generar")
        self.btn_export = QtWidgets.QPushButton("Exportar CSV")
        top.addWidget(QtWidgets.QLabel("Periodo:"))
        top.addWidget(self.periodo)
        top.addSpacing(12)
        top.addWidget(QtWidgets.QLabel("Desde:"))
        top.addWidget(self.desde)
        top.addWidget(QtWidgets.QLabel("Hasta:"))
        top.addWidget(self.hasta)
        top.addStretch(1)
        top.addWidget(self.btn_generar)
        top.addWidget(self.btn_export)

        self.rep_table = QtWidgets.QTableView()
        self.rep_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rep_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rep_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.rep_table.horizontalHeader().setStretchLastSection(True)
        self.rep_table.verticalHeader().setVisible(False)

        v.addLayout(top)
        v.addWidget(self.rep_table, 1)
        self.tabs.addTab(w, "Reportes")

        self.rep_model = QtGui.QStandardItemModel(self)
        self.rep_model.setHorizontalHeaderLabels(["Periodo", "Transacciones", "Total"])
        self.rep_table.setModel(self.rep_model)

        self.btn_generar.clicked.connect(self._generar_reporte)
        self.btn_export.clicked.connect(self._exportar_csv)

        self._generar_reporte()  # limpia

    def _generar_reporte(self):
        # Sin datos hasta conectar backend
        self.rep_model.removeRows(0, self.rep_model.rowCount())

    def _money_item(self, v: int) -> QtGui.QStandardItem:
        it = QtGui.QStandardItem(f"${v:,}".replace(",", "."))
        it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return it

    def _exportar_csv(self):
        if self.rep_model.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportar CSV", "reporte.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            headers = [self.rep_model.headerData(i, QtCore.Qt.Horizontal) for i in range(self.rep_model.columnCount())]
            w.writerow(headers)
            for r in range(self.rep_model.rowCount()):
                row = [
                    self.rep_model.item(r, c).text().replace("$", "").replace(".", "")
                    if c >= 2 else self.rep_model.item(r, c).text()
                    for c in range(self.rep_model.columnCount())
                ]
                w.writerow(row)
        QtWidgets.QMessageBox.information(self, "Exportar", "Archivo CSV exportado correctamente.")

    # ---------------- Movimientos ----------------
    def _init_tab_movimientos(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        top = QtWidgets.QHBoxLayout()
        self.mov_filter = QtWidgets.QLineEdit()
        self.mov_filter.setPlaceholderText("Filtrar por producto...")
        top.addWidget(self.mov_filter)
        v.addLayout(top)

        self.mov_table = QtWidgets.QTableView()
        self.mov_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.mov_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.mov_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.mov_table.horizontalHeader().setStretchLastSection(True)
        self.mov_table.verticalHeader().setVisible(False)

        v.addWidget(self.mov_table, 1)
        self.tabs.addTab(w, "Movimientos")

        self.mov_model = QtGui.QStandardItemModel(self)
        self.mov_model.setHorizontalHeaderLabels(["Fecha", "Usuario", "Producto", "Cambio", "Razón"])
        self.mov_table.setModel(self.mov_model)

        self.mov_filter.textChanged.connect(self._mov_apply_filter)

    def _delta_item(self, delta: int) -> QtGui.QStandardItem:
        s = f"+{delta}" if delta > 0 else str(delta)
        it = QtGui.QStandardItem(s)
        it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        color = "#2e7d32" if delta > 0 else "#d32f2f"
        it.setForeground(QtGui.QBrush(QtGui.QColor(color)))
        return it

    def _mov_apply_filter(self):
        text = self.mov_filter.text().lower().strip()
        for r in range(self.mov_model.rowCount()):
            prod = self.mov_model.item(r, 2).text().lower()
            self.mov_table.setRowHidden(r, text not in prod)


class CategoriaDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 data: Optional[Tuple[str, str, str]] = None,
                 editing: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Editar categoría" if editing else "Nueva categoría")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.code = QtWidgets.QLineEdit()
        self.name = QtWidgets.QLineEdit()
        self.desc = QtWidgets.QLineEdit()

        form.addRow("Código:", self.code)
        form.addRow("Nombre:", self.name)
        form.addRow("Descripción:", self.desc)
        lay.addLayout(form)

        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("errorLabel")
        self.error.setVisible(False)
        lay.addWidget(self.error)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        if data:
            code, name, desc = data
            self.code.setText(code)
            self.name.setText(name)
            self.desc.setText(desc)

    def _on_accept(self):
        code = self.code.text().strip()
        name = self.name.text().strip()
        if not code:
            return self._err("El código es obligatorio.")
        if not name:
            return self._err("El nombre es obligatorio.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[str, str, str]:
        return (self.code.text().strip(), self.name.text().strip(), self.desc.text().strip())