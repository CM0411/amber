"""
Parallel — the two cards as two processes (DDP), 16 Aug 2026.

WHY NOT DataParallel
--------------------
DataParallel is one boss and one helper: every step the boss copies the
weights to the helper, scatters the batch, gathers the outputs back, and
runs the loss and the optimizer alone. Measured on 16 Aug 2026 in the
run-6 shape: 9.5 s per step on one P100, 7.05 on two — ×1.35 out of a
second card that could give ×2.

Here every card gets its own process with its own complete Learner. Both
processes walk the very same road — same picks, same tasks, same memory,
same optimizer step — and differ in exactly one thing: each computes the
gradient over its own share of the batch. The shares are added over the
bus (an all-reduce, ~60–90 MB), and from that moment both hold the same
gradient again and take the same step. Nothing is copied that does not
have to be.

WHAT THIS MODULE IS
-------------------
The thin layer between torch.distributed and the rest of the core. It
answers four questions — am I in a group, which share is mine, add these
up, do we still agree — and nothing else knows about ranks. When no group
was started (a plain `python life.py`, every test, the Z490 with one
card) every function falls through to the single-process answer, so the
same code runs unchanged with one card or with two.

HOW IT IS STARTED
-----------------
By torchrun, which launches one process per card and puts RANK,
LOCAL_RANK and WORLD_SIZE in the environment:

    venv/bin/torchrun --standalone --nproc_per_node=2 fase1/life.py

`start()` reads those and joins the group; without them it does nothing
and returns 1. It must run after `determinism.lock()` (this module imports
torch, so it cannot come first) and before the Learner is built.

WHAT MUST HOLD — and is checked, not assumed
--------------------------------------------
Both processes must stay bit for bit the same, or the sum of their
gradients is the sum of two different networks. Everything that could
diverge derives from (seed, step) and is therefore equal by construction;
what is not derived is *shared*: answers are computed in shares and
gathered, so every process sees the same list. And on every snapshot
`same()` compares a fingerprint of the whole state across the group and
the run stops if they differ — a diverged pair must never write a
snapshot as if it were one learner.

Rounding: a two-process run is not bit-identical to a one-process run
(the gradient is summed in a different order), so switching the number of
cards is a run-boundary event, like every other change of arithmetic.
Between restarts with the same number of cards it is bit for bit
repeatable — test-parallel.py proves it.
"""

import datetime
import hashlib
import os

import torch
import torch.distributed as dist

_rank = 0
_world = 1
_device = None


def start(backend=None, timeout_minutes=10):
    """Join the process group if torchrun launched us; otherwise do nothing.

    Idempotent. Returns the world size (1 when alone). With NCCL every
    process is pinned to its own card first — otherwise both land on card
    0 and NCCL refuses (or, worse, silently shares one card).

    The timeout turns a hang into a crash: if one process dies mid-step
    the other would otherwise wait in its next all-reduce for ever, and a
    hung service at night is worse than a fallen one — the fallen one gets
    restarted and resumes from the snapshot.
    """
    global _rank, _world, _device
    if dist.is_available() and dist.is_initialized():
        return _world
    world = int(os.environ.get("WORLD_SIZE", "1"))
    if world <= 1:
        return 1
    rank = int(os.environ["RANK"])
    local = int(os.environ.get("LOCAL_RANK", rank))
    if backend is None:
        backend = "nccl" if torch.cuda.is_available() else "gloo"
    if backend == "nccl":
        if torch.cuda.device_count() < world:
            raise RuntimeError(
                f"parallel: {world} processes but only "
                f"{torch.cuda.device_count()} card(s) visible — one card per "
                f"process is the whole point (check CUDA_VISIBLE_DEVICES)")
        torch.cuda.set_device(local)
        _device = f"cuda:{local}"
    else:
        _device = "cpu"
    dist.init_process_group(backend,
                            timeout=datetime.timedelta(minutes=timeout_minutes))
    _rank, _world = dist.get_rank(), dist.get_world_size()
    return _world


def stop():
    """Leave the group. Safe to call when there is none."""
    global _rank, _world, _device
    if dist.is_available() and dist.is_initialized():
        dist.destroy_process_group()
    _rank, _world, _device = 0, 1, None


def active():
    return _world > 1 and dist.is_initialized()


def rank():
    return _rank


def world():
    return _world


def chief():
    """Is this the process that writes — snapshot, journal, report, prints?

    Exactly one process writes; the other computes and stays silent.
    Everything on disk then looks like one learner, which it is.
    """
    return _rank == 0


def device():
    """The card this process is pinned to, or None outside a group."""
    return _device if active() else None


# --- sharing the work --------------------------------------------------------

def share(items):
    """My share of a batch: every `world`-th item, starting at my rank.

    Strided rather than contiguous halves so shares stay balanced for any
    length (5 items over 2 processes: 3 and 2, never 5 and 0). `merge`
    undoes it. With one process the share is everything.
    """
    if not active():
        return items
    return items[_rank::_world]


def merge(parts):
    """Put shares from all ranks back in the original order (see share)."""
    if not active():
        return parts[0] if len(parts) == 1 else [x for p in parts for x in p]
    total = sum(len(p) for p in parts)
    merged = [None] * total
    for r, part in enumerate(parts):
        merged[r::_world] = part
    return merged


def gather(mine):
    """Everyone's list, merged in original order. A collective: every
    process must call it, also with an empty share."""
    if not active():
        return list(mine)
    parts = [None] * _world
    dist.all_gather_object(parts, list(mine))
    return merge(parts)


def sum_grads(params):
    """Add the gradients over the group, in place; every process ends with
    the total. Parameters without a gradient (a share of zero rows) count
    as zero. Done as one flat buffer: one transfer instead of a hundred
    small ones. With one process this does nothing."""
    if not active():
        return
    grads = []
    for p in params:
        if p.grad is None:
            p.grad = torch.zeros_like(p)
        grads.append(p.grad)
    if not grads:
        return
    flat = torch.cat([g.reshape(-1) for g in grads])
    dist.all_reduce(flat, op=dist.ReduceOp.SUM)
    offset = 0
    for g in grads:
        n = g.numel()
        g.copy_(flat[offset:offset + n].view_as(g))
        offset += n


def sum_number(x):
    """The sum of a Python number over the group."""
    if not active():
        return x
    t = torch.tensor([float(x)], dtype=torch.float64,
                     device=_device if _device != "cpu" else "cpu")
    dist.all_reduce(t, op=dist.ReduceOp.SUM)
    return float(t.item())


def same(value):
    """Do all processes hold this value? Returns (agree, all_values).

    Compares a fingerprint (any small hashable/serialisable thing) across
    the group. A collective. Alone: always True.
    """
    if not active():
        return True, [value]
    seen = [None] * _world
    dist.all_gather_object(seen, value)
    return all(v == seen[0] for v in seen), seen


def barrier():
    if active():
        dist.barrier()


def fingerprint(core, optimizer=None, extra=None):
    """A short digest of weights, optimizer moments and whatever else must
    be equal across the group. Everything is copied to the CPU first: the
    bytes must not depend on the card. Same recipe as fase1/herhaalproef.py
    for the weights and moments, so a run's proof and its watchdog agree."""
    h = hashlib.sha256()
    for name, w in core.state_dict().items():
        h.update(name.encode())
        h.update(w.detach().to("cpu").contiguous().view(torch.uint8)
                 .numpy().tobytes())
    if optimizer is not None:
        for p in core.parameters():
            st = optimizer.state.get(p)
            if not st:
                continue
            for k in ("exp_avg", "exp_avg_sq"):
                if k in st:
                    h.update(st[k].detach().to("cpu").contiguous()
                             .view(torch.uint8).numpy().tobytes())
    if extra is not None:
        h.update(repr(extra).encode())
    return h.hexdigest()
