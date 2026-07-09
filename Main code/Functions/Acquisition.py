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
 
    def __init__(
        self,
        stages_movement,
        DAQ,
        config_path: str = r"\Users\Hannah\Desktop\configuration\PVCAM_only.cfg"
    ):
        
        # Set the first instance of this class as the global singleton
        global mmc
        if mmc is not None:
            mmc.unloadAllDevices()
        if mmc is None:
            mmc = CMMCorePlus.instance()
        mmc.enableDebugLog(True)
        # Load the correct configuration file. NB! If a new configuration file is created, change the path to the new configuration file
        mmc.loadSystemConfiguration(config_path)
        mmc.setAutoShutter(False)
        #settings needed to set up the DAQ
        self.stages_movement = stages_movement
        self.DAQ_VC = DAQ
        
        
        #Setup the default Camera settings for 1 fps rolling shutter.
        self._exposure  = 2.44
        self._scan_width = 8
        self._scan_direction = 'Up'
        self._trigger  = 'Edge Trigger'
        self._Port = 'Dynamic Range'
        self._setup = False
        self._sequence = None
        self._cali_path = self.DAQ_VC.cali_path
        self._stack_height = 1
        self._X = 1
        self._current_X = 1
        self._current_Y = 1
        self._Y = 1
        self._meta = 1
        self._channels = ['488']
        self._cameras = 1
        self._frames = 1
        self._filename = 'Zstack'
        self._foldername = 'Default'
        self._save = False
        self._z_stepsize = 0.0002
        self._silence = False
        self._tiles = 0
        self._pause_duration = 2
        self._start_pos = []
        self._tile_move = 0.608
        self._move_forward = True
        self._queue = None
        self._stop_thread = None
        self._save_thread = None
        self._lag_limit = None
        self._disk = Path('E:')

        
    @property
    def save(self) -> bool:
        return getattr(self,"_save",None)
    @save.setter
    def save(self, value: bool):
        self._save = value

    @property
    def exposure(self) -> float:
        return getattr(self,"_exposure",None)
    @exposure.setter
    def exposure(self, value: float):
        self._exposure = value
    
    @property
    def scan_width(self) -> int:
        return getattr(self,"_scan_width",None)
    @scan_width.setter
    def scan_width(self, value: int):
        self._scan_width = value
        
    @property
    def cali_path(self) -> str:
        return getattr(self,"_cali_path",None)
    @cali_path.setter
    def cali_path(self, value: str):
        self.DAQ_VC.cali_path = value
        self._cali_path = self.DAQ_VC.cali_path            
    
    def connect_stages(self):
        self.stages_movement.connect_controller()
    
    def _pause(
        self,
        duration: float = None
    ):
        
        if duration is not None:
            self._pause_duration = duration
        mmc.stopSequenceAcquisition()
        self.DAQ_VC.stop()
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

        self._move_to(self._start_pos)
        time.sleep(self._pause_duration)

        if self._queue.qsize() > self._lag_limit:
            print('Saving is lagging behind. Stopping acquisition until caught up to limit...')
            while self._queue.qsize() > self._lag_limit:
                time.sleep(0.001)
            print('Saving is caught up!')
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
        today =datetime.datetime.now()   # Get date
        self._datestring = today.strftime("%Y-%m-%d")  # Date to the desired string format
        Path(self._datestring).mkdir(parents=True, exist_ok=True)   # Create folder
    
    def _set_callback(
        self
    ):
        self.DAQ_VC.register_save(self._acquire)
        
    def setup_save(
        self
    ):
        self._set_callback()
        if self._save is False:
            print('Saving is not enabled!')
            return
        self._save_path()
        
        
        
    def _setup_camera(self):
        for i in range(self._cameras):
            mmc.setProperty(f"Camera-{i+1}",'Exposure',self._exposure),
            mmc.setProperty(f"Camera-{i+1}",'TriggerMode',self._trigger)
            mmc.setProperty(f"Camera-{i+1}",'ScanDirection',self._scan_direction)
            mmc.setProperty(f"Camera-{i+1}",'ScanMode','Scan Width'),
            mmc.setProperty(f"Camera-{i+1}",'ScanWidth',self._scan_width)
            mmc.setProperty(f"Camera-{i+1}",'Port',self._Port)
            
    def _calculate_frames(self):
        self._frames = self._stack_height * self._X * self._Y * self._meta * self._cameras
        self._tiles = self._X * self._Y
    
    def _setup_daq(self):
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
        keep_save_on: bool = False,
        lag_limit: int = None
    ):
        
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

