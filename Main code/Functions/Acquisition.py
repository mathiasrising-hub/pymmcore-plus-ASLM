#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pymmcore_plus
from pymmcore_plus import CMMCorePlus
from useq import MDAEvent
from useq import MDASequence
from pathlib import Path
import numpy as np
import tifffile as tiff
import datetime
import threading
from queue import Queue
import queue
import time


# In[2]:


class Acquisition:
    '''Class: Acquisition
    This it the main class used to control the acquisition of images. It takes the two other classes, stages_movement and VoiceCoil_nidaqmx as input and calls specific functions from them.
    The main function of this class is to set up the acquisition parameters, start the acquisition, and save the images. It also handles the timing of movement of the stages and the DAQ.
    The class is designed in 3 different parts:
    1.
    This code is designed to be able to configure and setup each of the giving parameters used in the microscope. 
    This includes but are not limited to: The camera, the save location and name, define callback functions etc.
    2.
    This code is the main operator when it comes to the acquisition. This means it control whenever the acquisition should start, stop, pause etc.
    The code is also the main operator for fail safes implementation. This includes logging each images parameters and timing, to be able to debug issues.
    The acquisition works with multiple threads. This means that care should be taken to make sure every threads are started, defined and stopped.
    3.
    Saving the images. Right now this code uses big tiff as a file format. This can be changed by changing the package from tifffile to another package and of course updating the syntax in the saving function.
    It also has default saving operation and naming operation, to ensure files are not overwritten, and a logical naming convention. NB: There is no failsafe on the custom names given to files. Custom names are currently not implemented correctly. 
    It also has a queue system to ensure that the saving is not lagging behind the acquisition. This is important to ensure that the acquisition is not stopped due to saving issues. MaxQueue size should be changed to the specific acquisition probably. Keep in mind the ram usage
    And lastly the saving is running on a seperate thread to ensure that the acquisition is not slowed down if saving has issues, or large files. 
    This is furthermore improved by using a pause when the stages move tiles. This ensures that the saving does not lag too far behind.

    Terminology:
        Jog and move_to:
        These are also called relative move (jog) and absolute move(move_to). Only move_to supports multi axis movement. 
        
        Sequence:
        Sequence is sometimes used synonymously with acquisition. It essentially means one round of acquisition. 

        Pause:
        This is a relic from when the pause function was something else. Now it more accurately can be described as tiling. 

        pymmcore:
        If at any time pymmcore is written it actually means pymmcore-plus. 
        In this code pymmcore-plus and micromanager is also taken as synonymously most of the time.

        saving:
        While most of the saving relates to saving images in tiff files, there is an exception
        Sometimes the callback function may be referred to as a saving function. 
        Most obvious in the DAQ class. The reason was because of an old implementation, and should be changed.

        instance function:
        I write if it's an instance function or not in the descriptive text of functions. 
        This is to make it clear if the function is intended to be accessible to the user (most likely through the GUI)
        These can all still be called in the terminal if wished.

    This descriptive text is last edited 07-28-2026 by Mathias Hove Rising
    Main Author: Mathias Hove Rising
    Created for the Bewersdorf lab and the pan-ASLM microscope.
    '''
    def __init__(
        self,
        stages_movement, #This is the class that controls the stages. 
        DAQ, #This is the class that controls the DAQ.
        config_path: str = r"\Users\Hannah\Desktop\configuration\PVCAM_only.cfg" #The configuration path. For now it's hard coded, though this can be changed to be a parameter in the future.
    ):
        
        '''
        Here we basically defined the parameters for the micromanager core used.

        self.mmc:
        This defined as the micromanager core and where the Camera device adapter lies. 
        
        self.mmc.enableDebugLog(True):
        This should probably be changed to a parameter in the future, but for development purposes it is always true, to ensure that we don't miss crucial debugging information.
        
        self.mmc.loadSystemConfiguration(config_path):
        Load the correct configuration file. NB! If a new configuration file is created, change the path to the new configuration file

        self.mmc.setAutoShutter(False):
        The auto shutter should already be disabled in the config file, but just to be sure it is disabled here. If the autoshutter is not turned off, it can lead to issues.
        '''
        #print('mmc is being defiend as MDA mmc') -> This is a debuggin tool to check if __init__ crashes and if so where it does
        self.mmc = CMMCorePlus.instance()
        
        #print('mmc is enabling debulog') -> This is a debuggin tool to check if __init__ crashes and if so where it does
        self.mmc.enableDebugLog(True)

        #print('loading system config') -> This is a debuggin tool to check if __init__ crashes and if so where it does
        self.mmc.loadSystemConfiguration(config_path)

        #print('mmc autoshutter is turned off') -> This is a debuggin tool to check if __init__ crashes and if so where it does
        self.mmc.setAutoShutter(False)

        '''
        Now we define the other engines used, so we can call them later in the class. If at any time you want to use a different engine, just change the input engine. 
        NB: remember function names are already defined, so either those need to be the same in the new engine or changed in this class
        '''
        #print('mmc setup is done.') -> This is a debuggin tool to check if __init__ crashes and if so where it does
        self.stages_movement = stages_movement
        self.DAQ_VC = DAQ
        
        '''
        Now we define the camera parameters. These are set as default for the voice coil at 1 fps and 24 ms flyback. 
        The default is arbitrary as they are not set directly using pymmcore plus

        The purpose of the default is so the software can just run setup and start and an acquisition will begin. 
        If a different default is wished, this will not break anything. 
        Keep in mind:
        These values are first set in the setup function.
        Edge trigger shouldn't be changed as then hardware triggering is impossible
        '''
        
        self._exposure  = 2.44 #Exposure of the camera in ms. Correct exposure for 24 ms flyback can be found in the manual for the microscope.
        self._scan_width = 8 #Scan width of the rolling shutter. Default is 8 for higher intensity. 4 is diffraction limited and should be used for imaging.
        self._scan_direction = 'Up' #Scan direction of the rolling shutter. Down is default for the camera, so this should always be changed to up, UNLESS the scan direction is cahnged for the voice coil. (Current setup is min V to max V)
        self._trigger  = 'Edge Trigger' #The trigger mode. The setup is currently only setup to work in hardware trigger mode. If live features are implemented it should proabably be set to internal trigger.
        self._Port = 'Dynamic Range' #The port of the camera. Sensitivity is the default for live. Dynamic range is the default for imaging.
        '''
        This is simply just booleans to keep track what code is running. Feel free to add more.
        '''
        #Booleans to check waht code has run. 
        self._setup = False #This is an instance boolean variable to ensure that proper setup is done before acquiring images. This is to make sure that the user does not damage devices by not setting them up beforehand.
        self._sequence = None # This is an old check for sequencing. Should be deleted unless it is used in the future. It is currently not used anywhere in the code.
        '''
        Now we define the variables which are important for the DAQ. These are set to defaulting for the exact same reason as before
        '''
        #DAQ variables
        self._cali_path = self.DAQ_VC.cali_path # This is the current calibration file in use. Currently the calibration file is hard coded in the DAQ class, but it should be changed to be a parameter in the future. The calibration is deciding the framerate in the DAQ class. 
        self._channels = ['488'] # Different colors of lasers. This is also used in the DAQ, but keep in mind it is also used for saving purposes.

        '''
        These are all acquisition parameteres specifically with the purpose of defining everything needed for acquisition
        '''
        self._X = 1 # Number of tiles in the X direction
        self._Y = 1 # Number of tiles in the Y direction
        self._meta = 1 # Number of repitions. Currently not correctly implemented.
        self._cameras = 1 # Number of cameras. Currently not correctly implemented.
        self._filename = 'Zstack' # Default filename for saving. This can be changed by the user in the setup_sequence function.
        self._foldername = 'Default' # If the foldername is set to default the foldername is just the date. 
        self._save = False # Boolean to check if saving is enabled. The default should be False, and saving should only occur if the user wishes to save. This is to ensure that the user does not accidentally save images and fill up the disk.
        self._z_stepsize = 0.0002 # Z step size in mm. This is the distance between each slice in the Z stack. The default is 0.2 um.
        self._silence = False # Currently not implemented. The intended function is to turn on and off printing valuable debugging information to track acquisition in real time. Default should be False to ensure smooth user experience.
        self._pause_duration = 2 #Pause duration in seconds. This time can be adjusted, which are important if pause duration is found out to affect image quality. Remember there is an additional pause time to catch up to saving. This pause is seperate from that.
        self._lag_limit = None # The lag limit of the saving thread. This number should be reasonable. NB: If there actually is lagging behind there is a problem with the speed or saving. This is a failsafe. If this actually triggers there may be something wrong.
        self._disk = Path('E:') # The disk to save the images to. Currently hard coded to the computer in use.

        '''
        There is a lot of instance variable defiend here.
        THESE SHOULD NOT BE ADJUSTED BY THE USER, ONLY THE DEVELOPER.
        These are either defined here so we can define them later.
        or they have a purpose, like the self._running showing if the acquisition is running or not.

        Keep in mind some parameters are 0 index while some others are 1 indexed. Keep this in mind especially when modifying with the counters used in the threads and callback
        If something is set to None, it is to accomodate defining it later correctly.
        '''
        #Instance variables defined. Should not be changed by the user. These are mostly used for counting purposes.
        self._running = False # A boolean that communicates if the code is in the middle of an Acquisition
        self._finished_event = threading.Event() # A threading event used in the GUI, again to keep track on status
        self._finished_event.set() # idle initially
        self._stack_height = 1 # Stack height is the number of total slices in a Z stack
        self._frames = 1 # Total number of frames to be acquired. This is calculated from the other parameters.
        self._idx_frame = 0 # Current frame index. This is used to keep track
        self._current_X = 1 # Current tile in the X direction
        self._current_Y = 1 # Current tile in the Y direction
        self._tiles = 0 # Total number of tiles to be acquired. This is calculated from the other parameters.
        self._stack = 0 # Current stack index. This is used to keep track of the current stack being acquired. This is used for saving purposes.
        self._idx_slice = 0 # Current slice index. This is used to keep track of the current slice being acquired. This is used for saving purposes.
        self._start_pos = [] # This is the starting position of the stages. This is used to keep track of the current position of the stages. This is used for moving the stages to the correct position for each tile.
        self._tile_move = 0.608 # This is the distance that the stages will move for a tile. A tile is 640 um, and the default overlap is 5%
        self._move_forward = True # This is to make sure the stages move in the correct direction. The tiling can be found in the manual.
        self._queue = None #This is the queu that every image is popped into using mmc.popNextImage. 
        self._stop_thread = None # This is a parameter defined as an event, with the purpose of stopping the saving thread. 
        self._save_thread = None # This is the saving thread. 
        self._acquire_thread = None # The thread used for acquiring images from the camera
        self._acquire_event = None #The event used to call the acquire thread
        self._stop_sequence_thread = None # The thread used to stop the acquisition
        self._stop_sequence_event = None # The event to call the stop_sequence_thread
        self._jog_thread = None # The thread that jogs the stage
        self._jog_event = None # The event that triggers the _Jog_thread
        self._pause_thread = None # Called the pause thread, but more accurately is the tiling thread. 
        self._pause_event = None # Communicates when a Zstack is done and triggers the thread to move to the next tile
        self._count = 0 #
        self._pause_status = False


    '''
    This next section is all the different parameters which can be changed by the user. 

    If you do not know what exactly this means let me explain:

    @property
    is a way of a custom property which returns whatever we want it to return. 
    Most often this is used to give descriptive text to the different parameters, along with the possibility of returning additional information if necessary.
    (an example could be that calling channels could return all possible channels currently implemented)
    This is most often only relevant if calling in the terminal

    @property.settter
    This is a way of defining additional constraints when defining the parameter later. 
    How to call it is to say "MDA.channels = ['488']"
    A feature that could be implemented then is to check if the input is valid (like in this case check that its a list of str), set min and max etc. 

    If these features are not desired the etire section with @property and .setter is safe to delete.
    '''
    @property
    def channels(self) -> list:
        # The channels (laser colors) used for acquisition. Example: ['488'] or ['488', '560']. 
        # This is used both for DAQ control and saving purposes.
        return getattr(self, "_channels", None)
    @channels.setter
    def channels(self, value: list):
        if isinstance(value, list) == False:
            print("The channels should be a list of strings! This isn't!")
            return
        if all(isinstance(item, str) for item in value):
            self._channels = value

    @property
    def X(self) -> int:
        # Number of tiles in the X direction. Default is 1.
        return getattr(self, "_X", None)
    @X.setter
    def X(self, value: int):
        if isinstance(value,int):
            self._X = value

    @property
    def Y(self) -> int:
        # Number of tiles in the Y direction. Default is 1.
        return getattr(self, "_Y", None)
    @Y.setter
    def Y(self, value: int):
        if isinstance(value,int):
            self._Y = value
        else:
            print('Value needs to be an integer!')

    @property
    def meta(self) -> int:
        # Number of repetitions of the acquisition. Currently not correctly implemented. Default is 1.
        return getattr(self, "_meta", None)
    @meta.setter
    def meta(self, value: int):
        if isinstance(value,int):
            self._meta = value
        else:
            print('Value needs to be an integer!')  

    @property
    def cameras(self) -> int:
        # Number of cameras in use. Currently not correctly implemented. Default is 1.
        return getattr(self, "_cameras", None)
    @cameras.setter
    def cameras(self, value: int):
        if isinstance(value,int):
            self._cameras = value
        else:
            print('Value needs to be an integer!')

    @property
    def filename(self) -> str:
        # The filename used for saving. Default is 'Zstack'.
        # Can be changed by the user before acquisition.
        return getattr(self, "_filename", None)
    @filename.setter
    def filename(self, value: str):
        if isinstance(value,str):
            self._filename = value
        else:
            print('Value needs to be an string!')

    @property
    def foldername(self) -> str:
        # The foldername used for saving. 
        # If set to 'Default', the foldername will be the current date.
        return getattr(self, "_foldername", None)
    @foldername.setter
    def foldername(self, value: str):
        if isinstance(value,str):
            self._foldername = value
        else:
            print('Value needs to be a string!')

    @property
    def z_stepsize(self) -> float:
        # The step size between each slice in the Z stack, in mm. Default is 0.0002 mm (0.2 um).
        return getattr(self, "_z_stepsize", None)
    @z_stepsize.setter
    def z_stepsize(self, value: float):
        self._z_stepsize = value

    @property
    def silence(self) -> bool:
        # Currently not implemented. Intended to toggle printing of debugging information.
        # Default is False to ensure debugging information is printed.
        return getattr(self, "_silence", None)
    @silence.setter
    def silence(self, value: bool):
        self._silence = value

    @property
    def pause_duration(self) -> float:
        # The pause duration in seconds between tiles. Default is 2 seconds.
        # This is separate from the additional pause used to catch up to saving.
        # Adjust if pause duration is found to affect image quality.
        return getattr(self, "_pause_duration", None)
    @pause_duration.setter
    def pause_duration(self, value: float):
        self._pause_duration = value

    @property
    def lag_limit(self) -> int:
        # The maximum allowed lag of the saving thread in number of frames.
        # If this triggers, there may be an issue with saving speed.
        # Default is None, meaning no limit is set.
        return getattr(self, "_lag_limit", None)
    @lag_limit.setter
    def lag_limit(self, value: int):
        self._lag_limit = value

    @property
    def disk(self) -> Path:
        # The disk to save images to. Default is Path('E:').
        return getattr(self, "_disk", None)
    @disk.setter
    def disk(self, value: Path):
        self._disk = Path(value)

    @property
    def scan_direction(self) -> str:
        # The scan direction of the rolling shutter. Default is 'Up'.
        # Should always be 'Up' unless the scan direction of the voice coil is changed.
        return getattr(self, "_scan_direction", None)
    @scan_direction.setter
    def scan_direction(self, value: str):
        self._scan_direction = value

    @property
    def trigger(self) -> str:
        # The trigger mode of the camera. Default is 'Edge Trigger'.
        # The setup is currently only configured to work in hardware trigger mode.
        return getattr(self, "_trigger", None)
    @trigger.setter
    def trigger(self, value: str):
        self._trigger = value

    @property
    def Port(self) -> str:
        # The port of the camera. Default is 'Dynamic Range'.
        # 'Sensitivity' is recommended for live imaging, 'Dynamic Range' for acquisition.
        return getattr(self, "_Port", None)
    @Port.setter
    def Port(self, value: str):
        self._Port = value
            
    @property
    def save(self) -> bool:
        # This property is to enable and disable saving of the images. 
        # This should be enabled if the images should be saved.
        return getattr(self,"_save",None)
    @save.setter
    def save(self, value: bool):
        self._save = value

    @property
    def exposure(self) -> float:
        # Setting the exposure of the camera. 
        # Remember, for rolling shutter the exposure time should be set in accordance to the table in the manual.
        # The exposure time is dependent on the scan width and the flyback time. 
        # Of course it is also dependent on the calibration file and framerate.
        return getattr(self,"_exposure",None)
    @exposure.setter
    def exposure(self, value: float):
        self._exposure = value
    
    @property
    def scan_width(self) -> int:
        # The scan width of the rolling shutter. 
        return getattr(self,"_scan_width",None)
    @scan_width.setter
    def scan_width(self, value: int):
        self._scan_width = value
        
    @property
    def cali_path(self) -> str:
        # The path to the calibration file.
        return getattr(self,"_cali_path",None)
    @cali_path.setter
    def cali_path(self, value: str):
        self.DAQ_VC.cali_path = value
        self._cali_path = self.DAQ_VC.cali_path            




    def connect_stages(self):
        ''' 
        This functions purpose is to connect to the stages if for some reason there is a disconnect.
        If a disconnect happens, the program should probably be restarted, but this is defined primarily for future crash security.
        The idea is to implement if the stages are disconnected, then the program will try to reconnect and continue from where it left off
        '''
        self.stages_movement.connect_controller()

    def _pause_threading(self):
        '''
        This entire thread is continously checking if a stop event has been set.
        If the stop event is not set and the pause event is set it will then clear the event (preventing repetition) and run the _pause function.

        If not it will go back to wait. This thread is created and started when in run_sequence.
        '''
        while not self._stop_thread.is_set():
            trigger = self._pause_event.wait(timeout = 5)
            if not trigger:
                continue
            self._pause_event.clear()
            if self._pause_status:
                continue
            self._pause()


    def _pause(
        self,
        duration: float = None
    ):
        '''
        This function is an instance function.
        This is the pause function used to move tiles and pause between tiles. 
        The pause duration can be adjusted and removed. (based on a theory of gel needing to settle (Currently not experimentally proven))
        There is also a pause status essentially just stopping other threads from triggering which should be idle in while moving tiles
        
        There is an important ordering to this function. 
            First the DAQ is stopped
            Then there is a wait for images to reach the buffer.
            Then the buffer is drained using the acquire thread.
            Then we wait for the saving to be caught up.
            Now we stop the camera
        
        Aside from the last 2 steps (which can be swapped without much loss), This ordering is very important as stopping the camera deletes all images in the buffer and all images on the way to the buffer

        Lastly it moves the stages to the next tiling. 
        Then starts the camera and then the DAQ.
        '''
        
        # Stop DAQ and initial setup for tiling
        expected_frames = self._count
        if not self._silence:
            print(f"status: Images in the buffer: {self.mmc.getRemainingImageCount()}. Images acquired: {self._idx_frame}. Images in queue: {self._queue.qsize()}. Images saved: {self._idx_slice + (self._stack*self._stack_height)}")
            print(f"Pausing DAQ at {time.perf_counter()-self._tstart}")
        self.DAQ_VC.pause()

        self._pause_status = True
        if duration is not None:
            self._pause_duration = duration

        # wait until images reaches the buffer
        t_pause_start_1 = time.perf_counter()
        while self.mmc.getRemainingImageCount()+self._idx_frame < expected_frames:
            self._acquire_event.set()    
            if time.perf_counter() - t_pause_start_1 > 2:
                print('Timeout waiting for the circular buffer!')
                self._file_acquire.write(f"Time: {time.perf_counter()-self._tstart}. The acquire had a timeout while catching up in the pause function.\n")
                break
            time.sleep(0.05)
        # Drain the buffer (might be unnecessary, could be replaced with self._acquire_event.set())
        while self.mmc.getRemainingImageCount() > 0:
            self._acquire_event.set()
            if time.perf_counter() - t_pause_start_1 > 10:
                print('Timeout waiting for the acquiring!')
                self._file_acquire.write(f"Time: {time.perf_counter()-self._tstart}. The acquire had a timeout while catching up in the pause function.\n")
                break
            time.sleep(0.05)
        #Wait for saving thread to catch up. 
        t_pause_start = time.perf_counter()        
        if self._queue.qsize() > self._lag_limit:
            print('Saving is lagging behind. Stopping acquisition until caught up to limit...')
            while self._queue.qsize() > self._lag_limit:
                if time.perf_counter() - t_pause_start > 30:
                    print('Timeout waiting for the saving!')
                    self._file_save.write(f"Time: {time.perf_counter()-self._tstart}. The saving had a timeout while catching up in the pause function.\n")
                    break
                time.sleep(0.001)
            print('Saving is caught up!')
       
        #stop the camera
        if not self._silence:
            print(f"Pausing Acquisition at {time.perf_counter() - self._tstart}")
        self.mmc.stopSequenceAcquisition()

        # We now check if we are at the last tile in the X direction. 
        # If we are not, we move to the next tile in the X direction. 
        # If we are, we move to the next tile in the Y direction and change the direction of movement in the X direction.
        if not self._silence:
            print(f"starting move at {time.perf_counter() - self._tstart}")
        if self._current_X < self._X:
            self._current_X += 1
            if self._move_forward:
                self._start_pos[0] = self._start_pos[0] + self._tile_move
            else:
                self._start_pos[0] = self._start_pos[0] - self._tile_move
        else:
            self._current_X = 1
            self._current_Y += 1
            self._move_forward = not self._move_forward
            self._start_pos[1] = self._start_pos[1] + self._tile_move

        # Improvement: This should be changed to not redefining the self._start_pos, but have a seperate one. 
        # This is to ensure we know exactly where it started from, so it is easier to move back.
        # Move the stage
        self._move_to(self._start_pos)
        if not self._silence:
            print(f"Ending move at {time.perf_counter() - self._tstart}")

        # Adjustable pause
        time.sleep(self._pause_duration)

        # Now we start the sequence acquisition and the DAQ again.
        if not self._silence:
            print(f"starting again at {time.perf_counter() - self._tstart}")
        self._pause_status = False
        self.mmc.startContinuousSequenceAcquisition()
        self.DAQ_VC.pause_start()

        
    
    def _saving(
        self,
        tif,
        image
    ):
        '''
        This function is an instance function. 
        This function is called by the _saving_thread().
        This function works very simply by writing the image in the tiff file. 
        It then checks if then checks if we are at the end of the stack.
        If we are, then the tiff file is closed and new tiffiles for each channels are opened.

        NB:
        If alternative acquisition modes are implemented remember to modify when it closes and creates new files
        '''
        #save the image
        tif.write(image, photometric='minisblack')

        #Check if we at the end of a Zstack
        if self._idx_slice >= self._stack_height:
            #reset counters
            self._stack += 1
            self._idx_slice = 0
            #close and create new tiff files
            for chan in self._channels:
                getattr(self, f"_tif{chan}").close()
                if self._stack < self._tiles:
                    setattr(self, f"_tif{chan}", tiff.TiffWriter(
                    str(self._tif_path) + f"{self._stack:05d}{chan}.tif", bigtiff=True))
    
    def _saving_thread(
        self
    ):
        '''
        This function is an instance function. It also is a seperate thread
        This is the main thread used for saving.
        The main method is to set up a while loop that checks if the stop condition is set.
        Then it gets the last image from the queue.
        Then it calls the _saving function and increases the counter for idx_slice and the chan_idx is defined from that one.
        Afterwards, some information about timing and slice nr and such is written in the log.
        There is a if statement that checks for every 100 images it does a flush, which means it writes into the log from the buffer to make sure it never clutters up.
        Lastly there are some exceptions, mostly for if error happens, or if there is no image in the queue.

        NB:
        This assumes a queue with First in First Out property. If alternative sorting methods are used this should be changed
        It also is hardcoded to only flush at every 100 frames. This could be a problem if less than 100 frames are in a Zstack. Keep that in mind.
        The trry except has not yet been relevant but are failsafes
        '''
        while True:
            #Check if the thread should stop
            if self._stop_thread.is_set() and self._queue.empty():
                break
            try:
                #Get the image
                t1 = time.perf_counter()
                image = self._queue.get(timeout = 2)
                try:
                    t1 = time.perf_counter()

                    #Define/increase counters
                    self._idx_slice += 1
                    chan_idx = (self._idx_slice-1) % len(self._channels)

                    #Get the tiff file
                    tif = getattr(self, f"_tif{self._channels[chan_idx]}")
                    if not self._silence:
                        print(f"Saving image in {tif}. Slice nr{self._idx_slice}, channel {self._channels[chan_idx]}, stack nr {self._stack}")

                    #save the image in the tiff file
                    self._saving(tif,image)
                    t2 = time.perf_counter()

                    #Log
                    self._file_save.write(f"Time: {t2-self._tstart}. Slice nr: {self._idx_slice} channel: {self._channels[chan_idx]} took {t2-t1}\n")
                    if self._idx_slice % 100 == 0:
                        self._file_save.flush()

                except Exception as e:
                    #Exception if something failed in the saving.
                    print(f"Error happened in the saving thread: {e}")
                    self._file_save.write(f"Error happened in the saving thread: {e}")
                    self._stop_thread.set()
                    break

                finally:
                    #Important to set the specific queue element to finished.
                    self._queue.task_done()

            except queue.Empty:
                # Log if the queue is empty, unless Pause is underway
                if self._pause_status:
                    continue
                t3 = time.perf_counter()
                if not self._silence:
                    print(f"Queue is empty!")
                self._file_save.write(f"Time: {t3-self._tstart}. Queue is empty and took: {t3-t1}\n")
                continue




    def _acquire(
            self
    ):
        '''
        This is an instance function. This is a seperate thread.
        The function is a while loop. The condition is just the _stop_thread.is_set() like all the other threads in this code.
        This function then uses mmc.popNextImage() to get an np array of the current image in the camera. It also clear that image from the buffer
        This is then pulled into a queue (which _saving_thread uses). 
        Afterwards it logs and the loop continues and wait for the next trigger.  
        '''
        
        while not self._stop_thread.is_set() == True:

            #Wait for trigger
            triggered = self._acquire_event.wait(timeout=2) 

            #timout to prevent infinite loop
            if not triggered:
                if self._pause_status:
                    continue
                print('Timeout: no trigger received')
                continue
            self._acquire_event.clear()

            # drain buffer
            while self.mmc.getRemainingImageCount() > 0:
                tt = time.perf_counter()
                self._idx_frame += 1

                # Get the image from the circular buffer. Data structure is a np.array
                image = self.mmc.popNextImage()

                # This is debug for the buffer.
                if self._idx_frame % 100 == 0:
                    self._file_acquire.write(
                        f"Buffer free: {self.mmc.getBufferFreeCapacity()} / "
                        f"{self.mmc.getBufferTotalCapacity()}\n"
                    )
                    self._file_acquire.flush()

                #Put the image i nthe queue
                if self._save:
                    self._queue.put(image)
                if not self._silence:
                    print(f"Image acquired nr {self._idx_frame}")

                # Logging
                ttt = time.perf_counter()
                self._file_acquire.write(f"Time: {ttt-self._tstart}. Image nr {self._idx_frame} acquired in: {ttt-tt}\n")
                    

    def _callback(self):
        '''
        This is an internal function.
        This is the main callback function, which secures that the acquire thread keeps running. 
        This runs whenever the trigger is recieved from the camera. 
        
        It functions as the orchestrator, basically by triggering the other threads. 
        It also keeps an eye on the progress and stops if acquisition is done or camera has crashed.

        This runs on the main thread.
        '''
        # prevent running if a pause is initiated (most likely from the _pause/tiling function)
        if self._pause_status:
            return
        
        #Increase counter
        self._count += 1
        ttt = time.perf_counter()

        #Check status and stop if necessary
        if self._count >= self._frames or self.mmc.isSequenceRunning() == False:
            if not self._silence:
                print('Stopping Acquisition')
            self._file_acquire.write(f"Time: {ttt-self._tstart}. Status of stopping Acquisition: Sequence running? {self.mmc.isSequenceRunning()}. Frames taken vs total frames: {self._count} vs {self._frames}. Total frames acquired: {self._idx_frame}.\n")
            self._stop_sequence_event.set()
            return

        #Trigger the acquire thread
        self._acquire_event.set()

        #If end of stack trigger the _pause thread
        if self._count % self._stack_height == 0:
            self._pause_event.set()
            return

        #If not end of stack trigger the _jog thread
        chan = self._count % len(self._channels)
        if chan == 0:
            self._jog_event.set()
        
    
    def _setup_tiff(
        self,
        disk: str = None
    ):    
        '''
        This is an instance function.
        The main purpose of this is to setup the saving location of the tiff files. 
        Furthermore it defines the name of the tiff files. (This has a default of Zstack, but can be named whatever)

        NB:
        Right now the custom naming of folder and filename has not been tested 
        The default works fine, but keep in mind som debug should be handled.
        The disk is also hardcoded for now.

        NB:
        Using a custom naming of the folder and save name of the file WILL DELETE A PREVIOUS ACQUISITION IF THEY ARE THE SAME.
        There probably should be a failsafe, to make sure no accidental deletion happen. (like naming it _01 if there already is a folder of the same name)
        '''

        # Disk is defined
        if disk == None:
            self._disk = Path('E:')
        else:
            self._disk = disk

        #Get todays time and date
        today =datetime.datetime.now()

        #Make a folder of the hours and minutes if the foldername is default. Make it of the folder name if not so
        if self._foldername == 'Default':
            time_m_s = today.strftime("%H_%M")
            save_dir = self._disk / self._datestring / time_m_s
        else:
            save_dir = self._disk / self._datestring / self._foldername
        save_dir.mkdir(parents=True, exist_ok=True)

        #Make the path to the general Zstack file
        self._tif_path = save_dir / self._filename  

        #Now generate a file for all channels in bigtiff.
        #NB: if another filetype is desired, this is where it should be changed along with the _saving_function
        for chan in self._channels:
            setattr(self, f"_tif{chan}", tiff.TiffWriter(
                str(self._tif_path) + f"{self._stack:05d}{chan}.tif", bigtiff=True
            ))

        

    def _save_path(
        self
    ):
        '''
        This is an instance function. 
        Its main purpose is to make a general folder of todays date.
        The saving structure works by having this as the parent folder and using setup_tiff as the daughter folder and tiff file.
        ergo:
        _save_path is the folder for the entire day.
        _setup_tiff is the folder for the individual acquisition. 
        '''
        today =datetime.datetime.now()   # Get date
        self._datestring = today.strftime("%Y-%m-%d")  # Date to the desired string format
        Path(self._datestring).mkdir(parents=True, exist_ok=True)   # Create folder
    
    def _set_callback(
        self
    ):
        '''
        This is an instance function
        The main purpose is to define the callback function of the DAQ. 

        NB:
        The name is weird and is an artifact from a previous saving method. The "register_save" should be changed to "_register_callback"
        '''
        self.DAQ_VC.register_save(self._callback)
        
    def setup_save(
        self
    ):
        '''
        This is an instance function.
        This just sets the callback and sets up the save path.

        This is kinda unnecessary and should just be removed (calling the individual function in setup and run).
        '''
        self._set_callback()
        if self._save is False:
            print('Saving is not enabled!')
            return
        self._save_path()
        
        
        
    def _setup_camera(self):
        '''
        this is an instance function.
        This function sets up the parameters for all the cameras. 
        It is assumed that all cameras want the same settings.
        If this is not the case in the future (as only 1 camera is in use now), then the code needs to be changed.

        NB:
        Right now this does not interact with the pymmcore widget that sets the camera parameters. 
        This function therefore should probably change or not be called at all (so you only set up the camera using the widget)
        It can also be used as a way of dividing settings into preview/live mode and acquisition parameters. 
        '''
        for i in range(self._cameras):
            self.mmc.setProperty(f"Camera-{i+1}",'Exposure',self._exposure),
            self.mmc.setProperty(f"Camera-{i+1}",'TriggerMode',self._trigger)
            self.mmc.setProperty(f"Camera-{i+1}",'ScanDirection',self._scan_direction)
            self.mmc.setProperty(f"Camera-{i+1}",'ScanMode','Scan Width'),
            self.mmc.setProperty(f"Camera-{i+1}",'ScanWidth',self._scan_width)
            self.mmc.setProperty(f"Camera-{i+1}",'Port',self._Port)
            
    def _calculate_frames(self):
        '''
        This is an instance function.
        It is simply a function which calculates the frames. 
        '''
        self._frames = self._stack_height * self._X * self._Y * self._meta * self._cameras
        self._tiles = self._X * self._Y
    
    def _setup_daq(self):
        '''
        This is an instance function. 
        This calls the DAQ class to define the waveforms.
        This does not start the waveforms, only defines them. 

        NB:
        If you want to change the framerate the calibration file should be changed in the DAQ class
        '''
        self.DAQ_VC.program_waveforms(self._stack_height, self._channels)
    
    def setup_sequence(
        self,
        z_depth: float,
        z_stepsize: float = None,
        x_tiles: int = None,
        y_tiles: int = None,
        meta: int = None,
        channels: str = None,
        cameras: int = None,
        overlap: float = 5,
        saving: bool = None,
        silence: bool = None,
        filename: str = None,
        foldername: str = None,
        exposure: float = None,
        trigger_mode: str = None,
        lag_limit: int = None
    ):
        '''
        This is a function that is supposed to be called by the user. 
        First off it starts by checking every input parameter.
        If a parameter is defined by the user, it will be modified. 

        Then it runs all relevant setup functions.
        '''

        #Define parameters to the input
        if z_stepsize is not None:
            self._z_stepsize = z_stepsize
        if x_tiles is not None:
            self._X = x_tiles
        if y_tiles is not None:
            self._Y = y_tiles
        if meta is not None:
            self._meta = meta
        if channels is not None:
            self._channels = channels
        if cameras is not None:
            self._cameras = cameras
        if saving is not None:
            self._save = saving
        if silence is not None:
            self._silence = silence
        if filename is not None:
            self._filename = filename
        if foldername is not None:
            self._foldername = foldername
        if exposure is not None:
            self._exposure = exposure
        if trigger_mode is not None:
            self._trigger = trigger_mode

        #Run setup functions
        try:
            self._tile_move = 0.64*(100-overlap)/100
            
            self._stack_height = round(z_depth / (self._z_stepsize)) * len(self._channels)
            
            if lag_limit is None:
                self._lag_limit = self._stack_height
            else:
                self._lag_limit = lag_limit

            self._calculate_frames()
            
            self._setup_camera()
            
            self._setup_daq()
        

            self._setup = True
        except Exception as e:
            # A catch to make sure that the entire program doesn't crash if something wasn't defined or turned on.
            print(f"Something failed in the setup {e}")


    def _create_threads(self):
        '''
        this is an instance function.
        Create all the relevant threads and only creathe the saving thread if saving is turned on
        '''
        self._jog_event = threading.Event()
        self._jog_thread = threading.Thread(target= self._jog_threading, daemon=True)

        self._acquire_event = threading.Event()
        self._acquire_thread = threading.Thread(target = self._acquire, daemon = True)

        self._stop_sequence_event = threading.Event()
        self._stop_sequence_thread = threading.Thread(target = self._stop_threading, daemon = True)
        
        self._pause_thread = threading.Thread(target = self._pause_threading, daemon = True)
        self._pause_event = threading.Event()
        
        self._stop_thread = threading.Event()

        self._save_thread = None
        if self._save:
            self._save_thread = threading.Thread(target= self._saving_thread, daemon=True)
    def run_sequence(
            self,
            X: int = None,
            Y: int = None,
            frame_idx: int = None,
            slice_idx: int = None,
            stack_idx: int = None,
            count: int = None
    ):
        '''
        This function is linked to a button on the GUI. 
        It is the function that starts the acquisition. 

        Here the save path is defined
        The statuses are updated (like self._running)
        The queue is defined
        The threasd are created
        The save files are created
        The log files are created
        The stages are enabled and start position is recorded
        lastly the camera and DAQ is started

        NB:
        Right now the input of X, Y, count etc. is the fundament to implement crash recovery. 
        THIS DOES NOT WORK YET AND IS A WIP. 
        Most importantly, there are no moving into place. The rest of the functions like saving should work but are untested. 
        '''

        #Check if it should run
        if self._setup == False:
            print('Setup is not done! run MDA.setup_sequence before running it!')
            return
        if self._running:
            print('Acqusition is underway. Stop that one before creating a new one!')
            return

        #update statuses
        self._running = True
        self._pause_status = False
        self._finished_event.clear()

        #Define parameters    
        self._queue = Queue()
        self.setup_save()

        #create the threads
        self._create_threads()
        self._tstart = time.perf_counter()
        #Define the parameters by the input
        if X is None:
            self._current_X = 1
        else:
            self._current_X = X
        if Y is None:
            self._current_Y = 1
        else:
            self._current_Y = Y
        if count is None:
            self._count = 0
        else:
            self._count = count
        if frame_idx is None:
            self._idx_frame = 0
        else:
            self._idx_frame = frame_idx
        if self._save:    
            if slice_idx is None:
                self._idx_slice = 0
            else:
                self._idx_slice = slice_idx

            if stack_idx is None:
                self._stack = 0
            else:
                self._stack = stack_idx

            #make the necessary setup for saving to occur
            self._setup_tiff()
            self._file_save = open(f"{self._tif_path}_log_save.txt",'w')
            self._save_thread.start()
            self._file_save.write(f"stack height: {self._stack_height} \n")

        #Make acquire log and start all threads
        self._file_acquire = open(f"{self._tif_path}_log_acquire.txt",'w')
        self._acquire_thread.start()
        self._jog_thread.start()
        self._stop_sequence_thread.start()
        self._pause_thread.start()

        #Get start position and enable the stages
        self.stages_movement.enable_all()
        self._start_pos = self.stages_movement.get_pos()

        # start the camera
        self.mmc.startContinuousSequenceAcquisition()

        #Start the DAQ
        if self._trigger == 'Edge Trigger':
            self.DAQ_VC.start()
    
    def _stop_threading(self):
        '''
        This is an instance function. It runs on a seperate thread
        The only purpose is to always having the stop working on a seperate thread (so if the main thread freezes, the stop can still go through)
        '''
        self._stop_sequence_event.wait()
        self.stop_sequence()


    def stop_sequence(self):
        '''
        Technically an instance function. 
        The main purpose as the name implies is to stop the acquisition. 
        First it shuts down the DAQ and update statuses.
        It works then by ensuring we have the expected amount of images (with timeouts in case of failure)
        It then stops the camera.
        It then shuts down each thread 
        Lastly it ensures saving files are closed.
        finally it updates the running statuses to communicate with the GUI

        NB:
        It is paramount to avoid missing images that the images are all acquired BEFORE stopping the camera.
        '''
        try:
            #stop the camera
            if self._trigger == 'Edge Trigger':
                self.DAQ_VC.stop()

            #set statuses
            self._pause_status = True

            #Wait for images to reach the buffer
            expected_frames = self._count
            t_pause_start_1 = time.perf_counter()
            while self.mmc.getRemainingImageCount()+self._idx_frame < expected_frames:
                self._acquire_event.set()    
                if time.perf_counter() - t_pause_start_1 > 2:
                    print('Timeout waiting for the circular buffer!')
                    self._file_acquire.write(f"Time: {time.perf_counter()-self._tstart}. The acquire had a timeout while catching up in the stop function.\n")
                    break
                time.sleep(0.05)

            #Drain the buffer. NB this could theoretically be replaced with self._acquire_event.set(). 
            while self.mmc.getRemainingImageCount() > 0:
                self._acquire_event.set()
                if time.perf_counter() - t_pause_start_1 > 10:
                    print('Timeout waiting for the acquiring!')
                    self._file_acquire.write(f"Time: {time.perf_counter()-self._tstart}. The acquire had a timeout while catching up in the stop function.\n")
                    break
                time.sleep(0.05)

            #stop the camera
            if self.mmc.isSequenceRunning():
                self.mmc.stopSequenceAcquisition()   

            #sets the stop condition for all threads
            self._stop_thread.set()

            # stop and close the acquire thread and its log
            self._acquire_event.set()
            self._acquire_thread.join(timeout = 10)  
            if self._acquire_thread.is_alive():
                print("WARNING: Acquire thread did not stop cleanly!")
            self._file_acquire.write(f"Time: {time.perf_counter()-self._tstart}. Acquisition closed. Frames Acquired vs total frames: {self._idx_frame} vs {self._frames}. Total frames saved: {self._idx_slice+(self._stack_height*self._stack)}.\n")
            self._file_acquire.flush()
            self._file_acquire.close()

            # Stop the Jog thread
            self._jog_event.set()
            self._jog_thread.join(timeout = 10)  
            if self._jog_thread.is_alive():
                print("WARNING: jog thread did not stop cleanly!")

            # stop the tiling thread
            self._pause_event.set()
            self._pause_thread.join(timeout = 10)
            if self._pause_thread.is_alive():
                print('WARNING: Pause thread did not stop cleanly!')

            #stop the saving thread and close files if necessary
            if self._save:
                self._save_thread.join(timeout = 20)
                if self._save_thread.is_alive():
                    print("WARNING: save thread did not stop cleanly!")
                else:
                    self._file_save.flush()
                    self._file_save.close()
                    for chan in self._channels:
                        print("closing")
                        tif = getattr(self, f"_tif{chan}")
                        try:
                            tif.close()
                        except Exception as e:
                            print(f"couldn't close {chan}: {e}")  
            
        finally:
            #Set statuses that it's no longer running
            self._running = False
            self._finished_event.set() 

    def request_stop(self):
        '''
        Simple function for the GUI that stops the acquisition
        '''
        if self._stop_sequence_event is not None:
            self._stop_sequence_event.set()

    def _jog_threading(self):
        '''
        This is an instance function. it works on a seperate thread. 
        The main purpose is to move the stage in the Z direction, whenever it is triggered. 
        '''
        #Check stop condition
        while not self._stop_thread.is_set() == True:

            #wait for trigger
            triggered = self._jog_event.wait(timeout=len(self._channels)+1) 

            if not triggered:
                print('Timeout: no trigger received for jog')
                continue
            
            self._jog_event.clear()
            if self._pause_status:
                continue

            # move the stages
            self.stages_movement.jog(
            2,
            self._z_stepsize
        )


    def jog(self,
            distance: float,
            axis: int = 2
            ):
        '''
        a way of jogging the stages in the acquisition class
        This is outdated but harmless
        '''
        self.stages_movement.jog(
            axis,
            distance
        )
    
    def _move_to(
        self,
        coordinates: np.array
    ):
        '''
        This is a function which calls the stage class. 
        This is used in threads.
        '''  
        self.stages_movement.move_to(
            coordinates
        )
    
        
    def close(self):
        '''
        Close everything and is automatically called on window exit
        '''
        if self.mmc.isSequenceRunning():
            self.mmc.stopSequenceAcquisition()
        self.mmc.unloadAllDevices()
        try:
            self.DAQ_VC.close()
        except Exception as e:
            print(f"Could not close DAQ: {e}")       
        self.stages_movement.close()


# %%
