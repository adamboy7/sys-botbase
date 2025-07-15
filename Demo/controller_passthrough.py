import argparse
import socket
import time
import pygame


# Visualizer configuration
WINDOW_SIZE = (400, 200)
STICK_RADIUS = 80
LEFT_CENTER = (100, 100)
RIGHT_CENTER = (300, 100)
DEADZONE_COLOR = (200, 200, 200)
REAL_COLOR = (255, 0, 0)
SIM_COLOR = (0, 0, 255)

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
    *,
    points: int = 4,
    directions: int = 8,
) -> tuple[tuple[int, int], float]:
    """Send stick updates according to the selected mode."""
    now = time.monotonic()

    if mode == "approximate":
        x, y = _approximate_axes(x_val, y_val, points, directions)
        y = -y  # Switch expects up as positive
    else:
        x = int((x_val if abs(x_val) > DEADZONE else 0) * 32767)
        y = -int((y_val if abs(y_val) > DEADZONE else 0) * 32767)

    if (x, y) != last_state and now - last_time >= STICK_INTERVAL:
        send_cmd(sock, f"setStick {name} {x} {y}")
        return (x, y), now

    return last_state, last_time


def _simulated_axes(
    x_val: float, y_val: float, mode: str, *, points: int, directions: int
) -> tuple[float, float]:
    """Compute the stick values that would be sent."""
    if mode == "approximate":
        sx, sy = _approximate_axes(x_val, y_val, points, directions)
        return sx / 32767.0, sy / 32767.0
    sx = x_val if abs(x_val) > DEADZONE else 0.0
    sy = y_val if abs(y_val) > DEADZONE else 0.0
    return sx, sy


def _approximate_axes(x_val: float, y_val: float, points: int, directions: int) -> tuple[int, int]:
    """Quantize stick position into discrete steps."""
    import math

    r = math.hypot(x_val, y_val)
    if r <= DEADZONE:
        return 0, 0

    step = 1.0 / points
    level = min(points, max(1, int(r / step + 0.5)))
    radius = level * step

    angle = math.atan2(y_val, x_val)
    dir_step = 2 * math.pi / directions
    dir_index = int((angle + math.pi) / dir_step + 0.5) % directions
    quant_angle = dir_index * dir_step - math.pi

    qx = int(radius * math.cos(quant_angle) * 32767)
    qy = int(radius * math.sin(quant_angle) * 32767)
    return qx, qy


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
        choices=["polling", "approximate"],
        default="polling",
        help="stick update mode",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=4,
        help="number of distance steps for approximate mode",
    )
    parser.add_argument(
        "--directions",
        type=int,
        default=8,
        help="direction resolution for approximate mode",
    )
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()

    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Stick Visualizer")
    clock = pygame.time.Clock()

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
                points=args.points,
                directions=args.directions,
            )
            right_state, last_right_time = handle_stick(
                sock,
                "RIGHT",
                axis[2],
                axis[3],
                right_state,
                last_right_time,
                args.mode,
                points=args.points,
                directions=args.directions,
            )
            # compute simulated positions for visualization
            sim_left = _simulated_axes(
                axis[0], axis[1], args.mode, points=args.points, directions=args.directions
            )
            sim_right = _simulated_axes(
                axis[2], axis[3], args.mode, points=args.points, directions=args.directions
            )

            screen.fill((255, 255, 255))
            for center in (LEFT_CENTER, RIGHT_CENTER):
                pygame.draw.circle(screen, (0, 0, 0), center, STICK_RADIUS, 1)
                pygame.draw.circle(screen, DEADZONE_COLOR, center, int(DEADZONE * STICK_RADIUS))

            def _to_px(center, vec):
                return (
                    int(center[0] + vec[0] * STICK_RADIUS),
                    int(center[1] + vec[1] * STICK_RADIUS),
                )

            pygame.draw.circle(screen, REAL_COLOR, _to_px(LEFT_CENTER, (axis[0], axis[1])), 5)
            pygame.draw.circle(screen, SIM_COLOR, _to_px(LEFT_CENTER, sim_left), 5)
            pygame.draw.circle(screen, REAL_COLOR, _to_px(RIGHT_CENTER, (axis[2], axis[3])), 5)
            pygame.draw.circle(screen, SIM_COLOR, _to_px(RIGHT_CENTER, sim_right), 5)

            pygame.display.flip()
            clock.tick(60)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
