import argparse
import socket
import time
import pygame

BUTTON_MAP = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "MINUS",
    5: "HOME",
    6: "PLUS",
    7: "LSTICK",
    8: "RSTICK",
    9: "L",
    10: "R",
    11: "DUP",
    12: "DDOWN",
    13: "DLEFT",
    14: "DRIGHT",
    15: "PALMA",
}

DEADZONE = 0.1
# Only update the stick positions every 50ms to avoid flooding the connection
STICK_INTERVAL = 0.05


def handle_stick(
    sock: socket.socket,
    name: str,
    x_val: float,
    y_val: float,
    last_state: tuple[int, int],
    last_time: float,
    mode: str = "polling",
) -> tuple[tuple[int, int], float]:
    """Send stick updates according to the selected mode."""
    now = time.monotonic()
    x = int((x_val if abs(x_val) > DEADZONE else 0) * 32767)
    y = int((y_val if abs(y_val) > DEADZONE else 0) * 32767)

    if mode == "polling":
        if (x, y) != last_state and now - last_time >= STICK_INTERVAL:
            send_cmd(sock, f"setStick {name} {x} {y}")
            return (x, y), now

    return last_state, last_time


def send_cmd(sock: socket.socket, cmd: str) -> None:
    """Send a command to the sys-botbase client."""
    sock.sendall((cmd + "\r\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward controller input to sys-botbase")
    parser.add_argument("host", help="IP address of the sys-botbase server")
    parser.add_argument("-p", "--port", type=int, default=6000, help="sys-botbase port")
    parser.add_argument(
        "-m",
        "--mode",
        choices=["polling"],
        default="polling",
        help="stick update mode",
    )
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        raise SystemExit("No joystick detected")

    js = pygame.joystick.Joystick(0)
    js.init()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.host, args.port))

    axis = [0.0, 0.0, 0.0, 0.0]
    hat_state = (0, 0)
    left_state = (0, 0)
    right_state = (0, 0)
    last_left_time = time.monotonic()
    last_right_time = last_left_time

    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.JOYBUTTONDOWN:
                    btn = BUTTON_MAP.get(event.button)
                    if btn:
                        send_cmd(sock, f"press {btn}")
                elif event.type == pygame.JOYBUTTONUP:
                    btn = BUTTON_MAP.get(event.button)
                    if btn:
                        send_cmd(sock, f"release {btn}")
                elif event.type == pygame.JOYHATMOTION:
                    hx, hy = event.value
                    if hat_state[0] == -1 and hx != -1:
                        send_cmd(sock, "release DLEFT")
                    if hat_state[0] == 1 and hx != 1:
                        send_cmd(sock, "release DRIGHT")
                    if hat_state[1] == 1 and hy != 1:
                        send_cmd(sock, "release DUP")
                    if hat_state[1] == -1 and hy != -1:
                        send_cmd(sock, "release DDOWN")
                    if hx == -1:
                        send_cmd(sock, "press DLEFT")
                    if hx == 1:
                        send_cmd(sock, "press DRIGHT")
                    if hy == 1:
                        send_cmd(sock, "press DUP")
                    if hy == -1:
                        send_cmd(sock, "press DDOWN")
                    hat_state = (hx, hy)
                elif event.type == pygame.JOYAXISMOTION and event.axis < 4:
                    axis[event.axis] = event.value
            # send stick updates at a limited rate
            left_state, last_left_time = handle_stick(
                sock,
                "LEFT",
                axis[0],
                axis[1],
                left_state,
                last_left_time,
                args.mode,
            )
            right_state, last_right_time = handle_stick(
                sock,
                "RIGHT",
                axis[2],
                axis[3],
                right_state,
                last_right_time,
                args.mode,
            )
            time.sleep(0.01)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
