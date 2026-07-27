# %%
import sys
import os
os.environ["QT_API"] = "pyside6"

from qtpy.QtWidgets import QApplication
from Functions.VoiceCoil_nidaqmx import VoiceCoil_nidaqmx
from Functions.Acquisition import Acquisition
from Functions.stages_movement import stages_movement
from Main_window import MainWindow
def setup_classes(
):
    DAQ = VoiceCoil_nidaqmx()
    print('DAQ class initialized. Name: DAQ')
    stage = stages_movement()
    print('stage class initialized. Name: stage')
    MDA = Acquisition(stage,DAQ)
    print('Acquisition class initialized: Name: MDA')
    mmc = MDA.mmc
    print('Micromanager core initialized: Name: mmc')
    return DAQ, stage, MDA, mmc

def run(
):
    DAQ, stage, MDA, mmc = setup_classes()
    app = QApplication(sys.argv) 
    window = MainWindow(mmc, DAQ, stage, MDA)
    window.show() 
    print("about to start event loop")
    result = app.exec()
    print("app.exec() returned:", result)
    sys.exit(result)                  

if __name__ == '__main__':
    run()
