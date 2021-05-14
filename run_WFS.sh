#!/bin/env bash

while getopts u:e: flag
do 
    case "${flag}" in
        u) username=${OPTARG};;
        e) experiment=${OPTARG};;
    esac
done

echo "Username: $username";
ssh $username@psdev "source /cds/home/s/seaberg/psana_setup.sh; cd /cds/home/s/seaberg/Python/wfs_interface; python run_interface.py -e $experiment"
#cd /cds/home/s/seaberg/Python/wfs_interface

#python WFS_interface.py
