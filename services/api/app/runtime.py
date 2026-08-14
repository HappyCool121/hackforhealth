from __future__ import annotations

import signal
import subprocess
import sys
import time

from .config import get_settings


def migrate() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


def commands() -> list[list[str]]:
    port = str(get_settings().port)
    return [
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
        [sys.executable, "-m", "app.worker"],
    ]


def stop(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 10
    for process in processes:
        remaining = max(0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run() -> int:
    migrate()
    processes: list[subprocess.Popen[bytes]] = []
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        processes = [subprocess.Popen(command) for command in commands()]
        while not stopping:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    return return_code or 1
            time.sleep(0.5)
        return 0
    finally:
        stop(processes)


if __name__ == "__main__":
    raise SystemExit(run())
