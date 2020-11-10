# -*- coding: utf-8 -*-
"""
Created on Mon Nov  9 08:57:55 2020

@author: Administrator
"""

import os
import yaml
import logging

from Configuration import (Config, ModuleDescriptor, HviConstant,
                           HviModule, Hvi, PulseDescriptor, 
                           SubPulseDescriptor, Fpga, LoDescriptor, 
                           Queue, QueueItem, loadConfig)

log = logging.getLogger(__name__)

def saveConfig(config : Config):   
    if not os.path.exists('./config_hist'):
        os.mkdir('./config_hist')
    latest_hist = 0
    for file in os.listdir('./config_hist'):
        name = os.path.splitext(file)[0]
        hist = int(name.split('_')[-1])
        if hist > latest_hist:
            latest_hist = hist
    
    filename = './config_hist/config_' + str(latest_hist + 1) + '.yaml' 

    log.info("Generating Config file: {}".format(filename))
    with open(filename, 'w') as f:
        yaml.dump(config, f)
    with open('config_default.yaml', 'w') as f:
        yaml.dump(config, f)


if (__name__ == '__main__'):

    fpga = Fpga("test_test_partial.sbp")
    
    # mode: 0 = output individual waveform from one LO
    #       1 = output superimposed waveforms from all LOs
    mode = 1
    
    # los: #1 - channel number for LO bank
    #      #2 - list of LO frequencies for all LOs in bank
    los1 = LoDescriptor(1, [10E6, 30E6, 50E6, 70E6])
    los2 = LoDescriptor(1, [20E6, 30E6, 50E6, 70E6])
    
    # SubPulseDescriptor:
    #    #1 - carrier frequency inside envelope (generally 0 if using LO)
    #    #2 - Pulse width
    #    #3 - time offset in from start of pulse window 
    #            (needs to be long enough for envelope shaping)
    #    #4 - Amplitude (sum of amplitudes must be < 1.0)
    #    #5 - pulse shaping filter bandwidth
    pulseGroup = [SubPulseDescriptor(0, 10e-6, 1E-06,  0.3,   .1E06),
                  SubPulseDescriptor(0, 10e-6, 2E-06, -0.1,   1E06),
                  SubPulseDescriptor(0, 10e-6, 15E-06,  0.06,  1E06),
                  SubPulseDescriptor(0, 5e-6, 20E-06, -0.043, 1E06)]
    
    # PulseDescriptor
    #    #1 - Waveform ID to be used. Must be unique for every pulse (PulseGroup)
    #    #2 - The length of the pulse window 
    #            (must be long enough to hold all pulse enelopes, with transition times)
    #    #3 - List of SubPulseDescriptor details - to maximum of 5.
    pulseDescriptor = PulseDescriptor(1, 40e-06, pulseGroup)
    
    # QueueItem:
    #    #1 - PulseGroup ID that defines the waveform
    #    #2 - Trigger (False = auto, True = trigger from SW/HVI)
    #    #3 - Start Delay (how long, in time from trigger, to delay before play)
    #    #4 - How many repeats of the waveform
    # Queue:
    #    #1 - Channel
    #    #2 - IsCyclical 
    #    #3 - List of QueueItem details (waveforms)
    queue = Queue(1, True, [QueueItem(1, True, 0, 1)])
 
    # ModuleDescriptor:
    #    #1 - Model Number
    #    #2 - Number of channels
    #    #3 - Sample Rate of module
    #    #4 - Slot Number, in which the module is installed
    #    #5 - FPGA details
    #    #6 - List of LoDescriptor details
    #    #7 - List of PulseDescriptor details
    modules = [ModuleDescriptor("M3202A", 4, 1E09, 2, fpga, mode, [los1], [pulseDescriptor], [queue]), 
               ModuleDescriptor("M3202A", 4, 1E09, 4, fpga, mode, [los2], [pulseDescriptor], [queue])]
    
    # HviConstant:
    #    #1 - Constant name
    #    #2 - Constant value
    #    #3 - Constant units ('s' - seconds, 'Hz' - Herts, 'V' - Volts)
    # HVI:
    #    #1 - HVI file name to load
    #    #2 - List of HviConstants
    #    #3 - Slot number of module to be mapped to
    hvi = Hvi("quadLO.HVI", 
              [HviModule("AWG0",
                         [HviConstant("NumLoops", 5, ""),
                         HviConstant("PulsePeriod", 50e-06, "s")],
                         2),
               HviModule("AWG1", [], 4)
              ]
             )
    
    # Config:
    #   #1 - List of Module details
    #   #2 - HVI details
    config = Config(modules, hvi)
    
    name = __name__
    __name__ = "Configuration"
    saveConfig(config)
    __name__ = name

    config = loadConfig()

    log.info("Config File contents:\n{}".format(vars(config)))
        