# FTP SERVER
import socket
import os
import threading
import time
import json
import logging
from functools import wraps
from collections import namedtuple
from emails import Email


def _json_object_hook(d): return namedtuple('config', d.keys())(*d.values())


def json2obj(data): return json.loads(data, object_hook=_json_object_hook)


def is_protected_file(file_name):
    for file in authorization.files:
        if file[2:] in file_name:
            return True
    return False


def log(message):
    if logging_info.enable:
        logger.info(message)


class FTPThreadServer(threading.Thread):
    def __init__(self, server_socket, local_ip, d_port):
        (client, client_address) = server_socket
        self.client = client
        self.client_address = client_address
        self.cwd = os.getcwd()
        self.initial_wd = self.cwd
        self.data_address = (local_ip, d_port)
        self.user_data = {'name': None, 'password': None, 'is_login': False, 'is_admin': False}
        self.error_messages = {
            'internalErr': str.encode('500 Error.'),
            'unauthorizedErr': str.encode('332 Need account for login.'),
            'syntaxErr': str.encode('501 Syntax error in parameters or arguments.'),
            'invalidData': str.encode('430 Invalid username or password.'),
            'badRequest': str.encode('503 Bad sequence of commands.'),
            'notFound': str.encode('404 File not found.')
        }
        self.instructions = \
            ['USER [name], Its argument is used to specify the user\'s name. It is used for user authentication.\n',
             'PASS [password], Its argument is used to specify the user\'s password.'
             ' It is used for user authentication.\n',
             'PWD, It is used for displaying current working directory.\n',
             'MKD -i [name], It is used for creating a new folder or file with specified argument.'
             ' If flag \'i\' is present then the server is going to create a new file, otherwise a new folder.\n',
             'RMD -f [name], It is used for deleting an existing folder or file with specified name argument. '
             'If flag \'f\' is present then the server is going to delete that folder, otherwise the file.\n',
             'LIST, It is used for displaying current working directory\'s files.\n',
             'CWD <path>, It is used for changing current working directory.'
             ' Its argument is used to specify the path to go to.'
             ' If no path specified then it will go to initial directory.\n',
             'DL [name], It is used for downloading an existing file with specified argument.\n',
             'QUIT, It is used for signing out the current user.\n'
             ]

        threading.Thread.__init__(self)

    def start_data_socket(self):
        try:
            print('Creating data socket on' + str(self.data_address) + '...')

            # create TCP for data socket
            self.dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.dataSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.dataSocket.bind(self.data_address)
            self.dataSocket.listen(5)
            self.client.send(str.encode('125 Data connection already open.'))

            print('Data socket is started. Listening to' + str(self.data_address) + '...')
            return self.dataSocket.accept()
        except Exception as e:
            print('ERROR: ' + str(self.client_address) + ': ' + str(e))
            self.close_data_socket()
            self.client.send(self.error_messages.get('internalErr'))

    def close_data_socket(self):
        print('Closing data socket connection...')
        try:
            self.dataSocket.close()
        except Exception as e:
            print(str(e))

    def run(self):
        try:
            print('client connected: ' + str(self.client_address) + '\n')

            while True:
                cmd = self.client.recv(1024).decode("utf-8")
                if not cmd:
                    break
                try:
                    cmd_parts = cmd.split(' ')
                    func = getattr(self, cmd_parts[0].strip().upper())
                    func(cmd)
                except AttributeError as e:
                    self.client.send(self.error_messages.get('syntaxErr'))
        except Exception as e:
            print(f'Error processing user command. {str(e)}')
            self.client.send(str.encode('500 Error.'))
            self.shut_down()

    def HELP(self, cmd):
        self.client.send(str.encode('\n'.join(self.instructions)))

    def protected_func(fn):
        @wraps(fn)
        def wrapper(self, *args, **kwargs):
            if self.user_data.get('is_login'):
                return fn(self, *args, **kwargs)
            else:
                return self.client.send(self.error_messages.get('unauthorizedErr'))

        return wrapper

    def USER(self, cmd):
        user_name_to_check = cmd[4:].strip()
        if not any(usr.user == user_name_to_check for usr in users):
            self.client.send(self.error_messages.get('invalidData'))
        else:
            self.user_data['name'] = user_name_to_check
            self.client.send(str.encode('331 User name okay, need password.'))

    def PASS(self, cmd):
        if not self.user_data.get('name'):
            self.client.send(self.error_messages.get('badRequest'))
        else:
            password_to_check = cmd[4:].strip()
            if not any(usr.user == self.user_data.get('name') and usr.password == password_to_check for
                       usr in users):
                self.client.send(self.error_messages.get('invalidData'))
            else:
                self.user_data['password'] = password_to_check
                self.user_data['is_login'] = True
                if self.user_data.get('name') in authorization.admins:
                    self.user_data['is_admin'] = True
                log(f'{self.user_data.get("name")} logged in successfully')
                self.client.send(str.encode('230 User logged in, proceed.'))

    @protected_func
    def PWD(self, cmd):
        self.client.send(str.encode(f'257 {self.cwd}'))

    @protected_func
    def MKD(self, cmd):
        if not cmd[4:]:
            self.client.send(self.error_messages.get('syntaxErr'))
        part1, *part2 = cmd[4:].strip().split(' ')
        try:
            if len(part2) == 0:
                dirname = os.path.join(self.cwd, part1)
                os.mkdir(dirname)
                log(f'{self.user_data.get("name")} created new directory: {dirname}')
                self.client.send(str.encode(f'257 {dirname} created.'))
            elif part1 == '-i':
                file_name = os.path.join(self.cwd, part2[0])
                open(file_name, 'a').close()
                log(f'{self.user_data.get("name")} created new file: {file_name}')
                self.client.send(str.encode(f'257 {file_name} created.'))
            else:
                self.client.send(self.error_messages.get('syntaxErr'))
        except Exception as e:
            print('ERROR: ' + str(self.client_address) + ': ' + str(e))
            self.client.send(self.error_messages.get('internalErr'))

    @protected_func
    def RMD(self, cmd):
        if not cmd[4:]:
            self.client.send(self.error_messages.get('syntaxErr'))
        part1, *part2 = cmd[4:].strip().split(' ')
        try:
            if len(part2) == 0:
                file_name = os.path.join(self.cwd, part1)
                if not self.user_data.get('is_admin') and is_protected_file(file_name):
                    self.client.send(str.encode('550 File unavailable.'))
                    return
                os.remove(file_name)
                log(f'{self.user_data.get("name")} deleted file: {file_name}')
                self.client.send(str.encode(f'250 {file_name} deleted.'))
            elif part1 == '-f':
                dirname = os.path.join(self.cwd, part2[0])
                os.rmdir(dirname)
                log(f'{self.user_data.get("name")} deleted directory {dirname}')
                self.client.send(str.encode(f'250 {dirname} deleted.'))
            else:
                self.client.send(self.error_messages.get('syntaxErr'))
        except Exception as e:
            print('ERROR: ' + str(self.client_address) + ': ' + str(e))
            self.client.send(self.error_messages.get('internalErr'))

    @protected_func
    def LIST(self, cmd):
        (client_data, client_address) = self.start_data_socket()

        try:
            listdir = os.listdir(self.cwd)
            if not len(listdir):
                max_length = 0
            else:
                max_length = len(max(listdir, key=len))

            header = '| %*s | %9s | %12s | %20s | %11s | %12s |' % (
                max_length, 'Name', 'Filetype', 'Filesize', 'Last Modified', 'Permission', 'User/Group')
            table = '%s\n%s\n%s\n' % ('-' * len(header), header, '-' * len(header))
            client_data.send(str.encode(table))

            for i in listdir:
                path = os.path.join(self.cwd, i)
                stat = os.stat(path)
                if not os.path.isdir(path) and not self.user_data.get('is_admin') and is_protected_file(path):
                    continue
                data = '| %*s | %9s | %12s | %20s | %11s | %12s |\n' % (
                    max_length, i, 'Directory' if os.path.isdir(path) else 'File', str(stat.st_size) + 'B',
                    time.strftime('%b %d, %Y %H:%M', time.localtime(stat.st_mtime))
                    , oct(stat.st_mode)[-4:], str(stat.st_uid) + '/' + str(stat.st_gid))
                client_data.send(str.encode(data))

            table = '%s\n' % ('-' * len(header))
            client_data.send(str.encode(table))
        except Exception as e:
            print('ERROR: ' + str(self.client_address) + ': ' + str(e))
            self.client.send(self.error_messages.get('internalErr'))
        finally:
            client_data.close()
            self.close_data_socket()
            self.client.send(str.encode('226 List transfer done.'))

    @protected_func
    def CWD(self, cmd):
        dest = os.path.join(self.cwd, cmd[4:].strip())
        if len(cmd.strip()) == 3:
            os.chdir(self.initial_wd)
            self.cwd = self.initial_wd
        elif cmd[4:].strip() == '..':
            os.chdir('..')
            self.cwd = os.getcwd()
        elif os.path.isdir(dest):
            os.chdir(dest)
            self.cwd = dest
        else:
            print('ERROR: ' + str(self.client_address) + ': No such file or directory.')
            self.client.send(self.error_messages.get('internalErr'))
            return
        self.client.send(str.encode('250 Successful Change.'))

    @protected_func
    def DL(self, cmd):
        path = cmd[3:].strip()
        if not path:
            self.client.send(self.error_messages.get('syntaxErr'))
            return

        file_to_download = os.path.join(self.cwd, path)
        (client_data, client_address) = self.start_data_socket()
        if not os.path.isfile(file_to_download):
            self.client.send(self.error_messages.get('notFound'))
        else:
            if not self.manage_accounting(file_to_download):
                return
            try:
                target_file = open(file_to_download, "r")
                data = target_file.read(1024)

                while data:
                    client_data.send(str.encode(data))
                    data = target_file.read(1024)

                log(f'{self.user_data.get("name")} downloaded file: {file_to_download}')
                self.client.send(str.encode('226 Successful Download.'))
            except Exception as e:
                print('ERROR: ' + str(self.client_address) + ': ' + str(e))
                self.client.send(self.error_messages.get('internalErr'))
            finally:
                client_data.close()
                self.close_data_socket()
                target_file.close()

    def QUIT(self, cmd):
        try:
            if self.user_data.get('is_login'):
                self.client.send(str.encode('221 Successful Quit.'))
                log(f'{self.user_data.get("name")} logged out')
                print('Closing connection from ' + str(self.client_address) + '...')
                self.user_data['name'] = None
                self.user_data['password'] = None
                self.user_data['is_login'] = False
                self.shut_down()
            else:
                self.client.send(self.error_messages.get('badRequest'))
        except Exception as e:
            print(str(e))

    def manage_emails(self, user):
        pass

    def manage_accounting(self, file):
        if not self.user_data.get('is_admin') and is_protected_file(file):
            self.client.send(str.encode('550 File unavailable.'))
            return False

        target_file_size = os.stat(file).st_size
        if accounting.enable:
            # Read config file
            with open("config.json", "r") as config_file:
                data = config_file.read()

            # Parse the data
            data_obj = json2obj(data)
            # Find user
            (index, current_user) = next(
                ((i, x) for i, x in enumerate(data_obj.accounting.users) if x.user == self.user_data.get('name')), None)
            if not current_user:
                pass
            else:
                # In this case user has not enough data
                if target_file_size > int(current_user.size):
                    self.client.send(str.encode('425 Can\'t open data connection.'))
                    return False
                else:
                    with open('config.json', 'r+') as f:
                        new_data = json.load(f)
                        new_size = int(current_user.size) - target_file_size
                        new_data['accounting'].get('users')[index]['size'] = \
                            str(new_size)
                        f.seek(0)
                        json.dump(new_data, f, indent=4)
                        f.truncate()  # remove remaining part
                    if current_user.alert and  new_size < data_obj.accounting.threshold:
                        email = Email(current_user.email, current_user.user)
                        email.send_internet_data_notification(data_obj.accounting.threshold)
        return True
    def shut_down(self):
        self.close_data_socket()
        self.client.close()
        quit()



class FTPServer:
    def __init__(self, cmd_port, d_port):
        # server address at localhost
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.address = '0.0.0.0'

        self.cmd_port = int(cmd_port)
        self.data_port = int(d_port)

    def start_sock(self):
        # create TCP socket
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_address = (self.address, self.cmd_port)

        try:
            print(f'Creating data socket on {self.address}: {self.cmd_port}...')
            self.sock.bind(server_address)
            self.sock.listen(5)
            print(f'Server is up. Listening to {self.address}: {self.cmd_port}')
        except Exception as e:
            print(f'Failed to create server on {self.address} : {self.cmd_port}.\n Error: {str(e)}')
            quit()

    def start(self):
        self.start_sock()

        try:
            while True:
                print('Waiting for a connection')
                thread = FTPThreadServer(self.sock.accept(), self.address, self.data_port)
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print('Closing socket connection')
            self.sock.close()
            quit()


# Main
if __name__ == "__main__":
    # Read config file
    with open("config.json", "r") as config_file:
        data = config_file.read()

    # Parse the data
    data_obj = json2obj(data)

    # Retrieve data and command ports
    command_port = data_obj.commandChannelPort
    data_port = data_obj.dataChannelPort

    # Retrieve users
    users = data_obj.users

    # Retrieve accounting info
    accounting = data_obj.accounting

    # Retrieve authorization
    authorization = data_obj.authorization

    # Retrieve logging info
    logging_info = data_obj.logging

    if logging_info.enable:
        logging_dir = os.path.join(os.getcwd(), logging_info.path[2:])
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler = logging.FileHandler(filename=logging_dir, encoding='utf8')
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

    server = FTPServer(command_port, data_port)
    server.start()
