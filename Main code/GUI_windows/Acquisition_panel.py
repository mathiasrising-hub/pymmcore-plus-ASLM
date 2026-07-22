from qtpy.QtCore import Signal, Qt
from qtpy.QtWidgets import (
    QWidget, QGroupBox, QGridLayout, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QProgressBar, QFileDialog
)

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
        For now, it can be a placeholder object; we’ll wire calls later.
        """
        super().__init__(parent)
        self.acq = acquisition_controller
        self._running = False

        # ---- Left: Parameters ----
        params_box = QGroupBox("Acquisition Parameters")
        params_layout = QFormLayout(params_box)

        # Example parameters (replace/extend with your real ones)
        self.exposure_ms = QDoubleSpinBox()
        self.exposure_ms.setRange(0.01, 10000.0)
        self.exposure_ms.setDecimals(3)
        self.exposure_ms.setValue(10.0)

        self.n_frames = QSpinBox()
        self.n_frames.setRange(1, 10_000_000)
        self.n_frames.setValue(1000)

        self.save_path = QLineEdit()
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_save_path)

        save_row = QHBoxLayout()
        save_row.addWidget(self.save_path, 1)
        save_row.addWidget(browse_btn, 0)

        self.ch_488 = QCheckBox("488")
        self.ch_561 = QCheckBox("561")
        self.ch_488.setChecked(True)

        ch_row = QHBoxLayout()
        ch_row.addWidget(self.ch_488)
        ch_row.addWidget(self.ch_561)
        ch_row.addStretch(1)

        params_layout.addRow("Exposure (ms)", self.exposure_ms)
        params_layout.addRow("Frames", self.n_frames)
        params_layout.addRow("Save to", save_row)
        params_layout.addRow("Channels", ch_row)

        # ---- Top-right: Status ----
        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)

        self.status_label = QLabel("Idle")
        self.status_label.setWordWrap(True)

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

    def _collect_config(self) -> dict:
        # placeholder config container; you can switch to a dataclass later
        return {
            "exposure_ms": float(self.exposure_ms.value()),
            "n_frames": int(self.n_frames.value()),
            "save_path": self.save_path.text().strip(),
            "channels": {
                "488": self.ch_488.isChecked(),
                "561": self.ch_561.isChecked(),
            },
        }

    def _set_ui_running(self, running: bool):
        self._running = running

        # parameters locked while running
        self.exposure_ms.setEnabled(not running)
        self.n_frames.setEnabled(not running)
        self.save_path.setEnabled(not running)
        self.ch_488.setEnabled(not running)
        self.ch_561.setEnabled(not running)

        self.setup_btn.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    # ----------------------------
    # Button callbacks
    # ----------------------------
    def _on_setup(self):
        cfg = self._collect_config()
        self.status_label.setText("Setup…")
        self.status_message.emit("Setup requested")

        # call into your acquisition controller (wire later)
        if hasattr(self.acq, "setup_sequence"):
            self.acq.setup_sequence(cfg)

        self.status_label.setText("Setup complete")

    def _on_start(self):
        cfg = self._collect_config()

        self.status_label.setText("Running…")
        self.progress.setValue(0)
        self.frame_counter.setText(f"Frame: 0 / {cfg['n_frames']}")

        self._set_ui_running(True)
        self.acquisition_running_changed.emit(True)   # MainWindow disables ImagePreview

        # start acquisition (wire later)
        if hasattr(self.acq, "run_sequence"):
            self.acq.run_sequence(cfg)

    def _on_stop(self):
        self.status_label.setText("Stopping…")
        self.status_message.emit("Stop requested")

        # request stop (wire later; your code uses an event thread)
        if hasattr(self.acq, "request_stop"):
            self.acq.request_stop()
        elif hasattr(self.acq, "stop_sequence"):
            self.acq.stop_sequence()

        # For now we mark idle immediately. Later you can flip to idle only
        # after you get an "acquisition finished" signal from the worker.
        self._finish_run_ui()

    def _finish_run_ui(self):
        self._set_ui_running(False)
        self.acquisition_running_changed.emit(False)
        self.status_label.setText("Idle")