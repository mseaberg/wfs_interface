import sys
#from Talbot_functions_crop import *
from lcls_beamline_toolbox.xraybeamline2d import pitch
from lcls_beamline_toolbox.xraybeamline2d.util import Util
from beam import *
from psana import *
from skimage.transform import downscale_local_mean
import numpy as np
from mpidata import mpidata 
import h5py
import scipy.ndimage.interpolation as interpolate
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas
from pitch2 import *
import h5py
import psana_utility
import zmq
#from numpyClientServer import *
import cPickle as pickle

#from mpi4py import MPI
#comm = MPI.COMM_WORLD
#rank = comm.Get_rank()
#size = comm.Get_size()

    


def runclient(args,pars,comm,rank,size):

    sh_mem = args.live
    expName = args.experiment
    hutchName = args.hutch
    runNum = args.run
    pars['run'] = runNum
    detName = pars['detName']
    lineout_width = pars['lineout_width']
    fraction = pars['fraction']
    epics_keys = pars['epics_keys']

    # number of scan plots
    numPlots = len(pars['plot_list'])

    expName = expName
    update = pars['update_events']
    runString = 'exp=%s:run=%s:smd' % (expName, runNum)
    #runString = runNum
    #runString += ':dir=/reg/d/ffb/%s/%s/xtc:live' % (hutchName,expName)
    #print(runString)

    roi = pars['roi']
    padSize = pars['pad']-1
    xmin = roi[0]
    xmax = roi[1]
    ymin = roi[2]
    ymax = roi[3]

    # miscellaneous parameters
    dx = pars['pixel']
    dg = pars['pitch']
    lambda0 = 1239.8/pars['energy']/1000.*1.e-9

    N = ymax-ymin
    M = xmax-xmin

    f_x = np.linspace(-M/2.,M/2.-1.,M)/M/dx
    f_y = np.linspace(-N/2.,N/2.-1.,N)/N/dx

    f_x,f_y = np.meshgrid(f_x,f_y)



    calibDir = '/reg/d/psdm/%s/%s/calib' % (hutchName, expName)
    
    ds = []
    if sh_mem:
        
        setOption('psana.calib-dir', calibDir)
        ds = DataSource('shmem=psana.0:stop=no')
        
    else:
        ds = DataSource(runString)

    det0 = Detector(detName)
    epics = ds.env().epicsStore()
    eBeam = Detector('EBeam')

    nevents = np.empty(0)

    # initialize instance of the mpidata class for communication with the master process
#    md = mpidata()

    # initialize i1 (which resets after each update) depending on the rank of the process
    i1 = int((rank-1)*update/(size-1))


    md = mpidata()

    # initialize scan data (ordered as in plots.cfg file)
    scan = np.zeros((1,numPlots))
    epics_values = np.zeros(len(epics_keys))
    
    i0 = -1

    nevents = np.empty(0)


    # event loop
    for nevent,evt in enumerate(ds.events()):


        # check if we've reached the event limit        
        if nevent == args.noe : break
        if nevent%(size-1)!=rank-1: continue # different ranks look at different events

        #if det0.image(evt) is None: continue
        # increment counter
        i1 += 1

        i0 += 1

        nevents = np.append(nevents,nevent) 
       

        # send mpi data object to master when desired
        if i1 == update:

            md=mpidata()

            i1 = 0
            #print(i1)
            if det0.image(evt) is None: continue


            print(nevent)

            # select image ROI
            #img0 = np.copy(det0.image(evt)[ymin:ymax,xmin:xmax])
            img0 = det0.image(evt)
            #img0[img0<20] = 0
            #img0 -= 20
            #img0[img0<20] = 0
            # check if the image needs to be rotated
            img0 = interpolate.rotate(img0,pars['angle'],reshape=False)

            img0 = img0[ymin:ymax,xmin:xmax]

            if np.sum(img0)<0.5e7:continue

            N,M = np.shape(img0)
            #print(N)
            #print(M)
            img0 = np.pad(img0,((int(N/2*padSize),int(N/2*padSize)),
                                (int(M/2*padSize),int(M/2*padSize))),'constant')
            # get scan pv
            j1 = 0
            for plot1 in pars['plot_list']:
                scan[:,j1] = np.array(epics.value(pars[plot1]['scanpv']))
                j1 += 1

            j1 = 0
            for key in epics_keys:
                epics_values[j1] = np.array(epics.value(key))
                j1 += 1


            # get ebeam info
            L3E = 0.0
            BC2 = 0.0
            if eBeam.get(evt) is not None:
                L3E = eBeam.get(evt).ebeamL3Energy()
                BC2 = eBeam.get(evt).ebeamPkCurrBC2()


            #### find peaks ####
            #print(np.shape(scan))
            # calculate Talbot magnification
            if epics.value(pars['det_z']) is None:
                zD = 0.0
            else:
                zD = epics.value(pars['det_z'])*1e-3
            #zD = 0.0
            zG = epics.value(pars['grating_z'])*1.e-3
            # distance from grating to focus
            zf = pars['zf'] + zG
            # distance from grating to detector
            zT = pars['z0'] + zD - zG
            # magnification
            mag = (zT + zf) / zf
            #mag = 1.
            peak = 1./mag/dg

            fc = peak*dx
           
            #print(fc)

            x_mask = ((f_x-fc/dx)**2+f_y**2)<(fc/4/dx)**2
            x_mask = x_mask*(((f_x-fc/dx)**2+f_y**2)>(fc/4./dx-2./M/dx)**2)
            y_mask = ((f_x)**2+(f_y-fc/dx)**2)<(fc/4/dx)**2
            y_mask = y_mask*(((f_x)**2+(f_y-fc/dx)**2)>(fc/4./dx-2./N/dx)**2)

            lineout_x = Util.get_horizontal_lineout(img0, half_width=lineout_width/2)
            lineout_y = Util.get_vertical_lineout(img0, half_width=lineout_width/2)

            # lineout_x = np.sum(img0[int(N/2-lineout_width/2):int(N/2+lineout_width/2),:],axis=0)
            # lineout_y = np.sum(img0[:,int(M/2-lineout_width/2):int(M/2+lineout_width/2)],axis=1)

            x_Talbot_lineout = pitch.TalbotLineout(lineout_x, fc, fraction)
            y_Talbot_lineout = pitch.TalbotLineout(lineout_y, fc, fraction)

            x_pitch = x_Talbot_lineout.x_pitch
            x_grad = x_Talbot_lineout.residual
            # x_prime = x_Talbot_lineout.x_prime
            x_vis = x_Talbot_lineout.x_vis
            x_vis2 = x_Talbot_lineout.vis2

            y_pitch = y_Talbot_lineout.x_pitch
            y_grad = y_Talbot_lineout.residual
            # y_prime = y_Talbot_lineout.x_prime
            y_vis = y_Talbot_lineout.x_vis
            y_vis2 = y_Talbot_lineout.vis2



            # MH = np.size(lineout_x)
            # NH = np.size(lineout_y)
            #
            # xH = np.linspace(0,MH-1,MH)
            # yH = np.linspace(0,NH-1,NH)

            #lineout_x = lineout_x * (.52 - .46 * np.cos(2*np.pi*xH/MH))
            #lineout_y = lineout_y * (.52-.46*np.cos(2*np.pi*yH/NH))

            # x_pitch,x_res,x_prime,x_vis,x_vis2 = calc_pitch_vis(lineout_x,fc,fraction)
            # y_pitch,y_res,y_prime,y_vis,y_vis2 = calc_pitch_vis(lineout_y,fc,fraction)

            # lineout_x = np.sum(img0,axis=0)
            # lineout_y = np.sum(img0,axis=1)
            lineout_x = Util.get_horizontal_lineout(img0)
            lineout_y = Util.get_vertical_lineout(img0)

            x_Talbot_full_lineout = pitch.TalbotLineout(lineout_x, fc, fraction)
            y_Talbot_full_lineout = pitch.TalbotLineout(lineout_y, fc, fraction)

            x_pitch_full = x_Talbot_full_lineout.x_pitch
            y_pitch_full = y_Talbot_full_lineout.x_pitch

            # x_pitch_full,x_res_full,x_prime_full = calc_pitch(lineout_x,fc,fraction)
            # y_pitch_full,y_res_rull,y_prime_full = calc_pitch(lineout_y,fc,fraction)

            mag_x = x_pitch*dx/dg
            mag_y = y_pitch*dx/dg

            zf_x = -(zT*mag_x/(mag_x-1.) - zT - zf)*1e3
            zf_y = -(zT*mag_y/(mag_y-1.) - zT - zf)*1e3

            F0 = np.abs(Beam.NFFT(img0))

            dx_prime = x_Talbot_lineout.dx_prime
            dy_prime = y_Talbot_lineout.dx_prime
            # dx_prime = x_prime[1]-x_prime[0]
            # dy_prime = y_prime[1]-y_prime[0]

            param = {
                'dg': dg,
                'fraction': fraction,
                'dx': dx,
                'zT': zT,
                'lambda0': lambda0
            }

            zf_x, W, x_prime, x_res = x_Talbot_lineout.get_legendre(param)
            zf_y, W, y_prime, y_res = y_Talbot_lineout.get_legendre(param)

            x_prime *= 1e6
            y_prime *= 1e6

            # x_grad = np.copy(x_res)
            # y_grad = np.copy(y_res)

            # x_res = np.cumsum(x_res)*dg/lambda0/zT*dx_prime*dx
            # y_res = np.cumsum(y_res)*dg/lambda0/zT*dy_prime*dx
            # x_prime = x_prime*dx*1e6
            # y_prime = y_prime*dx*1e6
            #
            # px = np.polyfit(x_prime,x_res,2)
            # py = np.polyfit(y_prime,y_res,2)
            # x_res = x_res - px[0]*x_prime**2 - px[1]*x_prime - px[2]
            # y_res = y_res - py[0]*y_prime**2 - py[1]*y_prime - py[2]

            x_width = np.std(x_res)
            y_width = np.std(y_res)

            img0 = img0/np.max(img0)

            #F0 = np.abs(Beam.NFFT(img0))
            # normalize to maximum
            F0 = F0/np.max(F0)
            F0 += x_mask + y_mask
            # normalize to maximum
            #img0 = img0/np.max(img0)
            md.addarray('F0',F0)
            md.addarray('img0',img0)
            md.addarray('x_res',x_res)
            md.addarray('y_res',y_res)
            md.addarray('x_vis',x_vis)
            md.addarray('y_vis',y_vis)
            md.addarray('x_vis2',x_vis2)
            md.addarray('y_vis2',y_vis2)
            md.addarray('x_prime',x_prime)
            md.addarray('y_prime',y_prime)
            md.addarray('x_grad',x_grad)
            md.addarray('y_grad',y_grad)
            md.addarray('intensity',np.sum(img0))
            md.addarray('nevents',nevents[-1])
            md.addarray('zf_x',zf_x)
            md.addarray('zf_y',zf_y)
            md.addarray('x_width',x_width)
            md.addarray('y_width',y_width)
            md.addarray('scan',scan)
            md.addarray('x_pitch',x_pitch)
            md.addarray('y_pitch',y_pitch)
            md.addarray('x_pitch_full',x_pitch_full)
            md.addarray('y_pitch_full',y_pitch_full)
            md.addarray('L3E',np.array(L3E))
            md.addarray('BC2',np.array(BC2))
            md.addarray('epics_values',epics_values)
            md.small.event = nevent
           
            md.send()

            nevents = np.empty(0)
           # 
    md.endrun()


def runmaster(nClients,args,pars,comm,rank,size):

    print('running')

    servername = args.server

    context = zmq.Context()
    socket1 = context.socket(zmq.PUB)
    socket1.connect("tcp://"+servername+":12301")

    # get ROI info
    roi = pars['roi']
    xmin = roi[0]
    xmax = roi[1]
    ymin = roi[2]
    ymax = roi[3]

    epics_keys = pars['epics_keys']
    dx = pars['pixel']
    dg = pars['pitch']

    z0 = pars['z0']
    zf = pars['zf']

    mag1 = (z0+zf)/zf

    pixelPeriod = mag1*dg/dx

    # xlength = int((xmax-xmin)/pixelPeriod*2)
    # ylength = int((ymax-ymin)/pixelPeriod*2)
    xlength = xmax - xmin
    ylength = ymax - ymin


    # initialize arrays

    dataDict = {}
    dataDict['nevents'] = np.ones(30000)*-1
    dataDict['zf_x'] = np.zeros(30000)
    dataDict['zf_y'] = np.zeros(30000)
    dataDict['x_width'] = np.zeros(30000)
    dataDict['y_width'] = np.zeros(30000)
    dataDict['x_prime'] = np.zeros((30000,xlength))
    dataDict['x_res'] = np.zeros((30000,xlength))
    dataDict['y_prime'] = np.zeros((30000,ylength))
    dataDict['y_res'] = np.zeros((30000,ylength))
    dataDict['x_pitch'] = np.zeros(30000)
    dataDict['y_pitch'] = np.zeros(30000)
    dataDict['x_pitch_full'] = np.zeros(30000)
    dataDict['y_pitch_full'] = np.zeros(30000)
    dataDict['x_grad'] = np.zeros(30000)
    dataDict['y_grad'] = np.zeros(30000)
    dataDict['scanPos'] = np.zeros(30000)
    dataDict['intensity'] = np.zeros(30000)
    dataDict['L3E'] = np.zeros(30000)
    dataDict['BC2'] = np.zeros(30000)
    dataDict['x_vis'] = np.zeros(30000)
    dataDict['y_vis'] = np.zeros(30000)
    dataDict['x_vis2'] = np.zeros(30000)
    dataDict['y_vis2'] = np.zeros(30000)
    for key in epics_keys:
        dataDict[key] = np.zeros(30000)

    roi = pars['roi']
    xmin = roi[0]
    xmax = roi[1]
    ymin = roi[2]
    ymax = roi[3]

    # initialize list of scan plots



    padSize = pars['pad']
    xSize = (xmax-xmin)*padSize
    ySize = (ymax-ymin)*padSize


    #data_string = pickle.dumps(dataDict)
    #numpysocket.startClient(servername,12301,data_string) 
    #socket1.send_pyobj(dataDict)
    #print("sent data")

    nevent = -1

    while nClients > 0:
        # Remove client if the run ended
        md = mpidata()
        rank1 = md.recv()
        #print(rank1)
        if md.small.endrun:
            nClients -= 1
        else:

            #nevents = np.append(nevents,md.nevents)
            dataDict['nevents'] = update(md.nevents,dataDict['nevents']) 
            dataDict['x_vis'] = update(md.x_vis,dataDict['x_vis'])
            dataDict['y_vis'] = update(md.y_vis,dataDict['y_vis'])
            dataDict['x_vis2'] = update(md.x_vis2,dataDict['x_vis2'])
            dataDict['y_vis2'] = update(md.y_vis2,dataDict['y_vis2'])
            dataDict['zf_x'] = update(md.zf_x,dataDict['zf_x'])
            dataDict['zf_y'] = update(md.zf_y,dataDict['zf_y'])
            dataDict['x_width'] = update(md.x_width,dataDict['x_width'])
            dataDict['y_width'] = update(md.y_width,dataDict['y_width'])
            dataDict['intensity'] = update(md.intensity,dataDict['intensity'])
            dataDict['L3E'] = update(md.L3E,dataDict['L3E'])
            dataDict['BC2'] = update(md.BC2,dataDict['BC2'])
            dataDict['x_pitch'] = update(md.x_pitch,dataDict['x_pitch'])
            dataDict['y_pitch'] = update(md.y_pitch,dataDict['y_pitch'])
            dataDict['x_pitch_full'] = update(md.x_pitch_full,dataDict['x_pitch_full'])
            dataDict['y_pitch_full'] = update(md.y_pitch_full,dataDict['y_pitch_full'])
            dataDict['x_res'] = update(np.pad(md.x_res,(0,xlength-np.size(md.x_res)),'constant'),
                    dataDict['x_res'])
            # dataDict['x_res'] = update(md.x_res, dataDict['x_res'])
            dataDict['x_prime'] = update(np.pad(md.x_prime,(0,xlength-np.size(md.x_prime)),'constant'),
                    dataDict['x_prime'])
            dataDict['y_res'] = update(np.pad(md.y_res,(0,ylength-np.size(md.y_res)),'constant'),
                    dataDict['y_res'])
            dataDict['y_prime'] = update(np.pad(md.y_prime,(0,ylength-np.size(md.y_prime)),'constant'),
                    dataDict['y_prime'])
            j1 = 0
            for key in epics_keys:
                dataDict[key] = update(md.epics_values[j1],dataDict[key])
                j1 += 1

            if md.nevents>nevent:
                x_res = md.x_res
                y_res = md.y_res
                x_prime = md.x_prime
                y_prime = md.y_prime
                nevent = md.nevents
                img0 = md.img0
                F0 = md.F0


            #counterSum += md.counter
            if rank1 == size-1:
                
                mask = dataDict['nevents']>0
                #mask = np.logical_and(mask,dataDict['intensity']>1e6)

                eventMask = dataDict['nevents'][mask]

                order = np.argsort(eventMask)
                eventMask = eventMask[order]

                zf_x = dataDict['zf_x'][mask][order]
                zf_y = dataDict['zf_y'][mask][order]
                x_width = dataDict['x_width'][mask][order]
                y_width = dataDict['y_width'][mask][order]
                


                x_smooth = pandas.rolling_mean(zf_x,10,center=True)
                y_smooth = pandas.rolling_mean(zf_y,10,center=True)
                xw_smooth = pandas.rolling_mean(x_width,10,center=True)
                yw_smooth = pandas.rolling_mean(y_width,10,center=True)
                


                send_dict1 = {}
                send_dict = {}
                #send_dict['raw'] = downscale_local_mean(img0,(4,4))
                #send_dict['F0'] = downscale_local_mean(F0,(4,4))
                send_dict['raw_image'] = img0
                send_dict['FFT'] = F0
                send_dict['x_residual_phase'] = x_res
                send_dict['y_residual_phase'] = y_res
                send_dict['x_prime'] = x_prime
                send_dict['y_prime'] = y_prime
                send_dict['event_number'] = eventMask

                for key in epics_keys:
                    send_dict[key] = dataDict[key][mask][order]


                send_dict['x_focus_position'] = zf_x
                send_dict['y_focus_position'] = zf_y
                send_dict['x_phase_rms'] = x_width
                send_dict['y_phase_rms'] = y_width
                send_dict['x_smooth'] = x_smooth
                send_dict['y_smooth'] = y_smooth
                send_dict['xw_smooth'] = xw_smooth
                send_dict['yw_smooth'] = yw_smooth

                send_dict['key_list'] = ['event_number','x_focus_position',
                        'y_focus_position','x_phase_rms','y_phase_rms']

                for key in epics_keys:
                    send_dict['key_list'].append(key)

                
                #message = socket1.recv()
                #socket1.send_pyobj(send_dict)
                #print(message)

                #if message == 'stop':
                #    break
                #else:
                #    socket1.send_pyobj(send_dict)
                socket1.send_string('data', zmq.SNDMORE)
                socket1.send_pyobj(send_dict)
                print("sent data")
                #numpysocket.startClient(servername,12301,send_dict1) 


    send_dict = {}
    send_dict['message'] = 'finished'
    socket1.send_string('data', zmq.SNDMORE)
    socket1.send_pyobj(send_dict)
    socket1.close()

               
    fileName = '/reg/d/psdm/'+pars['hutch']+'/'+pars['hutch']+pars['exp_name']+'/results/wfs/'+args.run+'_data2.h5'

    mask = dataDict['nevents'] >= 0

    for key in dataDict.keys():
        dataDict[key] = dataDict[key][mask]

    i1 = np.argsort(dataDict['nevents'])
    for key in dataDict.keys():
        dataDict[key] = dataDict[key][i1]

    with h5py.File(fileName,'w') as f:
        for key in dataDict.keys():
            f.create_dataset(key, data=dataDict[key])



def update(newValue,currentArray):

    if len(np.shape(currentArray))>1:
        currentArray = np.roll(currentArray,-1,axis=0)
        currentArray[-1,:] = newValue
    else:
        currentArray = np.roll(currentArray,-1)
        currentArray[-1] = newValue
    return currentArray



