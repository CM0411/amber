"""
The journal — lose as little as possible.

The roadmap prescribes this design under N:

    "Separate the journal from the snapshot. Full snapshots are expensive,
    so you take them rarely; everything after is appended continuously to a
    journal. On startup you load the snapshot and replay the journal over
    it. Loss: seconds instead of hours."

WHAT GOES IN, AND WHAT DOES NOT
-------------------------------
Because everything derives deterministically from (seed, step number), what
was *computed* need not go in — redoing a step gives by definition the same
result. What must go in is everything that cannot be derived:

  * how far we were when it went wrong
  * what came from outside: what Cley said, what was observed, what came
    off the internet. None of that can be recomputed
  * outcomes you do not want to have to earn again, such as measurements

That is the difference between megabytes per hour and kilobytes.

THE TWO TRAPS FROM THE ROADMAP
------------------------------
1. "Linux reports your write long before anything is on disk — with 472 GB
   they buffer gigabytes." Hence forced fsyncs here. Not after every line:
   on an SSD without power-loss protection that costs more than it buys.
   But at least every `fsync_interval` seconds, and always on a clean
   shutdown. That honors the promise — loss in seconds, not hours.

2. The snapshot itself swaps atomically; see snapshot.py.

THE COUNT — one agreement, and stick to it
------------------------------------------
A snapshot with `stap=N` means: **N steps done, the next is number N.** The
snapshot holds the state after step N-1.

A journal row with `stap=k` means: **step k was executed.**

It follows that rows with k < N are inside the snapshot and rows with
k >= N are not. Wherever this file filters on step number the boundary is
`>= N`, never `> N`. Being one off silently throws away one step of work on
every restart — the kind of error that surfaces weeks later in the
measurements, not in an error message. On 8 Aug 2026 it was in, and the
test caught it.

TWO KINDS OF SILENCE
--------------------
"Announced shutdown because you leave is rest. Unannounced dropout is an
incident. She must keep those apart."

A clean shutdown writes a rest marker as its last row. If it is missing at
startup, it was an incident — a known fact instead of a hole.

English successor of logboek.py. The file format is one and the same — row
keys and kinds stay Dutch (code is English, her state is Dutch) — so both
sides read each other's journals, including the running run-3 journal.
"""

import json
import os
import time

END_KINDS = {"rust"}

# Rows that survive cleanup, however old they are.
#
# Cleanup exists for *recovery*: what the snapshot holds need not stay in
# the journal. But measurements are not recovery data — they are exactly
# the "outcomes you do not want to have to earn again" N speaks of. On
# 8 Aug 2026 they shared the file and cleanup ate them: after a 1500-step
# run one line of progress was left.
PERMANENT = {"meting", "proefwerk", "wereld_dieper", "besluit"}


class Journal:
    """A journal that is only appended to. Never rewritten."""

    def __init__(self, path, fsync_interval=1.0):
        self.path = os.path.abspath(path)
        self.fsync_interval = fsync_interval
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._f = open(self.path, "a", buffering=1)
        self._last_fsync = 0.0
        self._counter = self._last_counter()

    def _last_counter(self):
        try:
            rows, _ = read(self.path)
        except FileNotFoundError:
            return 0
        return rows[-1]["nr"] if rows else 0

    def write(self, kind, **fields):
        """Append an event.

        `kind` is the nature of the event, e.g. "stap", "waarneming" or
        "meting" — kinds are data and stay Dutch. The rest is free.
        """
        self._counter += 1
        row = {
            "nr": self._counter,
            "tijd": time.time(),
            "soort": kind,
            **fields,
        }
        self._f.write(json.dumps(row, ensure_ascii=False) + "\n")

        now = time.monotonic()
        if now - self._last_fsync >= self.fsync_interval:
            self._to_disk()
            self._last_fsync = now
        return self._counter

    def _to_disk(self):
        self._f.flush()
        os.fsync(self._f.fileno())

    def rest(self, **fields):
        """Clean shutdown. Without this marker it counts as an incident."""
        self.write("rust", **fields)
        self._to_disk()

    def clean_up(self, upto_step):
        """Shorten the journal after a snapshot has been written.

        Only call after a *successful* snapshot: rows from before
        `upto_step` are already inside it.

        Deliberately a method, not a loose function. Shortening swaps the
        file atomically, and a `Journal` still holding the old file then
        writes into an inode no longer attached to a name — the journal
        appears to work and stays empty. Only the journal itself can swap
        safely, because only the journal can reopen its own file after.
        """
        self._to_disk()
        self._f.close()

        rows, _ = read(self.path)
        # >= and not >: step `upto_step` itself has not run yet at snapshot
        # time. See "The count" above. And PERMANENT rows never leave: they
        # are not recovery data but the record itself.
        keep = [r for r in rows
                if r.get("soort") in PERMANENT
                or r.get("stap") is None or r["stap"] >= upto_step]

        temporary = self.path + ".deel"
        with open(temporary, "w") as f:
            for r in keep:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, self.path)

        folder = os.path.dirname(self.path)
        fd = os.open(folder, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

        self._f = open(self.path, "a", buffering=1)
        self._last_fsync = 0.0
        return len(rows) - len(keep)

    def close(self):
        if not self._f.closed:
            self._to_disk()
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def read(path):
    """Read a journal. Returns (rows, silence).

    A truncated last row is dropped rather than breaking the read. That is
    exactly the corruption you get when power drops mid-write, and then you
    still want every row before it.
    """
    rows = []
    with open(path) as f:
        raw = f.read().splitlines()

    for i, row in enumerate(raw):
        try:
            rows.append(json.loads(row))
        except json.JSONDecodeError:
            if i == len(raw) - 1:
                break          # truncated tail: expected, last row drops
            raise ValueError(
                f"journal {path} is corrupted at row {i + 1} — "
                f"not the last, so this is no truncated tail"
            )

    silence = "rest" if rows and rows[-1]["soort"] in END_KINDS else "incident"
    return rows, silence


def resume(folder, upto_step=None):
    """Everything you need to know at startup.

    Returns: which events happened after the snapshot, whether the shutdown
    was clean, and how long the silence lasted. What to do with those
    events is the caller's call — this knows nothing about learning.

    `upto_step` is the step number from the snapshot. Rows from before that
    point are already inside it and are skipped. So it does not matter
    whether things broke between writing the snapshot and cleaning the
    journal: replaying twice is impossible.
    """
    path = os.path.join(folder, "logboek.jsonl")
    if not os.path.exists(path):
        return {"events": [], "silence": "empty", "gap_seconds": None,
                "last_time": None}

    rows, silence = read(path)
    if upto_step is not None:
        # >= and not >: see "The count" above. The snapshot sits before
        # step `upto_step`, so that step must still be replayed.
        rows = [r for r in rows
                if r.get("stap") is None or r["stap"] >= upto_step]

    last = None
    gap = None
    if rows or silence != "empty":
        everything, _ = read(path)
        if everything:
            last = everything[-1]["tijd"]
            gap = time.time() - last

    return {
        "events": rows,
        "silence": silence,        # "rest" = announced, "incident" = dropped out
        "gap_seconds": gap,        # time as an explicit quantity, not missing data
        "last_time": last,
    }


# Note: there is deliberately no loose clean_up(folder, upto_step). See
# Journal.clean_up — shortening swaps the file atomically, and a Journal
# still holding the old file then writes into a nameless inode. The journal
# appears to work and stays empty. That bug was caught by the test on
# 8 Aug 2026; do not let it return as a loose function.
