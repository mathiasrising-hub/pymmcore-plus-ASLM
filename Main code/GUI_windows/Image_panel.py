from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from pymmcore_widgets import ImagePreview, LiveButton, SnapButton


class ImageFrame(QWidget):
    """Image preview with snap/live controls stacked above it."""

    def __init__(self, core):
        super().__init__()
        self._core = core
        self.preview = ImagePreview(mmcore=core)
        self.snap_button = SnapButton(mmcore=core)
        self.live_button = LiveButton(mmcore=core)

        button_row = QHBoxLayout()
        button_row.addWidget(self.snap_button)
        button_row.addWidget(self.live_button)
        button_row.addStretch()  # pushes buttons left, avoids them stretching full-width

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self.preview)
    def set_acquisition_running(self, running: bool):
        # 1) Make sure "Live" is off while you acquire
        if running:
            try:
                # MMCore API (common): stopSequenceAcquisition
                self._core.stopSequenceAcquisition()
            except Exception:
                pass

            # In case widgets maintain their own state/timers, prevent user interaction
            self.live_button.setEnabled(False)
            self.snap_button.setEnabled(False)
            self.preview.setEnabled(False)
        else:
            self.live_button.setEnabled(True)
            self.snap_button.setEnabled(True)
            self.preview.setEnabled(True)