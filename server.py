#!/usr/bin/python3
# coding=utf-8

"""
server.py: uses Statstics class from latex.py and plots statistics. Use in combination with client.py
"""

__author__ = "Simon Gunacker"
__copyright__ = "Copyright 2018, Graz"

import socket, os
from latex import *
from colorama import Fore, Back, Style, init
            
class StatsServer(object):
    _HOST = '127.0.0.1'
    _PORT = 1234

    def __init__(self):
        super(StatsServer, self).__init__()
        self.serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversock.bind( (self._HOST, self._PORT) )
        self.serversock.listen(1)
        self.print("Welcome. Server is running on {}:{}. Awaiting requests ...".format(self._HOST, self._PORT))

    def print(self, text):
        print(Fore.BLACK + Style.BRIGHT + "(server) " + Style.RESET_ALL + Fore.WHITE + text)

    def loop_forever(self):
        while True:
            clientsock, addr = self.serversock.accept()
            self.handle_request(clientsock, addr)

    def handle_request(self, clientsock, addr):
        while True:
            data = clientsock.recv(1024)
            if not data: 
                break
            data = data.decode()
            os.system("cls")
            if data == "toc":
                Statistics().print_table_of_content()
            elif data == "lot":
                Statistics().print_list_of_tables()
            elif data == "lof":
                Statistics().print_list_of_figures()
            elif data == "unu" or data == "unu refs":
                Statistics().print_unused_references()
            elif data == "unu figs":
                Statistics().print_unused_figures()
            elif data == "und":
                Statistics().print_undefined_references()
            elif data == "backup":
                Statistics().backup_first_start_of_day()
            else:
                self.print("Unknown command: {}".format(data))
        clientsock.close()
        
if __name__ == "__main__":
    os.system("cls")
    StatsServer().loop_forever()