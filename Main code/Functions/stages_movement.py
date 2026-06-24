
from acspy import acsc
from acspy.control import Controller
import time
import sys
import numpy as np
import subprocess as sp
#This document has all the functions related to stage movement.
controller = Controller(contype='ethernet',n_axes=3)
controller.connect()
#We want to define a jog movement. This is a relative move, which moves a set distance in a given axes.
#The axis is an integer value from 0-2 (0 = x axis, 1 = y axis, 2 = z axis)
def jog(axis, distance, controller, boundary):
    
    #First off we check if the axis is valid. Since we have a XYZ stage, it should be an integer between 0-2
    if axis not in (0,1,2):
        print('Not a valid axis!')
        return 
    
    #We define some variables to use later.
    ax = controller.axes[axis]
    pos = ax.rpos
    
    #We check if the movement exceeds the boundary threshold. If it does it's important that the movement doesn't start
    if not (boundary[axis,0] <= pos+distance <= boundary[axis,1]):
        print('Movement exceeds boundary!')
        return
    
    #We enable the axis if it isn't enabled already.
    if ax.enabled==False:
        ax.enable()
        #A timer is applied here, as there is a short delay from enabling the stage to the stage being able to move
        time.sleep(0.5)
    
    #ax.ptpr is a relative move (jog). We send a signal to move the distance given in the function. 
    ax.ptpr(distance)
    #Now we want to check if the movement has stopped, and when it has stopped we want to inform the position and exit the function
    while True:
        if ax.in_position:
            break
    print('Movement has finished. from position,',pos,'to',ax.rpos)
    return



#We next want to define a multi axis movement. The input is a 1 dimensional array of 3 coordinates. 
#This function then checks if the movement is possible, and afterwards move in all axes simultanously.
def move_to(coordinates, controller, boundary):
    
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






