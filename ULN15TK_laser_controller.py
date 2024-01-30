# -*- coding: utf-8 -*-
import subprocess
import serial
import PyQt5.uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction
from PyQt5 import QtCore as core
from serial import SerialException
from math import isclose
import csv
import datetime


class AppWindow(QMainWindow):
    serialPort = 0
    defaultPort = "COM5"

    def __init__(self, parent = None):
            super(AppWindow, self).__init__(parent)
        #---Load GUI
            PyQt5.uic.loadUi('ULN15TK_mainwindow.ui', self)
        
            # Initialize temperature limit variables
            # Temperature limits are +/- 5 deg C from the nominal temperature
            self.minFBGTemperature = 8.0
            self.maxFBGTemperature = 30.0
            self.minLaserChipTemperature = 15.0
            self.maxLaserChipTemperature = 30.0
            
            self.minAppliedTemperature = -5.5
            self.maxAppliedTemperature = 5.5
            
            self.connectButton.clicked.connect(self.connectSerial)
            self.temperatureSliderFBG.valueChanged.connect(self.updateTemperatureDisplayFBG)
            self.temperatureSliderLaserChip.valueChanged.connect(self.updateTemperatureDisplayLaserChip)
            self.currentSlider.valueChanged.connect(self.updateCurrentDisplay)
            self.FBGButton.toggled.connect(self.temperatureControlMode)
            self.LaserChipButton.toggled.connect(self.temperatureControlMode)
            self.OFFButton.toggled.connect(self.temperatureControlMode)
            self.inputTempLimit.valueChanged.connect(self.updateTemperatureLimit)

            quit = QAction("Quit", self)
            quit.triggered.connect(self.closeEvent)

            self.startTime = None
            #set up a timer to periodically get the amplifier status
            self.timer  = core.QTimer(self)
            self.timer.setInterval(1000)          # Throw event timeout with an interval of 1000 milliseconds
            self.timer.timeout.connect(self.getStatus) # each time timer counts a second, call self.blink
            
            #set up a second timer to periodically clear messages
            self.messageTimer  = core.QTimer(self)
            self.messageTimer.setInterval(7000)          # Throw event timeout with an interval of 1000 milliseconds
            self.messageTimer.timeout.connect(self.clearMessages) # each time timer counts a second, call self.blink            

            # Populate list of available COM ports
            output = subprocess.run(["python","-m","serial.tools.list_ports"],stdout=subprocess.PIPE)
            portlist = output.stdout.decode().split()

            defidx = 0
            for p in portlist:
                self.portlist.addItem(p)
                if p == self.defaultPort:
                    defidx = self.portlist.count() - 1

            self.portlist.setCurrentIndex(defidx)


    def updateTemperatureDisplayFBG(self):
        tempVal = float(self.temperatureSliderFBG.value() / 100.0)

        if tempVal > self.maxFBGTemperature:
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText('FBG T above limit of {:.2f} C'.format(self.maxFBGTemperature))            
            self.temperatureSliderFBG.setValue(int(self.maxFBGTemperature*100))
            tempVal = self.maxFBGTemperature
            
        elif tempVal < self.minFBGTemperature:
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText('FBG T below limit of {:.2f} C'.format(self.minFBGTemperature))            
            self.temperatureSliderFBG.setValue(int(self.minFBGTemperature*100))
            tempVal = self.minFBGTemperature                
        
        self.temperatureSetDisplayFBG.display('{:.2f}'.format(tempVal))
        self.setTemperature(tempVal, 'FBG')
        
        
    def updateTemperatureDisplayLaserChip(self):
        tempVal = float(self.temperatureSliderLaserChip.value() / 100.0)
        
        if tempVal > self.maxLaserChipTemperature:
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText('Laser Chip T above limit of {:.2f} C'.format(self.maxLaserChipTemperature))            
            self.temperatureSliderLaserChip.setValue(int(self.maxLaserChipTemperature*100))
            tempVal = self.maxLaserChipTemperature
            
        elif tempVal < self.minLaserChipTemperature:
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText('Laser Chip T set below limit of {:.2f} C'.format(self.minLaserChipTemperature))            
            self.temperatureSliderLaserChip.setValue(int(self.minLaserChipTemperature*100))
            tempVal = self.minLaserChipTemperature            

        self.temperatureSetDisplayLaserChip.display('{:.2f}'.format(tempVal))
        self.setTemperature(tempVal, 'Laser Chip')    
        
    
    def setTemperature(self, value, mode):
        
        if mode == 'FBG':
            cmdStr = 'write_param fbg_tec_ctrl.setpoint {:.2f}\r\n'.format(value)
             
        elif mode == 'Laser Chip':
            cmdStr = 'write_param laser_tec_ctrl.setpoint {:.2f}\r\n'.format(value)
            
        if self.serialPort:
            self.serialPort.write(cmdStr.encode('ascii'))
            outStr = self.serialPort.readlines(5)
            responses = [outs.decode('ascii').rstrip() for outs in outStr]
            for response in responses:
                if response:
                    message = response.split(':')[-1]
                    if 'OK' in message:
                        self.comoutLaserMessages.setStyleSheet('color: rgb(0,0,0)')
                        self.comoutLaserMessages.setText(message)                        
                    else:
                        self.comoutLaserMessages.setStyleSheet('color: rgb(255,0,0)')
                        self.comoutLaserMessages.setText(message)                         


    def updateCurrentDisplay(self):
        currentVal = self.currentSlider.value()
        
        self.currentSetDisplay.display('{:}'.format(currentVal))
        self.setCurrent(currentVal/1e3) # Value displayed in mA but needs to be passed as A    
        
    
    def setCurrent(self, value):
        
        cmdStr = 'write_param laser.current {:.3f}\r\n'.format(value)
             
        if self.serialPort:
            self.serialPort.write(cmdStr.encode('ascii'))
            outStr = self.serialPort.readlines(5)
            responses = [outs.decode('ascii').rstrip() for outs in outStr]
            for response in responses:
                if response:
                    message = response.split(':')[-1]
                    if 'OK' in message:
                        self.comoutLaserMessages.setStyleSheet('color: rgb(0,0,0)')
                        self.comoutLaserMessages.setText(message)                        
                    else:
                        self.comoutLaserMessages.setStyleSheet('color: rgb(255,0,0)')
                        self.comoutLaserMessages.setText(message)
                        
                        
    def updateTemperatures(self):
        '''Updates the temperature displays'''
        
        # Read FBG temperature
        fbgTemperature = self._getFBGTemperature()
        self.temperatureFBGDisplay.display('{:.2f}'.format(fbgTemperature))
        
        # Read laser chip temperature
        laserTemperature = self._getLaserChipTemperature()
        self.temperatureLaserChipDisplay.display('{:.2f}'.format(laserTemperature))
        
        # Read laser case temperature
        laserCaseTemperature = self._getLaserCaseTemperature()
        self.temperatureLaserCaseDisplay.display('{:.2f}'.format(laserCaseTemperature))
        
        # Read the external applied TEC temperature
        externalTECTempApplied = self._getExternalTECTempApplied()
        self.temperatureAppliedDisplay.display('{:.3f}'.format(externalTECTempApplied))
        
        # Read and update the status of the temperature controler
        controlMode = self._getTECControlMode()
        self.updateTECControlModeDisplay(controlMode)
        
        # Set the applied temperature to 0 if the TEC mode is off
        if controlMode == 'OFF':
            self.temperatureAppliedDisplay.display('{:.3f}'.format(0.0))
            
         
    def updateCurrent(self):
        '''Updates the current display'''
        
        # Read current
        laserCurrent = self._getLaserCurrent()
        self.currentDisplay.display('{:}'.format(laserCurrent))

        
    def getLaserInfo(self):
        
        cmdStr = 'read_string module_sn\r\n'
        self.serialPort.write(cmdStr.encode('ascii'))
            
        outStr = self.serialPort.readlines(3)
        laserInfo = [outs.decode('ascii').rstrip() for outs in outStr]        
        
        for infoStr in laserInfo:
            if infoStr:
                info = infoStr.split(':')
                self.serialOutput.setStyleSheet('color: rgb(0,0,0)')
                textOut = info[-1]
                self.serialOutput.setText(textOut)
          
        
    def getLaserState(self):
        cmdStr = 'read_param laser_state\r\n'
        self.serialPort.write(cmdStr.encode('ascii'))
        
        laserState = []
            
        outStr = self.serialPort.readlines(3)
        laserState = [outs.decode('ascii').rstrip() for outs in outStr]
                
        for stateStr in laserState:
            if stateStr:
                state = stateStr.split(':')
                stateValue = int(state[-1].split(',')[0])    
               
        if stateValue == 60:
            self.comoutLaser.setStyleSheet('color: rgb(0,0,0)')
            textOut = 'Laser ON'
            self.comoutLaser.setText(textOut)
            
        elif stateValue == 61:
            self.comoutLaser.setStyleSheet('color: rgb(0,0,0)')
            textOut = 'Laser OFF (normal)'
            self.comoutLaser.setText(textOut)
            
        elif stateValue == 62:
            self.comoutLaser.setStyleSheet('color: rgb(0,255,0)')
            textOut = 'Laser OFF: interlock'
            self.comoutLaser.setText(textOut)
            
        elif stateValue == 63:
            self.comoutLaser.setStyleSheet('color: rgb(255,0,0)')
            textOut = 'Laser OFF: fault'
            self.comoutLaser.setText(textOut)
            
        elif stateValue == 64:
            self.comoutLaser.setStyleSheet('color: rgb(255,0,0)')
            textOut = 'Laser state UNKNOWN'
            self.comoutLaser.setText(textOut)
            
        elif stateValue == 65:
            self.comoutLaser.setStyleSheet('color: rgb(0,0,0)')
            textOut = 'Laser is starting...'
            self.comoutLaser.setText(textOut)
            
        else:
            textOut = 'Bad message.'
            self.comoutLaser.setText(textOut)


    def connectSerial(self):
        if self.serialPort:
            self.serialPort.close()
        
        try:
            self.serialPort = serial.Serial(port = self.portlist.currentText(), baudrate=19200, bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)
            self.comoutProgram.setStyleSheet('color: rgb(0,255,0)')
            self.comoutProgram.setText('Connected!')
            self.startTime = datetime.datetime.now()
            
            self.getLaserInfo()
            self.getLaserState()
            self.updateTemperatures()
            self.updateCurrent()
            self.updateSliderValues()
            self.temperatureControlMode()         
            
            self.timer.start() # now that a serial port is connected, start poling for status updates
            self.messageTimer.start()
            
        except SerialException as e:
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText(e.args[0][0:65]+'...')
            self.serialPort = None


    def updateTemperatureLimit(self):
        '''Updates the temperature limit for external TEC setpoint.'''
        
        limitValue = float(self.inputTempLimit.value())
        
        # Verify that we are limiting to +/- 5.5 degrees
        if limitValue > 5.5:
            limitValue = 5.5
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            textOut = 'Limit value greater than 5.5 C'
            self.comoutProgram.setText(textOut)
        
        # Set new limit    
        cmdStr = 'write_param tec_adj.range {:.2f}\r\n'.format(limitValue)
        self.serialPort.write(cmdStr.encode('ascii'))
        
        outStr = self.serialPort.readlines(5)
        responses = [outs.decode('ascii').rstrip() for outs in outStr]
        for response in responses:
            if response:
                message = response.split(':')[-1]
                if 'OK' in message:
                    self.comoutLaserMessages.setStyleSheet('color: rgb(0,0,0)')
                    self.comoutLaserMessages.setText(message)                        
                else:
                    self.comoutLaserMessages.setStyleSheet('color: rgb(255,0,0)')
                    self.comoutLaserMessages.setText(message)
                    
        # Get limit value and verify it matches input
        cmdStr = 'read_param tec_adj.range\r\n'
        self.serialPort.write(cmdStr.encode('ascii'))
        
        outStr = self.serialPort.readlines(3)
        limitTemp = [outs.decode('ascii').rstrip() for outs in outStr]

        for limitTempStr in limitTemp:
            if limitTempStr:
                setLimitValueStr = limitTempStr.split(':')
                setLimitValue = float(setLimitValueStr[-1].split(',')[0])
                
        if not isclose(setLimitValue, limitValue, rel_tol=1e-6):
            self.comoutProgram.setStyleSheet('color: rgb(255,0,0)')
            self.comoutProgram.setText('Limit mismatch : {0:.2f} =/= {1:.2f}!!'.format(limitValue, setLimitValue))            
                
        
    def temperatureControlMode(self):
        '''This activates the external TEC setpoint adjustment.'''
        
        if self.OFFButton.isChecked():
            cmdStr = 'write_param tec_adj.select {:}\r\n'.format(int(120))
            
        elif self.FBGButton.isChecked():
            cmdStr = 'write_param tec_adj.select {:}\r\n'.format(int(122))
            
        elif self.LaserChipButton.isChecked():
            cmdStr = 'write_param tec_adj.select {:}\r\n'.format(int(121))
            
        self.serialPort.write(cmdStr.encode('ascii'))
        
        outStr = self.serialPort.readlines(5)
        responses = [outs.decode('ascii').rstrip() for outs in outStr]
        for response in responses:
            if response:
                message = response.split(':')[-1]
                if 'OK' in message:
                    self.comoutLaserMessages.setStyleSheet('color: rgb(0,0,0)')
                    self.comoutLaserMessages.setText(message)                        
                else:
                    self.comoutLaserMessages.setStyleSheet('color: rgb(255,0,0)')
                    self.comoutLaserMessages.setText(message)        

        
    def updateSliderValues(self):
        FBGValue = self._getFBGTemperature() * 100.0
        self.temperatureSliderFBG.setValue(int(FBGValue))
        
        LaserChipValue = self._getLaserChipTemperature() * 100.0
        self.temperatureSliderLaserChip.setValue(int(LaserChipValue))
        
        laserCurrentValue = self._getLaserCurrent()
        self.currentSlider.setValue(laserCurrentValue)
        
        
    def getStatus(self):

        if self.serialPort:
            
            self.getLaserState()
            self.updateTemperatures()
            self.updateCurrent()
            
            
    def clearMessages(self):
        
        self.comoutLaserMessages.clear()
        self.comoutProgram.clear()
        
        
    def _getFBGTemperature(self):
        # Read FBG temperature
        cmdStr = 'read_param fbg_tec_ctrl.temperature\r\n'
        self.serialPort.write(cmdStr.encode('ascii'))
                       
        outStr = self.serialPort.readlines(3)
        fbgTemp = [outs.decode('ascii').rstrip() for outs in outStr]

        for fbgTempStr in fbgTemp:
            if fbgTempStr:
                tempFBG = fbgTempStr.split(':')
                fbgTemperature = float(tempFBG[-1].split(',')[0])         

        return fbgTemperature
    
    
    def _getLaserChipTemperature(self):
        # Read laser chip temperature
        cmdStr = 'read_param laser_tec_ctrl.temperature\r\n'           
        self.serialPort.write(cmdStr.encode('ascii')) 
   
        outStr = self.serialPort.readlines(3)
        laserTemp = [outs.decode('ascii').rstrip() for outs in outStr]

        for laserTempStr in laserTemp:
            if laserTempStr:
                tempLaser = laserTempStr.split(':')
                laserTemperature = float(tempLaser[-1].split(',')[0])
                
        return laserTemperature
    
    
    def _getLaserCaseTemperature(self):
        # Read laser case temperature
        cmdStr = 'read_param laser.case.temperature\r\n'           
        self.serialPort.write(cmdStr.encode('ascii')) 
   
        outStr = self.serialPort.readlines(3)
        laserTemp = [outs.decode('ascii').rstrip() for outs in outStr]

        for laserTempStr in laserTemp:
            if laserTempStr:
                tempLaser = laserTempStr.split(':')
                laserCaseTemperature = float(tempLaser[-1].split(',')[0])
                
        return laserCaseTemperature
    
    
    def _getLaserCurrent(self):
        # Returns the current in mA
        # Note Thorlabs returns it in A, I do the conversion
        cmdStr = 'read_param laser.current\r\n'           
        self.serialPort.write(cmdStr.encode('ascii')) 
   
        outStr = self.serialPort.readlines(3)
        laserCurr = [outs.decode('ascii').rstrip() for outs in outStr]

        for laserCurrStr in laserCurr:
            if laserCurrStr:
                laserCurrentA = laserCurrStr.split(':')
                laserCurrentmA = int(float(laserCurrentA[-1].split(',')[0]) *1e3)
                
        return laserCurrentmA       
        
    
    def _getExternalTECTempApplied(self):
        # Read applied external TEC temperature
        cmdStr = 'read_param tec_adj\r\n'           
        self.serialPort.write(cmdStr.encode('ascii')) 
   
        outStr = self.serialPort.readlines(3)
        externalTemp = [outs.decode('ascii').rstrip() for outs in outStr]

        for tecTempStr in externalTemp:
            if tecTempStr:
                tempTEC = tecTempStr.split(':')
                externalTECTemperatureApplied = float(tempTEC[-1].split(',')[0])
                
        return externalTECTemperatureApplied
    
    
    def _getTECControlMode(self):
        # Read external TEC control mode
        cmdStr = 'read_param tec_adj.select\r\n'           
        self.serialPort.write(cmdStr.encode('ascii')) 
   
        outStr = self.serialPort.readlines(3)
        externalMode = [outs.decode('ascii').rstrip() for outs in outStr]

        for tecModeStr in externalMode:
            if tecModeStr:
                modeTEC = tecModeStr.split(':')
                externalTECMode = int(modeTEC[-1].split(',')[0])
                
        if externalTECMode == 120:
            mode = 'OFF'
            
        elif externalTECMode == 121:
            mode = 'Laser Chip'
            
        elif externalTECMode == 122:
            mode = 'FBG'
            
        else:
            print('whoops')
        
        return mode

    
    def updateTECControlModeDisplay(self, mode):
        
        if mode == 'OFF' and not self.OFFButton.isChecked():
            self.OFFButton.click()
            
        elif mode == 'Laser Chip' and not self.LaserChipButton.isChecked():
            self.LaserChipButton.click()
            
        elif mode == 'FBG' and not self.FBGButton.isChecked():
            self.FBGButton.click()
            
        else:
            pass


    def closeEvent(self, event):
        if self.serialPort:
            self.serialPort.close()
            self.serialPort = 0

        event.accept()
        

if ( __name__ == '__main__' ):
#---Initialize the APP
    app = None
    if ( not app ):
        app = QApplication([])
        app.setQuitOnLastWindowClosed(True)
    window = AppWindow()
    window.show()
#---RUN
    if ( app ):
        app.exec_()
