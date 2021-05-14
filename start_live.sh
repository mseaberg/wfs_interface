#!/bin/bash
source /reg/g/psdm/etc/psconda.sh
echo $(hostname)

# path to home directory
home_path=/cds/home/s/seaberg
# run command in xterm
xterm -e "ssh $1 'source $home_path/psana_setup.sh; cd $home_path/Python/wfs_interface; hostname; mpirun -n 8 python mpi_reply.py -b $2 -e $3 -r $4 -s $5 -c $6 -l True'"

