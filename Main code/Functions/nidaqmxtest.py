import nidaqmx
import numpy as np

task_co = nidaqmx.Task()
task_co.co_channels.add_co_pulse_chan_freq('Dev1/ctr0', name_to_assign_to_channel='pulse_gen', freq=1, duty_cycle=0.1)
task_co.timing.cfg_implicit_timing(nidaqmx.constants.AcquisitionType.CONTINUOUS)


cali_path = 'C:/Users/plexus/Documents/Lin-Sandbox/playwaveform.txt'
ao_waveform = np.loadtxt(cali_path)
voicecoil_samplingrate = 10000
task_ao = nidaqmx.Task()
task_ao.ao_channels.add_ao_voltage_chan('Dev1/ao0', 'ao0')
task_ao.timing.cfg_samp_clk_timing(voicecoil_samplingrate, # this AO task is driven by the onboard clock at this sampling rate
                                   sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                   samps_per_chan=ao_waveform.shape[0])
task_ao.write(ao_waveform, False) # "False" means the data is not automatically sent to the device

# PFI12 is the counter output channel; used here for triggering the AO task:
task_ao.triggers.start_trigger.cfg_dig_edge_start_trig('/Dev1/PFI12', nidaqmx.constants.Edge.RISING)
task_ao.triggers.start_trigger.retriggerable = True


task_ao.start()
task_co.start()

import time
time.sleep(10)

# task_do.stop()
task_ao.stop()
task_co.stop()
# task_do.close()
task_co.close()
task_ao.close()
