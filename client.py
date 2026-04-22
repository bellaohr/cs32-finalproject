import socket

HOST = "127.0.0.1"
PORT = 65434


def run_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        buffer = ""

        while True:
            chunk = s.recv(4096)
            if not chunk:
                # Server closed the connection – game over
                break

            buffer += chunk.decode()

            # Process all complete lines in the buffer
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)

                if line.startswith("INPUT:"):
                    # Server wants input – print the prompt and read from stdin
                    prompt = line[len("INPUT:"):]
                    user_input = input(prompt)
                    s.sendall((user_input + "\n").encode())
                else:
                    # Plain display line
                    print(line)


if __name__ == "__main__":
    run_client()
