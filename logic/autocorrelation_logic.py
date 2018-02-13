# -*- coding: utf-8 -*-
"""
This module operates a confocal microsope.

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

import datetime
import time
from collections import OrderedDict

import matplotlib.pyplot as plt
import numpy as np
from qtpy import QtCore

from core.module import Connector
from core.util.mutex import Mutex
from logic.generic_logic import GenericLogic


class AutocorrelationLogic(GenericLogic):
    """
    This is the Logic class for confocal scanning.
    """
    _modclass = 'AutocorrelationLogic'
    _modtype = 'logic'

    # declare connectors
    #_connectors = {
      #  'autocorrelator': 'AutocorrelationInterface',
      #  'savelogic': 'SaveLogic'
      #  }

    # signals

    autocorrelator = Connector(interface='AutocorrelationInterface')
    savelogic = Connector(interface='SaveLogic')

    sigCorrelationStatusChanged = QtCore.Signal(bool)
    sigCorrelationDataNext = QtCore.Signal()
    sigCorrelationUpdated = QtCore.Signal()


    sigCountLengthChanged = QtCore.Signal(int)
    sigCountingBinWidthChanged = QtCore.Signal(int)
    sigCountingRefreshTimeChanged = QtCore.Signal(int)



    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self.log.info('The following configuration was found.')

        # checking for the right configuration
        for key in config.keys():
            self.log.info('{0}: {1}'.format(key, config[key]))

        #locking for thread safety
        self.threadlock = Mutex()

        self._count_length = 50
        self._bin_width = 500
        self._refresh_time = 1000 #in ms
        self._saving = False

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """

        self._correlation_device = self.get_connector('autocorrelator')
        self._save_logic = self.get_connector('savelogic')

        # Recall saved app-parameters
        if 'count_length' in self._statusVariables:
            self._count_length = self._statusVariables['count_length']
        if 'bin_width' in self._statusVariables:
            self._bin_width = self._statusVariables['bin_width']
        if 'saving' in self._statusVariables:
            self._saving = self._statusVariables['saving']

        self.rawdata = np.zeros([self._correlation_device.get_count_length()])

        self.sigCorrelationDataNext.connect(self.correlation_loop_body, QtCore.Qt.QueuedConnection)

        self._plot_x = np.array(np.zeros(self._count_length),dtype='int32')
        self._plot_y = np.array(np.zeros(self._count_length),dtype='int32')
        self.stopRequested = False
        self.continueRequested = False

    def on_deactivate(self):
        """ Reverse steps of activation

        @return int: error code (0:OK, -1:error)
        """
        # Save parameters to disk
        self._statusVariables['count_length'] = self._count_length
        self._statusVariables['bin_width'] = self._bin_width
        self._statusVariables['saving'] = self._saving
        return 0

    def get_hardware_constraints(self):
        """
        Retrieve the hardware constrains from the counter device.

        @return AutocorrelationConstraints: object with constraints for the autocorrelator
        """
        return self._correlation_device.get_constraints()

    def set_count_length(self, count_length = 300):

        if self.module_state() == 'locked':
            restart = True
        else:
            restart = False

        if count_length > 0:
            self.stop_correlation()
            self._count_length = int(count_length)
            # if the counter was running, restart it
            if restart:
                self.start_correlation()
        else:
            self.log.warning('count_length has to be larger than 0! Command ignored!')
        self.sigCountLengthChanged.emit(self._count_length)
        return self._count_length

    def set_bin_width(self, bin_width=1000):
        """ Sets the frequency with which the data is acquired.

        @param float frequency: the desired frequency of counting in Hz

        @return float: the actual frequency of counting in Hz

        This makes sure, the counter is stopped first and restarted afterwards.
        """

        constraints = self._get_hardware_constraints()

        if self.module_state() == 'locked':
            restart = True
        else:
            restart = False

        if constraints.min_bin_width <= bin_width:
            self.stop_correlation()
            self._bin_width = bin_width
            # if the counter was running, restart it
            if restart:
                self.start_correlation()
        else:
            self.log.warning('bin_width too small! Command ignored!')
        self.sigCountingBinWidthChanged.emit(self._bin_width)

        return self._bin_width

    def set_refresh_time(self, refresh_time = 500):

        if self.module_state() == 'locked':
            restart = True
        else:
            restart = False

        if restart:
            self.start_correlation()
        self._refresh_time = refresh_time
        self.sigCountingRefreshTimeChanged.emit(self._refresh_time)


    def _get_hardware_constraints(self):

        return self._correlation_device.get_constraints()

    def get_count_length(self):
        """ Returns the currently set length of the counting array.

        @return int: count_length
        """
        return self._count_length

    def get_bin_width(self):
        """ Returns the currently set width of the bins in picoseconds.

        @return int: bin_width
        """
        return self._bin_width

    def get_refresh_time(self):


        return self._refresh_time

    def start_correlation(self):
        correlation_status = self._configure_correlation()
        self._correlation_device.start_measure()
        with self.threadlock:
            #Lock module
            self.module_state.lock()
            #configure correlation device

            if correlation_status <0 :
                self.module_state.unlock()
                self.sigCorrelationStatusChanged.emit(False)
                return -1

            self.rawdata = np.zeros((self.get_count_length(),), dtype='int32')
            self.sigCorrelationStatusChanged.emit(True)
            self.sigCorrelationDataNext.emit()
            return


    def stop_correlation(self):
        """ Set a flag to request stopping counting.
        """
        if self.module_state() == 'locked':
            with self.threadlock:
                self.stopRequested = True
        return

    def continue_correlation(self):

        if self.module_state() != 'locked':
            self._correlation_device.continue_measure()
            with self.threadlock:
                self.module_state.lock()
                self.sigCorrelationDataNext.emit()
        return


    def correlation_loop_body(self):

        if self.module_state() == 'locked':
            with self.threadlock:
                if self.stopRequested:
                    self._correlation_device.stop_measure()
                    self.stopRequested = False
                    self.module_state.unlock()
                    self.sigCorrelationUpdated.emit()
                    return
                time.sleep(self._refresh_time/1000) #sleep in seconds
                self.rawdata = self._correlation_device.get_data_trace()
                self.sigCorrelationUpdated.emit()
                self.sigCorrelationDataNext.emit()
        return

    def _configure_correlation(self):
        self._correlation_device.configure(self._bin_width, self._count_length)

        return 0

    def get_saving_state(self):
        """ Returns if the data is saved in the moment.

        @return bool: saving state
        """
        return self._saving

    def save_data(self, tag = None):
        """ Save the Autocorrelation trace data and writes it to a file (without figure).

            Figure still needs to be implemented!
        """
        # stop saving thus saving state has to be set to False
        self._saving = False
        #self._saving_stop_time = time.time()

        filepath = self._save_logic.get_path_for_module(module_name='Autocorrelation')

        if tag is None:
            tag = ''

        timestamp = datetime.datetime.now()
        if len(tag) > 0:
            filelabel = tag + '_Correlation_data'
        else:
            filelabel = 'Correlation_data'
        # write the parameters:
        parameters = OrderedDict()
        parameters['Count length'] = self._count_length
        parameters['Bin width'] = self._bin_width

        data = OrderedDict()
        data['delay (ps)'] = np.arange(-1 * ((self.get_count_length() / 2) * self.get_bin_width() / (1e12)),
                         (self.get_count_length()/2)*self.get_bin_width()/(1e12),
                          self.get_bin_width()/(1e12))
        data['counts'] = self.rawdata
        fig = self.draw_figure(data)
        self._save_logic.save_data(data,
                                   filepath=filepath,
                                   parameters=parameters,
                                   filelabel=filelabel,
                                   fmt='%.6e',
                                   delimiter='\t',
                                   timestamp=timestamp,
                                   plotfig=fig)
        return

    def draw_figure(self, data):
        """ Draw figure to save with data file.

        @param: nparray data: a numpy array containing counts vs delaytime between two detectors

        @return: fig fig: a matplotlib figure object to be saved to file.
        """

        count_data = data['counts']
        time_data = data['delay (ps)']
        time_data = time_data*1e9

        # Use qudi style
        plt.style.use(self._save_logic.mpl_qd_style)

        fig, ax = plt.subplots()
        ax.plot(time_data, count_data, linestyle=':',linewidth=0.5)
        ax.set_xlabel('Delay $\\tau$ (ns)')
        ax.set_ylabel('Counts')

        return fig