
from acspy import acsc
from acspy.control import Controller
import threading
import time
import sys
import numpy as np
import subprocess as sp
#This document has all the functions related to stage movement.
class stages_movement:

    def __init__(self):
        self._controller = Controller(contype='ethernet',n_axes=3)
        self._controller.connect()
        self._boundary = np.array([[-40, 20], [0.5, 18],[-0.5, 5]])
        self._home = np.array([-20, 6, 0])


    def connect_controller(self):
        try:
            self._controller = Controller(contype='ethernet',n_axes=3)
            self._controller.connect()
        except Exception as e:
            print(f'controller could not connect: {e}')
    
    def get_pos(self):
        controller = self._controller
        ax0 = controller.axes[0]
        pos0 = ax0.rpos
        ax1 = controller.axes[1]
        pos1 = ax1.rpos
        ax2 = controller.axes[2]
        pos2 = ax2.rpos
        return [pos0, pos1, pos2]
    

    def disable_x(self):
        ax0 = self._controller.axes[0]
        ax0.disable()
    
    def enable_x(self):
        ax0 = self._controller.axes[0]
        ax0.enable()
        
    def disable_y(self):
        ax1 = self._controller.axes[1]
        ax1.disable()
        
    def enable_y(self):
        ax1 = self._controller.axes[1]
        ax1.enable()
        
    def disable_z(self):
        ax2 = self._controller.axes[2]
        ax2.disable()
        
    def enable_z(self):
        ax2 = self._controller.axes[2]
        ax2.enable()
    
    def enable_all(self):
        ax0 = self._controller.axes[0]
        ax1 = self._controller.axes[1]
        ax2 = self._controller.axes[2]
        if not ax0.enabled:
            ax0.enable()
        if not ax1.enabled:
            ax1.enable()
        if not ax2.enabled:
            ax2.enable()
            
    def disable_all(self):
        ax0 = self._controller.axes[0]
        ax1 = self._controller.axes[1]
        ax2 = self._controller.axes[2]
        if ax0.enabled:
            ax0.disable()
        if ax1.enabled:
            ax1.disable()
        if ax2.enabled:
            ax2.disable()

    def set_home(
        self
    ):
        ax0 = self._controller.axes[0]
        ax1 = self._controller.axes[1]
        ax2 = self._controller.axes[2]
        
        ax0_bounds = [-40, 2]
        ax1_bounds = np.zeros(2)
        ax2_bounds = [-0.5, 5]
        self._boundary = None
        self._home = None
        
        if ax1.enabled==True:
            ax1.disable()
        if ax0.enabled==True:
            ax0.disable()
        if ax2.enabled==False:
            ax2.enable()
        
        for i in range(2):
            input('Move the stage to one edge')
            ax1_bounds[i] = ax1.rpos
        
        self.enable_all()
        
        ax1_bounds_sorted = np.sort(ax1_bounds)
        ax0_home = ax0.rpos
        ax1_home = (ax1_bounds[1] + ax1_bounds[0])/2
        ax2_home = 0
        self._home = np.array([ax0_home, ax1_home, ax2_home])
        self._boundary = np.array([ax0_bounds, ax1_bounds_sorted, ax2_bounds])

    def move_home(self):
    
        self.move_to(
            self._home
        )
    def jog(self, axis, distance):
        #t_start = time.perf_counter()
        #First off we check if the axis is valid. Since we have a XYZ stage, it should be an integer between 0-2
        boundary = self._boundary
        if axis not in (0,1,2):
            print('Not a valid axis!')
            return 
        controller = self._controller
        #We define some variables to use later.
        ax = controller.axes[axis]
        pos = ax.rpos
        
        #We check if the movement exceeds the boundary threshold. If it does it's important that the movement doesn't start
        if not (boundary[axis,0] <= pos+distance <= boundary[axis,1]):
            print('Movement exceeds boundary!')
            return
        
        #ax.ptpr is a relative move (jog). We send a signal to move the distance given in the function. 
        #t_middle_0 = time.perf_counter()
        acsc.toPoint(controller.hc,0,axis,pos+distance)
        #t_middle_1 = time.perf_counter()
        '''
        #Now we want to check if the movement has stopped, and when it has stopped we want to inform the position and exit the function
        positions = []
        while True:
            state = acsc.getMotorState(controller.hc, axis)
            positions.append((time.perf_counter(), acsc.getRPosition(controller.hc, axis)))
            if state['in position']:
                break

        for t, p in positions:
            print(f"{(t-t_middle_1)*1000:.2f}ms: {p}")
        #print('Movement has finished. from position,',pos,'to',ax.rpos)
        '''
        TARGET = pos + distance
        TOLERANCE = 0.0000001 

        while True:
            current_pos = acsc.getRPosition(controller.hc, 2)
            if abs(current_pos - TARGET) <= TOLERANCE:
                break
            time.sleep(0.00001)
        return



    #We next want to define a multi axis movement. The input is a 1 dimensional array of 3 coordinates. 
    #This function then checks if the movement is possible, and afterwards move in all axes simultanously.
    def move_to(self, coordinates):
        controller = self._controller
        boundary = self._boundary
        #First we want to check if the input is in the correct format. If it isn't the function stops to prevent errors.
        if len(coordinates) != 3:
            print('Coordinates are not in correct format! All 3 coordinates must be defined')
            return
        
        #We define the indidual controller axes
        ax_x = controller.axes[0]
        ax_y = controller.axes[1]
        ax_z = controller.axes[2]
        #We also define the current position for later control
        pos = [ax_x.rpos,ax_y.rpos,ax_z.rpos]
        
        #We enable all axes if any of them aren't enabled. Because of the potential delay, we won't enable if they're already enabled
        if False in [ax_x.enabled, ax_y.enabled, ax_z.enabled]:
            controller.enable_all()
            time.sleep(0.5)
            
        #We define a TRUE FALSE condition array. This array tests if each coordinate is within the boundary limits.
        boundary_check = [(boundary[0,0] <= coordinates[0] <= boundary[0,1]),
                        (boundary[1,0] <= coordinates[1] <= boundary[1,1]),
                        (boundary[2,0] <= coordinates[2] <= boundary[2,1])]
        
        #We know check if some of the coordinates are outside the boundary. If they are we inform which axes are exceeding. 
        #If any of them are exceeding the boundary, we stop the function to prevent damage to the equipment
        if False in boundary_check:
            if False in [boundary_check[0]]:
                print('X movement exceeds boundary')
            if False in [boundary_check[1]]:
                print('Y movement exceeds boundary')
            if False in [boundary_check[2]]:
                print('Z movement exceeds boundary')
            return
        
        #ptp is an absolute move to a specific coordinate. Even though the signal is sent sequentially, it's almost a simultanous movement
        ax_x.ptp(coordinates[0])
        ax_y.ptp(coordinates[1])
        ax_z.ptp(coordinates[2])
        
        #Last part we want to check if the movement has succeeded. If it has, inform the start and end position for control
        while True:
            if (ax_x.in_position == True) and (ax_y.in_position == True) and (ax_z.in_position == True):
                break
        print('Movement has finished. from position,',pos,'to',[ax_x.rpos, ax_y.rpos, ax_z.rpos])
        return

    def close(self):
        self._controller.disconnect()





