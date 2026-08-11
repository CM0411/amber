"""
Tests the journal.

The roadmap's promise is "loss: seconds instead of hours". That is only
true if a process that dies in the middle finds exactly where it was at
startup — and knows that it fell over.

Run:  venv/bin/python kern/test-journal.py
"""

import json
import os
import shutil
import subprocess
import sys
import time

import journal

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = "/home/arch/amber-werk/tmp/journaltest"
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


def worker(mode, expect_death=False):
    r = subprocess.run([PYTHON, "worker-journal.py", mode], cwd=HERE,
                       capture_output=True, text=True)
    if expect_death:
        return r
    if r.returncode != 0:
        print(r.stderr[-1500:])
        raise SystemExit(f"worker {mode} failed")
    return json.loads(r.stdout.strip().splitlines()[-1])


shutil.rmtree(FOLDER, ignore_errors=True)

print("=" * 70)
print("Test — the journal")
print("=" * 70)
print()

# --- 1. Falling over mid-work ----------------------------------------------

print("--- Power failure: SIGKILL at step 87 ---")
r = worker("drop_dead", expect_death=True)
check("the process truly died hard",
      r.returncode == -9,
      f"exit code {r.returncode} (-9 = SIGKILL, no cleanup, no flush)")

after = worker("resume")
check("the snapshot sits at step 50", after["snapshot_at"] == 50)
check(
    "the journal fills exactly the gap between snapshot and the fall",
    after["first_after_snapshot"] == 50 and after["last_after_snapshot"] == 87,
    f"events from step {after['first_after_snapshot']} through "
    f"{after['last_after_snapshot']} — the loss is zero steps, not 37",
)
check(
    "the fall is recognised as an incident and not as rest",
    after["silence"] == "incident",
    "announcing a shutdown and dropping out are two different things",
)
check("the duration of the silence is known", after["gap_measured"],
      "time as an explicit quantity, not missing data")
check(
    "what came from outside is preserved",
    after["observations"] == ["dit is niet af te leiden uit het zaad"],
    "steps are recomputable, observations are not — those must be in "
    "there literally",
)

print()

# --- 2. Clean shutdown -----------------------------------------------------

print("--- Clean shutdown ---")
shutil.rmtree(FOLDER, ignore_errors=True)
worker("clean")
after = worker("resume")
check("a clean shutdown is recognised as rest", after["silence"] == "rest")

print()

# --- 3. Cleaning up after a snapshot ---------------------------------------

print("--- Cleaning up ---")
rows, _ = journal.read(f"{FOLDER}/logboek.jsonl")
steps = [r["stap"] for r in rows if r["soort"] == "stap"]
check(
    "rows from before the snapshot have been cleaned away",
    min(steps) == 50,
    f"lowest step in the journal is {min(steps)}, the snapshot sits at 50",
)
check("no half-written file is left behind",
      not os.path.exists(f"{FOLDER}/logboek.jsonl.deel"))

# Measurements are not recovery data and must survive the cleanup.
probe = "/home/arch/amber-werk/tmp/blijvend"
shutil.rmtree(probe, ignore_errors=True)
log = journal.Journal(f"{probe}/logboek.jsonl", fsync_interval=0)
for i in range(20):
    log.write("stap", stap=i, verlies="0x1.0p+0")
    if i % 10 == 0:
        log.write("meting", stap=i, scores={"proef": 0.5})
log.clean_up(15)
log.close()
left, _ = journal.read(f"{probe}/logboek.jsonl")
check(
    "measurements survive the cleanup, ordinary steps do not",
    len([r for r in left if r["soort"] == "meting"]) == 2
    and min(r["stap"] for r in left if r["soort"] == "stap") == 15,
    "cleaning up serves recovery; measurements are the report itself. On "
    "8 Aug 2026 the cleanup ate them and a 1500-step run had one row left",
)
shutil.rmtree(probe, ignore_errors=True)

print()

# --- 4. A truncated tail ---------------------------------------------------
# This is the corruption power loss produces: the last line half written.
# Everything before it must remain usable.

print("--- A half-written last line ---")
path = f"{FOLDER}/logboek.jsonl"
whole, _ = journal.read(path)
with open(path, "a") as f:
    f.write('{"nr": 999, "tijd": 1.0, "soo')          # truncated

damaged, silence = journal.read(path)
check(
    "the truncated tail is dropped, the rest stays readable",
    len(damaged) == len(whole),
    f"{len(damaged)} rows recovered, as many as before the damage",
)

# Damage in the middle is different: that is not a truncated tail and must
# stand out instead of silently dropping rows.
with open(path) as f:
    content = f.read().splitlines()
content[1] = "{kapot"
with open(path, "w") as f:
    f.write("\n".join(content) + "\n")
try:
    journal.read(path)
    caught = False
except ValueError as e:
    caught = "corrupted" in str(e)
check("damage in the middle is reported", caught,
      "otherwise you silently lose rows and never notice")

print()

# --- 5. The price ----------------------------------------------------------

print("--- What it costs ---")
probe = "/home/arch/amber-werk/tmp/snelheid"
shutil.rmtree(probe, ignore_errors=True)

log = journal.Journal(f"{probe}/logboek.jsonl", fsync_interval=0)
t0 = time.perf_counter()
for i in range(200):
    log.write("stap", stap=i, verlies="0x1.0p+0")
every = (time.perf_counter() - t0) / 200 * 1000
log.close()

log = journal.Journal(f"{probe}/logboek2.jsonl", fsync_interval=1.0)
t0 = time.perf_counter()
for i in range(200):
    log.write("stap", stap=i, verlies="0x1.0p+0")
sometimes = (time.perf_counter() - t0) / 200 * 1000
log.close()

size = os.path.getsize(f"{probe}/logboek.jsonl") / 200
print(f"         fsync after every line:   {every:.3f} ms per line")
print(f"         fsync every second:       {sometimes:.3f} ms per line")
print(f"         size:                     {size:.0f} bytes per line")
check("the journal is cheap enough to write every step",
      sometimes < 1.0,
      "at the default interval of 1 s; the loss is at most that second")

shutil.rmtree(probe, ignore_errors=True)
shutil.rmtree(FOLDER, ignore_errors=True)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
