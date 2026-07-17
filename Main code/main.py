# %%

from Functions.VoiceCoil_nidaqmx import VoiceCoil_nidaqmx
from Functions.Acquisition import Acquisition
from Functions.stages_movement import stages_movement

def run(
):
    DAQ = VoiceCoil_nidaqmx()
    print('DAQ class initialized. Name: DAQ')
    stage = stages_movement()
    print('stage class initialized. Name: stage')
    MDA = Acquisition(stage,DAQ)
    print('Acquisition class initialized: Name: MDA')
    return DAQ, stage, MDA

if __name__ == '__main__':
    DAQ, stage, MDA = run()
# %%
MDA.save = True
MDA.exposure = 0.44
MDA.silence = True
DAQ.cali_path = "E:\\2026-6-17\\calibration file_5fps_24ms_2"

MDA.setup_sequence(z_depth = 0.1, x_tiles = 2, y_tiles = 2, channels = ['488','560','640'])
print(MDA._stack_height)

# %%
MDA.run_sequence()

# %%
MDA.stop_sequence()

# %%
stage.move_home()

# %%
MDA.close()

# %%
