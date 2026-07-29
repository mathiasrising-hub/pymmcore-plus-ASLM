import nidaqmx
import numpy as np
import warnings
import time # not currently used
warnings.simplefilter("ignore", nidaqmx.errors.DaqResourceWarning)

class VoiceCoil_nidaqmx:
    '''
    Descriptive text last updated: 7/28/2026. Code by the Bewersdorf lab - Mathias Rising main author.
    
    This class is the class used for alle control of the DAQ currently implemented in the pan-ASLM.
    
    The main goal of this code is to set up the DAQ for acquisition. 
    
    Current main implementations are the setup for the individual pins for analog and digital output. 
    Analog controls the voice coil, while digital controls the blanking of the lasers
    
    There is also a trigger generated depending on the framerate of the calibration file.
    This is the master trigger for the camera.

    Lastly there is a digital input wired to the camera, This is what the acquisition links the callback function to.

    Right now some quirks are:
    - The calibration path does not have a GUI element, and needs to be set manually throught the terminal
    - The global blanking does not work during testing.
    - The individual blanking is not turned off when the acquisition ends.  
    '''
    def __init__(
        self,
        name: str = "Dev1/",
        mirror_neutral_v: float = 0.725,
        cali_path: str = "E:\\2026-6-17\\calibration file_1fps_24ms_2",
        sample_rate: float = 10000
        ):
        '''
        There is a lot of variable needed. 
        The important thing to not here is 2 part:
            
            This is where ALL the adresses for the different input and output are defined.
            Remember to define these to the relevant DAQ card used.

            The calibration path is the one defining feature for framerate every else.
            There also is no place to define in the calibration path through the GUI.
            The calibration is the one big question mark for future development. 
        '''
        #This is a currently unused definition to check if the setup has run. Later implemenation will add it to make sure DAQ doesn't run without proper setup.
        self._registered = False
        
        # Define a empty list to contain the tasks. Used to make sure every task gets stopped and/or closed even if parameters change. 
        self._all_tasks = []

        # These are all default parameters for the purposes of DAQ specifics. These can be defined when calling the class, or changed later.
        self._daq_sample_rate_hz = sample_rate
        self._cali_path = cali_path
        self._do_waveform = [np.zeros(1)]
        self._ao_waveform = [np.zeros(1)]
        self._ao_neutral_positions = [mirror_neutral_v]
        self._do_lines = ''
        self._ao_waveform = None
        self._channels_length = 1
        # These are all the pins currently in use of the DAQ. If one wants to change the wiring, they should change the value here. 
        # These are not supposed to be modified by the user, but should only be defined once when wiring is done
        self._dev_name = name
        self._address_ao_mirror = 'ao0' #This is the voice coil
        self._address_do_ctr = 'ctr0' #Trigger that triggers the camera
        self._address_do_ctr1 = 'ctr1' # Unused
        self._address_do_488 = 'port0/line24' #488 nm Laser
        self._address_do_560 = 'port0/line23' #560 nm Laser
        self._address_do_595 = 'port0/line20' #595 nm Laser
        self._address_do_640 = 'port0/line19' #640 nm Laser
        self._address_do_775 = 'port0/line18' #775 nm Laser (NB: Not currently implemented)
        self._address_do_ = 'port0/line17' #Arbitrary empty channel, for testing and/or coding exposure pauses in the setup. 
        self._address_blanking = 'port0/line30' #Global blanking channel
        self._channel_di_trigger_from_camera_1 = "PFI0" # Currently unused
        self._channel_co0_output = "PFI12" # Counter 0 output channel for pulse generation to trigger the AO task
        self._channel_co1_output = "PFI13"

        # Task handles. These are set to None by default so we can control if a task has been defined or not. 
        self._task_co = None
        self._task_co1 = None
        self._task_ao = None
        self._task_do = None
        self._task_do_488 = None
        self._task_do_560 = None
        self._task_do_595 = None
        self._task_do_640 = None
        self._task_do_775 = None
        self._task_do_ = None
        self._blank = None

        # Lastly These are currently unused, but are callouts to if the DAQ is running or if the DAQ has setup the save. 
        # This can be added later to avoid errors.
        self._running = False
        self._saving_function = None


    '''
    # We start by adding some easy way of changing the properties of the DAQ. This is mostly used in debugging as for normal use the default values are sufficient.
    # The exception is the calibration path, that needs to be set to the current depending on the framerate. 
    '''
    @property
    def name(self) -> str:
        # The name of the DAQ. The Default name is: "Dev1/"
        return getattr(self,"_dev_name",None)
    
    @name.setter
    def name(self, value: str):
        # The way to set the name of the DAQ, if ones DAQ is named differently. Called by: DAQ.name = 'My_custom_name'    
        self._dev_name = value
            
    @property
    def mirror_neutral_v(self) -> float:
        # The neutral position of the voice coil. Default value is: 0.725
        return getattr(self,"_ao_neutral_positions",None)
    
    @mirror_neutral_v.setter
    def mirror_neutral_v(self, value: float):
        # The neutral position of the voice coil. The neutral position is defined as being the middle of FoV. Called by: DAQ.mirror_neutral_v = My_value
        self._ao_neutral_positions = value
            
    @property
    def cali_path(self) -> str:
        # The path to the calibration file. The default path is: E:\\2026-06-03\\calibration files\\calibration files_1fps_24ms
        return getattr(self,"_cali_path",None)
    
    @cali_path.setter
    def cali_path(self, value: str):
        # The way to set a new calibration file. Called by: DAQ.cali_path = 'E:\\2026-06-03\\calibration files\\my_new_calibration'
        self._cali_path = value

    @property
    def sample_rate(self) -> float:
        # This is the sample rate of the board. Unless otherwise specified each operation runs at this rate. Default value is: 10000 Hz
        return getattr(self,"_daq_sample_rate_hz",None)
    
    @sample_rate.setter
    def sample_rate(self, value: float):
        # Set the default sample rate of the DAQ. This will influence the precision of the board. Called by: DAQ.sample_rate = new_rate
        self._daq_sample_rate_hz = value


    def _setup_cameras(
        self,
        cameras: int = 1
    ):
        # This function is setting up digital input for each camera in use. By default we only use 1 camera. 
        # This function works by identifying the number of cameras, and making a digital input for each of them. 
        # Currently the save function is not compatible with multiple cameras, so that needs to be modified in the future

        for i in range(cameras):
            # Name of the task, so that they have a different number
            task_name = f"_task_di_{i}"
            
            # The pin address. Currently they are ordered so the 1st camera is on port0/line0, 2nd camera is on port0/line1 and so on
            address =self._dev_name + f"port0/line{i}"

            #If a task already exists for the current pin, we want to close and remove it before. If it doesn't exist, then we will just pass
            try:
                old_task = getattr(self,task_name)
                old_task.close()
                self._all_tasks.remove(old_task)
            except AttributeError:
                pass

            #We start by defining the task by it's name and actually make it a nidaqmx.Task
            setattr(self, task_name, nidaqmx.Task())
            task = getattr(self,task_name)
            self._all_tasks.append(task)

            # Now we define the pin that the DAQ should expect and input from
            task.di_channels.add_di_chan(address)

            #Because we want it to react to a change in a signal, we set the detection timing to be the falling edge of digital signal at the pin.
            task.timing.cfg_change_detection_timing(
                rising_edge_chan="",
                falling_edge_chan=address,
                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS
            )

            #This is the saving function in the acqusition code. This is defined and input in the register_save function. 
            saving_function = self._saving_function

            #We define the callback function.
            # The callback function has the functionality of registering what should happen when a trigger is recieved from the camera.
            # In this case we want the saving function to save the image.
            def callback_function(
                _,
                __,
                callback_data
            ):
                saving_function()
                return 0
            
            # This is registering the expected event (a change detection event with a falling edge) and the function that should be triggered by that event
            task.register_signal_event(
                nidaqmx.constants.Signal.CHANGE_DETECTION_EVENT,
                callback_function
            )

    # This function takes the saving_function as input and runs the setup for the saving and cameras digital input settings.
    # This can also allow for different saving function if one needs to modify in the future (example being saving in a different file format)
    def register_save(
        self,
        saving_function,
        cameras: int = 1
    ):
        self._saving_function = saving_function
        self._setup_cameras(cameras)

                
    
    

    # This is the main function that programs all the outputs of the DAQ. 
    def program_waveforms(
        self,
        stack_height: int,
        channels: str = ['488'], #The channels used
        cameras: int = 1, #How may cameras are in use
        meta: int = 1 #How many times the acqusition should run
    ):
        
        self._channels_length = len(channels)
        #First off we want check if the output pins already ahve a task assigned. If they do, we want to close them to make sure no errors disrupt the code
        if self._task_co is not None:
            try:
                self._task_co.close()
                self._all_tasks.remove(self._task_co)
            except Exception as e:
                print(f'Could not close co task: {e}')

        if self._blank is not None:
            try:
                self._blank.close()
                self._all_tasks.remove(self._blank)
            except Exception as e:
                print(f"Blanking could not e closed: {e}")

        if self._task_do is not None:
            try:
                self._task_do.close()
                #self._all_tasks.remove(self._task_do)
            except Exception as e:
                print(f'Could not close do task: {e}')

        for chan in channels:
            task = getattr(self,f"_task_do_{chan}")
            if task is not None:
                try:
                    self.task.close()
                    self._all_tasks.remove(self.task)
                except Exception as e:
                    print(f'Could not close do task: {e}')

        if self._task_ao is not None:
            try:
                self._task_ao.close()
                self._all_tasks.remove(self._task_ao)
            except Exception as e:
                print(f'Could not close ao task: {e}')
        


        #Now we define the counter output task. This is just defining it as a task and setting up the pin address for it
        self._task_co = nidaqmx.Task()
        self._all_tasks.append(self._task_co)
        co_address = self._dev_name + self._address_do_ctr


        self._task_co1 = nidaqmx.Task()
        self._all_tasks.append(self._task_co1)
        co1_address = self._dev_name + self._address_do_ctr1


        #Now we define the analog output task. This is just defining it as a task and setting up the pin address for it
        self._task_ao = nidaqmx.Task()
        self._all_tasks.append(self._task_ao)
        ao_address = self._dev_name + self._address_ao_mirror
        
        self._blank = nidaqmx.Task()
        self._all_tasks.append(self._blank)
        blank_address = self._dev_name + self._address_blanking


        #First of we define the specifics of the waveforms and frequencies used.
        # The waveform is loaded in from the calibration path defined.
        # The frequency is calculated from the calibration file and the sample rate.
        # Important disclaimer: This code assumes a calibration file with length corresponding to the framerate and the sample rate.
        # Ex. 1 fps requires 10000 samples at 10000 sample rate. 2 fps requires 5000 and so on. 
        self._ao_waveform = np.loadtxt(self._cali_path)
        frequency = self._daq_sample_rate_hz / len(self._ao_waveform)
        self._co0_address = '/' + self._dev_name + self._channel_co0_output
        co1PFI_address = '/' + self._dev_name + self._channel_co1_output
        
        # Now we define the counter. The frequency is the one that decides the timing. This is calculated automatically as long as the calibration file and sample rate is set correctly
        #Next we set the timing to be continuous. THis means that it will run until stopped. Optimally later we may want to add it to be finite. 
        self._task_co.co_channels.add_co_pulse_chan_freq(co_address, name_to_assign_to_channel='pulse_gen', freq=frequency, duty_cycle=0.1)
        self._task_co.timing.cfg_implicit_timing(
            nidaqmx.constants.AcquisitionType.FINITE,
            stack_height
                                                 )
        

        #Now we define the analog output channel
        self._task_ao.ao_channels.add_ao_voltage_chan(ao_address, self._address_ao_mirror)
        #The timing is dependent on the sample rate. If we want fewer samples on the calibration file the sample rate can be changed. 
        self._task_ao.timing.cfg_samp_clk_timing(self._daq_sample_rate_hz, 
                                           sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                           samps_per_chan=self._ao_waveform.shape[0])
        # PFI12 is the counter output channel; used here for triggering the AO task:
        self._task_ao.triggers.start_trigger.cfg_dig_edge_start_trig(self._co0_address, nidaqmx.constants.Edge.RISING)
        #This is a very important settings as it means the sweep can be triggered multiple times. Very important to set to True
        self._task_ao.triggers.start_trigger.retriggerable = True
        
        #Now finally we can write the waveform to the analog pin. The second argument is to inform that it shouldn't start automatically.
        self._task_ao.write(self._ao_waveform, False)

        self._blank.do_channels.add_do_chan(blank_address)

        #Now we define the digital output task. this is a for loop as its dependent on the individual channels. 
        #Here we also want to define the task done
        # This is WIP
        
        if len(channels) >= 2:
            self._do_waveform = np.identity(len(channels), dtype = np.bool_)
            self._do_lines = ''
            address ="/Dev1/PFI0"
            for _n ,chan in enumerate(channels):
                if _n == 0:
                    self._do_lines += f"{self._dev_name}{getattr(self,f"_address_do_{chan}")}"
                else:
                    self._do_lines += f",{self._dev_name}{getattr(self,f"_address_do_{chan}")}"
            self._task_do = nidaqmx.Task()
            self._task_do.do_channels.add_do_chan(self._do_lines,line_grouping=nidaqmx.constants.LineGrouping.CHAN_PER_LINE)
            self._task_do.timing.cfg_samp_clk_timing(1000,
                                    source = address,
                                    active_edge= nidaqmx.constants.Edge.RISING,
                                    sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
            self._task_do.write(self._do_waveform, False)
            '''
            self._task_do.triggers.start_trigger.cfg_dig_edge_start_trig(
            '/Dev1/Ctr0InternalOutput',                               
            nidaqmx.constants.Edge.RISING
            )
            '''
        else:
            self._do_waveform = True
            self._do_lines = f"{self._dev_name}{getattr(self,f"_address_do_{chan}")}"
        

    #This function is pretty simple. We want to make sure we close each task, so they don't cause problems. 
    #This could be optimized using the self._all_tasks, but havent yet.
    def close(self,
              cameras: int = 1):
        try:
            self._task_co.close()
        except Exception as e:
            print(f'Could not close co task: {e}')
        try:
            self._task_ao.close()
        except Exception as e:
            print(f'Could not close ao task: {e}')
        try:
            self._task_do.close()
        except Exception as e:
            print(f'Could not close do task: {e}')
        try:
            self._blank.close()
        except Exception as e:
            print(f'Could not close blank task: {e}')
        try: 
            for i in range(cameras):
                task_name = f"_task_di_{i}"
                task = getattr(self,task_name)
                task.close()
                task = None
        except Exception as e:
            print(f'Could not close DI task: {e}')
        self._task_co = None
        self._task_do = None
        self._task_ao = None
        self._blank = None
    

    # This is used to start all tasks in the DAQ.
    def start(self,
              cameras: int = 1):
        try:
            self._task_ao.start()
            if self._channels_length >= 2:
                self._task_do.start()
            else:
                self._task_do = nidaqmx.Task()
                self._task_do.do_channels.add_do_chan(self._do_lines,line_grouping=nidaqmx.constants.LineGrouping.CHAN_FOR_ALL_LINES)
                self._task_do.write(self._do_waveform,True)
            for i in range(cameras):
                task_name = f"_task_di_{i}"
                task = getattr(self,task_name)
                task.start()

            self._task_co.start()
        except Exception as e:
            print(f'Could not start tasks: {e}')
        try:
            self._blank.write(True,auto_start = True)
        except Exception as e:
            print(f"Could not start blanking: {e}")

    # this is used to stop all tasks in the DAQ. NB: Stop is not the same as close. Stop just stops the task for now, while close removes the task.
    def pause(self):
        self._task_co.stop()
        self._blank.write(False,auto_start = True)

    def pause_start(self):
        self._blank.write(True, auto_start = True)
        self._task_co.start()

    def VC_stop(self):
        self._task_co.stop()
        self._task_ao.stop()
        self._blank.write(False,auto_start = True)

    def VC_start(self):
        self._blank.write(True, auto_start = True)
        self._task_ao.start()
        self._task_co.start()

    def stop(self,
             cameras: int = 1):
        
        try:
            self._task_co.stop()
        except Exception as e:
            print(f'Could not stop co task: {e}')

        try:
            self._task_do.stop()
            '''
            if self._channels_length >=  2:
                arr = np.zeros((self._do_waveform.shape[0],1),dtype = np.bool_)
            else:
                arr = False
            blank = nidaqmx.Task()
            blank.do_channels.add_do_chan(self._do_lines,
            line_grouping=nidaqmx.constants.LineGrouping.CHAN_PER_LINE
            )
            blank.write(arr,True)
            time.sleep(0.1)
            blank.stop()
            '''
        except Exception as e:
            print(f'Could not stop do task: {e}')

        try:
            self._task_ao.stop()
            #self._task_ao.timing.cfg_samp_clk_timing(100,
            #                        sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
            #self._task_ao.write(self._ao_neutral_positions, True)
            #time.sleep(0.1)
            #self._task_ao.stop()
            #self._task_ao.timing.cfg_samp_clk_timing(self._daq_sample_rate_hz, 
            #                               sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            #                               samps_per_chan=self._ao_waveform.shape[0])
            #self._task_ao.triggers.start_trigger.cfg_dig_edge_start_trig(self._co0_address, nidaqmx.constants.Edge.RISING)
            #self._task_ao.triggers.start_trigger.retriggerable = True
            #self._task_ao.write(self._ao_waveform, False)
        except Exception as e:
            print(f'Could not stop ao task: {e}')

        try: 
            for i in range(cameras):
                task_name = f"_task_di_{i}"
                task = getattr(self,task_name)
                task.stop()
        except Exception as e:
            print(f'Could not stop DI task: {e}')
        try:
            self._blank.write(False,True)
        except Exception as e:
            print(f"Blanking did not stop: {e}")


# %%
