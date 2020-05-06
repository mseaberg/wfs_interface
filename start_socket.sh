#!/bin/bash
source /reg/g/psdm/etc/psconda.sh
echo $(hostname)

command="source /reg/neh/home/seaberg/psana_setup.sh;"
command+="cd /reg/neh/home/seaberg/Python/wfs_interface;"
command+="bsub -q psfehq -n 16 -o log/%J.log mpirun python mpi_socket.py -r $1 -s $2 -c $3"
ssh psana command
#ssh psana 'cd wfs_v4; echo $(hostname); mpirun -n 8 python mpi_socket.py -r $1 -s $2' &
#ssh psana "source /reg/g/psdm/etc/psconda.sh; cd wfs_v4; bsub -q psfehq -n 16 -o log/%J.log mpirun python mpi_socket.py -r $1 -s $2 -c $3" &
#ssh psana "source /reg/neh/home/seaberg/psana_setup.sh; cd /reg/neh/home/seaberg/Python_wfs_interface; bsub -q psfehq"