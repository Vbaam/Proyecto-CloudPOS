from __future__ import annotations
from typing import Optional
from PySide6 import QtCore, QtWidgets
from app.servicios.api import ApiClient


class LedIndicator(QtWidgets.QLabel):
    """
    Indicador redondo rojo/verde para estado de conexión.
    Úsalo en la barra de estado u otro contenedor.
    """
    def __init__(self, size: int = 10, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        self.set_state(False)

    @QtCore.Slot(bool)
    def set_state(self, on: bool):
        color = "#2ecc71" if on else "#e74c3c"  # verde / rojo
        self.setToolTip("Conectado a la API" if on else "Sin conexión a la API")
        self.setStyleSheet(
            f"background-color: {color}; border-radius: {self._size//2}px; margin: 0px;"
        )


class _PingWorker(QtCore.QObject):
    finished = QtCore.Signal(bool, str)  # (online, error)

    def __init__(self, client: ApiClient):
        super().__init__()
        self._client = client

    @QtCore.Slot()
    def run(self):
        try:
            ok = self._client.check_api()
            self.finished.emit(bool(ok), "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ApiMonitor(QtCore.QObject):
    """
    Monitorea la API con un ping periódico y emite onlineChanged(True/False).
    Puedes conectar esta señal a LedIndicator.set_state para reflejar el estado.
    """
    onlineChanged = QtCore.Signal(bool)
    error = QtCore.Signal(str)

    def __init__(self, client: Optional[ApiClient] = None, parent: Optional[QtCore.QObject] = None, interval_ms: int = 15000):
        super().__init__(parent)
        self._client = client or ApiClient()
        self._interval = max(3000, int(interval_ms))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self._interval)
        self._timer.timeout.connect(self._tick)
        self._online: Optional[bool] = None
        self._thread: Optional[QtCore.QThread] = None
        self._worker: Optional[_PingWorker] = None

    def start(self, run_immediately: bool = True):
        self._timer.start()
        if run_immediately:
            QtCore.QTimer.singleShot(0, self._tick)

    def stop(self):
        self._timer.stop()

    def bind_indicator(self, indicator: LedIndicator):
        """
        Conecta automáticamente el LED al estado del monitor y lo inicializa.
        """
        self.onlineChanged.connect(indicator.set_state)
        if self._online is not None:
            indicator.set_state(self._online)

    @QtCore.Slot()
    def _tick(self):
        if self._thread and self._thread.isRunning():
            return
        self._thread = QtCore.QThread(self)
        self._worker = _PingWorker(self._client)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_refs)
        self._thread.start()

    @QtCore.Slot()
    def _clear_refs(self):
        self._thread = None
        self._worker = None

    @QtCore.Slot(bool, str)
    def _on_finished(self, online: bool, err: str):
        if err:
            self.error.emit(err)
        if self._online is None or online != self._online:
            self._online = online
            self.onlineChanged.emit(online)