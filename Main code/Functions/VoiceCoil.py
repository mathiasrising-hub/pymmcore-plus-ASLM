#!/usr/bin/env python
# coding: utf-8

# In[2]:


import ctypes as ct
import warnings
from typing import Sequence

import numpy as np
import PyDAQmx as daqmx


# In[ ]:


# Suppress warning for stoping AO waveform before all samples are sent
warnings.filterwarnings("ignore", category=daqmx.DAQmxFunctions.StoppedBeforeDoneWarning)
_instance_daq = None


# In[1]:


class DAQ_VC:
  
    """Class to control the Voice coil at the pan-ASLM in Bewersdorf Lab. The code is based on code from Arizona state university qi2lab. 
    
    This code was originally developed to control galvo mirrors using a DAQ to load waveform functions and using the camera output to trigger the waveform function.
    
    The code is developed with multiple modes possible. Since this will only be used as a function to load and start the sweep, only one mode is programmed.
    If more modes are needed, a new "scan_type" should be defined and under relevant functions an "if scan_type == your_scan_type" can be implemented.
    
    This code is supposed to be called before image acquisition begins to load in the most recent calibration file, for the correct fps.
    
    The code does not yet have functionality to produce a calibration file itself, and is agnostic to settings done in pymmcore-plus. 
    
    The last edit of this description was at 06/16/2026.
    
    ----------
    scan_type: str, default = "projection"
        scan type
    calib_path: str, default = "C:\\Users\\Hannah\\Desktop\\calibration files_1fps_24ms.txt"
        path to the calibration file
    projection_mirror_neutral_v: float, default = 0.725 V
        The netrual position of the voice coil. 725 mV is the middle of the FoV for last calibration
    laser_blanking: bool, default = True
        synchronize laser output to the camera rolling shutter being fully open. For fast imaging, this likely needs to be `False`
    """

    @classmethod
    def instance(cls) -> 'DAQ_VC':
        """Return the global singleton instance of `DAQ_VC`.
        """

        global _instance_daq
        if _instance_daq is None:
            _instance_daq = cls()
        return _instance_daq

    def __init__(
        self,
        name = "Dev1",
        scan_type: str = "projection",
        exposure_ms: float = 50.,
        laser_blanking: bool = True,
        #image_mirror_calibration: float = .0433,
        #projection_mirror_calibration: float = .0052,
        #image_mirror_neutral_v: float = 0.725,
        projection_mirror_neutral_v: float = 0.725,
        #image_mirror_step_um = 0.4,
        verbose: bool=False
    ):
        
        # Set the first instance of this class as the global singleton
        global _instance_daq
        if _instance_daq is None:
            _instance_daq = self
        
        self.scan_type = scan_type
        self.exposure_ms = exposure_ms
        self.laser_blanking = laser_blanking
        #self.image_mirror_calibration = image_mirror_calibration
        #self.projection_mirror_calibration = projection_mirror_calibration
        #self.image_mirror_step_um = image_mirror_step_um
        self.verbose = verbose
        
        # Define waveform generation parameters
        self._daq_sample_rate_hz = 10000
        self._do_ind = [0,1,2,3,4]
        self._channel_states = [False, False, False, False, False]
        self._active_channels_indices = None
        self._n_active_channels = 0
        self._num_do_channels = 8
        self._cali_path = "E:\\2026-06-03\\calibration files\\calibration files_1fps_24ms"
        self._do_waveform = np.zeros((self._num_do_channels),dtype=np.uint8)
        self._ao_waveform = [np.zeros(1)]
        self._ao_neutral_positions = [projection_mirror_neutral_v]
        
        # Configure hardware pin addresses.
        self._dev_name = name
        # Program DO port0 using 8-bit waveforms
        ##self._address_channel_do = "/Dev1/port0/line0:7" # laser lines 0:4
        ##self._address_ao_mirrors = [
        ##    "/Dev1/ao0", # image scanning galvo
        ##    "/Dev1/ao1" # projection scanning galvo
        ##]
        self._address_ao_mirrors = [
            "/Dev1/ao0" # Voice coil
        ]
        self._channel_di_trigger_from_camera = "/Dev1/PFI0" # camera trig port 0
        self._channel_di_start_trigger = "/Dev1/PFI1" # Empty PFI pin
        self._channel_di_change_trigger = "/Dev1/PFI2" # Empty PFI pin
        self._channel_ao_start_trigger = "/Dev1/PFI0" # Route channel_do_trigger
        
        # task handles
        self._task_do = None
        self._task_ao = None
        self._task_di = None

        # daq running
        self._running = False
        
    @property
    def scan_type(self) -> str:
        """Scan type.
        
        Returns
        -------
        scan_type: str
            scan type. One of "2d", "mirror", "projection", or "stage"
        """
        
        return getattr(self,"_scan_type",None)
    @scan_type.setter
    def scan_type(self, value: str):
        """Set the scan type.
        
        Parameters
        ----------
        value: str
            scan type. One of "2d", "mirror", "projection", or "stage
        """
        
        if not hasattr(self, "_scan_type") or self._scan_type is None:
            self._scan_type = value
        else:
            self._scan_type = value
    @property
    def exposure_ms(self) -> float:
        """Exposure time in milliseconds.
        
        Returns
        -------
        exposure_ms: float
            exposure time in units of milliseconds.
        """
        
        return getattr(self,"_exposure_s",None) * 1000.
    
    @exposure_ms.setter
    def exposure_ms(self, value: float):
        """Set the exposure time in milliseconds.
        
        Parameters
        ----------
        value: float
            exposure time in units of milliseconds.
        """
        
        if not hasattr(self, "_exposure_s") or self._exposure_s is None:
            self._exposure_s = value / 1000.
        else:
            self._exposure_s = value / 1000.
            
    @property
    def laser_blanking(self) -> bool:
        """Laser blanking state.
        
        Returns
        -------
        laser_blanking: bool
            Laser blanking state: Active (True) or Inactive (False) 
        """
        
        return getattr(self,"_laser_blanking",None)
    
    @laser_blanking.setter
    def laser_blanking(self, value: bool):
        """Set the exposure time in milliseconds.
        
        Parameters
        ----------
        value: bool
            Laser blanking state: Active (True) or Inactive (False) 
        """
        
        if not hasattr(self, "_laser_blanking") or self._laser_blanking is None:
            self._laser_blanking = value
        else:
            self._laser_blanking = value
            
    @property
    def image_mirror_range_um(self) -> float:
        """Image mirror sweep in microns.
        
        This is the lateral footprint of sweep, symmetric around the zero point, along the coverslip.
        
        Returns
        -------
        image_mirror_range_um: float
            Image mirror sweep in microns.
        """
        
        return getattr(self,"_image_mirror_range_um",None)
    
    @image_mirror_range_um.setter
    def image_mirror_range_um(self, value: float):
        """Set the image mirror sweep in microns.
        
        Parameters
        ----------
        value: float
            Image mirror sweep in microns.
        """
        
        if not hasattr(self, "_image_mirror_range_um") or self._image_mirror_range_um is None:
            self._image_mirror_range_um = value
        else:
            self._image_mirror_range_um = value

        # setup image galvo mirror
        self._image_mirror_min_volt = -(self._image_mirror_range_um * self._image_mirror_calibration) / 2. + self._ao_neutral_positions[0] # unit: volts
        self._image_axis_range_volts = self._image_mirror_range_um * self._image_mirror_calibration
        self._image_scan_steps = int(np.rint(self._image_axis_range_volts / self._image_axis_step_volts)) # galvo steps

        # setup projection galvo mirror
        self._projection_scan_range_volts = self._image_mirror_range_um * self._projection_mirror_calibration
        
    @property
    def n_scan_steps(self) -> int:
        """Image mirror scan steps.
        
        Returns
        -------
        n_scan_steps: int
            Number of scan steps for a mirror sweep.
            
        """
        
        return int(getattr(self,"_image_scan_steps",None))
            
    @property
    def channel_states(self) -> Sequence:
        """Active channel states.
        
        Returns
        -------
        channel_states: Sequence
            Boolean array of active laser lines
        """
        
        return getattr(self,"_channel_states",None)
    
    @channel_states.setter
    def channel_states(self, value: Sequence):
        """Set the active channel states.
        
        Parameters
        ----------
        value: Sequence
            Boolean array of active laser lines.
        """
        
        if not hasattr(self, "_channel_states") or self._channel_states is None:
            self._channel_states = value
        else:
            self._channel_states = value
        
        self._active_channels_indices = [ind for ind, st in zip(self._do_ind, self._channel_states) if st]
        self._n_active_channels = len(self._active_channels_indices)

    @property
    def cali_path(self) -> str:
        return getattr(self,'_cali_path',None)
    
    @cali_path.setter
    def cali_path(self, value: str):
        """Set path to the calibration file.
        
        Parameters
        ----------
        value: str
            config path. A valid path to a 
        """
        _check = np.loadtxt(value)
        if _check.dtype == np.float64 and np.all(isfinite(_check)):
            self._cali_path = value
        else:
            return print('Not a valid path')

    def running(self) -> bool:
        """Returns true is playback is active, false otherwise"""
        
        return self._running
    
    #-----------------------------------------------------#
    # Helper function for setting daq values
    #-----------------------------------------------------#
        
    def set_acquisition_params(
        self,
        scan_type: str = None,
        channel_states: Sequence[bool] = None,
        laser_blanking: bool = None,
        exposure_ms: float = None
    ):
        """Convenience function to set the DAQ up for an acquisition.
        
        
        Parameters
        ----------
        scan_type: str
            scan type. One of "2d", "mirror", "projection", or "stage"
        channel_states: Sequence[bool]
            channel states, in order of [405nm, 488nm, 561nm, 637nm, 730nm].
        image_mirror_step_um: float
            Image mirror step size in microns. This is the lateral footprint along the coverslip.
        image_mirror_range_um: float
            Image mirror sweep in microns.
        laser_blanking: bool
            Laser blanking state: Active (True) or Inactive (False) 
        exposure_ms: float
            camera exposure time in milliseconds.
        """

        if scan_type:
            self.scan_type=scan_type
        if channel_states:
            self.channel_states = channel_states
        if laser_blanking:
            self.laser_blanking = laser_blanking
        if exposure_ms:
            self.exposure_ms = exposure_ms
    #-----------------------------------------------------#
    # Reset device methods
    #-----------------------------------------------------#
    
    def reset(self):
        """Reset the device."""

        daqmx.DAQmxResetDevice(self._dev_name)
        self.reset_ao_channels()

    def reset_ao_channels(self):
        """Stops any waveforms and deletes tasks, set analog lines to the mirror's neutral positions
        """
        self.clear_tasks()
        
        _ao_waveform = np.column_stack((np.full(1, self._ao_neutral_positions[0])))

        samples_per_ch_ct = ct.c_int32()
        try:
            with daqmx.Task("ResetAO") as _task:
                _task.CreateAOVoltageChan(
                    self._address_ao_mirrors[0], 
                    "reset_ao0", 
                    -0.5, 1.0, daqmx.DAQmx_Val_Volts, None
                )
                _task.WriteAnalogF64(
                    1, 
                    True, 
                    1, 
                    daqmx.DAQmx_Val_GroupByScanNumber, 
                    _ao_waveform, 
                    ct.byref(samples_per_ch_ct), None
                )
                _task.StopTask()
                _task.ClearTask()
        except (daqmx.DAQmxFunctions.InvalidTaskError, AttributeError):
            pass
      

    def program_daq_waveforms(self):
        """Create DAQ tasks for synchronizing camera output triggers to lasers and galvo mirrors."""
        
            #-------------------------------------------------#
            # Create AO tasks, dependent on acquisition scan mode
            # first, set the scan and projection galvo to the initial point if it is not already
        self._ao_waveform = np.loadtxt(self._cali_path)
        self._ao_waveform = np.delete(self._ao_waveform,range(self._ao_waveform.shape[0]-40,self._ao_waveform.shape[0]-10))
        samples_per_ch_ct = ct.c_int32()
        with daqmx.Task("TaskInitAO") as _task:
            # Create a 2d array that sets the initial AO voltage to the start of the scan.
            initial_ao_waveform = (
                np.full(1, self._ao_waveform[0]))
            _task.CreateAOVoltageChan(
                self._address_ao_mirrors[0], 
                "initialize_ao0", 
                -0.5, 
                1.0, 
                daqmx.DAQmx_Val_Volts, 
                None
                )
            _task.WriteAnalogF64(
                1, 
                True, 
                1, 
                daqmx.DAQmx_Val_GroupByScanNumber, 
                initial_ao_waveform, 
                ct.byref(samples_per_ch_ct), 
                None
            )
            _task.StartTask()
            _task.StopTask()
            _task.ClearTask()

            # Create and configure timing for AO tasks
            if self._task_ao is None:
                self._task_ao = daqmx.Task("TaskAO")
                self._task_ao.CreateAOVoltageChan(
                    self._address_ao_mirrors[0], 
                    "AO_ImageScanning", 
                    -0.5, 
                    1.1, 
                    daqmx.DAQmx_Val_Volts, 
                    None
                )
                
            if self.scan_type=="projection":
            # NOTE: 'projection' mode can be interweaved as the AO channels are
            #       triggered by the change in DO lines!
            # Configure to run on internal clock, ao_waveform has shape dictated
            # by camera exposure
                self._task_ao.CfgSampClkTiming(
                    "",
                    self._daq_sample_rate_hz,  # Define how fast the samples are output
                    daqmx.DAQmx_Val_Rising,
                    daqmx.DAQmx_Val_FiniteSamps,  # Output finite number of samples
                    self._ao_waveform.shape[0] # Total samples
                )  

                # Configure AO to start on the rising edge of DI signal
                self._task_ao.CfgDigEdgeStartTrig(
                    self._channel_di_trigger_from_camera,
                    daqmx.DAQmx_Val_Rising
                )

                # Make the task retriggerable, for every exposure
                self._task_ao.SetStartTrigRetriggerable(True)

            # Write waveforms
            if self.scan_type=="projection":                
                # Write the output waveform
                samples_per_ch_ct = ct.c_int32()
                self._task_ao.WriteAnalogF64(
                    self._ao_waveform.shape[0],
                    False, 
                    10.0, 
                    daqmx.DAQmx_Val_GroupByScanNumber, 
                    self._ao_waveform, 
                    ct.byref(samples_per_ch_ct), 
                    None
                )                
        
    def start_waveform_playback(self):
        """Starts any tasks that exist."""
        
        # if already running, stop playback
        if self._running:
            self.stop_waveform_playback()
        try:
            for _task in [self._task_di, self._task_do, self._task_ao]:
                if _task:
                    _task.StartTask()
            # set running flag
            self._running = True
        except (daqmx.DAQmxFunctions.InvalidTaskError, AttributeError):
            pass

    def stop_waveform_playback(self):
        """Stop any tasks that exist."""
        if self._running:
            try:
                for _task in [self._task_di, self._task_do, self._task_ao]:
                    if _task:
                        _task.StopTask()
                self._running = False
            except (daqmx.DAQmxFunctions.InvalidTaskError, AttributeError):
                pass
      
    def clear_tasks(self):
        """Stop, Clear and remove task handlers."""
        
        # if already running, stop playback
        if self._running:
            self.stop_waveform_playback()
        try:
            for task_name in ["_task_di", "_task_do", "_task_ao"]:
                if hasattr(self, task_name):
                    task = getattr(self, task_name)
                    if task is not None:
                        # task.StopTask()
                        task.ClearTask()
                    setattr(self, task_name, None) 
            self._running = False
        except (daqmx.DAQmxFunctions.InvalidTaskError, AttributeError):
            pass
        
    def __del__(self):
        """Set DO to 0s, AO to neutral positions, clear tasks."""
        
        self.reset()     







