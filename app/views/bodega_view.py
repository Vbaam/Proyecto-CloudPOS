from typing import Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets


class BodegaView(QtWidgets.QWidget):
    """
    Vista de Bodega — SOLO UI.
    Inicia sin datos: tabla vacía y solo 'Todas' en categorías.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()
        self._load_empty_state()
        self._wire_events()

    # ------------- UI -------------
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Fila de búsqueda
        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por código o nombre (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        self.category = QtWidgets.QComboBox()
        self.category.addItem("Todas")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.category, 0)

        # Toolbar de acciones
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_nuevo = QtWidgets.QPushButton("Nuevo (Ctrl+N)")
        self.btn_editar = QtWidgets.QPushButton("Editar (Enter)")
        self.btn_eliminar = QtWidgets.QPushButton("Eliminar (Supr)")
        self.btn_ajustar = QtWidgets.QPushButton("Ajustar stock (Ctrl+U)")
        toolbar.addWidget(self.btn_nuevo)
        toolbar.addWidget(self.btn_editar)
        toolbar.addWidget(self.btn_eliminar)
        toolbar.addWidget(self.btn_ajustar)
        toolbar.addStretch(1)

        self.table = QtWidgets.QTableView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        root.addLayout(search_row)
        root.addLayout(toolbar)
        root.addWidget(self.table, 1)

        # Modelo
        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Código", "Producto", "Categoría", "Precio", "Stock"])
        self.table.setModel(self.model)
        self.table.setColumnWidth(1, 250)

        # Atajos
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self._nuevo)
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, activated=self._editar)
        QtGui.QShortcut(QtGui.QKeySequence("Enter"), self, activated=self._editar)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._eliminar)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+U"), self, activated=self._ajustar)

    def _load_empty_state(self):
        # Deja la tabla sin filas y el combo de categorías en estado inicial
        if self.model.rowCount() > 0:
            self.model.removeRows(0, self.model.rowCount())

        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Todas")
        self.category.blockSignals(False)

    def _append_row(self, row: Tuple[str, str, str, int, int]):
        items = []
        for i, val in enumerate(row):
            it = QtGui.QStandardItem(str(val))
            if i in (3, 4):
                it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            items.append(it)
        self.model.appendRow(items)
        # Asegura que la categoría quede disponible en el filtro
        cat = row[2]
        if self.category.findText(cat) < 0:
            self.category.addItem(cat)

    def _wire_events(self):
        self.search_edit.textChanged.connect(self._filter_rows)
        self.category.currentIndexChanged.connect(self._filter_rows)
        self.table.doubleClicked.connect(self._editar)
        self.btn_nuevo.clicked.connect(self._nuevo)
        self.btn_editar.clicked.connect(self._editar)
        self.btn_eliminar.clicked.connect(self._eliminar)
        self.btn_ajustar.clicked.connect(self._ajustar)

    # ------------- Filtro -------------
    def _filter_rows(self):
        text = self.search_edit.text().lower().strip()
        cat = self.category.currentText()
        for r in range(self.model.rowCount()):
            code = self.model.item(r, 0).text().lower()
            name = self.model.item(r, 1).text().lower()
            cat_row = self.model.item(r, 2).text()
            match = (text in code or text in name) and (cat == "Todas" or cat == cat_row)
            self.table.setRowHidden(r, not match)

    # ------------- Acciones -------------
    def _nuevo(self):
        dlg = ProductoDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            code, name, cat, price, stock = dlg.values()
            if self._find_row_by_code(code) is not None:
                QtWidgets.QMessageBox.warning(self, "Código duplicado", "Ya existe un producto con ese código.")
                return
            self._append_row((code, name, cat, price, stock))

    def _editar(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        code = self.model.item(r, 0).text()
        name = self.model.item(r, 1).text()
        cat = self.model.item(r, 2).text()
        price = int(self.model.item(r, 3).text())
        stock = int(self.model.item(r, 4).text())
        dlg = ProductoDialog(self, (code, name, cat, price, stock), editing=True)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            ncode, nname, ncat, nprice, nstock = dlg.values()
            if ncode != code and self._find_row_by_code(ncode) is not None:
                QtWidgets.QMessageBox.warning(self, "Código duplicado", "Ya existe un producto con ese código.")
                return
            self.model.item(r, 0).setText(ncode)
            self.model.item(r, 1).setText(nname)
            self.model.item(r, 2).setText(ncat)
            self.model.item(r, 3).setText(str(nprice))
            self.model.item(r, 4).setText(str(nstock))
            if self.category.findText(ncat) < 0:
                self.category.addItem(ncat)

    def _eliminar(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        stock = int(self.model.item(r, 4).text())
        if stock != 0:
            QtWidgets.QMessageBox.warning(self, "Eliminar", "El producto debe tener stock 0 para eliminar (HU03).")
            return
        if QtWidgets.QMessageBox.question(self, "Eliminar", "¿Eliminar producto?") == QtWidgets.QMessageBox.Yes:
            self.model.removeRow(r)

    def _ajustar(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        code = self.model.item(r, 0).text()
        name = self.model.item(r, 1).text()
        current_stock = int(self.model.item(r, 4).text())

        dlg = AjusteStockDialog(self, code, name, current_stock)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            mode, qty, reason = dlg.values()
            if mode == "sum":
                new_stock = current_stock + qty
            else:
                if qty > current_stock:
                    QtWidgets.QMessageBox.warning(self, "Stock insuficiente", "No puedes dejar el stock negativo.")
                    return
                new_stock = current_stock - qty
            self.model.item(r, 4).setText(str(new_stock))
            # Aquí registrarías el movimiento con 'reason' cuando haya backend

    # ------------- Utilidades -------------
    def _find_row_by_code(self, code: str) -> Optional[int]:
        for r in range(self.model.rowCount()):
            if self.model.item(r, 0).text() == code:
                return r
        return None


class ProductoDialog(QtWidgets.QDialog):
    """
    Diálogo de producto: Crear/Editar.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None,
                 data: Optional[Tuple[str, str, str, int, int]] = None,
                 editing: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Editar producto" if editing else "Nuevo producto")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.code = QtWidgets.QLineEdit()
        self.name = QtWidgets.QLineEdit()
        self.cat = QtWidgets.QComboBox()
        self.cat.setEditable(True)
        self.cat.setInsertPolicy(QtWidgets.QComboBox.InsertAtTop)
        # Sugerencias (puedes dejarlo vacío si prefieres)
        self.cat.addItems(["Alimentos", "Aseo", "Bebidas"])

        self.price = QtWidgets.QSpinBox()
        self.price.setRange(0, 10_000_000)
        self.price.setSingleStep(100)
        self.price.setSuffix(" $")
        self.price.setAlignment(QtCore.Qt.AlignRight)

        self.stock = QtWidgets.QSpinBox()
        self.stock.setRange(0, 1_000_000)
        self.stock.setAlignment(QtCore.Qt.AlignRight)

        form.addRow("Código:", self.code)
        form.addRow("Nombre:", self.name)
        form.addRow("Categoría:", self.cat)
        form.addRow("Precio:", self.price)
        form.addRow("Stock:", self.stock)
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
            code, name, cat, price, stock = data
            self.code.setText(code)
            self.name.setText(name)
            if self.cat.findText(cat) < 0:
                self.cat.addItem(cat)
            self.cat.setCurrentText(cat)
            self.price.setValue(price)
            self.stock.setValue(stock)

    def _on_accept(self):
        code = self.code.text().strip()
        name = self.name.text().strip()
        cat = self.cat.currentText().strip()
        price = int(self.price.value())
        stock = int(self.stock.value())

        if not code:
            return self._err("El código es obligatorio.")
        if not name:
            return self._err("El nombre es obligatorio.")
        if not cat:
            return self._err("La categoría es obligatoria.")
        if price <= 0:
            return self._err("El precio debe ser mayor a 0.")
        if stock < 0:
            return self._err("El stock no puede ser negativo.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[str, str, str, int, int]:
        return (
            self.code.text().strip(),
            self.name.text().strip(),
            self.cat.currentText().strip(),
            int(self.price.value()),
            int(self.stock.value()),
        )


class AjusteStockDialog(QtWidgets.QDialog):
    """
    Ajuste de stock: sumar o restar unidades con una razón.
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget], code: str, name: str, current_stock: int):
        super().__init__(parent)
        self.setWindowTitle("Ajustar stock")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(f"Producto: <b>{name}</b> (Código: {code}) — Stock actual: <b>{current_stock}</b>")
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.mode_sum = QtWidgets.QRadioButton("Aumentar")
        self.mode_res = QtWidgets.QRadioButton("Disminuir")
        self.mode_sum.setChecked(True)
        mode_row = QtWidgets.QHBoxLayout()
        mode_row.addWidget(self.mode_sum)
        mode_row.addWidget(self.mode_res)
        mode_wrap = QtWidgets.QWidget()
        mode_wrap.setLayout(mode_row)

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 1_000_000)
        self.qty.setAlignment(QtCore.Qt.AlignRight)

        self.reason = QtWidgets.QLineEdit()
        self.reason.setPlaceholderText("Motivo del ajuste (compra, merma, corrección, etc.)")

        form.addRow("Operación:", mode_wrap)
        form.addRow("Cantidad:", self.qty)
        form.addRow("Razón:", self.reason)
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
        if int(self.qty.value()) <= 0:
            return self._err("La cantidad debe ser mayor a 0.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[str, int, str]:
        mode = "sum" if self.mode_sum.isChecked() else "res"
        return (mode, int(self.qty.value()), self.reason.text().strip())