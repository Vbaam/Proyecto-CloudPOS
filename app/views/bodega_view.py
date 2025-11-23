from __future__ import annotations
from typing import Optional, Tuple, List, Callable, Any
from PySide6 import QtCore, QtGui, QtWidgets

from app.funciones.bodega import (
    aplicar_filtro,
    colorizar_stock,
    listar_productos,
    crear_producto,
    actualizar_producto,
    listar_categorias,
    actualizar_categoria,
    eliminar_producto,
)


class _FuncWorker(QtCore.QObject):
    finished = QtCore.Signal(object, str)  # (resultado, error)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    @QtCore.Slot()
    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result, "")
        except Exception as e:
            self.finished.emit(None, str(e))


class BodegaView(QtWidgets.QWidget):
    _async_result = QtCore.Signal(object, str, object, object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build_ui()
        self._load_empty_state()
        self._wire_events()
        self._busy_cursor = False

        self._active_threads: List[QtCore.QThread] = []

        self._pending_cat_update: Optional[tuple[int, str]] = None  # (producto_id, nombre_categoria)

        self._async_result.connect(self._handle_async_result)

        self._load_products()


    def _run_async(self, fn: Callable, args: tuple = (), on_ok: Optional[Callable[[Any], None]] = None,
                   on_err: Optional[Callable[[str], None]] = None):
        thread = QtCore.QThread()
        worker = _FuncWorker(fn, *args)
        worker.moveToThread(thread)

        thread._worker = worker  
        self._active_threads.append(thread)

        def _done(res: object, err: str):
            self._async_result.emit(res, err, on_ok, on_err)
            thread.quit()

        def _cleanup():
            try:
                self._active_threads.remove(thread)
            except ValueError:
                pass
            if hasattr(thread, "_worker"):
                delattr(thread, "_worker")

        thread.started.connect(worker.run)
        worker.finished.connect(_done)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(_cleanup)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @QtCore.Slot(object, str, object, object)
    def _handle_async_result(self, res: object, err: str,
                             on_ok: Optional[Callable[[Any], None]],
                             on_err: Optional[Callable[[str], None]]):
        if err:
            if on_err:
                on_err(err)
            else:
                self._on_api_error(err)
        else:
            if on_ok:
                on_ok(res)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Barra de búsqueda y categoría
        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por código o nombre (Ctrl+F)")
        self.search_edit.setClearButtonEnabled(True)
        self.category = QtWidgets.QComboBox()
        self.category.addItem("Todas")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.category, 0)

        # Toolbar (acciones que llaman funciones de bodega.py)
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_recargar = QtWidgets.QPushButton("Recargar")
        self.btn_nuevo = QtWidgets.QPushButton("Nuevo")
        self.btn_editar = QtWidgets.QPushButton("Editar")
        self.btn_cambiar_cat = QtWidgets.QPushButton("Cambiar categoría")
        self.btn_eliminar = QtWidgets.QPushButton("Eliminar")
        self.btn_nuevo.setObjectName("primaryButton") 
        self.btn_eliminar.setObjectName("dangerButton")
        toolbar.addWidget(self.btn_recargar)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.btn_nuevo)
        toolbar.addWidget(self.btn_editar)
        toolbar.addWidget(self.btn_cambiar_cat)
        toolbar.addWidget(self.btn_eliminar)
        toolbar.addStretch(1)

        # Tabla
        self.table = QtWidgets.QTableView()
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        # Estado
        self.status_label = QtWidgets.QLabel("")

        root.addLayout(search_row)
        root.addLayout(toolbar)
        root.addWidget(self.table, 1)
        root.addWidget(self.status_label)

        # Modelo
        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Código", "Producto", "Categoría", "Precio", "Stock"])
        self.table.setModel(self.model)
        self.table.setColumnWidth(1, 250)

        # Atajos
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)
        # Doble clic para editar
        self.table.doubleClicked.connect(self._editar_api)

    def _load_empty_state(self):
        if self.model.rowCount() > 0:
            self.model.removeRows(0, self.model.rowCount())
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Todas")
        self.category.blockSignals(False)
        self.status_label.setText("")

    def _append_row(self, row: Tuple[str, str, str, int, int]):
        items = []
        for i, val in enumerate(row):
            it = QtGui.QStandardItem(str(val))
            if i in (3, 4):
                it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            items.append(it)
        self.model.appendRow(items)
        cat = row[2]
        if self.category.findText(cat) < 0:
            self.category.addItem(cat)

    def _wire_events(self):
        self.search_edit.textChanged.connect(self._filter_rows)
        self.category.currentIndexChanged.connect(self._filter_rows)
        self.btn_recargar.clicked.connect(self._load_products)
        self.btn_nuevo.clicked.connect(self._nuevo_api)
        self.btn_editar.clicked.connect(self._editar_api)
        self.btn_cambiar_cat.clicked.connect(self._cambiar_categoria_api)
        self.btn_eliminar.clicked.connect(self._eliminar_api) 

    def _filter_rows(self):
        aplicar_filtro(self.table, self.model, self.search_edit.text(), self.category.currentText())

    # -------------------------------- Acciones (vía funciones) --------------------------------
    def _load_products(self):
        self.status_label.setText("Cargando productos…")
        self._set_busy(True)

        def ok(items: List[dict]):
            self._set_busy(False)
            self._load_empty_state()
            for p in items or []:
                code = str(p.get("id", ""))
                name = str(p.get("nombre", ""))
                cat = str(p.get("categoria") or "Sin categoría")
                price = int(p.get("precio") or 0)
                stock = int(p.get("stock") or 0)
                self._append_row((code, name, cat, price, stock))
            colorizar_stock(self.model)
            self._filter_rows()
            n = self.model.rowCount()
            self.status_label.setText(f"{n} producto(s) cargado(s)" if n else "Sin productos desde la API")

        def err(msg: str):
            self._set_busy(False)
            self._on_api_error(msg)

        self._run_async(listar_productos, on_ok=ok, on_err=err)

    def _set_busy(self, busy: bool):
        if busy and not getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._busy_cursor = True
        elif not busy and getattr(self, "_busy_cursor", False):
            QtWidgets.QApplication.restoreOverrideCursor()
            self._busy_cursor = False

    def _on_api_error(self, msg: str):
        self.status_label.setText(f"Error de API: {msg}")
        QtWidgets.QMessageBox.warning(self, "API", f"Ocurrió un error:\n{msg}")

    # Utilidad: cargar categorías y luego ejecutar una acción que las necesita
    def _cargar_categorias_y(self, then: Callable[[List[dict]], None]):
        self.status_label.setText("Cargando categorías…")
        self._set_busy(True)

        def ok(items: List[dict]):
            self._set_busy(False)
            then(items or [])

        def err(msg: str):
            self._set_busy(False)
            self._on_api_error(msg)

        self._run_async(listar_categorias, on_ok=ok, on_err=err)

    # -------- Crear producto --------
    def _nuevo_api(self):
        def _abrir_dialogo(categorias: List[dict]):
            dlg = ProductoNuevoApiDialog(self, categorias)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                nombre, categoria_id, precio, cantidad = dlg.values()
                self.status_label.setText("Creando producto…")
                self._set_busy(True)

                def ok(message: str):
                    self._set_busy(False)
                    QtWidgets.QMessageBox.information(self, "Producto", message or "Producto creado correctamente.")
                    self._load_products()

                def err(msg: str):
                    self._set_busy(False)
                    self._on_api_error(msg)

                self._run_async(crear_producto, (nombre, categoria_id, precio, cantidad), ok, err)

        self._cargar_categorias_y(_abrir_dialogo)

    # -------- Editar (precio, cantidad) --------
    def _editar_api(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "Editar", "Selecciona un producto de la tabla.")
            return
        r = idx.row()
        pid = int(self.model.item(r, 0).text() or "0")
        name = self.model.item(r, 1).text()
        precio_actual = int(self.model.item(r, 3).text() or "0")
        cantidad_actual = int(self.model.item(r, 4).text() or "0")

        dlg = EditarProductoApiDialog(self, pid, name, precio_actual, cantidad_actual)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            new_precio, new_cantidad = dlg.values()
            self.status_label.setText("Actualizando producto…")
            self._set_busy(True)

            def ok(message: str):
                self._set_busy(False)
                QtWidgets.QMessageBox.information(self, "Producto", message or "Producto actualizado.")
                self._load_products()

            def err(msg: str):
                self._set_busy(False)
                self._on_api_error(msg)

            self._run_async(actualizar_producto, (pid, new_precio, new_cantidad), ok, err)

    # -------- Cambiar categoría --------
    def _cambiar_categoria_api(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "Cambiar categoría", "Selecciona un producto de la tabla.")
            return
        r = idx.row()
        producto_id = int(self.model.item(r, 0).text() or "0")

        def _abrir_dialogo(categorias: List[dict]):
            dlg = SeleccionarCategoriaDialog(self, categorias)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                categoria_id, categoria_nombre = dlg.values()
                if categoria_id <= 0:
                    QtWidgets.QMessageBox.warning(self, "Categoría", "Selecciona una categoría válida.")
                    return

                self._pending_cat_update = (producto_id, categoria_nombre)
                self.status_label.setText("Actualizando categoría…")
                self._set_busy(True)

                def ok(message: str):
                    self._set_busy(False)
                    # Actualiza visualmente la categoría sin esperar recarga completa
                    if self._pending_cat_update and self._pending_cat_update[0] == producto_id:
                        nuevo_nombre = self._pending_cat_update[1]
                        for rr in range(self.model.rowCount()):
                            pid = int(self.model.item(rr, 0).text() or "0")
                            if pid == producto_id:
                                self.model.item(rr, 2).setText(nuevo_nombre)
                                if self.category.findText(nuevo_nombre) < 0:
                                    self.category.addItem(nuevo_nombre)
                                break
                        self._pending_cat_update = None
                    QtWidgets.QMessageBox.information(self, "Producto", message or "Categoría actualizada.")
                    self.status_label.setText("Listo.")

                def err(msg: str):
                    self._set_busy(False)
                    self._on_api_error(msg)

                self._run_async(actualizar_categoria, (producto_id, categoria_id), ok, err)

        # Cargar categorías y luego abrir diálogo sin hilos internos
        self._cargar_categorias_y(_abrir_dialogo)


        # -------- Eliminar producto --------
    def _eliminar_api(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "Eliminar", "Selecciona un producto de la tabla.")
            return
        r = idx.row()
        try:
            producto_id = int(self.model.item(r, 0).text() or "0")
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Eliminar", "ID de producto inválido.")
            return
        if producto_id <= 0:
            QtWidgets.QMessageBox.warning(self, "Eliminar", "ID de producto inválido.")
            return

        if QtWidgets.QMessageBox.question(self, "Eliminar producto", f"¿Eliminar el producto ID {producto_id}?") != QtWidgets.QMessageBox.Yes:
            return

        # Ejecutar DELETE llamando a eliminar_producto de app.funciones.bodega
        self.status_label.setText("Eliminando producto…")
        self._set_busy(True)

        def on_ok(res: Any):
            self._set_busy(False)
            msg = str(res or "Producto eliminado")
            QtWidgets.QMessageBox.information(self, "Producto", msg)
            self._load_products()

        def on_err(msg: str):
            self._set_busy(False)
            self._on_api_error(msg)

        self._run_async(eliminar_producto, (producto_id,), on_ok, on_err)
# -------- Diálogo: crear producto --------
class ProductoNuevoApiDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, categorias: Optional[List[dict]] = None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo producto")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.nombre = QtWidgets.QLineEdit()

        self.categoria = QtWidgets.QComboBox()
        self.categoria.setEnabled(True)

        self.precio = QtWidgets.QSpinBox()
        self.precio.setRange(1, 10_000_000)
        self.precio.setSingleStep(100)
        self.precio.setSuffix(" $")
        self.precio.setAlignment(QtCore.Qt.AlignRight)

        self.cantidad = QtWidgets.QSpinBox()
        self.cantidad.setRange(0, 1_000_000)
        self.cantidad.setAlignment(QtCore.Qt.AlignRight)

        form.addRow("Nombre:", self.nombre)
        form.addRow("Categoría:", self.categoria)
        form.addRow("Precio:", self.precio)
        form.addRow("Cantidad:", self.cantidad)
        lay.addLayout(form)

        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("errorLabel")
        self.error.setVisible(False)
        lay.addWidget(self.error)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        # Poblar categorías recibidas
        self._populate_categorias(categorias or [])

    def _populate_categorias(self, items: List[dict]):
        self.categoria.clear()
        if not items:
            self.categoria.addItem("Sin categorías", -1)
            self.categoria.setEnabled(False)
            return
        for it in items:
            cid = int(it.get("id") or 0)
            name = str(it.get("categoria") or f"ID {cid}")
            self.categoria.addItem(name, cid)
        self.categoria.setEnabled(True)

    def _on_accept(self):
        nombre = self.nombre.text().strip()
        if not nombre:
            return self._err("El nombre es obligatorio.")
        categoria_id = int(self.categoria.currentData() or 0)
        if categoria_id <= 0:
            return self._err("Selecciona una categoría válida.")
        if int(self.precio.value()) <= 0:
            return self._err("El precio debe ser mayor a 0.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[str, int, int, int]:
        return (
            self.nombre.text().strip(),
            int(self.categoria.currentData() or 0),
            int(self.precio.value()),
            int(self.cantidad.value()),
        )


# -------- Diálogo: editar producto (precio/cantidad) --------
class EditarProductoApiDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget], producto_id: int, nombre: str, precio: int, cantidad: int):
        super().__init__(parent)
        self.setWindowTitle(f"Editar producto — ID {producto_id}")
        self.setModal(True)
        self.setMinimumWidth(420)

        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(f"Producto: <b>{nombre}</b>")
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.precio = QtWidgets.QSpinBox()
        self.precio.setRange(1, 10_000_000)
        self.precio.setSingleStep(100)
        self.precio.setSuffix(" $")
        self.precio.setAlignment(QtCore.Qt.AlignRight)
        self.precio.setValue(int(precio))

        self.cantidad = QtWidgets.QSpinBox()
        self.cantidad.setRange(0, 1_000_000)
        self.cantidad.setAlignment(QtCore.Qt.AlignRight)
        self.cantidad.setValue(int(cantidad))

        form.addRow("Precio:", self.precio)
        form.addRow("Cantidad:", self.cantidad)
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
        if int(self.precio.value()) <= 0:
            return self._err("El precio debe ser mayor a 0.")
        if int(self.cantidad.value()) < 0:
            return self._err("La cantidad no puede ser negativa.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[int, int]:
        return (int(self.precio.value()), int(self.cantidad.value()))


# -------- Diálogo: seleccionar categoría --------
class SeleccionarCategoriaDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, categorias: Optional[List[dict]] = None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar categoría")
        self.setModal(True)
        self.setMinimumWidth(380)

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.categoria = QtWidgets.QComboBox()
        self.categoria.setEnabled(True)

        form.addRow("Categoría:", self.categoria)
        lay.addLayout(form)

        self.error = QtWidgets.QLabel("")
        self.error.setObjectName("errorLabel")
        self.error.setVisible(False)
        lay.addWidget(self.error)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        # Poblar categorías recibidas
        self._populate_categorias(categorias or [])

    def _populate_categorias(self, items: List[dict]):
        self.categoria.clear()
        if not items:
            self.categoria.addItem("Sin categorías", -1)
            self.categoria.setEnabled(False)
            return
        for it in items:
            cid = int(it.get("id") or 0)
            name = str(it.get("categoria") or f"ID {cid}")
            self.categoria.addItem(name, cid)
        self.categoria.setEnabled(True)

    def _on_accept(self):
        categoria_id = int(self.categoria.currentData() or 0)
        if categoria_id <= 0:
            return self._err("Selecciona una categoría válida.")
        self.accept()

    def _err(self, msg: str):
        self.error.setText(msg)
        self.error.setVisible(True)

    def values(self) -> Tuple[int, str]:
        return (int(self.categoria.currentData() or 0), str(self.categoria.currentText() or ""))