import socket
import threading
import http.server

connections = {}

class UpdateServer (http.server.BaseHTTPRequestHandler):
    """Provide robots a way to fetch new copies of their client runtime."""
    def do_GET(self):
        print(self.path)
        if self.path != "/client":
            self.send_response(404)
            self.end_headers()
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        with open("client.lua", "r") as file:
            self.wfile.write(file.read().encode())


def get_robots() -> list[int]:
    """Get a list of all connected robots"""
    return list(connections.keys())

# Send a command to a bot, and returns the response. All commands will return a response or acknowledgement.
# If the connection fails or the bot is not online, the function will return an empty string.
def send_command(bot_id: int, message: str) -> str:
    socket = connections.get(bot_id)
    if not socket:
        print(f"Failed to send command ({message}): Bot {bot_id} not connected")
        return ""

    try:
        socket.sendall((message + ";\n").encode())
        return _receive_message(socket)
    
    except ConnectionResetError:
        print(f"Failed to send command ({message}): Bot {bot_id} connection reset")
        connections.pop(bot_id)
        return ""
    except ConnectionAbortedError:
        print(f"Failed to send command ({message}): Bot {bot_id} connection aborted by host")
        connections.pop(bot_id)
        return ""
    
    except UnicodeDecodeError:
        print(f"Bot {bot_id} response encoding incorrect for command ({message})")


def _handle_new_client(client_socket: socket.socket) -> None:
    try:
        message = _receive_message(client_socket)
        if not message:
            print(f"{client_socket.getpeername()}: Agent connection did not reply")
            client_socket.close()
            return
        
        bot_id = int(message)

        if bot_id in connections:
            print(f"Bot {bot_id} already connected: upadting connection")
        else:
            print(f"Bot {bot_id} connected")

        # Give the robot something to read to ensure the connect works
        client_socket.sendall(("ack;\n").encode())
        
        connections[bot_id] = client_socket
    except UnicodeDecodeError:
        print("[UnicodeDecodeError]: Agent text encoding incorrect")
        client_socket.close()
    except ValueError:
        print(f"[ValueError]: Received invalid bot ID: {message}")
        client_socket.close()


# Returns an empty string if the connection is closed
def _receive_message(client_socket: socket.socket) -> str:
    message = b""
    while True:
        data = client_socket.recv(1024)
        if not data:
            return
        message += data
        if message.endswith(b";"):
            break
    return message.decode()[:-1]


def start_server(host='localhost', port=3) -> None:
    threading.Thread(target=_server_internal, args=(host, port)).start()

    threading.Thread(
        target=lambda: http.server.HTTPServer(("localhost", 80), UpdateServer).serve_forever(), 
        name="Update Server"    
    ).start()


def _server_internal(host: str, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"Server listening on {host}:{port}")
    while True:
        client_socket, addr = server.accept()
        print(f"Accepting connection from {addr}")
        client_handler = threading.Thread(target=_handle_new_client, args=(client_socket,))
        client_handler.start()
