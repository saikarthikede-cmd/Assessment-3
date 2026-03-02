import json
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = "http://127.0.0.1:8005"


def _collect_process_output(process: subprocess.Popen) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        return "", ""
    return stdout or "", stderr or ""


def wait_for_server(
    process: subprocess.Popen,
    host: str = "127.0.0.1",
    port: int = 8005,
    timeout: int = 25,
) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if process.poll() is not None:
            stdout, stderr = _collect_process_output(process)
            raise RuntimeError(
                "Uvicorn exited before startup "
                f"(code={process.returncode}).\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def request(method: str, path: str, body: dict | None = None, token: str | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload) if payload else None
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        return exc.code, json.loads(payload) if payload else None


def run_phase3_check() -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "walletApp.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8005",
            "--log-level",
            "warning",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        if not wait_for_server(process):
            process.terminate()
            stdout, stderr = _collect_process_output(process)
            raise RuntimeError(
                "Could not start API server on port 8005 within timeout.\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        email1 = f"phase3_u1_{uuid4()}@example.com"
        email2 = f"phase3_u2_{uuid4()}@example.com"

        status_code, user1 = request("POST", "/users", {"email": email1})
        assert status_code == 200, (status_code, user1)

        status_code, user2 = request("POST", "/users", {"email": email2})
        assert status_code == 200, (status_code, user2)

        user1_id = user1["id"]
        user2_id = user2["id"]

        status_code, token1_response = request("POST", "/auth/token", {"email": email1})
        assert status_code == 200, (status_code, token1_response)

        status_code, token2_response = request("POST", "/auth/token", {"email": email2})
        assert status_code == 200, (status_code, token2_response)

        token1 = token1_response["access_token"]
        token2 = token2_response["access_token"]

        status_code, _ = request("POST", f"/wallets/{user1_id}")
        assert status_code == 401, status_code

        status_code, _ = request("POST", f"/wallets/{user1_id}", token=token1)
        assert status_code == 200, status_code

        status_code, _ = request("POST", f"/wallets/{user2_id}", token=token1)
        assert status_code == 403, status_code

        status_code, _ = request("POST", f"/wallets/{user1_id}/credit", {"amount": "100.00"}, token1)
        assert status_code == 200, status_code

        status_code, _ = request("POST", f"/wallets/{user1_id}/debit", {"amount": "40.00"}, token1)
        assert status_code == 200, status_code

        status_code, _ = request("GET", f"/wallets/{user1_id}/balance", token=token2)
        assert status_code == 403, status_code

        status_code, own_balance = request("GET", f"/wallets/{user1_id}/balance", token=token1)
        assert status_code == 200, status_code
        assert own_balance["balance"] == "60.00", own_balance

        status_code, own_ledger = request("GET", f"/wallets/{user1_id}/ledger", token=token1)
        assert status_code == 200, status_code
        assert len(own_ledger) >= 2, own_ledger

        print("PHASE3_AUTH_CHECK: PASS")
        print("no_token=401 own_access=200 cross_access=403 own_balance=60.00")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()


if __name__ == "__main__":
    run_phase3_check()
