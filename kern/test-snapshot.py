"""
Tests the snapshot format.

The phase-1 milestone, but already at the mechanism level: a hundred
steps, interrupted by a real process death, must come out bit for bit the
same as a hundred steps in a row.

And the second demand with it: the file must be readable on a machine
without these cards. That is mimicked here by hiding the cards.

Run:  venv/bin/python kern/test-snapshot.py
"""

import determinism                        # MUST come before torch
determinism.lock(1)

import json
import os
import subprocess
import sys

import torch

import snapshot

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = "/home/arch/amber-werk/tmp"
PATH = f"{FOLDER}/test-snapshot.pt"
PYTHON = sys.executable

passed = 0
failed = 0


def check(name, good, note=""):
    global passed, failed
    if good:
        passed += 1
        print(f"[  OK  ] {name}")
    else:
        failed += 1
        print(f"[ FAIL ] {name}")
    if note:
        print(f"         {note}")


def worker(mode, hide_cards=False):
    env = dict(os.environ)
    if hide_cards:
        env["CUDA_VISIBLE_DEVICES"] = ""
    r = subprocess.run([PYTHON, "worker.py", mode], cwd=HERE,
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"worker {mode} failed")
    return json.loads(r.stdout.strip().splitlines()[-1])


os.makedirs(FOLDER, exist_ok=True)
if os.path.exists(PATH):
    os.remove(PATH)

print("=" * 70)
print("Test — snapshots")
print("=" * 70)
print()

# --- 1. Interrupting and resuming ------------------------------------------

print("--- A hundred steps, with a process death in the middle ---")
print("  (every run is its own process; 'restarting' here really restarts)")
print()

whole = worker("through")
first = worker("part1")           # 0..50, writes a snapshot, dies
second = worker("part2")          # new process, reads the snapshot, 50..100

check("the snapshot was created", os.path.exists(PATH))
check(
    "the first half matches the same steps from the whole run",
    whole["losses"][:50] == first["losses"],
)
check(
    "the second half after the process death matches bit for bit",
    whole["losses"][50:] == second["losses"],
    "this is the phase-1 milestone, at the mechanism level",
)
check(
    "the final weights are identical",
    whole["fingerprint"] == second["fingerprint"],
    f"{whole['fingerprint'][:16]}… versus {second['fingerprint'][:16]}…",
)

print()

# --- 2. Hardware-independent -----------------------------------------------

print("--- Portability ---")

content = snapshot.read(PATH, device="cpu")
check("reads onto the CPU", content["stap"] == 50)

devices = set()


def find_devices(x):
    if torch.is_tensor(x):
        devices.add(str(x.device))
    elif isinstance(x, dict):
        for v in x.values():
            find_devices(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            find_devices(v)


find_devices({k: v for k, v in content.items() if k != "machine"})
check(
    "not a single tensor in the file carries a card device",
    devices <= {"cpu"},
    f"devices found: {devices or '{}'}",
)

# The real proof: a process that cannot see the cards at all.
without = worker("part2", hide_cards=True)
check(
    "a process without visible cards can use the snapshot",
    without["from"] == 50,
    "that is how state survives a GPU upgrade: moving instead of restarting",
)

check(
    "what the file says about the machine is information only",
    "kaarten" in content["machine"] and content["determinisme"]["seed"] == 1234,
    f"cards in the file: {content['machine']['kaarten']}",
)

print()

# --- 3. Proof against interruption and corruption --------------------------

print("--- Proof against power loss ---")

check(
    "no half-written file is left behind",
    not os.path.exists(PATH + ".deel"),
    "written to .deel, fsynced, only then atomically renamed",
)

# One flipped byte must show up at read time, not weeks later in the
# measurements.
with open(PATH, "r+b") as f:
    f.seek(os.path.getsize(PATH) - 20)
    b = f.read(1)
    f.seek(os.path.getsize(PATH) - 20)
    f.write(bytes([b[0] ^ 0xFF]))

try:
    snapshot.read(PATH)
    caught = False
except Exception as e:
    caught = "corrupted" in str(e)
check("a flipped byte is caught by the checksum", caught,
      "on this machine that is no luxury: no battery on the controller, "
      "and the boot disk has no power-loss protection")

os.remove(PATH)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
