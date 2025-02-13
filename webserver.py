import asyncio
import json
import logger
import socket
import threading
import http.server

connections: dict[int, tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}

new_connections = []
removed_connections = []
# Stops the planner to handle new/removed agents
connections_updated_event = asyncio.Event()

class UpdateServer (http.server.BaseHTTPRequestHandler):
    """Provide robots a way to fetch new copies of their client runtime."""
    def do_GET(self):
        if self.path != "/client":
            self.send_response(404)
            self.end_headers()
            return
        
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        with open("client.lua", "r") as file:
            self.wfile.write(file.read().encode())


def _disconnect(id):
    connections.pop(id)
    if id in removed_connections:
        removed_connections.append(id)
        connections_updated_event.set()

def get_robots() -> list[int]:
    """Get a list of all connected robots"""
    return list(connections.keys())

# Send a command to a bot, and returns the response. All commands will return a response or acknowledgement.
# If the connection fails or the bot is not online, the function will return an empty string.
async def send_command(bot_id: int, message: str) -> str:
    connection = connections.get(bot_id)
    if not connection:
        logger.error(f"Failed to send command ({message}): Bot not connected", bot_id)
        return "{\"success\": false, \"error\": \"Robot not connected\"}"
    reader, writer = connection

    try:
        writer.write((message + ";\n").encode())
        message = await _receive_message(reader)
        if message == "":
            logger.error(f"Failed to send command ({message}): No response", bot_id)
            writer.close()
            _disconnect(bot_id)
            return "{\"success\": false, \"error\": \"Robot disconnected\"}"
        else:
            return message

    except ConnectionResetError:
        logger.error(f"Failed to send command ({message}): Connection reset", bot_id)
        writer.close()
        _disconnect(bot_id)
        return "{\"success\": false, \"error\": \"Robot disconnected\"}"
    except ConnectionAbortedError:
        logger.error(f"Failed to send command ({message}): Connection aborted by host", bot_id)
        writer.close()
        _disconnect(bot_id)
        return "{\"success\": false, \"error\": \"Robot disconnected\"}"
    
    except UnicodeDecodeError:
        logger.error(f"Response encoding incorrect for command ({message})", bot_id)


async def _handle_new_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        message = await _receive_message(reader)
        if not message:
            logger.error("Agent connection did not reply", writer.get_extra_info("peername"))
            writer.close()
            return
        
        bot_id = int(message)

        if bot_id in connections:
            logger.info("Bot reconnected - switching to new connection", bot_id)
        else:
            logger.info(f"Bot connected", bot_id)

        # Give the robot something to read to ensure the connect works
        writer.write(("ack;\n").encode())
        connections[bot_id] = (reader, writer)
        new_connections.append(bot_id)
        connections_updated_event.set()
        
    except UnicodeDecodeError:
        logger.error("Agent text encoding incorrect, connection rejected", "Server")
        writer.close()
    except ValueError:
        logger.error(f"Received invalid bot ID: {message}, connection rejected", "Server")
        writer.close()

async def _receive_message(reader: asyncio.StreamReader) -> str:
    message = b""
    while True:
        try:
            message += await reader.readuntil(b";")
            break
        except asyncio.IncompleteReadError:
            return ""
        except asyncio.LimitOverrunError:
            continue

    # Strip the trailing semicolon
    return message.decode()[:-1]


async def start_server(host="localhost", port=3000) -> bool:
    """Start socket server and serve the client file over http"""
    await asyncio.start_server(_handle_new_client, host, port, start_serving=True)
    logger.info(f"Listening on {host}:{port}", "Server")

    http_server = http.server.HTTPServer(("localhost", 8080), UpdateServer)
    http_thread = threading.Thread(
        target=http_server.serve_forever,
        name="Update Server",
        daemon=True
    )
    http_thread.start()
    return True

# Basic call-and-response cli for testing robot functions
async def _cli():
    await start_server()

    while True:
        try:
            # Allow async network tasks to run while waiting for input 
            string = await asyncio.get_event_loop().run_in_executor(None, input, "Enter a command: ")

            if string == "exit":
                exit(0)

            else:
                bot_id, command = string.split(" ", 1)
                response = await send_command(int(bot_id), command)
                print(f"Response: {response}")
        except ValueError as e:
            print(e)


if __name__ == "__main__":
    asyncio.run(_cli())
