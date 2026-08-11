"""
A tiny learning loop, only to make the test real.

Runs as a separate process, so "restarting" really is a new process and
not a reused Python with warm state in memory. That difference is the
whole point: a loop that restarts inside one process proves nothing about
what happens when the server drops out at night.

  worker.py through    0 to 100 in one go
  worker.py part1      0 to 50, then write a snapshot and stop
  worker.py part2      read the snapshot, 50 to 100
"""

import determinism                        # MUST come before torch
determinism.lock(1234)

import hashlib
import json
import sys

import torch

import snapshot

END = 100
HALF = 50
FOLDER = "/home/arch/amber-werk/tmp"
PATH = f"{FOLDER}/test-snapshot.pt"

device = "cuda" if torch.cuda.is_available() else "cpu"


def build():
    """Fixed construction. After lock() the initial weights are determined."""
    determinism.begin_step(0)
    model = torch.nn.Sequential(
        torch.nn.Linear(16, 32),
        torch.nn.ReLU(),
        torch.nn.Linear(32, 4),
    ).to(device)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.05, momentum=0.9)
    return model, optimizer


def fingerprint(model):
    """One number over all weights, in fixed key order.

    Sorting is required: without a fixed order the outcome depends on
    dictionary order and you are not comparing what you think.
    """
    h = hashlib.sha256()
    for key in sorted(model.state_dict()):
        h.update(key.encode())
        h.update(model.state_dict()[key].detach().cpu().numpy().tobytes())
    return h.hexdigest()


def do_step(model, optimizer, step):
    determinism.begin_step(step)
    x = torch.randn(32, 16, device=device)
    target = torch.randn(32, 4, device=device)
    loss = ((model(x) - target) ** 2).mean()
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    # As hexadecimal, so the bits are compared and not a rounding.
    return loss.detach().cpu().item().hex()


def main():
    mode = sys.argv[1]
    model, optimizer = build()

    begin = 0
    losses = []

    if mode == "part2":
        content = snapshot.read(PATH, device=device)
        begin = snapshot.restore(content, model, optimizer, device)

    end = HALF if mode == "part1" else END
    for step in range(begin, end):
        losses.append(do_step(model, optimizer, step))

    if mode == "part1":
        snapshot.write(PATH, end, model, optimizer, determinism.state())

    print(json.dumps({
        "mode": mode,
        "from": begin,
        "to": end,
        "losses": losses,
        "fingerprint": fingerprint(model),
    }))


if __name__ == "__main__":
    main()
