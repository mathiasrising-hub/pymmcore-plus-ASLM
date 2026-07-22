from qtpy.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

class CalibrateHomeDialog(QDialog):
    def __init__(self, stage_movement, parent=None):
        super().__init__(parent)
        self.stage = stage_movement
        self.setWindowTitle("Calibrate Home")
        self.setModal(True)

        self._step = 0
        self._pos_a = None
        self._pos_b = None

        self.msg = QLabel("Step 1/2:\nManually move to one edge, then click Capture.")
        self.capture = QPushButton("Capture")
        self.cancel = QPushButton("Cancel")

        self.capture.clicked.connect(self._on_capture)
        self.cancel.clicked.connect(self._on_cancel)

        row = QHBoxLayout()
        row.addWidget(self.capture)
        row.addWidget(self.cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.msg)
        layout.addLayout(row)

        self.stage.begin_set_home()

    def _on_capture(self):
        pos = self.stage.capture_set_home_edge()

        if self._step == 0:
            self._pos_a = pos
            self._step = 1
            self.msg.setText(
                f"Captured edge A: {pos:.4f}\n\n"
                "Step 2/2:\nManually move to the other edge, then click Capture."
            )
        else:
            self._pos_b = pos
            home, bounds = self.stage.finish_set_home()
            # optional: show a summary for confidence
            self.msg.setText(
                f"Captured edge B: {pos:.4f}\n\n"
                f"Home set to: {home}\nBounds: {bounds}"
            )
            self.accept()

    def _on_cancel(self):
        # decide what “cancel” means for your hardware:
        # safest is re-enable motors
        try:
            self.stage.enable_all()
        except Exception:
            pass
        self.reject()