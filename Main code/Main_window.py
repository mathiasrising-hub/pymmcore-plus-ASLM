from qtpy.QtWidgets import QMainWindow, QDockWidget
from qtpy.QtCore import Qt
from pymmcore_widgets import PropertyBrowser, ImagePreview

from GUI_windows.Jog_panel import JogPanel
from GUI_windows.Acquisition_panel import AcquisitionPanel
from GUI_windows.debug_console import DebugConsole

class MainWindow(QMainWindow):
    def __init__(self, core, DAQ, stage, MDA):
        super().__init__()
        self.setWindowTitle("Light Sheet Control")
        self.DAQ, self.stage, self.MDA = DAQ, stage, MDA

        self.setCentralWidget(ImagePreview(mmcore=core))

        self._add_dock("Stage Jog", JogPanel(stage), Qt.LeftDockWidgetArea)
        self._add_dock("Acquisition", AcquisitionPanel(MDA), Qt.RightDockWidgetArea)
        self._add_dock("Camera Properties", PropertyBrowser(mmcore=core), Qt.RightDockWidgetArea)

        self.console = DebugConsole(stage=stage, DAQ=DAQ, MDA=MDA, mmc=core)
        self._add_dock("Debug Console", self.console, Qt.BottomDockWidgetArea)  

    def _add_dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)

    def closeEvent(self, event):
        """Ensure hardware shuts down cleanly when the window closes."""
        self.MDA.close()
        self.console.shutdown()
        event.accept()