# FTP CLIENT
import socket
import sys


class FTPClient:
    def __init__(self, addr, cmd_port, d_port):
        self.address = addr
        self.cmd_port = int(cmd_port)
        self.data_port = int(d_port)
        self.cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def create_connection(self):
        print('Starting connection to', self.address, ':', self.cmd_port)

        try:
            server_address = (self.address, self.cmd_port)
            self.cmd_socket.connect(server_address)
            print('Connected to', self.address, ':', self.cmd_port)
        except KeyboardInterrupt:
            self.close_client()
        except:
            print('Connection to', self.address, ':', self.cmd_port, 'failed')
            self.close_client()

    def start(self):
        try:
            self.create_connection()
        except Exception as e:
            print(str(e))
            self.close_client()

        while True:
            try:
                command = input('Enter command:\n')
                if not command:
                    print('Need a command.\n')
                    continue
            except KeyboardInterrupt:
                self.close_client()

            cmd, *path = command.split(' ')
            cmd = cmd.upper()

            try:
                self.cmd_socket.send(str.encode(command))
                data = self.cmd_socket.recv(1024).decode('utf-8')
                if data != '125 Data connection already open.':
                    print(data)

                if cmd == 'QUIT':
                    self.close_client()
                elif cmd == 'LIST' or cmd == 'DL':
                    if data and (data[0:3] == '125'):
                        func = getattr(self, cmd)
                        if not len(path):
                            func('')
                        else:
                            func(path[0])
            except Exception as e:
                print(str(e))
                self.close_client()

    def connect_data_socket(self):
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.address, self.data_port))

    def LIST(self, path):
        try:
            self.connect_data_socket()
            data = self.cmd_socket.recv(1024).decode('utf-8')
            print(data)
            while True:
                dirlist = self.data_socket.recv(1024).decode('utf-8')
                if not dirlist:
                    break
                sys.stdout.write(dirlist)
                sys.stdout.flush()
        except Exception as e:
            print(str(e))
        finally:
            self.data_socket.close()

    def DL(self, file_name):
        print(f'Downloading {file_name} from the server...')
        try:
            self.connect_data_socket()
            msg = self.cmd_socket.recv(1024).decode('utf-8')
            print(msg)
            if msg.startswith('4') or msg.startswith('5'):
                return
            file = open(file_name, 'w')
            while True:
                stream = self.data_socket.recv(1024).decode('utf-8')
                if not stream:
                    break
                file.write(stream)
        except Exception as e:
            print(str(e))
        finally:
            if 'file' in locals():
                file.close()
            self.data_socket.close()

    def close_client(self):
        print('Closing socket connection...')
        self.cmd_socket.close()
        print('FTP client terminating...')
        quit()


if __name__ == "__main__":
    address = 'localhost'
    command_port = 7001
    data_port = 7002

    ftpClient = FTPClient(address, command_port, data_port)
    ftpClient.start()
