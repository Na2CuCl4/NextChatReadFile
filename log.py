import threading
from datetime import datetime

lock = threading.Lock()


def log(status_code: int, info: str, ip: str):
    # Convert IPv4-mapped IPv6 address to IPv4 address
    if ip.startswith("::ffff:"):
        ip = ip[7:]

    with lock:
        with open("server.log", "a") as f:
            f.write(f"[{datetime.now()} IP={ip} {status_code}] {info}\n")
