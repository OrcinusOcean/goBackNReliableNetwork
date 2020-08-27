#!/bin/bash

host_address=$1
udp_port_data=$2
udp_port_ack=$3
file_to_transfer=$4

rm -f result.txt
rm -f seqnum.log
rm -f ack.log
python3 sender.py $host_address $udp_port_data $udp_port_ack $file_to_transfer
