import errno
import select
import socket
import sys
import traceback
from http_parser.parser import HttpParser
import time
import datetime
import os
class Poller:
    """ Polling server """
    def __init__(self,port, config):
        self.host = ""
        self.port = port
        self.open_socket()
        self.clients = {}
        self.size = 1024
        self.clientMeta = {}
        self.config = config
        self.timeoutTime = int(self.config.parameters['timeout'] or 5)
    def open_socket(self):
        """ Setup the socket for incoming clients """
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
            self.server.bind((self.host,self.port))
            self.server.listen(5)
            self.server.setblocking(0)
        except socket.error, (value,message):
            if self.server:
                self.server.close()
            print "Could not open socket: " + message
            sys.exit(1)

    def run(self):
        """ Use poll() to handle each incoming client."""
        self.poller = select.epoll()
        self.pollmask = select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR
        self.poller.register(self.server,self.pollmask)
        
        while True:
            # poll sockets
            try:
                fds = self.poller.poll(timeout=1)
            except:
                return
            self.time = time.time()
            for (fd,event) in fds:
                # handle errors
                if event & (select.POLLHUP | select.POLLERR):
                    self.handleError(fd)
                    continue
                # handle the server socket
                if fd == self.server.fileno():
                    self.handleServer()
                    continue
                # handle client socket
                result = self.handleClient(fd)

    def handleError(self,fd):
        self.poller.unregister(fd)
        if fd == self.server.fileno():
            # recreate server socket
            self.server.close()
            self.open_socket()
            self.poller.register(self.server,self.pollmask)
        else:
            # close the socket
            self.clients[fd].close()
            del self.clients[fd]

    def handleServer(self):
        # accept as many clients as possible
        while True:
            try:
                (client,address) = self.server.accept()
            except socket.error, (value,message):
                # if socket blocks because no clients are available,
                # then return
                if value == errno.EAGAIN or errno.EWOULDBLOCK:
                    return
                print traceback.format_exc()
                sys.exit()
            # set client socket to be non blocking
            client.setblocking(0)
            self.clients[client.fileno()] = client
            self.poller.register(client.fileno(),self.pollmask)
            
            # add metadata about the client
            self.clientMeta[client.fileno()] = {
                "cache": '',
                "time": time.time()
            }
    
    def getCommonHeaders(self, responseNumber,contentType,length,lastModified):
        codes = {
            '200': ' OK\r\n',
            '400': ' Bad Request\r\n',
            '403': ' Forbidden\r\n',
            '404': ' Not Found\r\n',
            '500': ' Internal Server Error\r\n',
            '501': ' Not Implemented\r\n'
        }
        now = datetime.datetime.now()
        lastModifiedDate = datetime.date.fromtimestamp(lastModified)
        res = 'HTTP/1.1 ' + responseNumber + codes[responseNumber]
        res = res + 'Date: ' + now.strftime('%a, %d %b %Y %H:%M:%S GMT') + '\r\n'
        res = res + 'Server: pythonServer\r\n'
        res = res + 'Content-Type: ' + contentType + '\r\n'
        res = res + 'Content-Length: ' + str(length) + '\r\n'
        return res + 'Last-Modified: ' + lastModifiedDate.strftime('%a, %d %b %Y %H:%M:%S GMT') + '\r\n\r\n'


    def makeErrorHttpPage(self, errorNumber): 
        body = '<html><body>' + errorNumber + ' error</body></html>'
        res = self.getCommonHeaders(errorNumber,'html',len(body),time.time())
        return res + body

    def makeResponse(self,message):
        method = message.get_method()
        if method != 'GET':
            return self.makeErrorHttpPage('501')
        file = message.get_path()
        headers = message.get_headers()
        host = headers['Host']
        path = ''
        if host in self.config.hosts:
            path = self.config.hosts['host']
        else:
            path = self.config.hosts['default']
        if file == '/':
            file = '/index.html'
        try: 
            filename = path + file
            lastModified = os.stat(filename).st_mtime
            f = open(filename)
            content = f.read()
            res = self.getCommonHeaders('200',file.split('.')[-1],len(content), lastModified)
            return res + content
        except Exception as e:
            if e[0] == 13:
                return self.makeErrorHttpPage('403')
            if e[0] == 2:
                return self.makeErrorHttpPage('404')
            return self.makeErrorHttpPage('500')

    def handleClient(self,fd):
        try:
            data = self.clients[fd].recv(self.size)
        except socket.error, (value,message):
            # if no data is available, move on to another client
            if value == errno.EAGAIN or errno.EWOULDBLOCK:
                return
            print traceback.format_exc()
            sys.exit()

        if data:
            self.clientMeta[fd]['cache'] = self.clientMeta[fd]['cache'] + data
            self.clientMeta[fd]['time'] = time.time()
            firstMessageLength = self.clientMeta[fd]['cache'].find('\r\n\r\n')
            if firstMessageLength >= 0:
                newData = self.clientMeta[fd]['cache'][:firstMessageLength + 4]
                self.clientMeta[fd]['cache'] = self.clientMeta[fd]['cache'][firstMessageLength + 4:]
                p = HttpParser()
                nparsed = p.execute(newData, len(newData))
                response = self.makeResponse(p)
                self.clients[fd].send(response)
                # self.poller.unregister(fd)
                # self.clients[fd].close()
                # del self.clients[fd]
            # self.clients[fd].send(data)
        elif self.time - self.clientMeta[fd]['time'] > self.timeoutTime:
            self.clients[fd].send(self.makeErrorHttpPage('400'))
            self.poller.unregister(fd)
            self.clients[fd].close()
            del self.clients[fd]
            del self.clientMeta[fd]