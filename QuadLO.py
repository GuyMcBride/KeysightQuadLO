# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 16:45:52 2020

@author: gumcbrid
"""

import os
import numpy as np
import time
import sys
import logging

sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1 as key

import pulses as pulseLab

import Configuration

log = logging.getLogger(__name__)

if len(sys.argv) > 1:
    configName = sys.argv[1]
else:
    configName = 'latest'   
log.info("Opening Config file: {})".format(configName))

config = Configuration.loadConfig(configName)

def main():
    configureAwgs()
    configureHvi()
    writeHviConstants()
    compileDownloadHvi()
    startHvi()
    time.sleep(1)
    closeHvi()
    closeAwgs()
   
    
def configureAwgs():
    chassis = key.SD_Module.getChassisByIndex(1)
    if chassis < 0:
        log.error("Finding Chassis: {} {}".format(chassis, 
                                                  key.SD_Error.getErrorMessage(chassis)))
    log.info("Chassis found: {}".format(chassis))
    for module in config.modules:
        if module.model == 'M3202A':
            log.info("Configuring AWG in slot {}...".format(module.slot))
            module.handle = key.SD_AOU()
            awg = module.handle
            error = awg.openWithSlotCompatibility('', 
                                                  chassis, 
                                                  module.slot,
                                                  key.SD_Compatibility.KEYSIGHT)
            if error < 0:
                log.info("Error Opening - {}".format(error))
            log.info("Loading FPGA image: {}".format(module.fpga.file_name))
            error = awg.FPGAload(os.getcwd() + '\\' + module.fpga.file_name)
            if error < 0:
               log.error('Loading FPGA bitfile: {} {}'.format(error, 
                                                              key.SD_Error.getErrorMessage(error)))
            #Clear all queues and waveforms
            awg.waveformFlush()
            for channel in range(module.channels):
                awg.AWGflush(channel + 1)
            #Set up the channels suppporting interleaving
            setupLOs(module)
            for register in module.fpga.registers:
                error = module.handle.FPGAwritePCport(0, 
                                                      [register.value], 
                                                      register.address, 
                                                      key.SD_AddressingMode.FIXED,
                                                      key.SD_AccessMode.NONDMA)
                if error < 0:
                    log.error('WriteRegister: {} {}'.format(error, 
                                                            key.SD_Error.getErrorMessage(error)))
                    log.error('Address: {}'.format(8))
                    log.error('Buffer [{}]'.format(module.mode))
            loadInterleavedWaves(module)
            enqueueWaves(module)
            trigmask = 0
            for channel in range(module.channels):
                awg.channelWaveShape(channel + 1, key.SD_Waveshapes.AOU_AWG)
                trigmask = trigmask | 2**channel
            #Remove this if using HVI
#            log.info("triggering with {}".format(trigmask))
#            awg.AWGtriggerMultiple(trigmask)

def closeAwgs():
    for module in config.modules:
        if module.model == "M3202A":
            log.info("Stopping AWG in slot {}...".format(module.slot))
            for channel in range(1, module.channels + 1):
                error = module.handle.AWGstop(channel)
                if error < 0:
                    log.info("Stopping AWG failed! - {}".format(error))
            module.handle.close()
            log.info("Finished stopping and closing AWG")
    

def setupLOs(module):
    for loBank in module.loDescriptors:
        for ii, carrier in enumerate(loBank.frequencies):
            log.info("Setting LO: {} to {} on channel {}".format(ii, 
                                                                 carrier, 
                                                                 loBank.channel))
            [A, B] = calcAandB(carrier, module.sample_rate)
            error = module.handle.FPGAwritePCport(loBank.channel - 1, 
                                                  [A], 
                                                  ii * 2, 
                                                  key.SD_AddressingMode.FIXED, 
                                                  key.SD_AccessMode.NONDMA)
            if error < 0:
                log.error('WriteRegister: {} {}'.format(error, 
                                                        key.SD_Error.getErrorMessage(error)))
                log.error('Address: {}'.format(ii))
                log.error('Buffer [{}]'.format(A))
            error = module.handle.FPGAwritePCport(loBank.channel, 
                                                  [B], 
                                                  ii * 2 + 1, 
                                                  key.SD_AddressingMode.FIXED,
                                                  key.SD_AccessMode.NONDMA)
            if error < 0:
                log.error('WriteRegister: {} {}'.format(error, 
                                                        key.SD_Error.getErrorMessage(error)))
                log.error('Address: {}'.format(ii + 1))
                log.error('Buffer [{}]'.format(B))
            
def loadInterleavedWaves(module):
    for pulseDescriptor in module.pulseDescriptors:
        if len(pulseDescriptor.pulses) > 1:
            waves = []
            for pulse in pulseDescriptor.pulses:
                wave = pulseLab.createPulse(module.sample_rate / 5,
                                            pulse.width,
                                            pulse.bandwidth,
                                            pulse.amplitude / 1.5,
                                            pulseDescriptor.pri,
                                            pulse.toa)
                waves.append(wave.wave)
            wave = interweavePulses(waves)
        else:
            pulse = pulseDescriptor.pulses[0]
            wave = pulseLab.createPulse(module.sample_rate,
                                        pulse.width,
                                        pulse.bandwidth,
                                        pulse.amplitude / 1.5,
                                        pulseDescriptor.pri,
                                        pulse.toa)

            waveform = key.SD_Wave()
            error = waveform.newFromArrayDouble(key.SD_WaveformTypes.WAVE_ANALOG, 
                                                wave)
            if error < 0:
                log.info("Error Creating Wave: {} {}".format(error,
                                                              key.SD_Error.getErrorMessage(error)))
            log.info("Loading waveform length: {} as ID: {} ".format(len(interweavePulses(waves)), 
                                                                     pulseDescriptor.id))
            error = module.handle.waveformLoad(waveform, pulseDescriptor.id)
            if error < 0:
                log.info("Error Loading Wave - {} {}".format(error,
                                                             key.SD_Error.getErrorMessage(error)))
                    
def enqueueWaves(module):
    for queue in module.queues:
        for item in queue.items:
            if item.trigger:
                trigger = key.SD_TriggerModes.SWHVITRIG
            else:
                trigger = key.SD_TriggerModes.AUTOTRIG
            start_delay = item.start_time / 10E-09 # expressed in 10ns
            start_delay = int(np.round(start_delay))
            log.info("Enqueueing: {} in channel {}".format(item.pulse_id, 
                                                           queue.channel))
            error = module.handle.AWGqueueWaveform(queue.channel, 
                                                    item.pulse_id, 
                                                    trigger, 
                                                    start_delay, 
                                                    1, 
                                                    0)
            if error < 0:
                log.info("Queueing waveform failed! - {}".format(error))
        error =module.handle.AWGqueueConfig(queue.channel, 
                                          key.SD_QueueMode.CYCLIC)
        if error < 0:
            log.error("Configure cyclic mode failed! - {}".format(error))
        log.info("starting channel {}".format(queue.channel))
        module.handle.AWGstart(queue.channel)


def writeHviConstants():
    hvi = config.hvi.handle
    for hviModule in config.hvi.hviModules:
        for constant in hviModule.constants:
            log.info("Writing HVI Constant: {}, {}{} to {}".format(constant.name,
                                                                    constant.value,
                                                                    constant.units,
                                                                    hviModule.name))
            if constant.units == '':
                error = hvi.writeIntegerConstantWithUserName(hviModule.name, 
                                                             constant.name, 
                                                             int(constant.value))
            else:
                error = hvi.writeDoubleConstantWithUserName(hviModule.name, 
                                                            constant.name, 
                                                            float(constant.value),
                                                            constant.units)
    
            if error < 0:
                log.error(" for {}, Writing HVI Register: {} - Error: {}: {}".format(hviModule.name,
                                                                                     constant.name, 
                                                                                     error, 
                                                                                     key.SD_Error.getErrorMessage(error)))
    
def configureHvi():
    config.hvi.handle = key.SD_HVI()
    hvi = config.hvi.handle
    log.info("Opening HVI file: {}".format(config.hvi.file_name))
    hviID = hvi.open(config.hvi.file_name)
    if hviID ==  key.SD_Error.RESOURCE_NOT_READY: #Only for old library
        log.debug("No Critical Error - {}: {}".format(hviID, key.SD_Error.getErrorMessage(hviID)))
        log.debug("Using old library -> Need to compile HVI...")
    elif hviID == key.SD_Error.DEMO_MODULE: #Only for old library
         log.debug("No Critical Error - {} {}".format(hviID, key.SD_Error.getErrorMessage(hviID)))
         log.debug("Using old library -> need to assigning HW modules...")
    elif hviID < 0:
         log.error("Opening HVI - {}: {}".format(hviID, key.SD_Error.getErrorMessage(hviID)))
       
    for hviModule in config.hvi.hviModules:
        #Find the handle for this module from its slot
        for module in config.modules:
            if module.slot == hviModule.slot:
                hviModule.handle = module.handle
                log.info("Assigning {} to {} in slot {}".format(hviModule.name, module.model, module.slot))
                error = hvi.assignHardwareWithUserNameAndModuleID(hviModule.name, module.handle)
                if error == -8069:
                    log.debug("Assigning HVI {}, Spurious Error- {}: {}".format(hviModule.name, error, key.SD_Error.getErrorMessage(error)))
                    log.info("HVI HW assigned for {}, {} in slot {}".format(hviModule.name, module.model, module.slot))
                elif error < 0:
                    error_msg = "HVI assign HW AOU Failed for: {} in slot {}, {}: {}".format(
                            hviModule.name, 
                            module.model,
                            module.slot,
                            key.SD_Error.getErrorMessage(error))
                    log.error(error_msg)
                else:
                    log.info("HVI HW assigned for {}, {} in slot {}".format(hviModule.name, module.model, module.slot))
    # if the last module assigned has this error then it is more serious
    if error == -8069:
        log.error("Assigning HVI - {}: {}".format(error, key.SD_Error.getErrorMessage(error)))

    
def compileDownloadHvi():
    log.info("Compiling HVI...")
    cmpID = config.hvi.handle.compile()
    if cmpID != 0:
        error = "HVI compile failed : {}".format(key.SD_Error.getErrorMessage(cmpID))
        log.debug(error)
    log.info("Loading HVI...")
    cmpID = config.hvi.handle.load()
    if cmpID == -8038:
        log.debug("HVI contains Demo Module. Please make sure you do an assignHW()")
    elif cmpID != 0:
        error = "HVI load failed : {}".format(key.SD_Error.getErrorMessage(cmpID))
        log.error(error)

def startHvi():
    log.info("Starting HVI...")
    error = config.hvi.handle.start()
    if (error < 0):
        log.error("Starting HVI- {}: {}".format(error, key.SD_Error.getErrorMessage(error)))
        
def closeHvi():
    error  = config.hvi.handle.releaseHW()
    if (error < 0):
        __log.error("Releasing HW - {}: {}".format(error, key.SD_Error.getErrorMessage(error)))
    error = config.hvi.handle.close()
    if (error < 0):
        log.error("Closing HVI - {}: {}".format(error, key.SD_Error.getErrorMessage(error)))
        

def stop():
       pass    

def calcAandB(f, fs=1E9):
    S = 5
    T = 8
    K = (f / fs) * (S / T) * 2**25
    A = int(K)
    B = round((K-A) * 5**10) 
    return A, B

def interweavePulses(pulses):
    interweaved = np.zeros(len(pulses[0]) * 5)
    for ii in range(len(pulses)):
        interweaved[ii::5] = pulses[ii]
    return interweaved

    
if (__name__ == '__main__'):
    main()