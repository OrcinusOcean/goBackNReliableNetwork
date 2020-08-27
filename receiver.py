from packet import packet
from socket import *
import sys

class receiver:

    def __init__(self, host_address, udp_port_ack, udp_port_data, file_to_write):
        self.host_address = host_address
        self.udp_port_ack = int(udp_port_ack)
        self.udp_port_data = int(udp_port_data)
        self.file_to_write = file_to_write
        self.expect_seqnum = 0

    #log
    def log(self, text):
        with open("arrival.log", "a+") as f:
            f.write(text + '\n')

    #get next inoder seqnum
    def get_expect_squnum(self):
        SEQ_NUM_MODULO = 32
        return self.expect_seqnum % SEQ_NUM_MODULO

    def run(self):
        udp_socket_receive = socket(AF_INET, SOCK_DGRAM)
        udp_socket_receive.bind(('', self.udp_port_data))
        udp_socket_send = socket(AF_INET, SOCK_DGRAM)
        while True:
            #print("waitting...")
            row_data, clientAddress = udp_socket_receive.recvfrom(1024) #1024 if buffer size
            received_packet = packet.parse_udp_data(row_data)
            #print("except seqnum: " + str(self.get_expect_squnum()))
            #print("actual seqnum: " + str(received_packet.seq_num))

            #print(received_packet.data)
            if received_packet.type == 1:
                self.log(str(received_packet.seq_num))
                if (received_packet.seq_num == self.get_expect_squnum()):
                    self.expect_seqnum += 1
                    if received_packet.type == 1:
                        if (self.expect_seqnum-1) == 0:
                            with open(self.file_to_write, "w+") as f:
                                f.write(received_packet.data)
                        else:
                            with open(self.file_to_write, "a") as f:
                                f.write(received_packet.data)
                        #last acked pkt's seqnum is excepted next seqnum - 1
                        packet_to_send = packet.create_ack(self.get_expect_squnum()-1)
                        #print("send ack: "+ str(packet_to_send.seq_num))
                        udp_socket_send.sendto(packet_to_send.get_udp_data(), (self.host_address, self.udp_port_ack))
                else:
                    #if the last pkt is not what we want, 
                    #resend the lastest acked seqnum
                    #last acked pkt's seqnum is excepted next seqnum - 1
                    if self.expect_seqnum != 0:
                        packet_to_send = packet.create_ack(self.get_expect_squnum()-1)
                        #print("send previous ack: "+ str(packet_to_send.seq_num))
                        udp_socket_send.sendto(packet_to_send.get_udp_data(), (self.host_address, self.udp_port_ack))
            elif received_packet.type == 2:
                packet_to_send = packet.create_eot(self.get_expect_squnum())
                udp_socket_send.sendto(packet_to_send.get_udp_data(), (self.host_address, self.udp_port_ack))
                #print("eot seqnum: " + str(packet_to_send.seq_num))
                udp_socket_send.close()
                break
            

if __name__ == "__main__":
    host_address = sys.argv[1]
    udp_port_ack = int(sys.argv[2])
    udp_port_data = int(sys.argv[3])
    file_to_write = sys.argv[4]
    with open(file_to_write, "w+") as f:
        f.write("")
    with open("arrival.log", "w+") as f:
        f.write("")
    receiver = receiver(host_address, udp_port_ack, udp_port_data, file_to_write)
    receiver.run()
