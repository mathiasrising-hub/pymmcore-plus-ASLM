#!/usr/bin/env python
# coding: utf-8

# In[1]:


from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import MDAEngine
import useq
import stages_movement

class No_Stage(MDAEngine):
    
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


class Z_Stack(MDAEngine): 
    def setup_event(self, event: useq.MDAEvent) -> None:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-setup
        print(event.metadata)
        super().setup_event(event)
        print(event.metadata)  
        self.z_move(event.metadata)
        # do some custom post-setup

    def z_move(self, metadata: dict) -> none:
        print(metadata)
        sz = metadata['step_size']
        step_size = float(sz)
        stages_movement.jog(2, step_size, controller, bound)
        
    def exec_event(self, event: useq.MDAEvent) -> object:
        """Prepare state of system (hardware, etc.) for `event`."""
        # do some custom pre-execution
        result = super().exec_event(event)  
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




