"""
Determinism — the requirement all of Amber's later code hangs from.

Phase 1's proof point is: a hundred steps, shut down, restart, and come out
bit for bit the same. On a GPU that is not free. By default several CUDA
operations are non-deterministic; you must force it explicitly, it costs
speed, and some operations then have no permitted variant left. Building it
in afterwards is impossible: no measurement from before can be trusted.

This module is therefore not advice but a latch. It refuses to run when the
settings are wrong, instead of quietly continuing half-configured. That is
the lesson of the sound calibration of 8 Aug 2026: nvidia-smi accepted an
invalid value with a warning and exit code 0, and the wrong state was
measured for six minutes without anyone noticing.

USAGE — the order is mandatory:

    import determinism             # MUST come before torch
    determinism.lock(1234)

    for step in range(...):
        determinism.begin_step(step)
        ...

WHY begin_step() ON EVERY STEP
------------------------------
The random generator's state is never saved. Instead it is re-derived every
step from (seed, step number). That is the choice that delivers "store state
hardware-independently": a checkpoint then holds two numbers instead of a
blob of card-specific memory, and is readable on any machine. A GPU upgrade
is a move, not a fresh start.

It also enforces discipline: every source of randomness runs through one
derivation, and resuming from step N gives by definition the same stream as
running through to N.

This file is the English successor of determinisme.py; toets-migratie.py
enforces that both derive identical seeds.
"""

import os
import sys

# CUBLAS_WORKSPACE_CONFIG must be set before cuBLAS initializes, which
# happens when torch is imported. After that it has no effect and torch
# refuses determinism for matmul on the GPU.
#
# Read what was already there BEFORE setting it: the latch below must
# compare against the value that held when torch loaded. Until 11 Aug 2026
# the setdefault ran first, so the check compared against its own repair
# and never fired — a latch that does not clamp, found the day the test
# suite was translated.
_WORKSPACE = ":4096:8"
_ALREADY = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", _WORKSPACE)

# Refuse when torch was loaded without the workspace setting. During the
# migration the Dutch module may legitimately have run first — then the
# environment is already correct and importing torch again changes nothing.
if "torch" in sys.modules and _ALREADY != _WORKSPACE:
    raise RuntimeError(
        "determinism was imported after torch was already loaded.\n"
        "CUBLAS_WORKSPACE_CONFIG then has no effect anymore and determinism "
        "for matmul on the GPU is silently disabled.\n"
        "Put 'import determinism' at the top, before any import of torch."
    )

import random

import numpy as np
import torch

_MASK64 = (1 << 64) - 1
_seed = None


def _mix(x):
    """SplitMix64 — a fixed, portable mixer.

    Deliberately not hash() or anything from random: those are not
    guaranteed equal across Python versions or machines, and then the
    checkpoint is not portable while looking like it is.
    """
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return (z ^ (z >> 31)) & _MASK64


def seed_for_step(step, seed=None):
    """One step's seed, derived from (seed, step number).

    Portable and repeatable: the same two numbers give the same result on
    every machine.
    """
    base = _seed if seed is None else seed
    if base is None:
        raise RuntimeError("lock() has not been called yet")
    # Mix twice so consecutive step numbers land far apart.
    return _mix(base ^ _mix(step)) >> 1   # >> 1: safely within what torch accepts


def lock(seed):
    """Switch determinism on and verify it actually took."""
    global _seed
    _seed = int(seed)

    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    begin_step(0)
    verify()
    return state()


def begin_step(number):
    """Point every generator at this step's seed.

    Anew at every step, so that resuming from a checkpoint gives the same
    stream as running through. The global generators too, because operations
    like dropout use those rather than a generator you pass in.
    """
    s = seed_for_step(number)
    random.seed(s)
    np.random.seed(s % (2**32))          # numpy only accepts 32 bits
    torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)
    return s


def generator(number, device="cpu"):
    """A separate generator for this step, for where you want to be explicit.

    The object itself is device-bound, but the seed is not — and only the
    seed enters the checkpoint.
    """
    g = torch.Generator(device=device)
    g.manual_seed(seed_for_step(number))
    return g


def verify():
    """Refuse to continue when determinism is not actually on.

    Check back; never trust the absence of an error.
    """
    complaints = []

    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != _WORKSPACE:
        complaints.append(
            f"CUBLAS_WORKSPACE_CONFIG is "
            f"{os.environ.get('CUBLAS_WORKSPACE_CONFIG')!r}, not {_WORKSPACE!r}"
        )
    if not torch.are_deterministic_algorithms_enabled():
        complaints.append("torch.use_deterministic_algorithms is off")
    if not torch.backends.cudnn.deterministic:
        complaints.append("cudnn.deterministic is off")
    if torch.backends.cudnn.benchmark:
        complaints.append(
            "cudnn.benchmark is on — it picks a different algorithm per run"
        )
    if _seed is None:
        complaints.append("no seed has been set")

    if complaints:
        raise RuntimeError(
            "Determinism is not set up right:\n  - " + "\n  - ".join(complaints)
        )
    return True


def state():
    """What is switched on, to write unchanged into every checkpoint.

    Numbers and text only, nothing device-bound. This records under which
    settings a measurement ran — without anything in it being needed to be
    able to load the checkpoint.
    """
    return {
        "seed": _seed,
        "cublas_workspace": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "derivation": "splitmix64(seed ^ splitmix64(step)) >> 1",
    }
