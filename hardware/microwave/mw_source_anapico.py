# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware file to control Anritsu 70GHz Device.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Parts of this file were developed from a PI3diamond module which is
Copyright (C) 2009 Helmut Rathgen <helmut.rathgen@gmail.com>

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import numpy as np
import visa

from core.module import Base, ConfigOption
from interface.microwave_interface import MicrowaveInterface
from interface.microwave_interface import MicrowaveLimits
from interface.microwave_interface import MicrowaveMode
from interface.microwave_interface import TriggerEdge


class MicrowaveAnapico(Base, MicrowaveInterface):
    """ This is the Interface class to define the controls for the simple
        microwave hardware from Anapico (APSIN 6000) via Ethernet.
        sweep mode not tested and might be unstable
    """
    _modclass = 'MicrowaveAnapico'
    _modtype = 'hardware'
    _ip_address = ConfigOption('ip_address', missing='error')
    _ip_timeout = ConfigOption('ip_timeout', missing='warn')

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        # trying to load the visa connection to the module
        self.rm = visa.ResourceManager()
        try:
            self._ip_connection = self.rm.open_resource(
                self._ip_address,
                timeout=self._ip_timeout*1000)
        except:
            self.log.error('This is Anapico: could not connect to IP '
                      'address >>{}<<.'.format(self._ip_address))
            raise
        # native command mode, some things are missing in SCPI mode
        #self._ip_connection.write('SYST:LANG \"NATIVE\"')
        self._ip_connection.read_termination = '\n'
        self.model = self._ip_connection.query('*IDN?;').split(',')[1]
        self.log.info('Anapico {} initialised and connected to hardware.'
                ''.format(self.model))

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        self._ip_connection.close()
        self.rm.close()

    def get_limits(self):
        """ Right now, this is for APSIN6000 only."""
        limits = MicrowaveLimits()
        limits.supported_modes = (MicrowaveMode.CW, MicrowaveMode.LIST)

        limits.min_frequency = 10e3
        limits.max_frequency = 6e9

        limits.min_power = -50
        limits.max_power = 10

        limits.list_minstep = 0.001
        limits.list_maxstep = 6e9
        limits.list_maxentries = 2000

        limits.sweep_minstep = 0.001
        limits.sweep_maxstep = 6e9
        limits.sweep_maxentries = 3501
        return limits

    def on(self):
        """ Switches on any preconfigured microwave output.

        @return int: error code (0:OK, -1:error)
        """
        self._ip_connection.write(':OUTP ON;')
        self._ip_connection.write('*WAI;')

        return 0

    def off(self):
        """ Switches off any microwave output.

        @return int: error code (0:OK, -1:error)
        """

        if self._ip_connection.query(':FREQ:MODE?;') != 'CW':
            self._ip_connection.write(':FREQ:MODE CW;')
        self._ip_connection.write(':OUTP OFF;')
        self._ip_connection.write('*WAI;')
        return 0

    def get_power(self):
        """ Gets the microwave output power.

        @return float: the power set at the device in dBm
        """
        return float(self._ip_connection.ask(':POW?;'))

    def set_power(self, power=None):
        """ Sets the microwave output power.

        @param float power: the power (in dBm) set for this device

        @return int: error code (0:OK, -1:error)
        """
        if power is not None:
            self._ip_connection.write(':POW {0:f};'.format(power))
            return 0
        else:
            return -1

    def get_frequency(self):
        """ Gets the frequency of the microwave output.

        @return float: frequency (in Hz), which is currently set for this device
        """
        return float(self._ip_connection.ask(':FREQ?;'))

    def set_frequency(self, freq=None):
        """ Sets the frequency of the microwave output.

        @param float freq: the frequency (in Hz) set for this device

        @return int: error code (0:OK, -1:error)
        """
        if freq is not None:
            self._ip_connection.write(':FREQ:CW {0:f};'.format(freq))
            return 0
        else:
            return -1

    def set_cw(self, freq=None, power=None, useinterleave=None):
        """ Sets the MW mode to cw and additionally frequency and power

        @param float freq: frequency to set in Hz
        @param float power: power to set in dBm
        @param bool useinterleave: If this mode exists you can choose it.

        @return int: error code (0:OK, -1:error)

        Interleave option is used for arbitrary waveform generator devices.
        """
        error = 0
        if freq is not None:
            error = self.set_frequency(freq)
        else:
            return -1

        if power is not None:
            error = self.set_power(power)
        else:
            return -1
        self._ip_connection.write(':FREQ:MODE CW;')
        return error

    def set_list(self, freq=None, power=None):
        """ Sets the MW mode to list mode

        @param list freq: list of frequencies in Hz
        @param float power: MW power of the frequency list in dBm

        @return int: error code (0:OK, -1:error)
        """
        error = 0

        # put all frequencies into a string
        self._ip_connection.write(':LIST:DIR UP')
        freqstring = ' {0:f}'.format(freq[0])
        for f in freq[:-1]:
            freqstring += ' ,{0:f}'.format(f)
        freqstring += ' ,{0:f}'.format(freq[-1])

        freqcommand = ':LIST:FREQ' + freqstring

        self._ip_connection.write(freqcommand)
        self._ip_connection.write('*WAI;')

        # there are n+1 list entries for scanning n frequencies
        # due to counter/trigger issues
        powcommand = ':LIST:POW {0}{1};'.format(power, (' ,' + str(power)) * (len(freq)))
        self._ip_connection.write(powcommand)

        self._ip_connection.write('*WAI;')
        self._ip_connection.write(':LIST:MODE:MAN')

        #create command for delaytime, apparently important because otherwise list mode won't work (bug anapico???)
        delstring = ' {0:f}'.format(0)
        dwellstring = ' {0:f}'.format(1)
        for i in range(0,len(freq)):
            delstring += ' ,{0:f}'.format(0)
            dwellstring+= ' ,{0:f}'.format(1)
        delcommand = ':LIST:DEL' + delstring
        dwellcommand = 'LIST:DWEL' + dwellstring
        self._ip_connection.write(delcommand)
        self._ip_connection.write(dwellcommand)


        return error

    def reset_listpos(self):
        """ Reset of MW List Mode position to start from first given frequency

        @return int: error code (0:OK, -1:error)
        """
        self._ip_connection.write(':ABOR;')
        self._ip_connection.write('*WAI;')
        return 0

    def list_on(self):
        """ Switches on the list mode.

        @return int: error code (1: ready, 0:not ready, -1:error)
        """
        self._ip_connection.write(':OUTP ON;')
        self._ip_connection.write('*WAI;')
        self._ip_connection.write(':FREQ:MODE LIST;')
        self._ip_connection.write('*WAI;')

        return self._ip_connection.query('*OPC?')

    def set_ext_trigger(self, pol=TriggerEdge.RISING):
        """ Set the external trigger for this device with proper polarization.

        @param TriggerEdge pol: polarisation of the trigger (basically rising edge or
                        falling edge)

        @return int: error code (0:OK, -1:error)
        """
        if pol == TriggerEdge.RISING:
            edge = 'POS'
        elif pol == TriggerEdge.FALLING:
            edge = 'NEG'
        else:
            return -1
        try:

            self._ip_connection.write(':TRIG:TYPE POIN')
            self._ip_connection.write(':TRIG:SOUR EXT;')
            self._ip_connection.write(':TRIG:SLOP {0};'.format(edge))

        except:
            return -1
        return 0

    def set_sweep(self, start, stop, step, power):

        """ Activate sweep mode on the microwave source


        @param start float: start frequency
        @param stop float: stop frequency
        @param step float: frequency step
        @param power float: output power
        @return int: number of frequency steps generated
        """
        self._ip_connection.write(':SOUR:POW ' + str(power)+';')
        self._ip_connection.write('*WAI')
        self._step_points = int((stop-start-step)/step)
        self._ip_connection.write(':SOUR:FREQ:STAR ' + str(start-step)+';')
        self._ip_connection.write(':SOUR:FREQ:STOP ' + str(stop)+';')
        self._ip_connection.write(':SOUR:SWE:POIN' + str(self._step_points)+';')
        self._ip_connection.write(':SOUR:SWE:SPAC LIN;')
        self._ip_connection.write(':TRIG:SOUR BUS;')
        self._ip_connection.write('*WAI;')
        n = int(np.round(float(self._ip_connection.query(':SWE:FREQ:POIN?;'))))
        if n != len(self._mw_frequency_list):
             return -1
        return n - 1

    def reset_sweep(self):
        """ Reset of MW List Mode position to start from first given frequency

        @return int: error code (0:OK, -1:error)
        """
        self._ip_connection.write(':ABOR;')
        return 0

    def sweep_on(self):
        """ Switches on sweep mode.

        @return int: error code ( 0:ok, -1:error)
        """
        self._ip_connection.write('*TRG;')
        return 0
