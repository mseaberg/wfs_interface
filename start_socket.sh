#!/bin/bash
source /reg/g/psdm/etc/psconda.sh
echo $(hostname)
#ssh psana 'cd wfs_v4; echo $(hostname); mpirun -n 8 python mpi_socket.py -r $1 -s $2' &
ssh psana "source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; bsub -q psfehq -n 16 -o log/%J.log mpirun python mpi_socket.py -r $1 -s $2 -c $3" &
