from __future__ import annotations
from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets
from app.funciones.admin import exportar_csv, aplicar_filtro_movimientos
from app.funciones.admin import validar_nombre_categoria
from app.servicios.api import ApiClient
from app.servicios.categorias_service import CategoriasService


class AdminView(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._busy_cursor = False
        self.tabs = QtWidgets.QTabWidget(self)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(self.tabs)

        self._init_tab_categorias()
        self._init_tab_reportes()
        self._init_tab_movimientos()

    def _init_tab_categorias(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        toolbar = QtWidgets.QHBoxLayout()
        self.btn_cat_reload = QtWidgets.QPushButton("Recargar")
        self.btn_cat_new = QtWidgets.QPushButton("Nueva")
        self.btn_cat_del = QtWidgets.QPushButton("Eliminar")
        toolbar.addWidget(self.btn_cat_reload)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.btn_cat_new)
        toolbar.addWidget(self.btn_cat_del)
        toolbar.addStretch(1)

        self.cat_table = QtWidgets.QTableView()
        self.cat_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cat_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.cat_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.cat_table.horizontalHeader().setStretchLastSection(True)
        self.cat_table.verticalHeader().setVisible(False)

        self.cat_status = QtWidgets.QLabel("")

        v.addLayout(toolbar)
        v.addWidget(self.cat_table, 1)
        v.addWidget(self.cat_status)
        self.tabs.addTab(w, "Categorías")

        self.cat_model = QtGui.QStandardItemModel(self)
        self.cat_model.setHorizontalHeaderLabels(["ID", "Categoría"])
        self.cat_table.setModel(self.cat_model)
        self.cat_table.setColumnWidth(1, 260)

        self._cat_svc = CategoriasService(ApiClient(), self)
        self._cat_svc.busy.connect(self._set_busy)
        self._cat_svc.error.connect(self._cat_on_error)
        self._cat_svc.categoriasCargadas.connect(self._cat_on_ok)
        self._cat_svc.categoriaCreada.connect(self._cat_on_created)
        self._cat_svc.categoriaEliminada.connect(self._cat_on_deleted)

        self.btn_cat_reload.clicked.connect(self._cat_load)
        self.btn_cat_new.clicked.connect(self._cat_new)
        self.btn_cat_del.setEnabled(False)
        sel_model = self.cat_table.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(
                lambda *_: self.btn_cat_del.setEnabled(self.cat_table.currentIndex().isValid())
        )
        self.btn_cat_del.clicked.connect(self._cat_delete)        
        self.cat_table.doubleClicked.connect(lambda _=None: None)

        self._cat_load()

    def _cat_load(self):
        self.cat_status.setText("Cargando categorías…")
        self._cat_svc.cargar_categorias()

    def _cat_new(self):
        dlg = CategoryCreateDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            nombre = dlg.value().strip()
            err = validar_nombre_categoria(nombre)
            if err:
                QtWidgets.QMessageBox.warning(self, "Validación", err)
                return
            self.cat_status.setText("Creando categoría…")
            self._cat_svc.crear_categoria(nombre)

    def _cat_on_created(self, msg: str):
        QtWidgets.QMessageBox.information(self, "Categorías", msg or "Categoría creada correctamente.")
        self._cat_load()

    def _cat_on_error(self, msg: str):
        self.cat_status.setText(f"Error al operar con categorías: {msg}")
        QtWidgets.QMessageBox.warning(self, "API", f"Ocurrió un error:\n{msg}")

    def _cat_on_ok(self, items: list[dict]):
        self.cat_model.removeRows(0, self.cat_model.rowCount())
        for it in items:
            cid = str(it.get("id", ""))
            name = str(it.get("categoria", ""))
            self.cat_model.appendRow([QtGui.QStandardItem(cid), QtGui.QStandardItem(name)])
        n = self.cat_model.rowCount()
        self.cat_status.setText(f"{n} categoría(s) cargada(s)" if n else "Sin categorías desde la API")

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

        self._generar_reporte()

    def _generar_reporte(self):
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
        exportar_csv(self.rep_model, path)
        QtWidgets.QMessageBox.information(self, "Exportar", "Archivo CSV exportado correctamente.")

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
        aplicar_filtro_movimientos(self.mov_table, self.mov_model, self.mov_filter.text())

    def _set_busy(self, busy: bool):
        if busy and not getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._busy_cursor = True
        elif not busy and getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.restoreOverrideCursor()
            self._busy_cursor = False

    def _cat_delete(self):
        idx = self.cat_table.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "Eliminar", "Selecciona una categoría de la tabla.")
            return
        r = idx.row()
        try:
            cat_id = int(self.cat_model.item(r, 0).text() or "0")
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Eliminar", "ID de categoría inválido.")
            return
        if cat_id <= 0:
            QtWidgets.QMessageBox.warning(self, "Eliminar", "ID de categoría inválido.")
            return

        if QtWidgets.QMessageBox.question(self, "Eliminar categoría",
                                        f"¿Eliminar la categoría ID {cat_id}?") != QtWidgets.QMessageBox.Yes:
            return

        self.cat_status.setText("Eliminando categoría…")
        self._cat_svc.eliminar_categoria(cat_id)

    def _cat_on_deleted(self, msg: str):
        QtWidgets.QMessageBox.information(self, "Categorías", msg or "Categoría eliminada.")
        self._cat_load()


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


class CategoryCreateDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Nueva categoría")
        self.setModal(True)
        self.setMinimumWidth(360)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Nombre de la categoría (p. ej. audio)")
        form.addRow("Categoría:", self.name)
        lay.addLayout(form)

        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("errorLabel")
        self.error.setVisible(False)
        lay.addWidget(self.error)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _on_accept(self):
        if not self.name.text().strip():
            self.error.setText("La categoría es obligatoria.")
            self.error.setVisible(True)
            return
        self.accept()

    def value(self) -> str:
        return self.name.text()

