#!/usr/bin/env python
# coding: utf-8

# In[5]:


import nidaqmx
import numpy as np
import warnings
warnings.simplefilter("ignore", nidaqmx.errors.DaqResourceWarning)


# In[6]:


class DAQ:
    def __init__(
        self,
        name: str = "Dev1/",
        mirror_neutral_v: float = 0.725,
        cali_path: str = "E:\\2026-06-03\\calibration files\\calibration files_1fps_24ms",
        sample_rate: float = 10000
        ):
        
        # Define waveform generation parameters
        self._daq_sample_rate_hz = sample_rate
        self._cali_path = cali_path
        self._do_waveform = [np.zeros(1)]
        self._ao_waveform = [np.zeros(1)]
        self._ao_neutral_positions = [mirror_neutral_v]
        
        
        # Configure hardware pin addresses.
        self._dev_name = name
        self._address_ao_mirror = 'ao0'
        self._address_do_ctr = 'ctr0'
        self._channel_di_trigger_from_camera = "PFI0" # camera trig port 0
        self._channel_co0_output = "PFI12" # Counter 0 output channel for pulse generation to trigger the AO task

        # task handles
        self._task_co = None
        self._task_ao = None
        # daq running
        self._running = False
    @property
    def name(self) -> str:
        
        return getattr(self,"_dev_name",None)
    @name.setter
    def name(self, value: str):
        
        self._dev_name = value
            
    @property
    def mirror_neutral_v(self) -> float:
        
        return getattr(self,"_ao_neutral_positions",None)
    @mirror_neutral_v.setter
    def mirror_neutral_v(self, value: float):
        
        self._ao_neutral_positions = value
            
    @property
    def cali_path(self) -> str:
        
        return getattr(self,"_cali_path",None)
    @cali_path.setter
    def cali_path(self, value: str):
        
        self._cali_path = value
    @property
    def sample_rate(self) -> float:
        
        return getattr(self,"_daq_sample_rate_hz",None)
    @sample_rate.setter
    def sample_rate(self, value: float):
        
        
        self._daq_sample_rate_hz = value
            
    def program_waveforms(self):
        if self._task_co is not None:
            try:
                self._task_co.close()
            except Exception as e:
                print(f'Could not close co task: {e}')
        if self._task_ao is not None:
            try:
                self._task_ao.close()
            except Exception as e:
                print(f'Could not close ao task: {e}')
        
        self._task_co = nidaqmx.Task()
        co_address = self._dev_name + self._address_do_ctr
        
        self._task_ao = nidaqmx.Task()
        ao_address = self._dev_name + self._address_ao_mirror
        
        ao_waveform = np.loadtxt(self._cali_path)
        frequency = self._daq_sample_rate_hz / len(ao_waveform)
        co0_address = '/' + self._dev_name + self._channel_co0_output
        
        self._task_co.co_channels.add_co_pulse_chan_freq(co_address, name_to_assign_to_channel='pulse_gen', freq=frequency, duty_cycle=0.1)
        self._task_co.timing.cfg_implicit_timing(nidaqmx.constants.AcquisitionType.CONTINUOUS)
        
        
        
        self._task_ao.ao_channels.add_ao_voltage_chan(ao_address, self._address_ao_mirror)
        self._task_ao.timing.cfg_samp_clk_timing(self._daq_sample_rate_hz, # this AO task is driven by the onboard clock at this sampling rate
                                           sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                           samps_per_chan=ao_waveform.shape[0])
        # PFI12 is the counter output channel; used here for triggering the AO task:
        self._task_ao.triggers.start_trigger.cfg_dig_edge_start_trig(co0_address, nidaqmx.constants.Edge.RISING)
        self._task_ao.triggers.start_trigger.retriggerable = True
        
        self._task_ao.write(ao_waveform, False) # "False" means the data is not automatically sent to the device
        #self._task_ao.control(nidaqmx.constants.TaskMode.TASK_COMMIT)


    
    def close(self):
        try:
            self._task_co.close()
        except Exception as e:
            print(f'Could not close co task: {e}')
        try:
            self._task_ao.close()
        except Exception as e:
            print(f'Could not close ao task: {e}')
        self._task_co = None
        self._task_ao = None
        
    def start(self):
        try:
            self._task_ao.start()
            self._task_co.start()

        except Exception as e:
            print(f'Could not start tasks: {e}')
    
    def stop(self):
        try:
            self._task_co.stop()
        except Exception as e:
            print(f'Could not stop co task: {e}')
        try:
            self._task_ao.stop()
        except Exception as e:
            print(f'Could not stop ao task: {e}')
  


# In[15]:





# In[16]:





# In[ ]:




