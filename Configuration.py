# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 09:08:30 2020

@author: gumcbrid
"""

import os
import yaml
import json
from dataclasses import dataclass
import logging.config

def setup_logging(
    default_path='logging.json',
    default_level=logging.INFO,
    env_key='LOG_CFG'):
    """Setup logging configuration"""
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
        
setup_logging()

log = logging.getLogger(__name__)

@dataclass
class LoDescriptor:
    channel : int
    frequencies : [float]

@dataclass
class QueueItem:
    pulse_id : int
    trigger : bool
    start_time : float
    cycles : int
    
@dataclass
class Queue:
    channel : int
    cyclic : bool
    items : [QueueItem]

@dataclass
class HviConstant:
    name : str
    value : str
    units : str

@dataclass
class HviModule:
    name : str
    constants : [HviConstant]
    slot : int
    handle : int = 0
    
@dataclass
class Hvi:
    file_name : str
    hviModules : [HviModule]
    handle : int = 0

@dataclass
class Fpga:
    file_name : str

@dataclass
class SubPulseDescriptor:
    carrier : float
    width : float
    toa : float
    amplitude : float
    bandwidth : float

@dataclass
class PulseDescriptor:
    id : int
    pri : float()
    pulses : [SubPulseDescriptor] = None

@dataclass
class ModuleDescriptor:
    model : str
    channels: int
    sample_rate : float
    slot : int
    fpga : Fpga
    mode : int
    loDescriptors : [LoDescriptor]
    pulseDescriptors : [PulseDescriptor]
    queues: [Queue] = None
    handle : int = 0

@dataclass
class Config:
    modules : [ModuleDescriptor]
    hvi : Hvi


def loadConfig(configFile : str = 'latest'):
    if configFile == 'latest':
        if os.path.exists('./config_hist'):
            latest_hist = 0
            for file in os.listdir('./config_hist'):
                name = os.path.splitext(file)[0]
                hist = int(name.split('_')[-1])
                if hist > latest_hist:
                    latest_hist = hist
            configFile = './config_hist/config_' + str(latest_hist) + '.yaml'
        else:
            configFile = 'config_default.yaml'
            
    with open(configFile, 'r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    log.info("Opened: {}".format(configFile))
    return (config)
    

