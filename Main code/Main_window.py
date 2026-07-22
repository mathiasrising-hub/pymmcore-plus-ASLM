from qtpy.QtWidgets import QMainWindow, QDockWidget
from qtpy.QtCore import Qt
from pymmcore_widgets import PropertyBrowser

from GUI_windows.Jog_panel import JogPanel
from GUI_windows.Acquisition_panel import AcquisitionPanel
from GUI_windows.debug_console import DebugConsole
from GUI_windows.Image_panel import ImageFrame
class MainWindow(QMainWindow):
    def __init__(self, core, DAQ, stage, MDA):
        super().__init__()
        self.setWindowTitle("Light Sheet Control")
        self.DAQ, self.stage, self.MDA = DAQ, stage, MDA

        self.image_frame = ImageFrame(core)
        self.setCentralWidget(self.image_frame)


        stage_dock = self._add_dock("Stage Jog", JogPanel(stage), Qt.LeftDockWidgetArea)
        self.acquisition_panel = AcquisitionPanel(acquisition_controller=self.MDA)
        acquisition_dock = self._add_dock("Acquisition", self.acquisition_panel, Qt.RightDockWidgetArea)

        self.acquisition_panel.acquisition_running_changed.connect(
            self.image_frame.set_acquisition_running
        )
        camera_prop_dock = self._add_dock("Camera Properties", PropertyBrowser(mmcore=core), Qt.RightDockWidgetArea)
        self.showMaximized()
        self.console = DebugConsole(stage=stage, DAQ=DAQ, MDA=MDA, mmc=core)
        console_dock = self._add_dock("Debug Console", self.console, Qt.BottomDockWidgetArea)
        dock_width = self.width() // 4  
        self.resizeDocks([stage_dock, camera_prop_dock, acquisition_dock], [dock_width, dock_width, dock_width], Qt.Horizontal)
        self.resizeDocks([console_dock], [self.height() // 4], Qt.Vertical)
  


    def _add_dock(self, title, widget, area):
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        return dock
    
    def closeEvent(self, event):
        self.MDA.close()

        print("closeEvent: shutting down console")
        self.console.shutdown()
        print("closeEvent: console shut down")

        event.accept()

        import threading
        print("Alive threads before exit:")
        for t in threading.enumerate():
            print(f"  name={t.name!r}  daemon={t.daemon}  alive={t.is_alive()}  ident={t.ident}")

        import os
        os._exit(0)