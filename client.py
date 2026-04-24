# import the socket module for network communication
import socket

# define the host address and port number to connect to
HOST = "127.0.0.1"
PORT = 65434


def run_client():
    # create a TCP socket and connect to the server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        # buffer to accumulate incoming data until we have complete lines
        buffer = ""

        # keep receiving data from the server until the connection closes
        while True:
            chunk = s.recv(4096)
            if not chunk:
                # server closed the connection – game over
                break

            # decode the incoming bytes and append them to the buffer
            buffer += chunk.decode()

            # process all complete lines in the buffer
            while "\n" in buffer:
                # split off the first complete line, leaving the rest in the buffer
                line, buffer = buffer.split("\n", 1)

                if line.startswith("INPUT:"):
                    # server wants input – print the prompt and read from stdin
                    prompt = line[len("INPUT:"):]
                    user_input = input(prompt)
                    # send the user's response back to the server
                    s.sendall((user_input + "\n").encode())
                else:
                    # plain display line – just print it
                    print(line)


# entry point: run the client when this script is executed directly
if __name__ == "__main__":
    run_client()
