#!/bin/bash
source /reg/g/psdm/etc/psconda.sh
echo $(hostname)
#ssh psana 'cd wfs_v4; echo $(hostname); mpirun -n 8 python mpi_socket.py -r $1 -s $2' &
#ssh psana "source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; hostname
#ssh psana "source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; hostname; mpirun -n 8 python mpi_reply.py -r $1 -s $2 -c $3 &" &
command="ssh $1 'source /reg/g/psdm/etc/psconda.sh;"
command+="export /reg/neh/home/seaberg/Python/lcls_beamline_toolbox;"
command+="cd /reg/neh/home/seaberg/Python/WFS_interface;"
command+="hostname;"
command+="mpirun -n 8 python mpi_reply.py -b $2 -e $3 -r $4 -s $5 -c $6'"
xterm -e command
# xterm -e "ssh $1 'source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; hostname; mpirun -n 8 python mpi_reply.py -b $2 -e $3 -r $4 -s $5 -c $6'"
#xterm -e "ssh psana 'source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; hostname; top'"
