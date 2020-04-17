from socket import *
import base64
import time


class Email:

    def __init__(self, user_email, user_name):
        self.user_email = user_email
        self.user_name = user_name
        self.mail_from = 'admin@ut.ac.ir'

    def send(self, template, mail_subject):
        mail_server = ('mail.ut.ac.ir', 25)
        client_socket = socket(AF_INET, SOCK_STREAM)
        client_socket.connect(mail_server)
        recv = client_socket.recv(1024)
        recv = recv.decode()

        print(f'Message after connection request: {recv}')
        if recv[:3] != '220':
            print('220 reply not received from server.')

        helo_command = 'Helo Admin\r\n'
        client_socket.send(helo_command.encode())
        recv1 = client_socket.recv(1024)
        recv1 = recv1.decode()

        print(f'Message after Helo command: {recv1}')
        if recv1[:3] != '250':
            print('250 reply not received from server.')

        #Info for username and password
        # *** You need to change username and password *** #
        username = "user-name"
        password = "XXXXXXXXXXXX"
        base64_str = ("\x00"+username+"\x00"+password).encode()
        base64_str = base64.b64encode(base64_str)
        auth_msg = "AUTH PLAIN ".encode()+base64_str+"\r\n".encode()
        client_socket.send(auth_msg)
        recv_auth = client_socket.recv(1024)
        print(recv_auth.decode())

        mail_from = f'MAIL FROM:<{self.mail_from}>\r\n'
        client_socket.send(mail_from.encode())
        recv2 = client_socket.recv(1024)
        recv2 = recv2.decode()
        print(f'After MAIL FROM command: {recv2}')

        rcptTo = f'RCPT TO:<{self.user_email}>\r\n'
        client_socket.send(rcptTo.encode())
        recv3 = client_socket.recv(1024)
        recv3 = recv3.decode()
        print(f'After RCPT TO command: {recv3}')

        data = "DATA\r\n"
        client_socket.send(data.encode())
        recv4 = client_socket.recv(1024)
        recv4 = recv4.decode()
        print(f'After DATA command: {recv4}')

        # Send actual mail to the user
        subject = f"Subject: {mail_subject}\r\n\r\n"
        client_socket.send(subject.encode())
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
        date = date + "\r\n\r\n"
        end_msg = '\r\n.\r\n'
        client_socket.send(date.encode())
        client_socket.send(template.encode())
        client_socket.send(end_msg.encode())
        recv_msg = client_socket.recv(1024)
        print("Response after sending message body:"+recv_msg.decode())

        # Close connection
        quit = "QUIT\r\n"
        client_socket.send(quit.encode())
        recv5 = client_socket.recv(1024)
        print(recv5.decode())
        client_socket.close()

    def send_internet_data_notification(self, threshold):
        msg = f'\r\nAttention:\n\n Dear client {self.user_name}, your internet data capacity is below {threshold}mb.'
        try:
            self.send(msg, mail_subject='FTP Server')
        except Exception as e:
            print(f'Error sending email: {str(e)}')