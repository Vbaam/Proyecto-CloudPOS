from __future__ import annotations
from typing import Optional, Tuple, List
from PySide6 import QtCore, QtGui, QtWidgets
import os

from app.funciones.admin import exportar_csv, aplicar_filtro_movimientos, validar_nombre_categoria
from app.servicios.api import ApiClient
from app.servicios.categorias_service import CategoriasService
from app.servicios.usuarios_service import UsuariosService


class AdminView(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("AdminView")
        self._busy_cursor = False

        self.tabs = QtWidgets.QTabWidget(self)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(self.tabs)

        # Pestañas existentes
        self._init_tab_categorias()
        self._init_tab_ventas()
        self._init_tab_movimientos()
        self._init_tab_usuarios()

    # CATEGORÍAS

    def _init_tab_categorias(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        toolbar = QtWidgets.QHBoxLayout()
        self.btn_cat_reload = QtWidgets.QPushButton("Recargar")
        self.btn_cat_new = QtWidgets.QPushButton("Nueva")
        self.btn_cat_del = QtWidgets.QPushButton("Eliminar")
        self.btn_cat_new.setObjectName("primaryButton") 
        self.btn_cat_del.setObjectName("dangerButton")
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
        self.cat_table.selectionModel().selectionChanged.connect(
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
        QtWidgets.QMessageBox.information(
            self,
            "Categorías",
            f'Se ha creado la categoría correctamente.'
        )
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

    # VENTAS

    def _init_tab_ventas(self):
        """Crea la pestaña 'Ventas' y consume GET /ListadoVentas con filtros."""
        w = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        # --------- Filtros ---------
        filtros = QtWidgets.QHBoxLayout()
        filtros.setSpacing(8)

        lbl_desde = QtWidgets.QLabel("Desde:")
        self.dt_desde = QtWidgets.QDateEdit()
        self.dt_desde.setCalendarPopup(True)
        self.dt_desde.setDisplayFormat("yyyy-MM-dd")
        self.dt_desde.setDate(QtCore.QDate.currentDate().addMonths(-1))  # último mes

        lbl_hasta = QtWidgets.QLabel("Hasta:")
        self.dt_hasta = QtWidgets.QDateEdit()
        self.dt_hasta.setCalendarPopup(True)
        self.dt_hasta.setDisplayFormat("yyyy-MM-dd")
        self.dt_hasta.setDate(QtCore.QDate.currentDate())

        # Filtros de fecha (Ventas)
        self.dt_desde.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.dt_hasta.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        
        cal_d = QtWidgets.QCalendarWidget()
        cal_d.setObjectName("AppCalendar")
        cal_d.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader) 
        self.dt_desde.setCalendarWidget(cal_d)

        cal_h = QtWidgets.QCalendarWidget()
        cal_h.setObjectName("AppCalendar")
        cal_h.setVerticalHeaderFormat(QtWidgets.QCalendarWidget.NoVerticalHeader)
        self.dt_hasta.setCalendarWidget(cal_h)
        # ------------------------------------------------------------------------

        self.txt_buscar_ventas = QtWidgets.QLineEdit()
        self.txt_buscar_ventas.setPlaceholderText("Buscar: transacción, vendedor o producto…")

        self.btn_filtrar_ventas = QtWidgets.QPushButton("Buscar")
        self.btn_filtrar_ventas.setObjectName("primaryButton")
        self.btn_limpiar_ventas = QtWidgets.QPushButton("Limpiar")

        filtros.addWidget(lbl_desde)
        filtros.addWidget(self.dt_desde)
        filtros.addSpacing(6)
        filtros.addWidget(lbl_hasta)
        filtros.addWidget(self.dt_hasta)
        filtros.addSpacing(12)
        filtros.addWidget(self.txt_buscar_ventas, 1)
        filtros.addWidget(self.btn_filtrar_ventas)
        filtros.addWidget(self.btn_limpiar_ventas)

        v.addLayout(filtros)

        # --------- Tabla ---------
        cols = [
            "Fecha", "Hora", "Venta ID", "Transacción", "Vendedor",
            "Producto", "Cantidad", "Precio", "Precio c/IVA", "Subtotal", "Total venta"
        ]
        self.model_ventas = QtGui.QStandardItemModel(0, len(cols), self)
        self.model_ventas.setHorizontalHeaderLabels(cols)

        self.proxy_ventas = QtCore.QSortFilterProxyModel(self)
        self.proxy_ventas.setSourceModel(self.model_ventas)
        self.proxy_ventas.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy_ventas.setFilterKeyColumn(-1)

        self.tbl_ventas = QtWidgets.QTableView(self)
        self.tbl_ventas.setModel(self.proxy_ventas)
        self.tbl_ventas.setSortingEnabled(True)
        self.tbl_ventas.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_ventas.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tbl_ventas.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_ventas.verticalHeader().setVisible(False)
        v.addWidget(self.tbl_ventas)

        hdr = self.tbl_ventas.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)   # Fecha
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)   # Hora
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)   # Venta ID
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)            # Transacción
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)   # Vendedor
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)            # Producto
        hdr.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)   # Cantidad
        hdr.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)   # Precio
        hdr.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeToContents)   # Precio c/IVA
        hdr.setSectionResizeMode(9, QtWidgets.QHeaderView.ResizeToContents)   # Subtotal
        hdr.setSectionResizeMode(10, QtWidgets.QHeaderView.ResizeToContents)  # Total venta

        self.lbl_ventas_status = QtWidgets.QLabel("")
        v.addWidget(self.lbl_ventas_status)

        # --------- Conexiones filtros ---------
        self.btn_filtrar_ventas.clicked.connect(self._buscar_ventas)
        self.btn_limpiar_ventas.clicked.connect(self._limpiar_filtros_ventas)
        self.txt_buscar_ventas.textChanged.connect(self._aplicar_filtro_texto_ventas)

        # --------- Thread/Worker y flag de ocupación ---------
        self._ventas_thread: Optional[QtCore.QThread] = None
        self._ventas_worker: Optional[QtCore.QObject] = None
        self._ventas_busy: bool = False

        self.tabs.addTab(w, "Ventas")

        # Primera carga
        self._buscar_ventas()

    # --- Ventas: filtros ---
    def _limpiar_filtros_ventas(self):
        self.dt_desde.setDate(QtCore.QDate.currentDate().addMonths(-1))
        self.dt_hasta.setDate(QtCore.QDate.currentDate())
        self.txt_buscar_ventas.clear()
        self._buscar_ventas()

    def _aplicar_filtro_texto_ventas(self, text: str):
        self.proxy_ventas.setFilterFixedString((text or "").strip())

    # --- Ventas: formatos ---
    def _fmt_money(self, v: int) -> str:
        try:
            return f"{int(v):,}".replace(",", ".")
        except Exception:
            return str(v)

    def _fmt_hora_hhmmss(self, seconds: int) -> str:
        try:
            seconds = int(seconds)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"
        except Exception:
            return str(seconds)

    def _buscar_ventas(self):
        if self._ventas_busy:
            return
        self._ventas_busy = True

        start = self.dt_desde.date().toString("yyyy-MM-dd")
        end = self.dt_hasta.date().toString("yyyy-MM-dd")
        self.lbl_ventas_status.setText("Cargando ventas…")

        class _VentasWorker(QtCore.QObject):
            finished = QtCore.Signal(list, str)  # (items, err)

            def __init__(self, client: ApiClient, start_date: str | None, end_date: str | None):
                super().__init__()
                self.client = client
                self.start_date = start_date
                self.end_date = end_date

            @QtCore.Slot()
            def run(self):
                try:
                    path = "/ListadoVentas"
                    params = []
                    if self.start_date:
                        params.append(f"start_date={self.start_date}")
                    if self.end_date:
                        params.append(f"end_date={self.end_date}")
                    if params:
                        path = f"{path}?{'&'.join(params)}"

                    res = self.client.get_json(path)
                    if isinstance(res, dict) and isinstance(res.get("Ventas"), list):
                        self.finished.emit(res["Ventas"], "")
                    else:
                        self.finished.emit([], "Formato inesperado de respuesta.")
                except Exception as e:
                    self.finished.emit([], str(e))

        # Crea hilo y worker nuevos para cada búsqueda
        self._ventas_thread = QtCore.QThread(self)
        self._ventas_worker = _VentasWorker(ApiClient(), start, end)
        self._ventas_worker.moveToThread(self._ventas_thread)

        # Conexiones
        self._ventas_thread.started.connect(self._ventas_worker.run)
        self._ventas_worker.finished.connect(self._on_ventas_loaded)
        self._ventas_worker.finished.connect(self._ventas_thread.quit)
        self._ventas_worker.finished.connect(self._ventas_worker.deleteLater)
        self._ventas_thread.finished.connect(self._ventas_thread.deleteLater)
        self._ventas_thread.finished.connect(self._ventas_clear_refs)

        self._ventas_thread.start()

    @QtCore.Slot()
    def _ventas_clear_refs(self):
        self._ventas_thread = None
        self._ventas_worker = None
        self._ventas_busy = False

    @QtCore.Slot(list, str)
    def _on_ventas_loaded(self, rows: List[dict], err: str):
        self._ventas_busy = False

        if err:
            self.lbl_ventas_status.setText(f"Error: {err}")
            QtWidgets.QMessageBox.warning(self, "Ventas", err)
            return

        self.model_ventas.removeRows(0, self.model_ventas.rowCount())

        # Una fila por producto (una venta puede traer múltiples items)
        for r in rows:
            fecha = str(r.get("fecha") or "")
            hora = self._fmt_hora_hhmmss(r.get("hora") or 0)
            venta_id = str(r.get("venta_id") or "")
            trans = str(r.get("transaccion") or "")
            vendedor = str(r.get("vendedor") or "") 
            producto = str(r.get("producto") or "")
            cantidad = int(r.get("cantidad") or 0)
            precio = int(r.get("precio") or 0)
            precio_iva = int(r.get("precio_con_iva") or 0)
            subtotal = int(r.get("subtotal") or 0)
            total_venta = int(r.get("total_venta") or 0)

            items = [
                QtGui.QStandardItem(fecha),
                QtGui.QStandardItem(hora),
                QtGui.QStandardItem(venta_id),
                QtGui.QStandardItem(trans),
                QtGui.QStandardItem(vendedor),
                QtGui.QStandardItem(producto),
                QtGui.QStandardItem(str(cantidad)),
                QtGui.QStandardItem(self._fmt_money(precio)),
                QtGui.QStandardItem(self._fmt_money(precio_iva)),
                QtGui.QStandardItem(self._fmt_money(subtotal)),
                QtGui.QStandardItem(self._fmt_money(total_venta)),
            ]
            for idx in (6, 7, 8, 9, 10):
                items[idx].setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            self.model_ventas.appendRow(items)

        self.lbl_ventas_status.setText(
            f"Filas: {self.model_ventas.rowCount()}  (una fila por producto dentro de cada venta)"
        )

    # MOVIMIENTOS

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

    # USUARIOS

    def _init_tab_usuarios(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 8)

        # toolbar
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_usr_reload = QtWidgets.QPushButton("Recargar")
        self.btn_usr_new = QtWidgets.QPushButton("Nuevo usuario")
        self.btn_usr_new.setObjectName("primaryButton")
        self.btn_usr_edit_name = QtWidgets.QPushButton("Editar nombre")
        self.btn_usr_edit_pwd = QtWidgets.QPushButton("Cambiar contraseña")
        toolbar.addWidget(self.btn_usr_reload)
        toolbar.addWidget(self.btn_usr_new)
        toolbar.addWidget(self.btn_usr_edit_name)
        toolbar.addWidget(self.btn_usr_edit_pwd)
        toolbar.addStretch(1)
        v.addLayout(toolbar)

        # tabla de usuarios
        self.tbl_usuarios = QtWidgets.QTableWidget(0, 3)
        self.tbl_usuarios.setHorizontalHeaderLabels(["ID", "Nombre", "Rol"])
        self.tbl_usuarios.verticalHeader().setVisible(False)
        self.tbl_usuarios.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl_usuarios.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tbl_usuarios.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        v.addWidget(self.tbl_usuarios)

        header = self.tbl_usuarios.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        self.lbl_usr_status = QtWidgets.QLabel("")
        v.addWidget(self.lbl_usr_status)

        # servicio de usuarios
        self._usr_svc = UsuariosService(ApiClient(), self)
        self._usr_svc.busy.connect(lambda b: self.lbl_usr_status.setText("Cargando..." if b else ""))
        self._usr_svc.error.connect(lambda e: QtWidgets.QMessageBox.warning(self, "Usuarios", e))
        self._usr_svc.usuariosListados.connect(self._on_users_loaded)
        self._usr_svc.usuarioCreado.connect(self._on_user_created)
        self._usr_svc.usuarioActualizado.connect(self._on_user_updated)

        self.btn_usr_reload.clicked.connect(self._usr_svc.listar)
        self.btn_usr_new.clicked.connect(self._on_new_user)
        self.btn_usr_edit_name.clicked.connect(self._on_edit_user_name)
        self.btn_usr_edit_pwd.clicked.connect(self._on_edit_user_pwd)

        self.tabs.addTab(w, "Usuarios")

        self._usr_svc.listar()

    def _on_users_loaded(self, usuarios: list):
        self.tbl_usuarios.setRowCount(0)
        for u in usuarios:
            row = self.tbl_usuarios.rowCount()
            self.tbl_usuarios.insertRow(row)

            uid = u.get("id", "")
            nombre = u.get("nombre", "")
            rol = u.get("rol", "")

            self.tbl_usuarios.setItem(row, 0, QtWidgets.QTableWidgetItem(str(uid)))
            self.tbl_usuarios.setItem(row, 1, QtWidgets.QTableWidgetItem(str(nombre)))
            self.tbl_usuarios.setItem(row, 2, QtWidgets.QTableWidgetItem(str(rol)))

        self.lbl_usr_status.setText(f"Usuarios cargados: {len(usuarios)}")

    def _on_user_created(self, msg: str):
        QtWidgets.QMessageBox.information(self, "Usuarios", msg or "Usuario creado.")
        self._usr_svc.listar()

    def _get_selected_user_id(self) -> int | None:
        idx = self.tbl_usuarios.currentRow()
        if idx < 0:
            return None
        item = self.tbl_usuarios.item(idx, 0)
        if not item:
            return None
        try:
            return int(item.text())
        except Exception:
            return None

    def _on_edit_user_name(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            QtWidgets.QMessageBox.information(self, "Usuarios", "Selecciona un usuario primero.")
            return
        current_name_item = self.tbl_usuarios.item(self.tbl_usuarios.currentRow(), 1)
        current_name = current_name_item.text() if current_name_item else ""
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Editar nombre", "Nuevo nombre:", text=current_name)
        if not ok or not new_name.strip():
            return
        self._usr_svc.actualizar_nombre(user_id, new_name.strip())

    def _on_edit_user_pwd(self):
        user_id = self._get_selected_user_id()
        if not user_id:
            QtWidgets.QMessageBox.information(self, "Usuarios", "Selecciona un usuario primero.")
            return
        new_pwd, ok = QtWidgets.QInputDialog.getText(
            self, "Cambiar contraseña", "Nueva contraseña:", echo=QtWidgets.QLineEdit.Password
        )
        if not ok or not new_pwd:
            return
        self._usr_svc.actualizar_contrasena(user_id, new_pwd)

    def _on_user_updated(self, msg: str):
        QtWidgets.QMessageBox.information(self, "Usuarios", msg or "Usuario actualizado.")
        self._usr_svc.listar()

    def _on_new_user(self):
        dlg = NewUserDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            payload = dlg.get_payload()
            if not payload["nombre"] or not payload["contrasena"]:
                QtWidgets.QMessageBox.warning(self, "Usuarios", "Nombre y contraseña son obligatorios.")
                return
            self._usr_svc.crear(payload)

    # Busy cursor

    def _set_busy(self, busy: bool):
        if busy and not getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._busy_cursor = True
        elif not busy and getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.restoreOverrideCursor()
            self._busy_cursor = False

# Diálogos

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


class NewUserDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear usuario")
        self.setModal(True)
        layout = QtWidgets.QFormLayout(self)

        self.txt_nombre = QtWidgets.QLineEdit()
        self.txt_contrasena = QtWidgets.QLineEdit()
        self.txt_contrasena.setEchoMode(QtWidgets.QLineEdit.Password)

        self.cbo_rol = QtWidgets.QComboBox()
        self.cbo_rol.addItem("Caja", 2)
        self.cbo_rol.addItem("Bodega", 3)

        layout.addRow("Nombre:", self.txt_nombre)
        layout.addRow("Contraseña:", self.txt_contrasena)
        layout.addRow("Rol:", self.cbo_rol)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_payload(self) -> dict:
        from datetime import datetime
        rol_id = self.cbo_rol.currentData()
        return {
            "nombre": self.txt_nombre.text().strip(),
            "contrasena": self.txt_contrasena.text(),
            "rol_id": int(rol_id),
            "fecha": datetime.now().isoformat()
        }