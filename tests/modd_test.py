#!/usr/bin/env python3
"""Tests for apps/modd (module supervisor) - no device required.

Spawns modd against the fixture modules in tests/fixtures/modd and drives it
through its UNIX-socket NDJSON protocol.
"""
from __future__ import annotations

import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODD = ROOT / "apps" / "modd" / "modd"
FIXTURES = ROOT / "tests" / "fixtures" / "modd"

failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        failures.append(msg)


class Client:
    def __init__(self, path: pathlib.Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect(str(path))
        self.buf = b""
        self.next_id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        payload: dict = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.sock.sendall((json.dumps(payload) + "\n").encode())
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("modd closed the socket")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        reply = json.loads(line.decode())
        check(reply.get("id") == self.next_id,
              f"{method}: reply id {reply.get('id')} != {self.next_id}")
        return reply

    def close(self) -> None:
        self.sock.close()


def wait_socket(path: pathlib.Path, deadline: float = 5.0) -> bool:
    end = time.time() + deadline
    while time.time() < end:
        if path.exists():
            return True
        time.sleep(0.02)
    return False


def start_modd(tmp: pathlib.Path, modules: pathlib.Path) -> tuple[subprocess.Popen, pathlib.Path]:
    sock = tmp / "modd.sock"
    env = dict(os.environ)
    env.update({
        "MODD_INIT_MS": "400",
        "MODD_ACTION_MS": "300",
    })
    proc = subprocess.Popen(
        [str(MODD), "--modules", str(modules), "--socket", str(sock),
         "--data", str(tmp / "data")],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    check(wait_socket(sock), "modd did not create its socket")
    return proc, sock


def run() -> None:
    check(MODD.exists(), f"modd binary missing: {MODD} (run make -C apps/modd)")
    if not MODD.exists():
        return

    with tempfile.TemporaryDirectory() as raw:
        tmp = pathlib.Path(raw)
        proc, sock = start_modd(tmp, FIXTURES)
        try:
            client = Client(sock)

            status = client.call("status")
            result = status.get("result", {})
            ids = sorted(m["id"] for m in result.get("modules", []))
            check(ids == ["crash", "hang", "hook", "thermal"],
                  f"status: modules {ids} != ['crash','hang','hook','thermal']")
            check(result.get("version") == "0.1", "status: version mismatch")

            init = client.call("initialize", {"module": "thermal"})
            check(init.get("result", {}).get("ready") is True,
                  f"initialize thermal failed: {init}")
            state_file = tmp / "data" / "thermal" / "state"
            check(state_file.exists(), "thermal module did not run initialize")

            for action in ("eco", "balanced"):
                reply = client.call("action.invoke",
                                    {"module": "thermal", "action": action})
                check(reply.get("result", {}).get("ok") is True,
                      f"action {action} failed: {reply}")
            log = (tmp / "data" / "thermal" / "actions.log").read_text().split()
            check(log == ["eco", "balanced"], f"actions log {log} != ['eco','balanced']")

            unknown = client.call("action.invoke",
                                  {"module": "nope", "action": "eco"})
            check("error" in unknown, "unknown module must return an error")

            started = time.time()
            hang = client.call("initialize", {"module": "hang"})
            elapsed = time.time() - started
            check("error" in hang, f"hang module must time out: {hang}")
            check(elapsed < 3.0, f"timeout path took {elapsed:.1f}s (init budget 0.4s)")

            for _ in range(3):
                client.call("initialize", {"module": "crash"})
            status = client.call("status").get("result", {})
            crash = next(m for m in status["modules"] if m["id"] == "crash")
            check(crash["state"] == "disabled",
                  f"crash module state {crash['state']} != disabled")
            check(crash["failures"] >= 3, f"crash failures {crash['failures']} < 3")

            allow = client.call("launch.before", {"system": "md", "rom": "g0.md"})
            allow_res = allow.get("result", {})
            check(allow_res.get("allow") is True, f"launch.before allow: {allow}")
            check(allow_res.get("asked", 0) >= 1,
                  f"launch.before asked {allow_res.get('asked')} < 1")

            deny = client.call("launch.before", {"system": "md", "rom": "blocked.md"})
            check(deny.get("result", {}).get("allow") is False,
                  f"launch.before must deny blocked rom: {deny}")

            off = client.call("module.set_enabled", {"module": "hook", "enabled": 0})
            check(off.get("result", {}).get("enabled") is False, f"disable hook: {off}")
            hook = next(m for m in client.call("status")["result"]["modules"]
                        if m["id"] == "hook")
            check(hook.get("enabled") is False and hook["state"] == "stopped",
                  f"disabled hook was running or missing its saved state: {hook}")
            check("error" in client.call("initialize", {"module": "hook"}),
                  "a disabled module was initialized")
            check(client.call("launch.before", {"system": "md", "rom": "blocked.md"})
                  .get("result", {}).get("allow") is True, "disabled hook still blocks games")
            check("result" in client.call("module.describe", {"module": "hook"}),
                  "module description should be available when disabled")

            bye = client.call("shutdown")
            check(bye.get("result", {}).get("stopped") is True, f"shutdown: {bye}")
            client.close()
        finally:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                failures.append("modd did not exit after shutdown")
            if proc.returncode not in (0, None) and proc.returncode != 0:
                failures.append(f"modd exit code {proc.returncode}")
            err = proc.stderr.read().decode(errors="replace")
            check("listening on" in err, "modd did not log its listening socket")

        proc, sock = start_modd(tmp, FIXTURES)
        try:
            client = Client(sock)
            hook = next(m for m in client.call("status")["result"]["modules"]
                        if m["id"] == "hook")
            check(hook.get("enabled") is False, "module switch was lost on restart")
            on = client.call("module.set_enabled", {"module": "hook", "enabled": 1})
            check(on.get("result", {}).get("enabled") is True, f"enable hook: {on}")
            check(client.call("launch.before", {"system": "md", "rom": "blocked.md"})
                  .get("result", {}).get("allow") is False, "re-enabled hook does not run")
            client.call("shutdown")
            client.close()
        finally:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                failures.append("restarted modd did not exit")


def main() -> int:
    run()
    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS  modd: status, initialize, action.invoke, launch.before, timeout, watchdog, shutdown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
