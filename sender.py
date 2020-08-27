from socket import *
from packet import packet
import time
import threading
import sys

class sender:
    cur_file_position = 0
    PACKET_MAX_LOAD = 500
    SEQ_NUM_MODULO = 32
    WINDOW_SIZE = 10
    MAX_DELAY = 150
    lock_window = None
    lock_timer = None
    window = []
    next_seqnum = 0
    base = 0
    start_time = None

    def __init__(self, host_address, udp_port_data, udp_port_ack, file_to_transfer):
        self.host_address = host_address
        self.udp_port_data = int(udp_port_data)
        self.udp_port_ack = int(udp_port_ack)
        self.file_to_transfer = file_to_transfer
        self.lock_window = threading.Lock()
        self.lock_timer = threading.Lock()
    
    #log
    def log_sent(self, text):
        with open("seqnum.log", "a+") as f:
            f.write(text+'\n')
            
    def log_receive(self, text):
        with open("ack.log", "a+") as f:
            f.write(text+'\n')

    #get_next_seqnum
    def get_next_seqnum(self):
        return self.next_seqnum%self.SEQ_NUM_MODULO
    
    #set the timer
    def set_timer(self):
        self.lock_timer.acquire()
        self.start_time = time.time()
        self.lock_timer.release()

    #if the start time hasn't been setted, return -1
    def get_timer(self):
        self.lock_timer.acquire()
        return_value = -1
        if self.start_time != None:
            return_value = (time.time() - self.start_time)*1000
        self.lock_timer.release()
        return return_value

    #read target file to get next 500 byte data to send
    def get_next_filedata(self):
        file_to_send = open(self.file_to_transfer, "r")
        file_to_send.seek(self.cur_file_position)
        data_chunk = file_to_send.read(self.PACKET_MAX_LOAD)
        if data_chunk != "":
            self.cur_file_position += self.PACKET_MAX_LOAD
        return data_chunk

    #send data pkts
    def send_file(self):
        udp_socket = socket(AF_INET, SOCK_DGRAM)
        while True:
            if self.get_timer() > self.MAX_DELAY:
                #print("timer timeout: " + str(self.get_timer()))
                self.lock_window.acquire()
                for pkt in self.window:
                    udp_socket.sendto(pkt.get_udp_data(), (self.host_address, self.udp_port_data))
                    #print("timeout pkt: seqnum " + str(pkt.seq_num))
                    self.log_sent(str(pkt.seq_num))
                self.set_timer()
                self.lock_window.release()
            #if window is not full, load new packet
            self.lock_window.acquire()
            if len(self.window) < self.WINDOW_SIZE:
                """
                #after all pkt 0-31 has been sent, wait for all of then be acked 
                if len(self.window) != 0 and self.get_next_seqnum() == 0:
                    self.lock_window.release()
                    continue
                """
                self.lock_window.release()
                data = self.get_next_filedata()
                if data == "":
                    #file has been completely read and
                    #all the packet in window has sent
                    self.lock_window.acquire()
                    if len(self.window) == 0:
                        self.lock_window.release()
                        #send eot
                        #print("pkt: eot seq_num " + str(self.get_next_seqnum()))
                        packet_to_send = packet.create_eot(self.get_next_seqnum())
                        udp_socket.sendto(packet_to_send.get_udp_data(), (self.host_address, self.udp_port_data))
                        udp_socket.close()
                        break
                    else:
                        self.lock_window.release()
                #create new pkt and send it
                elif data != "":
                    packet_to_send = packet.create_packet(self.get_next_seqnum(), data)
                    self.lock_window.acquire()
                    #print("pkt: seq_num " + str(self.get_next_seqnum()))
                    #print(self.window)
                    udp_socket.sendto(packet_to_send.get_udp_data(), (self.host_address, self.udp_port_data))
                    self.log_sent(str(packet_to_send.seq_num))
                    #set timer if the pkt is the only pkt sent but not acked
                    if len(self.window) == 0:
                        self.set_timer()
                    self.window.append(packet_to_send)
                    self.next_seqnum += 1
                    self.lock_window.release()
            else:
                self.lock_window.release()

    #receive ack pkt and pop the acked packet form the window 
    def verify_ack(self):
        udp_socket = socket(AF_INET, SOCK_DGRAM)
        udp_socket.bind(('', self.udp_port_ack))
        is_first_ack = True
        while True:
            #waiting ack
            row_data, clientAddress = udp_socket.recvfrom(1024) #1024 if buffer size
            received_packet = packet.parse_udp_data(row_data)
            if received_packet.type == 0:
                self.lock_window.acquire()
                #print("ack: seq_num "+str(received_packet.seq_num))
                #print("base: "+str(self.base))
                self.log_receive(str(received_packet.seq_num))
                #define base_seqnum = 1 which represent the relationship 
                #between base and new acked seqnum
                last_sent_seqnum = (self.next_seqnum-1)%self.SEQ_NUM_MODULO
                base_seqnum_type = 3 #should not be acked if 3
                if (self.base <= received_packet.seq_num and received_packet.seq_num <= last_sent_seqnum) or\
                   (self.base > last_sent_seqnum and received_packet.seq_num >= self.base):
                    base_seqnum_type = 1 #not cross 31
                elif (self.base > last_sent_seqnum and received_packet.seq_num <= last_sent_seqnum):
                    base_seqnum_type = 2 #cross 31
                else:
                    base_seqnum_type = 3 #not valid ack seqnum
                #delete the packet form window with the right seq_num, 
                len_window = len(self.window)
                i = 0
                while i < len_window:
                    if (base_seqnum_type == 1 and self.window[i].seq_num <= received_packet.seq_num and self.window[i].seq_num >= self.base) or \
                    (base_seqnum_type == 2 and (self.window[i].seq_num >= self.base or self.window[i].seq_num <= received_packet.seq_num)):
                        pkt=self.window.pop(i)
                        #print("delete: " + str(pkt.seq_num))
                        len_window -= 1
                    else:
                        i += 1
                #update base
                if base_seqnum_type != 3:
                    self.base = (received_packet.seq_num + 1)%self.SEQ_NUM_MODULO
                #print(self.window)
                #if there is still some packet sent but not acked
                #set timer for one of them
                if len(self.window) != 0:
                    self.set_timer()
                self.lock_window.release()
            elif received_packet.type == 2:
                #print("ack: eot seq_num "+str(received_packet.seq_num))
                break

    def run(self):
        #send packet in another thread
        sending_thread = threading.Thread(target=self.send_file)
        sending_thread.start()
        #receving the acks in the main thread
        self.verify_ack()
        sending_thread.join()

if __name__ == "__main__":
    program_start_time = time.time()
    with open("seqnum.log", "w+") as f:
        f.write("")
    with open("ack.log", "w+") as f:
        f.write("")
    host_address = sys.argv[1]
    udp_port_data = int(sys.argv[2])
    udp_port_ack = int(sys.argv[3])
    file_to_transfer = sys.argv[4]
    sender = sender(host_address, udp_port_data, udp_port_ack, file_to_transfer)
    sender.run()
    program_total_time = time.time() - program_start_time
    with open("time.log", "w") as f:
        f.write(str(program_total_time))
    print("total cost time: " + str(program_total_time))
    
