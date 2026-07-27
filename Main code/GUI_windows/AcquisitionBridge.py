from qtpy.QtCore import QObject, Signal, Slot, QTimer
from .acq_config import AcqConfig
class AcquisitionBridge(QObject):
    running_changed = Signal(bool)
    status_message = Signal(str)
    finished = Signal()

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._poll_finished = QTimer(self)
        self._poll_finished.setInterval(100)
        self._poll_finished.timeout.connect(self._check_finished)

    @Slot(object)
    def setup(self, cfg: AcqConfig):
        cfg.validate()

        # Prefer mapping only through public API:
        self.engine.setup_sequence(
            z_depth=cfg.z_depth,
            z_stepsize=cfg.z_stepsize,
            x_tiles = cfg.x_tiles,
            y_tiles = cfg.y_tiles,
            channels=cfg.channels,  # or tuple; must support len() and iteration
            saving=cfg.saving,
            filename=cfg.filename,
            foldername=cfg.foldername,
            exposure = cfg.exposure_ms,
        )

        self.status_message.emit("Setup complete")
    

    @Slot()
    def start(self):
        if not getattr(self.engine, "_setup", False):
            self.status_message.emit("Not set up. Click Setup first.")
            self.running_changed.emit(False)
            return
        self.running_changed.emit(True)
        self.status_message.emit("Running…")
        self._poll_finished.start()
        self.engine.run_sequence()

    @Slot()
    def stop(self):
        self.status_message.emit("Stopping…")
        self.engine.request_stop()

    def _check_finished(self):
        # you already have: self._finished_event.set() at end of stop_sequence
        ev = getattr(self.engine, "_finished_event", None)
        if ev is not None and ev.is_set():
            self._poll_finished.stop()
            self.running_changed.emit(False)
            self.finished.emit()
            self.status_message.emit("Idle")