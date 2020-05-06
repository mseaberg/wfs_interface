#!/bin/bash
source /reg/g/psdm/etc/psconda.sh
echo $(hostname)
#ssh psana 'cd wfs_v4; echo $(hostname); mpirun -n 8 python mpi_socket.py -r $1 -s $2' &
#command="source /reg/neh/home/seaberg/psana_setup.sh;"
#command+="cd /reg/neh/home/seaberg/Python/WFS_interface;"
#command+="bsub -q psfehq -n 16 -o log/%J.log mpirun python mpi_reply.py -b $1 -e $2 -r $3 -s $4 -c $5"
#ssh psana command &
ssh psana "source /reg/g/psdm/etc/psconda.sh; cd Python/wfs_interface; bsub -q psfehq -n 16 -o log/%J.log mpirun python mpi_reply.py -b $1 -e $2 -r $3 -s $4 -c $5" &
