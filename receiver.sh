#!/bin/bash
host_address=$1
udp_port_ack=$2
udp_port_data=$3 
file_to_write=$4

python3 receiver.py $host_address $udp_port_ack $udp_port_data $file_to_write
