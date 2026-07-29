from qtpy.QtCore import Signal, Qt, QTimer
from qtpy.QtWidgets import (
    QWidget, QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QProgressBar, QFileDialog
)
from pathlib import Path
from .acq_config import AcqConfig

class AcquisitionPanel(QWidget):
    # MainWindow can connect to these to disable ImagePreview, etc.
    acquisition_running_changed = Signal(bool)   # True when running, False when not
    status_message = Signal(str)                 # optional: forward log text/messages

    def __init__(self, acquisition_controller, parent=None):
        """
        acquisition_controller: your acquisition object with methods:
          - setup_sequence(config)
          - run_sequence(config)   (should return quickly / start threads)
          - request_stop() or stop_sequence()
        For now, it can be a placeholder object; well wire calls later.
        """
        super().__init__(parent)
        self.acq = acquisition_controller
        self._running = False
        self._total_frames = 0

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(200)
        self._progress_timer.timeout.connect(self._poll_progress)

        
        # ---- Left: Parameters ----
        params_box = QGroupBox("Acquisition Parameters")
        params_layout = QFormLayout(params_box)

        # Example parameters (replace/extend with your real ones)
        self.exposure_ms = QDoubleSpinBox()
        self.exposure_ms.setRange(0.01, 10000.0)
        self.exposure_ms.setDecimals(3)
        self.exposure_ms.setValue(10.0)

        self.z_depth = QDoubleSpinBox()
        self.z_depth.setRange(0.01, 10000.0)
        self.z_depth.setDecimals(3)
        self.z_depth.setValue(0.1)

        self.z_stepsize = QDoubleSpinBox()
        self.z_stepsize.setRange(0.00001, 10000.0)
        self.z_stepsize.setDecimals(6)
        self.z_stepsize.setValue(0.0002)

        self.X_tiles = QSpinBox()
        self.X_tiles.setRange(1, 1000)
        self.X_tiles.setValue(1)

        self.Y_tiles = QSpinBox()
        self.Y_tiles.setRange(1, 1000)
        self.Y_tiles.setValue(1)


        self.save_path = QLineEdit()
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_save_path)

        save_row = QHBoxLayout()
        save_row.addWidget(self.save_path, 1)
        save_row.addWidget(browse_btn, 0)

        self.ch_488 = QCheckBox("488")
        self.ch_560 = QCheckBox("560")
        self.ch_640 = QCheckBox("640")
        self.ch_488.setChecked(True)
        self.saving = QCheckBox('Saving')
        self.saving.clicked.connect(self._save_toggle)

        ch_row = QHBoxLayout()
        ch_row.addWidget(self.ch_488)
        ch_row.addWidget(self.ch_560)
        ch_row.addWidget(self.ch_640)
        ch_row.addStretch(1)

        params_layout.addRow("Exposure (ms)", self.exposure_ms)
        params_layout.addRow("Z_stepsize (mm)", self.z_stepsize)
        params_layout.addRow('Z_depth (mm)', self.z_depth)
        params_layout.addRow("X tiles", self.X_tiles)
        params_layout.addRow("Y tiles", self.Y_tiles)
        params_layout.addRow("Enabled", self.saving)
        params_layout.addRow("Save to", save_row)
        params_layout.addRow("Channels", ch_row)

        # ---- Top-right: Status ----
        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)

        self.status_label = QLabel("Idle")
        self.status_label.setWordWrap(True)

        # connect bridge -> panel UI state
        self.acq.running_changed.connect(self._on_running_changed)
        self.acq.status_message.connect(self.status_label.setText)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        self.frame_counter = QLabel("Frame: 0 / 0")

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress)
        status_layout.addWidget(self.frame_counter)
        status_layout.addStretch(1)

        # ---- Bottom-right: Controls ----
        controls_box = QGroupBox("Controls")
        controls_layout = QHBoxLayout(controls_box)

        self.setup_btn = QPushButton("Setup")
        self.start_btn = QPushButton("Start")
        self.stop_btn  = QPushButton("Stop")

        self.stop_btn.setEnabled(False)  # only enabled while running

        self.setup_btn.clicked.connect(self._on_setup)
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)

        controls_layout.addWidget(self.setup_btn)
        controls_layout.addWidget(self.start_btn)
        controls_layout.addWidget(self.stop_btn)

        # ---- Arrange: parameters left, status top-right, controls bottom-right ----
        right_col = QVBoxLayout()
        right_col.addWidget(status_box, 1)
        right_col.addWidget(controls_box, 0)

        main = QGridLayout(self)
        main.addWidget(params_box, 0, 0, 2, 1)     # spans rows; left side tall
        main.addLayout(right_col, 0, 1, 2, 1)

        main.setColumnStretch(0, 2)  # parameters wider
        main.setColumnStretch(1, 1)  # right column narrower
        main.setRowStretch(0, 1)

        self._set_ui_running(False)

    # ----------------------------
    # UI helpers
    # ----------------------------
    def _browse_save_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select save folder")
        if folder:
            self.save_path.setText(folder)


    def _collect_config(self) -> AcqConfig:
        channels = []
        if self.ch_488.isChecked(): channels.append("488")
        if self.ch_560.isChecked(): channels.append("560")
        if self.ch_640.isChecked(): channels.append("640")
                
        cfg = AcqConfig(
            exposure_ms=float(self.exposure_ms.value()),
            z_depth=float(self.z_depth.value()),
            z_stepsize=float(self.z_stepsize.value()),
            x_tiles=int(self.X_tiles.value()),
            y_tiles=int(self.Y_tiles.value()),
            channels=channels,
            save_path=Path(self.save_path.text().strip()) if self.save_path.text().strip() else None,
            saving=bool(self.saving.isChecked()),
            filename="Zstack",
            foldername="Default",
        )
        cfg.validate()
        return cfg
    def _set_ui_running(self, running: bool):
        self._running = running

        # parameters locked while running
        self.exposure_ms.setEnabled(not running)
        self.save_path.setEnabled(not running)
        self.ch_488.setEnabled(not running)
        self.ch_560.setEnabled(not running)
        self.ch_640.setEnabled(not running)
                
        self.setup_btn.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    # ----------------------------
    # Button callbacks
    # ----------------------------
    def _on_setup(self):
        try:
            cfg = self._collect_config()
        except Exception as e:
            self.status_label.setText(f"Config error: {e}")
            return

        self.status_label.setText("Setup…")
        self.status_message.emit("Setup requested")
        self.acq.setup(cfg)

    def _save_toggle(self):
        engine = getattr(self.acq, "engine", None)
        engine._save = bool(self.saving.isChecked())

    def _on_start(self):
        try:
            cfg = self._collect_config()
        except Exception as e:
            self.status_label.setText(f"Config error: {e}")
            return

        engine = getattr(self.acq, "engine", None)
        total = int(getattr(engine, "_frames", 0)) if engine is not None else 0
        self.status_label.setText("Running…")
        self.progress.setValue(0)
        self.frame_counter.setText(f"Frame: 0 / {total if total else '?'}")

        self.acq.start()
    def _on_stop(self):
        self.status_label.setText("Stopping…")
        self.status_message.emit("Stop requested")
        self.stop_btn.setEnabled(False)  # avoid repeated clicks
        self.acq.stop()
        # do NOT finish UI here; wait for running_changed(False)

    def _finish_run_ui(self):
        self._set_ui_running(False)
        self.acquisition_running_changed.emit(False)
        self.status_label.setText("Idle")
    
    def _on_running_changed(self, running: bool):
        if running:
            self._set_ui_running(True)
            self.acquisition_running_changed.emit(True)
            self._progress_timer.start()
        else:
            self._progress_timer.stop()
            self._finish_run_ui()


    def _poll_progress(self):
        engine = getattr(self.acq, "engine", None)  # if bridge stores it as .engine
        if engine is None:
            engine = getattr(self.acq, "acq", None) # if you named it .acq
        if engine is None:
            return

        cur = int(getattr(engine, "_count", 0))
        total = int(getattr(engine, "_frames", 0))
        if total > 0:
            pct = min(100, int(cur * 100 / total))
            self.progress.setValue(pct)
            self.frame_counter.setText(f"Frame: {cur} / {total}")
        else:
            # unknown total
            self.frame_counter.setText(f"Frame: {cur}")