from typing import List, Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets


class CajaView(QtWidgets.QWidget):
    """
    Vista de Caja (Cajero) — SOLO UI.
    Sin IVA: solo muestra y calcula Total (suma de líneas del carrito).
    Inicia sin datos: sin productos, carrito vacío, y solo 'Todas' en categorías.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_empty_state()
        self._wire_events()
        self._update_totals()

    # ----------------- UI -----------------
    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Panel de búsqueda y lista de productos
        left = QtWidgets.QVBoxLayout()
        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por código o nombre (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        self.category = QtWidgets.QComboBox()
        self.category.addItem("Todas")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.category, 0)

        self.products = QtWidgets.QTableView()
        self.products.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.products.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.products.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.products.horizontalHeader().setStretchLastSection(True)
        self.products.verticalHeader().setVisible(False)

        left.addLayout(search_row)
        left.addWidget(self.products, 1)

        # Panel de carrito
        right = QtWidgets.QVBoxLayout()
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Carrito de venta"))
        header.addStretch(1)
        self.btn_vaciar = QtWidgets.QPushButton("Vaciar")
        self.btn_quitar = QtWidgets.QPushButton("Quitar")
        self.btn_menos = QtWidgets.QPushButton("−")
        self.btn_mas = QtWidgets.QPushButton("+")
        for b in (self.btn_menos, self.btn_mas):
            b.setFixedWidth(36)
        header.addWidget(self.btn_menos)
        header.addWidget(self.btn_mas)
        header.addWidget(self.btn_quitar)
        header.addWidget(self.btn_vaciar)

        self.cart = QtWidgets.QTableView()
        self.cart.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cart.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.cart.horizontalHeader().setStretchLastSection(True)
        self.cart.verticalHeader().setVisible(False)
        self.cart.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # Totales (solo Total)
        totals = QtWidgets.QFormLayout()
        self.lbl_total = QtWidgets.QLabel("$0")
        totals.addRow("<b>Total:</b>", self.lbl_total)

        pay_row = QtWidgets.QHBoxLayout()
        self.btn_efectivo = QtWidgets.QPushButton("Efectivo (F5)")
        self.btn_tarjeta = QtWidgets.QPushButton("Tarjeta (F6)")
        self.btn_emitir = QtWidgets.QPushButton("Generar comprobante (F12)")
        self.btn_emitir.setObjectName("primaryButton")
        pay_row.addWidget(self.btn_efectivo)
        pay_row.addWidget(self.btn_tarjeta)
        pay_row.addStretch(1)
        pay_row.addWidget(self.btn_emitir)

        right.addLayout(header)
        right.addWidget(self.cart, 1)
        right.addSpacing(8)
        right.addLayout(totals)
        right.addSpacing(8)
        right.addLayout(pay_row)

        layout.addLayout(left, 3)
        layout.addLayout(right, 4)

        # Modelos
        self.prod_model = QtGui.QStandardItemModel(self)
        self.prod_model.setHorizontalHeaderLabels(["Código", "Producto", "Categoría", "Precio", "Stock"])
        self.products.setModel(self.prod_model)
        self.products.setColumnWidth(1, 220)

        self.cart_model = QtGui.QStandardItemModel(self)
        self.cart_model.setHorizontalHeaderLabels(["Código", "Producto", "Cant.", "Precio", "Total"])
        self.cart.setModel(self.cart_model)
        self.cart.setColumnWidth(1, 220)

        # Atajos
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)
        QtGui.QShortcut(QtGui.QKeySequence("Insert"), self, activated=self._agregar_producto_seleccionado)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._quitar_seleccion)
        QtGui.QShortcut(QtGui.QKeySequence("F5"), self, activated=lambda: self._pagar("Efectivo"))
        QtGui.QShortcut(QtGui.QKeySequence("F6"), self, activated=lambda: self._pagar("Tarjeta"))
        QtGui.QShortcut(QtGui.QKeySequence("F12"), self, activated=self._emitir)

    # ----------------- Estado vacío garantizado -----------------
    def _load_empty_state(self):
        # Limpia modelos
        if self.prod_model.rowCount() > 0:
            self.prod_model.removeRows(0, self.prod_model.rowCount())
        if self.cart_model.rowCount() > 0:
            self.cart_model.removeRows(0, self.cart_model.rowCount())

        # Reinicia categorías a solo "Todas"
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Todas")
        self.category.blockSignals(False)

        # Sin inventario en memoria
        self._inventory: List[Tuple[str, str, str, int, int]] = []
        self._update_stock_styles()
        self._do_filter()

    # ----------------- Eventos -----------------
    def _wire_events(self):
        self.search_edit.textChanged.connect(self._do_filter)
        self.category.currentIndexChanged.connect(self._do_filter)
        self.products.doubleClicked.connect(lambda _=None: self._agregar_producto_seleccionado())
        self.btn_vaciar.clicked.connect(self._vaciar)
        self.btn_quitar.clicked.connect(self._quitar_seleccion)
        self.btn_mas.clicked.connect(lambda: self._ajustar_cantidad(+1))
        self.btn_menos.clicked.connect(lambda: self._ajustar_cantidad(-1))
        self.btn_emitir.clicked.connect(self._emitir)
        self.btn_efectivo.clicked.connect(lambda: self._pagar("Efectivo"))
        self.btn_tarjeta.clicked.connect(lambda: self._pagar("Tarjeta"))

    # ----------------- Utilidades de tabla -----------------
    def _do_filter(self):
        text = self.search_edit.text().lower().strip()
        cat = self.category.currentText()
        for r in range(self.prod_model.rowCount()):
            code = self.prod_model.item(r, 0).text().lower()
            name = self.prod_model.item(r, 1).text().lower()
            cat_row = self.prod_model.item(r, 2).text()
            match = (text in code or text in name) and (cat == "Todas" or cat == cat_row)
            self.products.setRowHidden(r, not match)

    def _update_stock_styles(self):
        for r in range(self.prod_model.rowCount()):
            stock = int(self.prod_model.item(r, 4).text())
            bg = None
            if stock == 0:
                bg = QtGui.QBrush(QtGui.QColor("#ffebee"))
            elif stock <= 5:
                bg = QtGui.QBrush(QtGui.QColor("#fff8e1"))
            for c in range(self.prod_model.columnCount()):
                self.prod_model.item(r, c).setBackground(bg if bg else QtGui.QBrush())

    # ----------------- Carrito -----------------
    def _agregar_producto_seleccionado(self):
        # Sin productos cargados, no hará nada.
        idx = self.products.currentIndex()
        if not idx.isValid():
            return

    def _current_cart_row(self) -> Optional[int]:
        idx = self.cart.currentIndex()
        return idx.row() if idx.isValid() else None

    def _quitar_seleccion(self):
        r = self._current_cart_row()
        if r is None:
            return
        self.cart_model.removeRow(r)
        self._update_totals()

    def _ajustar_cantidad(self, delta: int):
        r = self._current_cart_row()
        if r is None:
            return

    def _vaciar(self):
        if self.cart_model.rowCount() > 0:
            self.cart_model.removeRows(0, self.cart_model.rowCount())
        self._update_totals()

    # ----------------- Totales (sin IVA) -----------------
    def _fmt_money(self, v: int) -> str:
        return f"${v:,}".replace(",", ".")

    def _parse_money(self, s: str) -> int:
        return int(s.replace("$", "").replace(".", "").strip())

    def _update_totals(self):
        total = 0
        for r in range(self.cart_model.rowCount()):
            total += self._parse_money(self.cart_model.item(r, 4).text())
        self.lbl_total.setText(f"<b>{self._fmt_money(total)}</b>")
        self.btn_emitir.setEnabled(self.cart_model.rowCount() > 0)

    # ----------------- Pago/Comprobante (simulado) -----------------
    def _pagar(self, medio: str):
        if self.cart_model.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Pago", "No hay productos en el carrito.")
            return
        QtWidgets.QMessageBox.information(self, "Pago", f"Pago simulado con {medio}.\n(Solo UI)")

    def _emitir(self):
        if self.cart_model.rowCount() == 0:
            return
        QtWidgets.QMessageBox.information(self, "Comprobante", "Boleta generada (simulada).\n(Solo UI)")
        self.cart_model.removeRows(0, self.cart_model.rowCount())
        self._update_totals()