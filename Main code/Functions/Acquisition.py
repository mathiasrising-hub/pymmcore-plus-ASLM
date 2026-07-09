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
mmc = None


# In[2]:


class Acquisition:
    '''Class: Acquisition
    This it the main class used to control the acquisition of images. It calls the 2 other classes, stages_movement and DAQ.
    The main function of this class is to set up the acquisition parameters, start the acquisition, and save the images. It also handles the movement of the stages and the DAQ.
    The class is designed in 3 different parts:
    1.
    This code is designed to be able to configure and setup each of the giving parameters used in the microscope. 
    This includes but are not limited to: The camera, the save location and name, the DAQ, home and boundary of tge stages etc.
    2.
    This code is the main operator when it comes to the acquisition. This means it control whenever the acquisition should start, stop, pause etc.
    The code is also the main operator for fail safes implementation. This includes logging each images parameters and timing, to be able to debug issues
    3.
    Saving the images. Right now this code uses big tiff as a file format. This can be changed by changing the package from tifffile to another package and of course updating the syntax in the saving function.
    It also has default saving operation and naming operation, to ensure files are not overwritten, and a logical naming convention. 
    It also has a queue system to ensure that the saving is not lagging behind the acquisition. This is important to ensure that the acquisition is not stopped due to saving issues.
    And lastly the system is running on a seperate thread to ensure that the acquisition is not slowed down if saving has issues, or large files. 
    This is furthermore improved by using a pause when the stages move tiles. This ensures that the saving does not lag too far behind.

    This descriptive text is last editet 09-08-2026 by Mathias Rising
    Main Author: Mathias Rising
    Created for the Bewersdorf lab and the pan-ASLM microscope.
    '''
    def __init__(
        self,
        stages_movement, #This is the class that controls the stages. 
        DAQ, #This is the class that controls the DAQ.
        config_path: str = r"\Users\Hannah\Desktop\configuration\PVCAM_only.cfg" #The configuration path. For now it's hard coded, though this can be changed to be a parameter in the future.
    ):
        
        # Set the first instance of this class as the global singleton
        global mmc #This is made a global variable purely for debugging purposes. It can be used to check the status of the micro manager core
        if mmc is not None:
            mmc.unloadAllDevices() #We want to make sure, if there is a previous instance of the core, that it is unloaded before we start a new one. This is to avoid issues with lingering devices.
        if mmc is None:
            mmc = CMMCorePlus.instance() #If there is not previous instance, we of course create a new one.
        
        #This should probably be changed to a parameter in the future, but for development purposes it is always true, to ensure that we don't miss crucial debugging information.
        mmc.enableDebugLog(True)

        # Load the correct configuration file. NB! If a new configuration file is created, change the path to the new configuration file
        mmc.loadSystemConfiguration(config_path)
        
        #The auto shutter should already be disabled in the config file, but just to be sure it is disabled here. If the autoshutter is not turned off, it can lead to issues.
        mmc.setAutoShutter(False)


        #Now we name the other classes to be used in the class. They are of course also set to instance variables to ensure use in the entire class
        self.stages_movement = stages_movement
        self.DAQ_VC = DAQ
        
        
        #Setup the default Camera settings for 1 fps rolling shutter. In the future this should probably be loaded as a config file, to make it easy to change the settings. But for now it is hard coded.
        self._exposure  = 2.44 #Exposure of the camera in ms. Correct exposure for 24 ms flyback can be found in the manual for the microscope.
        self._scan_width = 8 #Scan width of the rolling shutter. Default is 8 for higher intensity. 4 is diffraction limited and should be used for imaging.
        self._scan_direction = 'Up' #Scan direction of the rolling shutter. Down is default for the camera, so this should always be changed to up, UNLESS the scan direction is cahnged for the voice coil. (Current setup is min V to max V)
        self._trigger  = 'Edge Trigger' #The trigger mode. The setup is currently only setup to work in hardware trigger mode. If live features are implemented it should proabably be set to internal trigger.
        self._Port = 'Dynamic Range' #The port of the camera. Sensitivity is the default for live. Dynamic range is the default for imaging.
        
        #Booleans to check waht code has run. 
        self._setup = False #This is an instance boolean variable to ensure that proper setup is done before acquiring images. This is to make sure that the user does not damage devices by not setting them up beforehand.
        self._sequence = None # This is an old check for sequencing. Should be deleted unless it is used in the future. It is currently not used anywhere in the code.
        
        #DAQ variables
        self._cali_path = self.DAQ_VC.cali_path # This is the current calibration file in use. Currently the calibration file is hard coded in the DAQ class, but it should be changed to be a parameter in the future. The calibration is deciding the framerate in the DAQ class. 
        self._channels = ['488'] # Different colors of lasers. This is also used in the DAQ, but keep in mind it is also used for saving purposes.

        #Acquisition parameters. These are calculated or inputted by the user, so are just set to a single image in the initiation.
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

        
        # Instance variables defined. Should not be changed by the user. These are mostly used for counting purposes.
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
    @property
    def channels(self) -> list:
        # The channels (laser colors) used for acquisition. Example: ['488'] or ['488', '560']. 
        # This is used both for DAQ control and saving purposes.
        return getattr(self, "_channels", None)
    @channels.setter
    def channels(self, value: list):
        self._channels = value

    @property
    def X(self) -> int:
        # Number of tiles in the X direction. Default is 1.
        return getattr(self, "_X", None)
    @X.setter
    def X(self, value: int):
        self._X = value

    @property
    def Y(self) -> int:
        # Number of tiles in the Y direction. Default is 1.
        return getattr(self, "_Y", None)
    @Y.setter
    def Y(self, value: int):
        self._Y = value

    @property
    def meta(self) -> int:
        # Number of repetitions of the acquisition. Currently not correctly implemented. Default is 1.
        return getattr(self, "_meta", None)
    @meta.setter
    def meta(self, value: int):
        self._meta = value

    @property
    def cameras(self) -> int:
        # Number of cameras in use. Currently not correctly implemented. Default is 1.
        return getattr(self, "_cameras", None)
    @cameras.setter
    def cameras(self, value: int):
        self._cameras = value

    @property
    def filename(self) -> str:
        # The filename used for saving. Default is 'Zstack'.
        # Can be changed by the user before acquisition.
        return getattr(self, "_filename", None)
    @filename.setter
    def filename(self, value: str):
        self._filename = value

    @property
    def foldername(self) -> str:
        # The foldername used for saving. 
        # If set to 'Default', the foldername will be the current date.
        return getattr(self, "_foldername", None)
    @foldername.setter
    def foldername(self, value: str):
        self._foldername = value

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
        # This functions purpose is to connect to the stages if for some reason there is a disconnect.
        # If a disconnect happens, the program should probably be restarted, but this is defined primarily for future crash security.
        # The idea is to implement if the stages are disconnected, then the program will try to reconnect and continue from where it left off
        self.stages_movement.connect_controller()


    def _pause(
        self,
        duration: float = None
    ):
        # This function is an instance function.
        # This is the pause function used to move tiles and pause between tiles. 
        # The current theory is that the gel needs time to settle, so after moving it should have a small delay
        # The pause duration can be set before the acquisition.
        # There also is a pause to catch up to saving, if the saving is lagging behind. This is a failsafe to ensure that the acquisition does not stop due to saving issues.
        if duration is not None:
            self._pause_duration = duration
        
        #MIGHT BE CHANGED. KEEP IN MIND.
        # We start off by stopping the sequence acquisition and the DAQ.
        # This is to ensure that no images are taken and the callback function isn't called while stages are moving.
        mmc.stopSequenceAcquisition()
        self.DAQ_VC.stop()

        # We now check if we are at the last tile in the X direction. 
        # If we are not, we move to the next tile in the X direction. 
        # If we are, we move to the next tile in the Y direction and change the direction of movement in the X direction.
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

        #We not move to the position of the next tile
        # Improvement: This should be changed to not redefining the self._start_pos, but have a seperate one. 
        # This is to ensure we know exactly where it started from, so it is easier to move back. 
        self._move_to(self._start_pos)

        #Now we actually pause the function. 
        # Since _move_to is not a blocking function, this will pause the script while the stages are moving.
        time.sleep(self._pause_duration)

        #Lastly we check if the saving is lagging behind. 
        # If it is, then we pause the function and wait till it's caught up.
        # NB: There should be implemented a timeout to make sure that it's not stuck indefinetly if the saving thread is stuck for some reason.
        if self._queue.qsize() > self._lag_limit:
            print('Saving is lagging behind. Stopping acquisition until caught up to limit...')
            while self._queue.qsize() > self._lag_limit:
                time.sleep(0.001)
            print('Saving is caught up!')

        # Now we start the sequence acquisition and the DAQ again.
        mmc.startSequenceAcquisition(
            self._stack_height,
            0,
            True
        )
        self.DAQ_VC.start()
        
    
    def _saving(
        self,
        tif,
        image
    ):
        '''
        This function is an instance function. 
        This function is called by the saving thread.
        This function works very simply by writing the image in the tiff file. 
        It then checks if then checks if we are at the end of the stack.
        If we are, then the tiff file is closed and new tiffiles for each channels are opened.
        '''
        tif.write(image, photometric='minisblack')
        if self._idx_slice >= self._stack_height:
            self._stack += 1
            self._idx_slice = 0
            for chan in self._channels:
                getattr(self, f"_tif{chan}").close()
                if self._stack < self._tiles:
                    setattr(self, f"_tif{chan}", tiff.TiffWriter(
                    str(self._tif_path) + f"{self._stack:05d}{chan}.tif", bigtiff=True))
    
    def _saving_thread(
        self
    ):
        '''
        This function is an instance function.
        This is the main thread used for saving.
        The main method is to set up a while loop that checks if the stop condition is set.
        Then it gets the last image from the queue.
        Then it calls the _saving function and increases the counter for idx_slice and the chan_idx is defined from that one.
        Afterwards, some information about timing and slice nr and such is written in the log.
        There is a if statement that checks for every 100 images it does a flush, which means it writes into the log from the buffer to make sure it never clutters up.
        Lastly there are some exceptions, mostly for if error happens, or if there is no image in the queue.
        '''
        while self._stop_thread.is_set() == False:
            try:
                t1 = time.perf_counter()
                image = self._queue.get(timeout = self._pause_duration+2)
                try:
                    t1 = time.perf_counter()
                    self._idx_slice += 1
                    chan_idx = (self._idx_slice - 1) % len(self._channels)
                    tif = getattr(self, f"_tif{self._channels[chan_idx]}")
                    self._saving(tif,image)
                    t2 = time.perf_counter()
                    self._file_save.write(f"Time: {t2-self._tstart}. Slice nr: {self._idx_slice} channel: {self._channels[chan_idx]} took {t2-t1}\n")
                    if self._idx_slice % 100 == 0:
                        self._file_save.flush()
                except Exception as e:
                    print(f"Error happened in the saving thread: {e}")
                    self._file_save.write(f"Error happened in the saving thread: {e}")
                    self._stop_thread.set()
                    break
                finally:
                    self._queue.task_done()
            except queue.Empty:
                t3 = time.perf_counter()
                self._file_save.write(f"Time: {t3-self._tstart}. Queue is empty and took: {t3-t1}\n")
                continue




    def _acquire(
            self
    ):
        '''
        This is an instance function.
        The function is used as a callback function for the DAQ class. 
        Specifically the DAQ class calls to this function whenever the camera is done acquiring an image.
        The purpose of this functin is to acquire an image and put it into the queue. 
        Afterwards as long as none of the stage triggers are true, the code exits and wait for the next trigger.
        
        This code also functions as stage cotnrol. 
        More specifically it "Jogs" (single axis relative move) the stage when all channels have been acquired.
        It also calls the _pause function when the Zstack is done. This moves to the next tile. 
        Lastly if all the frames has been taken it stops the acquisition. 
        '''
        tt = time.perf_counter()
        ttt = tt
        while True:
            if mmc.getRemainingImageCount() > 0:
                image = mmc.popNextImage()
                if self._idx_frame % 100 == 0:
                    self._file_acquire.write(
                        f"Buffer free: {mmc.getBufferFreeCapacity()} / "
                        f"{mmc.getBufferTotalCapacity()}\n"
                    )
                if self._save:
                    self._queue.put(image)
                    print('Image recieved')
                self._idx_frame += 1
                chan_idx = (self._idx_frame - 1) % len(self._channels)
                ttt = time.perf_counter()
                self._file_acquire.write(f"Time: {ttt-self._tstart}. Image nr {self._idx_frame} acquired in: {ttt-tt}\n")
                if self._idx_frame % 100 == 0:
                    self._file_acquire.flush()
                if chan_idx == len(self._channels)-1:
                    self._jog(self._z_stepsize)
                break
            if ttt-tt >= 1:
                print('Timeout: _acquire')
                break
        if self._idx_frame % self._stack_height == 0 and self._idx_frame < self._frames:
            self._pause()
        if self._idx_frame >= self._frames or mmc.isSequenceRunning() == False:
            self._file_acquire.write(f"Time: {ttt-self._tstart}. Status of stopping Acquisition: Sequence running? {mmc.isSequenceRunning()}. Frames taken vs total frames: {self._idx_frame} vs {self._frames}\n")
            self.stop_sequence()
            return

    

    
    def _setup_tiff(
        self,
        disk: str = None
    ):    
        '''
        This is an instance function.
        The main purpose of this is to setup the saving location of the tiff files. 
        Furthermore it defines the name of the tiff files. 

        Lastly this is the code that defines the queue size and the threads used to save
        '''
        if disk == None:
            self._disk = Path('E:')
        else:
            self._disk = disk
        today =datetime.datetime.now()
        if self._foldername == 'Default':
            time_m_s = today.strftime("%H_%M")
            save_dir = self._disk / self._datestring / time_m_s
        else:
            save_dir = self._disk / self._datestring / self._foldername

        save_dir.mkdir(parents=True, exist_ok=True)
        self._tif_path = save_dir / self._filename  

        for chan in self._channels:
            setattr(self, f"_tif{chan}", tiff.TiffWriter(
                str(self._tif_path) + f"{self._stack:05d}{chan}.tif", bigtiff=True
            ))
        self._queue = Queue(maxsize = 2000)
        self._stop_thread = threading.Event()
        self._save_thread = threading.Thread(target= self._saving_thread, daemon=True)
        
    def _save_path(
        self
    ):
        '''
        This is an instance function. 
        Its main purpose is to define the save path and make the folder.
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
        Importantly this should be done even if saving is not enabled, as it controls timing of everything.
        '''
        self.DAQ_VC.register_save(self._acquire)
        
    def setup_save(
        self
    ):
        '''
        This is a function to setup saving.
        It just calls the callback function and if saving is enabled it uses the save path.
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
        If this is not the case in the future (as only 1 camera is in use now), then the code needs to be changed
        '''
        for i in range(self._cameras):
            mmc.setProperty(f"Camera-{i+1}",'Exposure',self._exposure),
            mmc.setProperty(f"Camera-{i+1}",'TriggerMode',self._trigger)
            mmc.setProperty(f"Camera-{i+1}",'ScanDirection',self._scan_direction)
            mmc.setProperty(f"Camera-{i+1}",'ScanMode','Scan Width'),
            mmc.setProperty(f"Camera-{i+1}",'ScanWidth',self._scan_width)
            mmc.setProperty(f"Camera-{i+1}",'Port',self._Port)
            
    def _calculate_frames(self):
        '''
        This is an instance function.
        It is simply a function which calculates the frames
        '''
        self._frames = self._stack_height * self._X * self._Y * self._meta * self._cameras
        self._tiles = self._X * self._Y
    
    def _setup_daq(self):
        '''
        This is an instance function. 
        This calls the DAQ class to define the waveforms.
        This does not start the waveforms, only defines them
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
        lag_limit: int = None
    ):
        '''
        This is a function that is supposed to be called by the user. 
        First off it starts by checking every input parameter.
        If a parameter is defined by the user, it will be modified. 
        '''
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
            
            self.setup_save()

            self._setup = True
        except Exception as e:
            print(f"Something failed in the setup {e}")
            
        

        
    def run_sequence(
            self,
            X: int = None,
            Y: int = None,
            frame_idx: int = None,
            slice_idx: int = None,
            stack_idx: int = None
    ):
        if self._setup == False:
            print('Setup is not done! run MDA.setup_sequence before running it!')
            return
        if X is None:
            self._current_X = 1
        else:
            self._current_X = X

        if Y is None:
            self._current_Y = 1
        else:
            self._current_Y = Y

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
            self._setup_tiff()
            self._file_save = open(f"{self._tif_path}_log_save.txt",'w')
            self._file_acquire = open(f"{self._tif_path}_log_acquire.txt",'w')
            self._save_thread.start()
            self._tstart = time.perf_counter()
            

        
        self.stages_movement.enable_all()
        self._start_pos = self.stages_movement.get_pos()
        mmc.startSequenceAcquisition(
            self._stack_height,
            0,
            True
        )
        self._file_save.write(f"stack height: {self._stack_height} \n")
        
        if self._trigger == 'Edge Trigger':
            self.DAQ_VC.start()
            
    def stop_sequence(self):
        mmc.stopSequenceAcquisition()
        if self._trigger == 'Edge Trigger':
            self.DAQ_VC.stop()
        
        if self._save:    
            timeout = 60
            t_start = time.perf_counter()
            while not self._queue.empty():
                if time.perf_counter() - t_start > timeout:
                    print("WARNING: queue drain timed out!")
                    break
                time.sleep(0.05)

            self._stop_thread.set()
            self._save_thread.join(timeout=10)
            if self._save_thread.is_alive():
                print("WARNING: save thread did not stop cleanly!")

            self._file_save.close()
            self._file_acquire.close()
            for chan in self._channels:
                print("closing")
                tif = getattr(self, f"_tif{chan}")
                try:
                    tif.close()
                except Exception as e:
                    print(f"couldn't close {chan}: {e}")    
        
    def _jog(self,
            distance: float,
            axis: int = 2
            ):
        
        self.stages_movement.jog(
            axis,
            distance
        )
    
    def _move_to(
        self,
        coordinates: np.array
    ):
        
        self.stages_movement.move_to(
            coordinates
        )
    
        
    def close(self):
        mmc.unloadAllDevices()
        try:
            self.DAQ_VC.close()
        except Exception as e:
            print(f"Could not close DAQ: {e}")       
        self.stages_movement.close()

