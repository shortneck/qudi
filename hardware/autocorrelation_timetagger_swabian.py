# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware dummy for fast counting devices.

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

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import TimeTagger as tt
import numpy as np

from core.module import Base, ConfigOption
from interface.autocorrelation_interface import AutocorrelationConstraints
from interface.autocorrelation_interface import AutocorrelationInterface


class AutocorrelationTimetagger(Base, AutocorrelationInterface):
    """unstable: Jan Kurzhals
    """
    _modclass = 'autocorrelationinterface'
    _modtype = 'hardware'
    _channel_apd_0 = ConfigOption('timetagger_channel_apd_0', missing='error')
    _channel_apd_1 = ConfigOption('timetagger_channel_apd_1', missing='error')

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._count_length = int(10)
        self._bin_width = 1 # bin width in ps
        self._tagger = tt.createTimeTagger()
        self._tagger.reset()
        self.correlation = None

        self.statusvar = 0

    def on_deactivate(self):
        """ Deactivate the FPGA.
        """
        if self.getState() == 'locked':
            self.correlation.stop()
        self.correlation.clear()
        self.correlation = None

    def get_constraints(self):

        """ Get hardware limits of NI device.

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
            """
        constraints = AutocorrelationConstraints()
        constraints.max_channels = 2
        constraints.min_channels = 2
        constraints.min_count_length = 1
        constraints.min_bin_width = 100

        return constraints

    def configure(self, bin_width, count_length):

        """ Configuration of the fast counter.

        @param float bin_width: Length of a single time bin in the time trace
                                  histogram in picoseconds.
        @param float count_length: Total number of bins.

        @return tuple(bin_width, count_length):
                    bin_width: float the actual set binwidth in picoseconds
                    count_length: actual number of bins
        """

        self._bin_width = bin_width
        self._count_length = count_length
        self.statusvar = 1
        if self.correlation != None:
            self._reset_hardware()
        if self._tagger == None:
            return -1
        else:
            try:
                self.correlation = tt.Correlation(
                tagger = self._tagger,
                channel_1 = self._channel_apd_0,
                channel_2 = self._channel_apd_1,
                binwidth = self._bin_width,
                n_bins = self._count_length
                )
                self.correlation.stop()
                return 0

            except:
                return -1

    def _reset_hardware(self):

        self.correlation.clear()

        return 0


    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.statusvar

    def start_measure(self):
        """ Start the fast counter. """
        if self.getState() != 'locked':
            self.lock()
            self.correlation.clear()
            self.correlation.start()
            self.statusvar = 2
        return 0

    def stop_measure(self):
        """ Stop the fast counter. """
        if self.getState() == 'locked':
            self.correlation.stop()
            self.unlock()
        self.statusvar = 1
        return 0

    def pause_measure(self):
        """ Pauses the current measurement.

        Fast counter must be initially in the run state to make it pause.
        """
        if self.getState() == 'locked':
            self.correlation.stop()
            self.statusvar = 3
        return 0

    def continue_measure(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """
        if self.getState() == 'locked':
            self.correlation.start()
            self.statusvar = 2
        return 0

    def get_bin_width(self):
        """ Returns the width of a single timebin in the timetrace in picoseconds.

        @return float: current length of a single bin in seconds (seconds/bin)
        """
        return self._bin_width

    def get_count_length(self):
        """ Returns the number of time bins.

        @return float: number of bins
        """
        return (2*self._count_length+1)

    def get_data_trace(self):
        """

        @return numpy.array: onedimensional array of dtype = int64.
                             Size of array is determined by 2*count_length+1
        """
        correlation_data = np.array(self.correlation.getData(), dtype='int32')

        return correlation_data

    def get_normalized_data_trace(self):
        """

        @return numpy.array: onedimensional array of dtype = int64 normalized
                             according to
                             https://www.physi.uni-heidelberg.de/~schmiedm/seminar/QIPC2002/SinglePhotonSource/SolidStateSingPhotSource_PRL85(2000).pdf
                             Size of array is determined by 2*count_length+1
        """
        return np.array(self.correlation.getDataNormalized(), dtype='int32')

class AutocorrelationDummy(Base, AutocorrelationInterface):
    """
        Dummy for Autocorrelation
    """


    _modclass = 'autocorrelationinterface'
    _modtype = 'hardware'

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._count_length = int(10)
        self._bin_width = 1  # bin width in ps


    def on_deactivate(self):
        """ Deactivate the FPGA.
        """


    def get_constraints(self):

        """ Get hardware limits of NI device.

        @return SlowCounterConstraints: constraints class for slow counter

        FIXME: ask hardware for limits when module is loaded
            """
        constraints = AutocorrelationConstraints()
        constraints.max_channels = 2
        constraints.min_channels = 2
        constraints.min_count_length = 1
        constraints.min_bin_width = 100

        return constraints

    def configure(self, bin_width, count_length):

        """ Configuration of the fast counter.

        @param float bin_width: Length of a single time bin in the time trace
                                  histogram in picoseconds.
        @param float count_length: Total number of bins.

        @return tuple(bin_width, count_length):
                    bin_width: float the actual set binwidth in picoseconds
                    count_length: actual number of bins
        """

        self._bin_width = bin_width
        self._count_length = count_length


    def _reset_hardware(self):


        return 0

    def get_status(self):
        """ Receives the current status of the Fast Counter and outputs it as
            return value.

        0 = unconfigured
        1 = idle
        2 = running
        3 = paused
        -1 = error state
        """
        return self.statusvar

    def start_measure(self):
        """ Start the fast counter. """

        return 0

    def stop_measure(self):
        """ Stop the fast counter. """

        return 0

    def pause_measure(self):
        """ Pauses the current measurement.

        Fast counter must be initially in the run state to make it pause.
        """

        return 0

    def continue_measure(self):
        """ Continues the current measurement.

        If fast counter is in pause state, then fast counter will be continued.
        """

        return 0

    def get_bin_width(self):
        """ Returns the width of a single timebin in the timetrace in picoseconds.

        @return float: current length of a single bin in seconds (seconds/bin)
        """
        return self._bin_width

    def get_count_length(self):
        """ Returns the number of time bins.

        @return float: number of bins
        """
        return (2 * self._count_length + 1)

    def get_data_trace(self):
        """

        @return numpy.array: onedimensional array of dtype = int64.
                             Size of array is determined by 2*count_length+1
        """


        correlation_data = np.random.randint(0, 100, self._count_length, dtype='int32')
        return correlation_data

    def get_normalized_data_trace(self):
        """

        @return numpy.array: onedimensional array of dtype = int64 normalized
                             according to
                             https://www.physi.uni-heidelberg.de/~schmiedm/seminar/QIPC2002/SinglePhotonSource/SolidStateSingPhotSource_PRL85(2000).pdf
                             Size of array is determined by 2*count_length+1
        """
        return np.array(self.correlation.getDataNormalized(), dtype='int32')