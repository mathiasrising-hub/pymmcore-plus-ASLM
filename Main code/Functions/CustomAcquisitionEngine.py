#!/usr/bin/env python
# coding: utf-8

# In[1]:


from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import MDAEngine
import useq
import tifffile
import stages_movement

class No_Stage(MDAEngine):
    
    def setup_event(self, event: useq.MDAEvent) -> None:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-setup
        print(f"Event number: {event.metadata}")
        super().setup_event(event)  
        # do some custom post-setup

    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)  
        # do some custom post-execution
        return result 


class Z_Stack(MDAEngine): 
    def __init__(self, mmc, step_size, controller,boundary):
        super().__init__(mmc)
        self.controller = controller
        self.step_size = step_size
        self.bound = boundary
    def z_move(self, metadata: dict) -> none:
        stages_movement.jog(2, self.step_size, self.controller, self.bound)
    def setup_event(self, event: useq.MDAEvent) -> None:
        print(f"--- Event start ---")
        print('setup')
        super().setup_event(event)
        # do some custom post-setup
        
    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)
        print('exec')
        self.z_move(event.metadata)
        # do some custom post-execution
        return result 
'''
class Tiling(MDAEngine): 
    def setup_event(self, event: useq.MDAEvent) -> None:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-setup
        super().setup_event(event)  
        # do some custom post-setup

    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)  
        # do some custom post-execution
        return result

class Multi_Color_Z_Stack(MDAEngine): 
    def setup_event(self, event: useq.MDAEvent) -> None:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-setup
        super().setup_event(event)  
        # do some custom post-setup

    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)  
        # do some custom post-execution
        return result

class Multi_Color_Tiling(MDAEngine): 
    def setup_event(self, event: useq.MDAEvent) -> None:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-setup
        super().setup_event(event)  
        # do some custom post-setup

    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)  
        # do some custom post-execution
        return result
        '''


# In[2]:





# In[ ]:




