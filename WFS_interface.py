import numpy as np
import warnings
from matplotlib import cm
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
from PyQt4.uic import loadUiType
import sys
import os
import time
import wfs_utils
import cPickle as pickle
#from numpyClientServer import *
import socket
import subprocess
import zmq
import ConfigParser

Ui_MainWindow, QMainWindow = loadUiType('WFS_form.ui')
Ui_Plot, QPlot = loadUiType('WFS_plot.ui')
Ui_Config, QConfig = loadUiType('WFS_config.ui')

class App(QMainWindow, Ui_MainWindow):
    """
    The GUI class defining the user interface. This is based on a designer file WFS_form.ui.

    Signals:
    ----------
    triggerStart : pyqtSignal
        a trigger to start data analysis process
    triggerStop : pyqtSignal
        a trigger to stop the data analysis process
    """


    triggerStart = QtCore.pyqtSignal()
    triggerStop = QtCore.pyqtSignal()

    def __init__(self):
        """
        Set up interface
        """

        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        ## button callbacks
        self.runPushButton.clicked.connect(self.change_state)
        self.hutchComboBox.currentIndexChanged.connect(self.set_hutch)
        self.experimentComboBox.currentIndexChanged.connect(self.set_experiment)
        self.runnumberEdit.returnPressed.connect(self.set_run)
        self.plotPushButton.clicked.connect(self.make_plot)

        ## menu callbacks
        self.actionLoad_configuration.triggered.connect(self.load_config)
        self.actionNew_configuration.triggered.connect(self.new_config)
        self.actionModify_configuration.triggered.connect(self.modify_config)

        ## font styles
        self.labelStyle = {'color': '#FFF', 'font-size': '12pt'}
        self.font = QtGui.QFont()
        self.font.setPointSize(10)
        self.font.setFamily('Arial')


        ## raw Image view
        self.topCanvas.addLabel(text='Raw Image',row=0,col=0,color='FFFFFF',bold=True)
        self.rawView = self.topCanvas.addViewBox(row=1,col=0,border='w')
        self.setup_viewbox(self.rawView,2048)
        self.rawImg = pg.ImageItem()
        self.rawView.addItem(self.rawImg)


        ## FFT view
        self.topCanvas.addLabel(text='FFT',row=0,col=1,color='FFFFFF',bold=True)
        self.fftView = self.topCanvas.addViewBox(row=1,col=1,border='w')
        self.setup_viewbox(self.fftView,2048)
        self.fftImg = pg.ImageItem()
        self.fftView.addItem(self.fftImg)

        ## legend settings
        self.legendLabelStyle = {'color': '#FFF', 'size': '10pt'}

        ## focus plot vs event
        self.topCanvas.addLabel(text='Focus position',row=0,col=2,color='FFFFFF',bold=True)
        self.focusPlot = self.topCanvas.addPlot(row=1,col=2)
        legend = self.focusPlot.addLegend()
        self.focus_x = self.initialize_point_plot(self.focusPlot,color='r',
                name='horizontal')
        self.focus_y = self.initialize_point_plot(self.focusPlot,color='c',
                name='vertical')
        self.label_plot(self.focusPlot,'Event number', 'Focus position (mm)')
        self.set_legend(legend)


        ## rms plot vs event
        self.bottomCanvas.addLabel(text='RMS High Order Phase',row=0,col=0,color='FFFFFF',bold=True)
        self.rmsPlot = self.bottomCanvas.addPlot(row=1,col=0)
        legend = self.rmsPlot.addLegend()
        self.rms_x = self.initialize_point_plot(self.rmsPlot,color='r',
                name='horizontal')
        self.rms_y = self.initialize_point_plot(self.rmsPlot,color='c',
                name='vertical')
        self.label_plot(self.rmsPlot,'Event number', 'RMS residual phase (rad)')
        self.set_legend(legend)



        ## 1D x residual
        self.bottomCanvas.addLabel(text='Horizontal High Order Lineout',row=0,col=1,color='FFFFFF',bold=True)
        self.xresPlot = self.bottomCanvas.addPlot(row=1,col=1)
        self.xres_data = self.xresPlot.plot(np.linspace(0,99,100),np.zeros(100),
                pen=pg.mkPen('r',width=5))
        self.label_plot(self.xresPlot,'x (microns)','Residual phase (rad)')

        ## 1D y residual
        self.bottomCanvas.addLabel(text='Vertical High Order Lineout',row=0,col=2,color='FFFFFF',bold=True) 
        self.yresPlot = self.bottomCanvas.addPlot(row=1,col=2)
        self.yres_data = self.yresPlot.plot(np.linspace(0,99,100),np.zeros(100),
                pen=pg.mkPen('r',width=5))
        self.label_plot(self.yresPlot,'y (microns)','Residual phase (rad)')

        ## default parameters
        self.runstring = ''
        self.runnumber = '1'

        ## colormap for images
        colormap = cm.get_cmap("gnuplot")
        colormap._init()
        self.lut = (colormap._lut * 255).view(np.ndarray)

        ## set default experiment
        self.set_hutch()
        self.set_experiment()
        self.set_run()

        ## set default experiment and run
        index = self.experimentComboBox.findText('xppx28816',QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.experimentComboBox.setCurrentIndex(index)
        self.runnumberEdit.setText('58')
        self.set_run()

        ## initialize various attributes
        self.plots = []
        self.pars = {}
        self.data_dict = {}
        self.config = 'config/wfs.cfg'

    def load_config(self):
        """
        Load configuration file for data processing
        """

        # get current directory and add config directory to it.
        homeDir = os.getcwd()
        defaultDir = homeDir+'/config'
        formats = 'Config file (*.cfg)'
        # open a dialog to select a config file
        filename = QtGui.QFileDialog.getOpenFileName(self,
                'Load Configuration File',defaultDir,formats)

        # make sure a file was chosen
        if not filename == '':
            self.config = str(filename)


        try:
            # check if the file can be loaded
            #self.pars = wfs_utils.parse_wfs_config_gui(self.config)
            self.modify_config()
        except:
            # print an error message if it can't be loaded (and don't do anything).
            print('Failed to load config file')

            
    def modify_config(self):
        """
        Method to view config file parameters in a new window
        """
        config_window = Config(self,self.config)
        config_window.show()

    def initialize_point_plot(self,plot,color,name=None):
        """
        Parameters
        ----------
        :param plot: pyqtgraph plot item
        :param color: line color (str)
        :param name: label for legend (str)
        Returns
        ----------
        :return: line plot
        """
        plot_data = plot.plot(np.linspace(0,99,100),np.zeros(100),
                pen=None,symbol='o',symbolBrush=color,name=name,
                pxMode=True,symbolSize=7)

        return plot_data



    def set_legend(self,legend):
        """
        Parameters
        -----------
        :param legend: pyqtgraph legend object
        :return: None
        """
        for item in legend.items:
            for single_item in item:
                if isinstance(single_item, pg.graphicsItems.LabelItem.LabelItem):
                    single_item.setText(single_item.text, **self.legendLabelStyle)


    def make_plot(self):
        """
        Open a new window to make an AMI-style plot, by creating a NewPlot object
        """

        plot_window = NewPlot(self)
        print('opening new window')
        plot_window.show()
        self.plots.append(plot_window)

    def new_config(self):
        """
        Open a new window to create a new config file
        """

        config_window = Config(self)
        config_window.show()


    def update_runstring(self):
        """
        Update run string based on what is set in the GUI.
        """

        self.runstring = ('exp='+self.experiment+':run='+
                self.runnumber+':smd')

        self.messageLabel.setText(self.runstring)

    def set_hutch(self):
        """
        Called when a change is made in the hutch combo box.
        """
        self.hutch = str(self.hutchComboBox.currentText())
        dataDir = '/reg/d/psdm/'+self.hutch
        experiments = wfs_utils.get_immediate_subdirectories(dataDir,self.hutch)
        self.experimentComboBox.clear()
        self.experimentComboBox.addItems(sorted(experiments))

        # update the run string with the new choice
        self.update_runstring()

    def set_experiment(self):
        """
        Called when a new experiment is selected in the experiment combo box.
        """

        self.experiment = str(self.experimentComboBox.currentText())

        # update the run string with the new choice
        self.update_runstring()

    def set_run(self):
        """
        Called when a new run number is entered in the run textbox.
        """
        self.runnumber = str(self.runnumberEdit.text())

        # update the run string with the new choice
        self.update_runstring()

    def thread_finished(self):
        """
        Method to call when the thread is finished
        """
        # quit the thread and wait for it to finish
        self.thread.quit()
        self.thread.wait()
        # reset text to Run and re-enable
        self.runPushButton.setText('Run')
        self.runPushButton.setEnabled(True)

    def enable_button(self):
        """
        Method to re-enable the run button
        """
        self.runPushButton.setEnabled(True)

    def change_state(self):
        """
        Method that is called when the run button is pressed
        """

        # if nothing was running, start processing. Otherwise, user is requesting that processing stops.
        if self.runPushButton.text() == 'Run':

            # disable run button while things are starting up
            self.runPushButton.setEnabled(False)
            # change button text to Stop
            self.runPushButton.setText('Stop')

            # start a new thread for the processing to run on
            self.thread = QtCore.QThread()
            self.thread.start()

            # create a RunWFS object for processing
            self.wfs_calc = RunWFS(self.runnumber, self.config, self.update_plots, self.thread_finished,self.enable_button)
            # move RunWFS to the thread we created, before calling anything
            self.wfs_calc.moveToThread(self.thread)
            # connect triggers
            self.triggerStart.connect(self.wfs_calc.start)
            self.triggerStop.connect(self.wfs_calc.stop)
            # send the signal to start
            self.triggerStart.emit()

        elif self.runPushButton.text() == 'Stop':

            # disable button while things are getting cleaned up
            self.runPushButton.setEnabled(False)
            # send signal to stop
            self.triggerStop.emit()

    def update_plots(self,data_dict):
        """
        Function that gets called whenever a plot signal is sent
        :param data_dict: dictionary containing all data for plotting, from the plot signal
        """

        self.data_dict = data_dict
        # make sure we're actually getting data. Don't change anything if not.
        if 'raw' in data_dict.keys():

            # FFT data
            F0 = data_dict['F0']
            # FFT display threshold
            F0[F0>.1] = 0.1
            # update images
            self.rawImg.setImage(data_dict['raw'],levels=(0,1),lut=self.lut)
            self.fftImg.setImage(F0,levels=(0,.101),lut=self.lut)
            # update plots
            self.focus_x.setData(data_dict['nevent'],data_dict['zf_x'])
            self.focus_y.setData(data_dict['nevent'],data_dict['zf_y'])
            self.rms_x.setData(data_dict['nevent'],data_dict['x_width'])
            self.rms_y.setData(data_dict['nevent'],data_dict['y_width'])
            self.xres_data.setData(data_dict['x_prime'],data_dict['x_res'])
            self.yres_data.setData(data_dict['y_prime'],data_dict['y_res'])
            self.messageLabel.setText('Message received')

            # if this is the first iteration, re-size image boxes to match images
            if data_dict['iteration'] == 0:
                N,M = np.shape(data_dict['raw'])
                self.update_viewbox(self.rawView,M,N)
                self.update_viewbox(self.fftView,M,N)
                for plot in self.plots:
                    plot.populate_combobox(data_dict)
            # update any AMI-style plots
            for plot in self.plots:
                plot.update_plot(data_dict)


    def label_plot(self,plot,xlabel,ylabel):
        """
        Helper function to set plot labels
        :param plot: pyqtgraph plot item
        :param xlabel: x-axis label (str)
        :param ylabel: y-axis label (str)
        """
        xaxis = plot.getAxis('bottom')
        xaxis.setLabel(text=xlabel,**self.labelStyle)
        xaxis.tickFont = self.font
        xaxis.setPen(pg.mkPen('w',width=1))
        yaxis = plot.getAxis('left')
        yaxis.setLabel(text=ylabel,**self.labelStyle)
        yaxis.tickFont = self.font
        yaxis.setPen(pg.mkPen('w',width=1))


    def setup_viewbox(self,viewbox,width):
        """
        Helper function to set up viewbox with title
        :param viewbox: pyqtgraph viewbox
        :param title: image title (str)
        :param width: image width in pixels (int)
        """
        viewbox.setAspectLocked(True)
        viewbox.setRange(QtCore.QRectF(0,0,width,width))

    def update_viewbox(self,viewbox,width,height):
        """
        Helper function to adjust viewbox settings
        :param viewbox: pyqtgraph viewbox
        :param title: image title (pyqtgraph text item)
        :param width: new width in pixels (int)
        :param height: new height in pixels (int)
        :return:
        """
        viewbox.setRange(QtCore.QRectF(0,0,width,height))

    def closeEvent(self, event):
        """
        Method called when the window is closed
        :param event: close event
        """
        # if a process is running, try to stop smoothly, otherwise there is nothing to do.
        if self.runPushButton.text() == 'Stop':
            self.wfs_calc.stop()
            self.thread.quit()
            self.thread.wait()


class Config(QConfig, Ui_Config):
    """
    Class for creating config files
    """

    def __init__(self,parent,filename=None):
        """
        Create Config object
        :param parent: parent is the App object
        """
        super(Config, self).__init__(parent)
        self.setupUi(self)

        self.parent = parent

        self.buttonBox.accepted.connect(self.save_config)
        
        self.filename = filename
        if filename is not None:
            self.load_config()
            

    def load_config(self):
        """
        Method that populates dialog with entries from a previously
        created config file.
        """
        # get information from file
        pars = wfs_utils.parse_wfs_config_gui(self.filename)

        # get only the name of the file
        name = self.filename.split('/')[-1][:-4]
        self.lineEdit_filename.setText(name) 
        
        # set lineEdits based on what's in file
        self.lineEdit_energy.setText(str(pars['energy']))
        self.lineEdit_ROI.setText(', '.join(map(str, pars['roi'])))
        self.lineEdit_lineout.setText(str(pars['lineout_width']))
        self.lineEdit_fraction.setText(str(pars['fraction']))
        self.lineEdit_threshold.setText(str(pars['thresh']))
        self.lineEdit_downsampling.setText(str(pars['downsample']))
        self.lineEdit_order.setText(str(pars['order']))
        self.lineEdit_z0.setText(str(pars['z0']))
        self.lineEdit_zf.setText(str(pars['zf']))
        pix = str(pars['pixel']*1e6)
        self.lineEdit_pix.setText(pix)
        self.lineEdit_grating_motor.setText(pars['grating_z'])
        self.lineEdit_det_motor.setText(pars['det_z'])
        pitch = str(pars['pitch']*1e6)
        self.lineEdit_pitch.setText(pitch)
        self.lineEdit_detName.setText(pars['detName'])
        self.lineEdit_rotation.setText(str(pars['angle']))

        epics_list = pars['epics_keys']
        epics_text = '\n'.join(epics_list)
        self.epics_TextEdit.setPlainText(epics_text)

    def save_config(self):
        """
        Method that runs when the "Ok" button is clicked. Saves config file
        """
        # make a config parser
        config_parser = ConfigParser.ConfigParser()

        # set all the parameters based on what has been entered
        config_parser.add_section('Main')
        config_parser.set('Main','hutch',self.parent.hutch)
        config_parser.set('Main','exp_name',self.parent.experiment)
        config_parser.set('Main','energy',str(self.lineEdit_energy.text()))
        config_parser.set('Main','live',str(self.parent.liveCheckBox.isChecked()))
        config_parser.add_section('Processing')
        roi = [x.strip() for x in str(self.lineEdit_ROI.text()).split(',')]
        config_parser.set('Processing','xmin',roi[0])
        config_parser.set('Processing','xmax',roi[1])
        config_parser.set('Processing','ymin',roi[2])
        config_parser.set('Processing','ymax',roi[3])
        config_parser.set('Processing','pad','1')
        config_parser.set('Processing','lineout_width',
                str(self.lineEdit_lineout.text()))
        config_parser.set('Processing','fraction',
                str(self.lineEdit_fraction.text()))
        config_parser.set('Processing','padding','0')
        config_parser.set('Processing','thresh',
                str(self.lineEdit_threshold.text()))
        config_parser.set('Processing','downsample',
                str(self.lineEdit_downsampling.text()))
        config_parser.set('Processing','order',
                str(self.lineEdit_order.text()))
        config_parser.add_section('Setup')
        config_parser.set('Setup','z0',str(self.lineEdit_z0.text()))
        config_parser.set('Setup','zf',str(self.lineEdit_zf.text()))
        config_parser.set('Setup','pixel',
                str(self.lineEdit_pix.text())+'e-6')
        config_parser.set('Setup','grating_z',
                str(self.lineEdit_grating_motor.text()))
        config_parser.set('Setup','det_z',
                str(self.lineEdit_det_motor.text()))
        config_parser.set('Setup','pitch',
                str(self.lineEdit_pitch.text())+'e-6')
        config_parser.set('Setup','detName',
                str(self.lineEdit_detName.text()))
        config_parser.set('Setup','angle',
                str(self.lineEdit_rotation.text()))
        config_parser.add_section('Update')
        config_parser.set('Update','updateEvents','1')

        # epics keys need to be parsed from textbox, and put into a
        # comma separated string
        epics_text = str(self.epics_TextEdit.toPlainText())
        # convert text to list
        epics_list = [x.strip() for x in epics_text.split('\n')]
        # remove any empty strings
        epics_list = list(filter(None, epics_list))
        # convert to single string with comma separation
        epics_string = ','.join(epics_list)
        config_parser.set('Processing','epics_keys',epics_string)


        # get the filename that was entered
        filename = 'config/'+str(self.lineEdit_filename.text())+'.cfg'

        # write the new config file
        with open(filename,'wb') as configfile:
            config_parser.write(configfile)

        # make sure this is the config file that is being used now
        self.parent.config = filename


class NewPlot(QPlot, Ui_Plot):
    """
    Class for making AMI-style plots in a separate window
    """
    
    def __init__(self,parent):
        """
        Create NewPlot object
        :param parent: parent is the App object
        """
        super(NewPlot, self).__init__(parent)
        self.setupUi(self)

        # add parent attribute
        self.parent = parent

        # make a new pyqtgraph plot
        self.plot_item = self.canvas.addPlot(row=0,col=0)
        self.plot_item.showGrid(x=True,y=True,alpha=.7)
        self.plot_data = self.plot_item.plot(np.linspace(0,99,100),np.zeros(100),
                pen=pg.mkPen('r',width=5),symbol='o',symbolBrush='r')
        parent.label_plot(self.plot_item,'', '')
        # get information from the plot window
        self.minimum = float(self.min_lineEdit.text())
        self.maximum = float(self.max_lineEdit.text())
        self.points = float(self.points_lineEdit.text())
        self.update_bins()

        # connect plot window buttons
        self.min_lineEdit.returnPressed.connect(self.update_min)
        self.max_lineEdit.returnPressed.connect(self.update_max)
        self.points_lineEdit.returnPressed.connect(self.update_points)
        self.xaxis_comboBox.activated.connect(self.update_axes)
        self.yaxis_comboBox.activated.connect(self.update_axes)
        self.actionChange_title.triggered.connect(self.change_title)

        # flag to keep track of if a selection has been made yet in a combo box
        self.flag = 1

        # populate combo boxes
        self.populate_combobox(parent.data_dict)

    def populate_combobox(self, axis_dict):
        """
        Method to populate x and y data combo boxes
        :param axis_dict: dictionary of data
        """

        # check if a selection has been made yet. If not, do nothing
        if self.flag:
            # get all the keys from the dictionary and populate the combo boxes
            axis_list = []
            for key in axis_dict.keys():
                axis_list.append(key)
            self.xaxis_comboBox.clear()
            self.xaxis_comboBox.addItems(sorted(axis_list))
            self.yaxis_comboBox.clear()
            self.yaxis_comboBox.addItems(sorted(axis_list))

    def change_title(self):
        """
        Method to change the plot title. Called from the file menu.
        :return:
        """

        # get input from a dialog
        text, ok = QtGui.QInputDialog.getText(self, 'Change Title', 'Enter title:')

        # set the title if something was entered
        if ok:
            self.setWindowTitle(text)

    def update_min(self):
        """
        Update the x-axis minimum. Called when enter is pressed.
        """
        self.minimum = float(self.min_lineEdit.text())
        self.update_bins()

    def update_max(self):
        """
        Update the x-axis maximum. Called when enter is pressed.
        """
        self.maximum = float(self.max_lineEdit.text())
        self.update_bins()

    def update_points(self):
        """
        Update the number of bins. Called when enter is pressed.
        """
        self.points = float(self.points_lineEdit.text())
        self.update_bins()

    def update_bins(self):
        # calculate bin parameters
        bin_width = (self.maximum - self.minimum) / (self.points - 1)
        dx = bin_width / 2.
        self.bins = np.linspace(self.minimum - dx, self.maximum + dx, self.points + 1)
        self.binPlot = (self.bins[:-1] + self.bins[1:]) / 2.

    def update_axes(self):
        """
        Called when a selection is made in the combo boxes. Updates plot labels and sets keys for data access.
        """
        self.xaxis = str(self.xaxis_comboBox.currentText())
        self.yaxis = str(self.yaxis_comboBox.currentText())
        self.parent.label_plot(self.plot_item,self.xaxis,self.yaxis)
        # disable re-population of combo boxes by setting the flag to 0.
        self.flag = 0

    def update_plot(self,data_dict):
        """
        Called from the main GUI when new data comes in.
        :param data_dict: dictionary containing the data to plot
        """

        try:
            # if we're starting a new data analysis process, see if we should update combo box
            if data_dict['iteration'] == 0:
                self.populate_combobox(data_dict)
            # get data based on x and y-axis keys
            xdata = data_dict[self.xaxis]
            ydata = data_dict[self.yaxis]

            #bin_width = (self.maximum - self.minimum)/(self.points-1)
            #dx = bin_width/2.
            #bins = np.linspace(self.minimum-dx,self.maximum+dx,self.points+1)
            #binPlot = (bins[:-1]+bins[1:])/2.
            
            # figure out which bin each xdata belongs to
            digitized = np.digitize(xdata,self.bins)

            # ignore any warnings about nan's
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)

                # calculate y-values for each bin
                bin_means = [ydata[digitized==i].mean() for i in range(1, len(self.bins))]

            # create a mask to avoid nan's
            mask = np.logical_not(np.isnan(bin_means))
            # update the plot
            self.plot_data.setData(np.array(self.binPlot)[mask],np.array(bin_means)[mask])

        except:
            # print that there was an error if something didn't work.
            print('error')

    def closeEvent(self,event):
        """
        Called when the window is closed
        :param event: close event
        """

        # remove plot from App's plot list
        self.parent.plots.remove(self)


class RunWFS(QtCore.QObject):
    """
    Class for running the wavefront sensor data processing

    Signals
    --------
    triggerPlot: connected to App's update_plots method. Sends a dictionary with data to plot
    triggerStop: tells App that the thread is finished.
    triggerEnable: tells App to re-enable the Run button.
    """
    triggerPlot = QtCore.pyqtSignal(dict)
    triggerStop = QtCore.pyqtSignal()
    triggerEnable = QtCore.pyqtSignal()

    def __init__(self,runstring,config,update_function,finished_function,enable_function):
        """
        Initialize a RunWFS object
        :param runstring: data access string (str)
        :param config: configuration file path (str)
        :param update_function: update_plots function
        :param finished_function: thread_finished function
        :param enable_function: enable_button function
        """
        QtCore.QObject.__init__(self)

        # set attributes
        self.runstring = runstring
        self.config = config
        self.update_function = update_function
        self.finished_function = finished_function
        self.enable_function = enable_function

        # set iteration number to zero
        self.iteration = 0
         
    
    def start(self):
        """
        Method to start data processing using MPI.
        """

        # connect signals
        self.triggerPlot.connect(self.update_function)
        self.triggerStop.connect(self.finished_function)
        self.triggerEnable.connect(self.enable_function)

        # flag set to true when running, False when the processing should/does stop
        self.running = True
        # get the hostname to set up ZMQ server
        self.hostname = socket.gethostname()
        # get the IP address of the host
        self.ipaddr = socket.gethostbyname(self.hostname)

        # start data processing on another server using batch processing
        # string to run a bash command
        command_string = './start_socket.sh '+self.runstring+' ' +self.ipaddr + ' '+self.config
        # run the command
        proc = subprocess.Popen(['/bin/bash','-c',command_string],stdout=subprocess.PIPE)
        # capture any output. This includes the job ID.
        out = proc.communicate()
        print(out) 

        # find the job ID number
        i1 = out[0].find('<')
        i2 = out[0].find('>')
        self.jobID = out[0][i1+1:i2]
        # print the job ID number
        print('Starting job ID '+self.jobID)
        #### Start

        # start the zmq server
        context = zmq.Context()
        self.socket1 = context.socket(zmq.REP)
        # bind the port. Change this in the future to be more flexible
        self.socket1.bind("tcp://*:12301")

        print('starting loop')
        # send the signal to re-enable the Run button
        self.triggerEnable.emit()
        # call the update function and start the loop
        self._update()

    def _update(self):
        """
        Method to listen for data from the batch job. This runs in a loop until the Stop button is pressed
        or the job is finished.
        """
        # if it doesn't work just send an empty dictionary.
        try:
            # listen for a python object (dictionary)
            dataDict = self.socket1.recv_pyobj()
            # add the iteration number to the dictionary
            dataDict['iteration'] = self.iteration
            # check if the job told us it's finished and set running flag to False if so.
            if 'message' in dataDict.keys():
                if dataDict['message'] == 'finished':
                    self.running = False

            if self.running == False:
                # if the stop button was pressed, send a stop message to the job.
                self.socket1.send("stop")
            else:
                # otherwise, just send a message to the job that the data was received.
                self.socket1.send("received")

            # send the data to the GUI
            self.triggerPlot.emit(dataDict)
            # increment the iteration number
            self.iteration += 1

        except:
            # just send an empty dictionary if something didn't work.
            self.triggerPlot.emit({})

        # if we want to keep running, call the function again to keep the loop running.
        # Cap updates at 20 Hz.
        if self.running:
            QtCore.QTimer.singleShot(50, self._update)
        else:
            # if we want to stop, tell the GUI we're stopping and close the socket.
            self.triggerStop.emit()
            self.socket1.close()

            # try to kill the batch process if it isn't already finished.
            command_string = 'bkill '+self.jobID
            subprocess.Popen(['/bin/bash','-c',command_string])
            # send the command a second time after half a second.
            time.sleep(.5)
            subprocess.Popen(['/bin/bash','-c',command_string])

    def stop(self):
        """
        Method that is called when the signal that the stop button has been pressed is sent.
        """
        # set the running flag to False
        self.running = False


# run the program
if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    myapp = App()
    myapp.show()
    sys.exit(app.exec_())
