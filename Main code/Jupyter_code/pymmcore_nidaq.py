from pymmcore_plus import CMMCorePlus, mda
from useq import MDAEvent
mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration('c:/users/scape20/documents/scape-yale-NIDAQ.cfg')

cam = mmc.getCameraDevice()
mmc.setProperty(cam, 'TriggerMode', 'External')

# mmc.setProperty('NIDAQDO-Dev1/port0', 'Blanking', 'On')

from useq import MDASequence
mda_sequence = MDASequence(axis_order='zc', channels=['Green','Red'], z_plan={"range": 400, "step": 1})
# use 'axis_order="zc", channels=[..,..]' to make channel change fastest

# opt-in hardware trigger:
# mmc.mda.engine.use_hardware_sequencing = True # redundant if myEngine is used below

from pymmcore_plus.core._sequencing import SequencedEvent
import nidaqmx
task_co = nidaqmx.Task()
task_co.co_channels.add_co_pulse_chan_freq('Dev1/ctr0', name_to_assign_to_channel='trigger_gen', freq=50)
mmc.setExposure(15)
task_co.timing.cfg_implicit_timing(nidaqmx.constants.AcquisitionType.FINITE,
                                   mda_sequence.shape[0] * mda_sequence.shape[1]+1)

class EngineWithPulse(mda.MDAEngine):
    def __init__(self, mmc: CMMCorePlus, use_hardware_sequencing: bool, pulsetask) -> None:
        super().__init__(mmc)
        self.use_hardware_sequencing = use_hardware_sequencing
        self.task_co = pulsetask
    # def post_sequence_started(self, event: SequencedEvent) -> None:
    #     self.task_co.start()

myEngine = EngineWithPulse(mmc, True, task_co)
mmc.register_mda_engine(myEngine)
mmc.run_mda(mda_sequence)  # add 'output=' parameter to handle output image
task_co.start()

task_co.wait_until_done(100)
mmc.stopSequenceAcquisition()
task_co.stop()
task_co.close()
