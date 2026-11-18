#!/usr/bin/env python3
"""Host tests for DEEPoS modules (protocol level, no device).

Two layers:
  1. the module's NDJSON loop is driven directly with scripted stdin (fast,
     checks ui.update targets and the request file);
  2. modd is started over a UNIX socket against the same module directory,
     proving the supervisor handshake works with a real module.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODD = os.path.join(ROOT, "apps", "modd", "modd")
MODULES = os.path.join(ROOT, "modules")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def sysfs_fixture(base, cpu_max=1008000, governor="schedutil", gpu_max=400000000):
    tree = {
        "sys/class/thermal/thermal_zone0/type": "soc-thermal\n",
        "sys/class/thermal/thermal_zone0/temp": "48000\n",
        "sys/class/thermal/thermal_zone1/type": "gpu-thermal\n",
        "sys/class/thermal/thermal_zone1/temp": "51000\n",
        "sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq": "1008000\n",
        "sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq": f"{cpu_max}\n",
        "sys/devices/system/cpu/cpufreq/policy0/scaling_governor": governor + "\n",
        "sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/cur_freq": "400000000\n",
        "sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/max_freq": f"{gpu_max}\n",
    }
    for rel, text in tree.items():
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return base


def run_module(tmp):
    data = os.path.join(tmp, "data")
    os.makedirs(data, exist_ok=True)
    env = dict(os.environ, SYSFS_PREFIX=tmp, MODD_MODULE_DATA=data)
    script = "\n".join([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"api":3}}',
        '{"jsonrpc":"2.0","id":2,"method":"action.invoke","params":{"action":"eco"}}',
        '{"jsonrpc":"2.0","id":3,"method":"shutdown"}',
    ]) + "\n"
    proc = subprocess.run(["bash", os.path.join(MODULES, "thermal", "main.sh")],
                          input=script, capture_output=True, text=True, env=env, timeout=20)
    check("module exits 0", proc.returncode == 0, proc.stderr.strip())
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    replies = [json.loads(line) for line in lines if '"id"' in line]
    check("initialize ready", replies and replies[0].get("result", {}).get("ready") is True, str(replies[:1]))
    check("action ok", len(replies) > 1 and replies[1].get("result", {}).get("ok") is True, str(replies[1:2]))
    updates = [json.loads(line) for line in lines if "ui.update" in line]
    targets = {item["params"]["target"] for item in updates}
    check("tile updated", "tile:temps" in targets, str(sorted(targets)))
    check("rows updated", {"row:soc", "row:gpu", "row:cpu", "row:gpuclock", "row:mode"} <= targets, str(sorted(targets)))
    request = os.path.join(data, "request")
    check("request written", os.path.exists(request))
    return data


def run_root_helper(tmp, data):
    helper = os.path.join(MODULES, "thermal", "root", "thermal-apply.sh")
    profile = os.path.join(tmp, "cpu-profile")
    env = dict(os.environ, SYSFS_PREFIX=tmp, PROFILE_FILE=profile, APPLY="/bin/true")
    proc = subprocess.run(["sh", helper, data], capture_output=True, text=True, env=env, timeout=20)
    check("helper exits 0", proc.returncode == 0, proc.stderr.strip())
    check("request consumed", not os.path.exists(os.path.join(data, "request")))
    status_path = os.path.join(data, "status")
    check("status written", os.path.exists(status_path))
    if os.path.exists(status_path):
        status = json.load(open(status_path, encoding="utf-8"))
        check("status mode", status.get("mode") == "eco", str(status))
        check("status cpu", status.get("cpu_max_khz") == 1008000, str(status))
        check("status governor", status.get("governor") == "schedutil", str(status))
    check("profile file", os.path.exists(profile) and open(profile).read().strip() == "eco")


def run_modd(tmp, data):
    if not os.path.exists(MODD):
        failures.append("modd binary missing")
        return
    modules = os.path.join(tmp, "modules")
    os.makedirs(modules, exist_ok=True)
    shutil.copytree(os.path.join(MODULES, "thermal"), os.path.join(modules, "thermal"), dirs_exist_ok=True)
    for name in ("main.sh",):
        path = os.path.join(modules, "thermal", name)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    socket = os.path.join(tmp, "modd.sock")
    env = dict(os.environ, MODD_INIT_MS="2000", MODD_ACTION_MS="2000", SYSFS_PREFIX=tmp)
    proc = subprocess.Popen([MODD, "--modules", modules, "--socket", socket, "--data", data],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    try:
        import socket as sock_lib
        import time
        deadline = time.time() + 5
        client = sock_lib.socket(sock_lib.AF_UNIX, sock_lib.SOCK_STREAM)
        while time.time() < deadline:
            try:
                client.connect(socket)
                break
            except OSError:
                time.sleep(0.05)
        reader = client.makefile("rwb", buffering=0)

        def call(payload):
            reader.write((json.dumps(payload) + "\n").encode())
            return json.loads(reader.readline().decode())

        status = call({"id": 1, "method": "status"})
        check("modd sees module", isinstance(status.get("result"), dict), str(status)[:120])
        init = call({"id": 2, "method": "initialize", "params": {"module": "thermal"}})
        check("modd initialize", "result" in init and "error" not in init, str(init)[:120])
        act = call({"id": 3, "method": "action.invoke", "params": {"module": "thermal", "action": "eco"}})
        check("modd action", "result" in act and "error" not in act, str(act)[:120])
        call({"id": 4, "method": "shutdown"})
        client.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()



def run_saves_module(tmp):
    data = os.path.join(tmp, "saves-data")
    os.makedirs(data, exist_ok=True)
    with open(os.path.join(data, "status"), "w", encoding="utf-8") as handle:
        handle.write('{"ok":true,"ts":1763467200,"file":"/x.tar.gz","bytes":135,"files":3}\n')
    env = dict(os.environ, MODD_MODULE_DATA=data)
    script = "\n".join([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"api":3}}',
        '{"jsonrpc":"2.0","id":2,"method":"action.invoke","params":{"action":"backup"}}',
        '{"jsonrpc":"2.0","id":3,"method":"shutdown"}',
    ]) + "\n"
    proc = subprocess.run(["bash", os.path.join(MODULES, "saves", "main.sh")],
                          input=script, capture_output=True, text=True, env=env, timeout=20)
    check("saves module exits 0", proc.returncode == 0, proc.stderr.strip())
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    replies = [json.loads(line) for line in lines if '"id"' in line]
    check("saves initialize ready", replies and replies[0].get("result", {}).get("ready") is True, str(replies[:1]))
    check("saves action ok", len(replies) > 1 and replies[1].get("result", {}).get("ok") is True, str(replies[1:2]))
    updates = [json.loads(line) for line in lines if "ui.update" in line]
    targets = {item["params"]["target"] for item in updates}
    check("saves tile updated", "tile:saves" in targets, str(sorted(targets)))
    check("saves request written", os.path.exists(os.path.join(data, "request")))
    return data


def run_saves_helper(tmp, data):
    saves = os.path.join(tmp, "retroarch", "saves")
    states = os.path.join(tmp, "retroarch", "states")
    backup = os.path.join(tmp, "backup")
    os.makedirs(os.path.join(saves, "snes"), exist_ok=True)
    os.makedirs(os.path.join(states, "snes"), exist_ok=True)
    with open(os.path.join(saves, "snes", "game.srm"), "wb") as handle:
        handle.write(b"SRAM" * 8)
    with open(os.path.join(states, "snes", "game.state0"), "wb") as handle:
        handle.write(b"STATE" * 16)
    helper = os.path.join(MODULES, "saves", "root", "saves-backup.sh")
    env = dict(os.environ, SAVES_DIR=saves, STATES_DIR=states, BACKUP_DIR=backup, KEEP="2")
    proc = subprocess.run(["sh", helper, data], capture_output=True, text=True, env=env, timeout=30)
    check("saves helper exits 0", proc.returncode == 0, proc.stderr.strip())
    check("saves request consumed", not os.path.exists(os.path.join(data, "request")))
    status_path = os.path.join(data, "status")
    if os.path.exists(status_path):
        status = json.load(open(status_path, encoding="utf-8"))
        check("saves status ok", status.get("ok") is True, str(status))
        check("saves status files", status.get("files") == 2, str(status))
        check("saves archive exists", os.path.exists(status.get("file", "")), str(status))
    else:
        check("saves status written", False)


def run_saves_rotation(tmp, data):
    helper = os.path.join(MODULES, "saves", "root", "saves-backup.sh")
    env = dict(os.environ, SAVES_DIR=os.path.join(tmp, "retroarch", "saves"),
               STATES_DIR=os.path.join(tmp, "retroarch", "states"),
               BACKUP_DIR=os.path.join(tmp, "backup"), KEEP="2")
    import time
    for _ in range(3):
        with open(os.path.join(data, "request"), "w", encoding="utf-8") as handle:
            handle.write("backup\n")
        subprocess.run(["sh", helper, data], capture_output=True, text=True, env=env, timeout=30)
        time.sleep(1.1)
    archives = sorted(os.listdir(os.path.join(tmp, "backup")))
    check("saves rotation keeps 2", len(archives) == 2, str(archives))

def main():
    tmp = tempfile.mkdtemp(prefix="deepos-modules-")
    try:
        sysfs_fixture(tmp)
        print("module thermal: direct protocol")
        data = run_module(tmp)
        print("module thermal: root helper")
        run_root_helper(tmp, data)
        print("module thermal: through modd")
        run_modd(tmp, data)
        print("module saves: direct protocol")
        sdata = run_saves_module(tmp)
        print("module saves: root helper")
        run_saves_helper(tmp, sdata)
        print("module saves: rotation")
        run_saves_rotation(tmp, sdata)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"\nFAIL  modules: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nPASS  modules: thermal + saves protocol, root helpers, modd handshake, rotation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
