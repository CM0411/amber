"""
Worker for the journal test.

Mimics what happens at night: keep working, a snapshot every so often, and
then either shut down cleanly or drop dead in the middle.

  worker-journal.py drop_dead    to step 87, then SIGKILL on itself
  worker-journal.py clean        to step 87, then a clean shutdown
  worker-journal.py resume       start up and report what was found

SIGKILL on your own process id is the most honest model of power loss a
test can get: no cleanup, no flush, no handler that makes anything of it.
And it is exactly timed, so the test is repeatable.
"""

import determinism                        # MUST come before torch
determinism.lock(1234)

import json
import os
import signal
import sys

import torch

import journal
import snapshot

FOLDER = "/home/arch/amber-werk/tmp/journaltest"
SNAPSHOT = f"{FOLDER}/momentopname.pt"
SNAPSHOT_AT = 50         # a full snapshot too often is too expensive
DROP_AT = 87
END = 120


def build():
    determinism.begin_step(0)
    model = torch.nn.Linear(8, 4)
    return model, torch.optim.SGD(model.parameters(), lr=0.1)


def main():
    mode = sys.argv[1]
    os.makedirs(FOLDER, exist_ok=True)
    model, optimizer = build()

    if mode == "resume":
        step = 0
        if os.path.exists(SNAPSHOT):
            content = snapshot.read(SNAPSHOT)
            step = snapshot.restore(content, model, optimizer)
        state = journal.resume(FOLDER, upto_step=step)
        print(json.dumps({
            "snapshot_at": step,
            "events_after_snapshot": len(state["events"]),
            "first_after_snapshot": (state["events"][0]["stap"]
                                     if state["events"] else None),
            "last_after_snapshot": (state["events"][-1].get("stap")
                                    if state["events"] else None),
            "silence": state["silence"],
            "gap_measured": state["gap_seconds"] is not None,
            "observations": [e["tekst"] for e in state["events"]
                             if e["soort"] == "waarneming"],
        }))
        return

    # fsync after every line: makes the test repeatable instead of
    # dependent on where the interval happened to fall.
    log = journal.Journal(f"{FOLDER}/logboek.jsonl", fsync_interval=0)

    for step in range(END):
        determinism.begin_step(step)
        x = torch.randn(4, 8)
        loss = model(x).pow(2).mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        log.write("stap", stap=step, verlies=loss.item().hex())

        # Something that came from outside and so cannot be recomputed
        # from the seed.
        if step == 60:
            log.write("waarneming", stap=step, bron="cley",
                      tekst="dit is niet af te leiden uit het zaad")

        if step + 1 == SNAPSHOT_AT:
            snapshot.write(SNAPSHOT, step + 1, model, optimizer,
                           determinism.state())
            # Clean up only after a successful snapshot. If it breaks in
            # between, resume() filters on step number and nothing can
            # replay twice.
            log.clean_up(step + 1)

        if mode == "drop_dead" and step == DROP_AT:
            log._to_disk()
            os.kill(os.getpid(), signal.SIGKILL)     # power off

    if mode == "clean":
        log.rest(stap=END - 1, reden="Cley gaat weg")
        log.close()
        print(json.dumps({"mode": "clean", "to": END}))


if __name__ == "__main__":
    main()
