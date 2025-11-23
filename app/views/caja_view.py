from __future__ import annotations
import json
from typing import Optional, List, Tuple, Dict
from PySide6 import QtCore, QtGui, QtWidgets
from app.servicios.api import ApiClient
from app.servicios.productos_service import ProductosService
from app.funciones.caja import generate_sale_json


USER_ROLE_PRODUCT = QtCore.Qt.UserRole + 1  

class CashPaymentDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget], model_carrito: QtGui.QStandardItemModel, parse_money: callable, fmt_money: callable):
        super().__init__(parent)
        self.setWindowTitle("Cobro en efectivo")
        self.setModal(True)
        self.setMinimumWidth(520)

        self._model = model_carrito
        self._parse_money = parse_money
        self._fmt_money = fmt_money

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Tabla resumida del carrito (Producto, Cant., Subtotal)
        self.tbl = QtWidgets.QTableWidget(self)
        self.tbl.setColumnCount(3)
        self.tbl.setHorizontalHeaderLabels(["Producto", "Cant.", "Subtotal"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._load_cart_rows()
        lay.addWidget(self.tbl)

        # Total
        self.total = self._calc_total()
        self.lbl_total = QtWidgets.QLabel(f"Total: {self._fmt_money(self.total)}")
        font = self.lbl_total.font()
        font.setBold(True)
        self.lbl_total.setFont(font)
        lay.addWidget(self.lbl_total)

        # Monto recibido
        frm = QtWidgets.QFormLayout()
        self.efectivo_edit = QtWidgets.QLineEdit()
        self.efectivo_edit.setPlaceholderText("Ingrese efectivo recibido (ej: 10000)")
        self.efectivo_edit.setClearButtonEnabled(True)
        self.efectivo_edit.setValidator(QtGui.QIntValidator(0, 1_000_000_000, self))
        frm.addRow("Efectivo:", self.efectivo_edit)

        self.lbl_vuelto = QtWidgets.QLabel("Vuelto: $0")
        frm.addRow("Vuelto:", self.lbl_vuelto)
        lay.addLayout(frm)

        # Botones
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.button(QtWidgets.QDialogButtonBox.Ok).setText("Terminar")
        btns.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        # Eventos
        self.efectivo_edit.textChanged.connect(self._recalc_change)

        # Estado inicial
        self._recalc_change()

    def _load_cart_rows(self):
        rows = self._model.rowCount()
        self.tbl.setRowCount(rows)
        r = 0
        for r in range(rows):
            prod = self._model.item(r, 1).text() if self._model.item(r, 1) else ""
            cant = self._model.item(r, 4).text() if self._model.item(r, 4) else "0"
            sub  = self._model.item(r, 5).text() if self._model.item(r, 5) else "$0"

            it_prod = QtWidgets.QTableWidgetItem(prod)
            it_cant = QtWidgets.QTableWidgetItem(cant)
            it_sub  = QtWidgets.QTableWidgetItem(sub)

            it_cant.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            it_sub.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            self.tbl.setItem(r, 0, it_prod)
            self.tbl.setItem(r, 1, it_cant)
            self.tbl.setItem(r, 2, it_sub)

        self.tbl.resizeColumnsToContents()

    def _calc_total(self) -> int:
        total = 0
        for r in range(self._model.rowCount()):
            subtotal = self._parse_money(self._model.item(r, 5).text())
            total += subtotal
        return total

    def _recalc_change(self):
        try:
            efectivo = int(self.efectivo_edit.text() or "0")
        except Exception:
            efectivo = 0
        vuelto = max(0, efectivo - self.total)
        self.lbl_vuelto.setText(f"Vuelto: {self._fmt_money(vuelto)}")

        # Deshabilita "Terminar" si no alcanza el efectivo
        btn_ok = self.findChild(QtWidgets.QDialogButtonBox).button(QtWidgets.QDialogButtonBox.Ok)
        if btn_ok:
            btn_ok.setEnabled(efectivo >= self.total)

    def _on_accept(self):
        # Valida nuevamente
        try:
            efectivo = int(self.efectivo_edit.text() or "0")
        except Exception:
            efectivo = 0
        if efectivo < self.total:
            QtWidgets.QMessageBox.warning(self, "Efectivo insuficiente", "El monto ingresado es menor que el total.")
            return
        self.accept()

class CajaView(QtWidgets.QWidget):
    """
    Vista de Caja con:
    - Catálogo de productos cargado desde la API (/muestra_productos)
    - Carrito: permite agregar con cantidad, actualizar, eliminar y muestra el total
    """
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._busy_cursor = False
        self._products_by_id: Dict[str, dict] = {}
        self._last_sale_json: str | None = None
        self._build_ui()
        self._wire_events()

        # Servicio de productos compartido
        self._svc = ProductosService(ApiClient(), self)
        self._svc.busy.connect(self._set_busy)
        self._svc.error.connect(self._on_api_error)
        self._svc.productosCargados.connect(self._on_api_ok)

        self._load_products()

    # ------------------- UI -------------------
    def _build_ui(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # Panel izquierdo: catálogo + filtros
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)

        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Buscar producto por nombre o categoría…")
        self.btn_recargar = QtWidgets.QPushButton("Recargar")
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_recargar)
        left.addLayout(top)

        # Tabla de catálogo
        self.tbl_catalogo = QtWidgets.QTableView()
        self.tbl_catalogo.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_catalogo.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_catalogo.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_catalogo.horizontalHeader().setStretchLastSection(True)
        self.tbl_catalogo.verticalHeader().setVisible(False)
        left.addWidget(self.tbl_catalogo, 1)

        # Selector de cantidad + botón agregar
        qty_row = QtWidgets.QHBoxLayout()
        self.spn_qty = QtWidgets.QSpinBox()
        self.spn_qty.setRange(1, 1_000_000)
        self.spn_qty.setValue(1)
        self.btn_agregar = QtWidgets.QPushButton("Agregar al carrito")
        self.btn_agregar.setObjectName("primaryButton")
        self.spn_qty.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)  
        self.spn_qty.setFocusPolicy(QtCore.Qt.StrongFocus)                   
        self.spn_qty.setAccelerated(True)                                    
        self.spn_qty.setKeyboardTracking(True)   
        qty_row.addWidget(QtWidgets.QLabel("Cantidad:"))
        qty_row.addWidget(self.spn_qty)
        qty_row.addStretch(1)
        qty_row.addWidget(self.btn_agregar)
        left.addLayout(qty_row)

        # Estado catálogo
        self.lbl_status_catalogo = QtWidgets.QLabel("")
        left.addWidget(self.lbl_status_catalogo)

        # Panel derecho: carrito
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(6)

        cart_lbl = QtWidgets.QLabel("Carrito")
        cart_lbl.setStyleSheet("font-weight: bold;")
        right.addWidget(cart_lbl)

        self.tbl_carrito = QtWidgets.QTableView()
        self.tbl_carrito.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_carrito.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_carrito.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_carrito.horizontalHeader().setStretchLastSection(True)
        self.tbl_carrito.verticalHeader().setVisible(False)
        right.addWidget(self.tbl_carrito, 1)

        # Acciones del carrito
        cart_actions = QtWidgets.QHBoxLayout()
        self.btn_aumentar = QtWidgets.QPushButton("Aumentar (+)")
        self.btn_disminuir = QtWidgets.QPushButton("Disminuir (–)")
        self.btn_eliminar = QtWidgets.QPushButton("Eliminar (Supr)")
        self.btn_vaciar = QtWidgets.QPushButton("Vaciar")
        self.btn_eliminar.setObjectName("dangerButton") 
        self.btn_vaciar.setObjectName("dangerButton")  
        cart_actions.addWidget(self.btn_aumentar)
        cart_actions.addWidget(self.btn_disminuir)
        cart_actions.addWidget(self.btn_eliminar)
        cart_actions.addStretch(1)
        cart_actions.addWidget(self.btn_vaciar)
        right.addLayout(cart_actions)

        # Total y cobrar
        bottom = QtWidgets.QHBoxLayout()
        self.lbl_total = QtWidgets.QLabel("Total: $0")
        self.lbl_total.setStyleSheet("font-size: 16px; font-weight: bold;")
        bottom.addWidget(self.lbl_total)
        bottom.addStretch(1)
        self.btn_cobrar = QtWidgets.QPushButton("Cobrar")
        self.btn_cobrar.setObjectName("primaryButton") 
        bottom.addWidget(self.btn_cobrar)
        right.addLayout(bottom)

        # Ensamble
        root.addLayout(left, 7)
        root.addLayout(right, 5)

        # Modelos: catálogo
        self.model_catalogo = QtGui.QStandardItemModel(self)
        self.model_catalogo.setHorizontalHeaderLabels(["ID", "Producto", "Categoría", "Precio", "Stock"])
        self.proxy_catalogo = QtCore.QSortFilterProxyModel(self)
        self.proxy_catalogo.setSourceModel(self.model_catalogo)
        self.proxy_catalogo.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy_catalogo.setFilterKeyColumn(-1)  # todas
        self.tbl_catalogo.setModel(self.proxy_catalogo)
        self.tbl_catalogo.setColumnWidth(1, 260)

        # Modelo: carrito
        # Nuevo esquema: ["ID", "Producto", "Precio", "Precio con IVA", "Cant.", "Subtotal"]
        self.model_carrito = QtGui.QStandardItemModel(self)
        self.model_carrito.setHorizontalHeaderLabels(["ID", "Producto", "Precio", "Precio con IVA", "Cant.", "Subtotal"])
        self.tbl_carrito.setModel(self.model_carrito)
        # Oculta columna ID en el carrito
        self.tbl_carrito.setColumnHidden(0, True)

        # Atajos de teclado
        QtGui.QShortcut(QtGui.QKeySequence("Return"), self, activated=self._agregar_seleccionado)
        QtGui.QShortcut(QtGui.QKeySequence("Enter"), self, activated=self._agregar_seleccionado)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, activated=self._eliminar_item_carrito)
        QtGui.QShortcut(QtGui.QKeySequence("+"), self, activated=lambda: self._ajustar_cantidad(+1))
        QtGui.QShortcut(QtGui.QKeySequence("-"), self, activated=lambda: self._ajustar_cantidad(-1))

    def _wire_events(self):
        self.search.textChanged.connect(self._on_filter)
        self.btn_recargar.clicked.connect(self._load_products)
        self.tbl_catalogo.doubleClicked.connect(self._agregar_seleccionado)
        self.btn_agregar.clicked.connect(self._agregar_seleccionado)

        self.btn_aumentar.clicked.connect(lambda: self._ajustar_cantidad(+1))
        self.btn_disminuir.clicked.connect(lambda: self._ajustar_cantidad(-1))
        self.btn_eliminar.clicked.connect(self._eliminar_item_carrito)
        self.btn_vaciar.clicked.connect(self._vaciar_carrito)
        self.btn_cobrar.clicked.connect(self._on_cobrar)

    # ------------------- Catálogo (API) -------------------
    def _on_filter(self, text: str):
        self.proxy_catalogo.setFilterFixedString(text.strip())

    def _load_products(self):
        self.lbl_status_catalogo.setText("Cargando productos…")
        self._svc.cargar_productos()

    def _set_busy(self, busy: bool):
        if busy and not getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._busy_cursor = True
        elif not busy and getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.restoreOverrideCursor()
            self._busy_cursor = False

    def _on_api_error(self, msg: str):
        self.lbl_status_catalogo.setText(f"Error al cargar productos: {msg}")
        QtWidgets.QMessageBox.warning(self, "API", f"No se pudieron cargar productos:\n{msg}")

    def _on_api_ok(self, items: List[dict]):
        self.model_catalogo.removeRows(0, self.model_catalogo.rowCount())
        self._products_by_id.clear()

        for p in items:
            pid = str(p.get("id", ""))
            name = str(p.get("nombre", ""))
            cat = str(p.get("categoria") or "")
            price = int(p.get("precio") or 0)
            stock = int(p.get("stock") or 0)

            # no mostrar productos sin stock
            if stock <= 0:
                continue

            row_items: list[QtGui.QStandardItem] = []
            for i, val in enumerate((pid, name, cat, self._fmt_money(price), stock)):
                it = QtGui.QStandardItem(str(val))
                if i == 0:
                    it.setData(
                        {
                            "id": pid,
                            "nombre": name,
                            "categoria": cat,
                            "precio": price,
                            "stock": stock,
                        },
                        USER_ROLE_PRODUCT,
                    )
                if i in (3, 4):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                row_items.append(it)

            self.model_catalogo.appendRow(row_items)
            # solo guardamos los que sí se muestran
            self._products_by_id[pid] = {
                "id": pid,
                "nombre": name,
                "categoria": cat,
                "precio": price,
                "stock": stock,
            }

        n = self.model_catalogo.rowCount()
        self.lbl_status_catalogo.setText(f"{n} producto(s) disponible(s)")


    # ------------------- Carrito -------------------
    def _agregar_seleccionado(self):
        idx = self.tbl_catalogo.currentIndex()
        if not idx.isValid():
            return
        src_idx = self.proxy_catalogo.mapToSource(idx)
        pid_item = self.model_catalogo.item(src_idx.row(), 0)
        product = pid_item.data(USER_ROLE_PRODUCT) or {}
        if not product:
            return

        qty_req = int(self.spn_qty.value())
        self._agregar_producto_al_carrito(product, qty_req)

    def _agregar_producto_al_carrito(self, product: dict, qty: int):
        pid = str(product.get("id"))
        name = str(product.get("nombre", ""))
        price = int(product.get("precio") or 0)
        stock = int(product.get("stock") or 0)

        current_row = self._find_cart_row(pid)
        current_qty = int(self.model_carrito.item(current_row, 4).text()) if current_row is not None else 0

        if qty <= 0:
            QtWidgets.QMessageBox.warning(self, "Cantidad inválida", "La cantidad debe ser mayor a 0.")
            return

        if current_qty + qty > stock:
            QtWidgets.QMessageBox.warning(
                self, "Stock insuficiente",
                f"No hay stock suficiente.\nDisponible: {stock} • En carrito: {current_qty} • Solicitado: {qty}"
            )
            return

        # Calcular Precio con IVA (1.19) y subtotal en base a ese precio
        price_with_tax = int(round(price * 1.19))
        if current_row is None:
            # Crear nueva fila en carrito
            items: list[QtGui.QStandardItem] = []
            for i, val in enumerate((pid, name, self._fmt_money(price), self._fmt_money(price_with_tax), qty, self._fmt_money(price_with_tax * qty))):
                it = QtGui.QStandardItem(str(val))
                if i in (2, 3, 4, 5):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                items.append(it)
            self.model_carrito.appendRow(items)
        else:
            # Actualizar cantidad y subtotal (usar Precio con IVA en columna 3)
            new_qty = current_qty + qty
            self.model_carrito.item(current_row, 4).setText(str(new_qty))
            price_with_tax_existing = self._parse_money(self.model_carrito.item(current_row, 3).text())
            self.model_carrito.item(current_row, 5).setText(self._fmt_money(price_with_tax_existing * new_qty))

        self._actualizar_total()

    def _ajustar_cantidad(self, delta: int):
        idx = self.tbl_carrito.currentIndex()
        if not idx.isValid():
            return
        r = idx.row()
        price_with_tax = self._parse_money(self.model_carrito.item(r, 3).text())
        qty = int(self.model_carrito.item(r, 4).text())
        new_qty = qty + delta

        # Validaciones
        if new_qty <= 0:
            # elimina si llega a 0 o menos
            self.model_carrito.removeRow(r)
            self._actualizar_total()
            return

        stock = int((self._products_by_id.get(self.model_carrito.item(r, 0).text()) or {}).get("stock") or 0)
        if new_qty > stock:
            QtWidgets.QMessageBox.warning(self, "Stock insuficiente", f"Stock disponible: {stock}")
            return

        self.model_carrito.item(r, 4).setText(str(new_qty))
        self.model_carrito.item(r, 5).setText(self._fmt_money(price_with_tax * new_qty))
        self._actualizar_total()

    def _eliminar_item_carrito(self):
        idx = self.tbl_carrito.currentIndex()
        if not idx.isValid():
            return
        self.model_carrito.removeRow(idx.row())
        self._actualizar_total()

    def _vaciar_carrito(self):
        if self.model_carrito.rowCount() == 0:
            return
        if QtWidgets.QMessageBox.question(self, "Vaciar carrito", "¿Eliminar todos los ítems del carrito?") == QtWidgets.QMessageBox.Yes:
            self.model_carrito.removeRows(0, self.model_carrito.rowCount())
            self._actualizar_total()

    def _find_cart_row(self, pid: str) -> Optional[int]:
        for r in range(self.model_carrito.rowCount()):
            if self.model_carrito.item(r, 0).text() == pid:
                return r
        return None

    def _actualizar_total(self):
        total = 0
        for r in range(self.model_carrito.rowCount()):
            subtotal = self._parse_money(self.model_carrito.item(r, 5).text())
            total += subtotal
        self.lbl_total.setText(f"Total: {self._fmt_money(total)}")

    def _on_cobrar(self):
        if self.model_carrito.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Cobrar", "El carrito está vacío.")
            return

        # Evitar dobles disparos
        if getattr(self, "_sale_in_progress", False):
            return
        self._sale_in_progress = True

        # Preguntar método de pago
        mb = QtWidgets.QMessageBox(self)
        mb.setWindowTitle("Cobrar")
        mb.setText("Selecciona el método de pago:")
        btn_efectivo = mb.addButton("Efectivo", QtWidgets.QMessageBox.AcceptRole)
        btn_tarjeta  = mb.addButton("Tarjeta",  QtWidgets.QMessageBox.ActionRole)
        mb.addButton("Cancelar", QtWidgets.QMessageBox.RejectRole)
        mb.exec()

        clicked = mb.clickedButton()
        # Cancelado
        if clicked is None or mb.buttonRole(clicked) == QtWidgets.QMessageBox.RejectRole:
            self._sale_in_progress = False
            return

        usuario = getattr(self, "usuario_actual", "Desconocido")

        if clicked == btn_tarjeta:
            # Generar una sola vez
            self._generar_json_venta(usuario, metodo_pago="Tarjeta")
            self._sale_in_progress = False
            return

        if clicked == btn_efectivo:
            # Mostrar diálogo de efectivo y, si acepta, generar una sola vez
            dlg = CashPaymentDialog(self, self.model_carrito, self._parse_money, self._fmt_money)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                self._generar_json_venta(usuario, metodo_pago="Efectivo")
            # si cancela, no pasa nada
            self._sale_in_progress = False
            return

    def _generar_json_venta(self, usuario: str, metodo_pago: str):
        import json
        json_str = generate_sale_json(self.model_carrito, usuario, metodo_pago=metodo_pago)
        self._last_sale_json = json_str
        print("[CajaView] Venta (JSON):", json_str)

        if metodo_pago == "Tarjeta":
            total_text = self.lbl_total.text().replace("Total: ", "")
            QtWidgets.QMessageBox.information(
                self, "Cobrar",
                f"JSON de venta generado internamente.\n"
                f"Usuario: {usuario}\n"
                f"Método: {metodo_pago}\n"
                f"Elementos: {self.model_carrito.rowCount()}\n"
                f"Total: {total_text}"
            )
            return

        try:
            payload_full = json.loads(json_str)
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Efectivo", "No se pudo preparar el payload de la venta.")
            return

        payload_api = {
            "fecha": payload_full.get("fecha"),
            "hora":  payload_full.get("hora"),
            "total": payload_full.get("total"),
            "items": payload_full.get("items") or [],
        }

        client = ApiClient()
        resp = client.post_json("/ventas", payload_api)

        if isinstance(resp, dict) and resp.get("error"):
            msg = resp.get("detail")
            if isinstance(msg, list) and msg and isinstance(msg[0], dict):
                msg = msg[0].get("msg") or str(msg)
            msg = msg or f"HTTP {resp.get('status', '')}"
            QtWidgets.QMessageBox.warning(self, "Efectivo", f"No se pudo registrar la venta:\n{msg}")
            return

        QtWidgets.QMessageBox.information(self, "Efectivo", "Venta registrada correctamente.")
        self._vaciar_carrito()

    # ------------------- Utilidades -------------------
    def _fmt_money(self, v: int) -> str:
        return f"${v:,}".replace(",", ".")

    def _parse_money(self, s: str) -> int:
        s = (s or "").strip()
        s = s.replace("$", "").replace(".", "").replace(" ", "")
        return int(s or "0")
