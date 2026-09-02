"""
Snapshots — state that survives a restart and a move.

Two demands from the roadmap meet here:

"Store state hardware-independently. No card-specific memory layout in
files. Otherwise every GPU upgrade is a fresh start instead of a move."

"Everything is interruptible. The server sometimes shuts down at night from
heat, and Cley can call a sleep at any moment."

And on 8 Aug 2026 a third arrived, from the hardware itself: the controller
is an H240ar without cache module and without battery. Nothing catches what
was in flight when the power dropped, and the boot disk is moreover a
consumer SSD without power-loss protection. Write safety must come from
here, not from the hardware.

How that is solved here:

  * write to a temporary file, fsync, only then rename atomically. An
    interruption leaves the old snapshot untouched — you lose at most the
    latest, never the previous one
  * the directory is fsynced too, or the rename itself can still evaporate
  * a checksum over the content, so silent corruption surfaces at read time
    instead of much later in the measurements

And hardware-independent:

  * every tensor moves to the CPU before being written
  * no generator state goes in; only (seed, step number), from which
    everything re-derives — see determinism.py
  * what it records about the machine is information only. None of it is
    needed to load the file

English successor of checkpoint.py. The file format is identical — the
stored keys stay Dutch (code is English, her state is Dutch) — so both
sides read each other's files. `restore` additionally runs the key bridge,
so a run-3 snapshot loads straight into the English core.
"""

import hashlib
import io
import os

import torch

import bridge

VERSION = 1


def _to_cpu(x):
    """Everything that is a tensor to the CPU, the rest untouched.

    Walks through lists and dicts, because an optimizer's state is nested
    and full of tensors that would otherwise carry a device number.
    """
    if torch.is_tensor(x):
        return x.detach().to("cpu").clone()
    if isinstance(x, dict):
        return {k: _to_cpu(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        converted = [_to_cpu(v) for v in x]
        return type(x)(converted) if isinstance(x, tuple) else converted
    return x


_CHILD = None        # pid of the writer child still running, if any


def reap(block=False):
    """Collect the writer child (see write, in_child). Returns True when
    no child is running (any more); False while one still writes. A child
    that failed is reported loudly here — its snapshot was not written,
    the previous one still stands."""
    global _CHILD
    if _CHILD is None:
        return True
    pid, status = os.waitpid(_CHILD, 0 if block else os.WNOHANG)
    if pid == 0:
        return False
    _CHILD = None
    if status != 0:
        print(f"LET OP: momentopname-kind {pid} eindigde met status {status} "
              f"— die momentopname is NIET geschreven", flush=True)
    return True


def write(path, step, model=None, optimizer=None, settings=None, extra=None,
          in_child=False):
    """Write a snapshot. Interruptible at any moment.

    `settings` is what determinism.state() returns — written along so it is
    later beyond doubt under which settings this state arose.

    `in_child` (1 sep 2026, the P100 sprint): the copy to the processor
    is made here, then a forked child pickles, hashes and writes while the
    caller goes on — the same bytes, two minutes of her time given back
    every 500 steps. The child never touches the card. `reap()` collects
    it; a second write while the first still runs waits for it first.
    """
    path = os.path.abspath(path)
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)

    content = {
        "versie": VERSION,
        "stap": int(step),
        "determinisme": settings,
        "model": _to_cpu(model.state_dict()) if model is not None else None,
        "optimizer": _to_cpu(optimizer.state_dict()) if optimizer is not None else None,
        # `extra` is lists and numbers by contract (replay_memory.carry:
        # "nothing device-bound"); walking her 390k rows in Python took
        # 77 s per snapshot (measured 1 sep 2026) and changed nothing.
        "extra": extra,
        # Information only. None of this is needed to be able to load.
        "machine": {
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "kaarten": [torch.cuda.get_device_name(i)
                        for i in range(torch.cuda.device_count())],
        },
    }

    if in_child:
        global _CHILD
        reap(block=True)
        pid = os.fork()
        if pid == 0:
            # the child: a stop signal for the trainer must not tear the
            # half-written snapshot; finish, then leave without cleanup
            import signal
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            code = 0
            try:
                _write_bytes(path, content)
            except BaseException as e:      # noqa: BLE001 — report, then exit
                print(f"momentopname-kind faalde: {e!r}", flush=True)
                code = 1
            os._exit(code)
        _CHILD = pid
        return
    _write_bytes(path, content)


def _write_bytes(path, content):
    folder = os.path.dirname(path)
    # To memory first, so the checksum covers the bytes before anything
    # touches the disk.
    buffer = io.BytesIO()
    torch.save(content, buffer)
    raw = buffer.getvalue()
    checksum = hashlib.sha256(raw).hexdigest()

    temporary = path + ".deel"
    with open(temporary, "wb") as f:
        f.write(len(checksum).to_bytes(2, "big"))
        f.write(checksum.encode())
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())          # the bytes are now truly on disk

    os.replace(temporary, path)       # atomic: either the old or the new

    # The rename itself must be durable too, or it can still vanish on
    # power loss while the file appears to be there.
    fd = os.open(folder, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    return {"pad": path, "bytes": len(raw), "controlegetal": checksum}


def read(path, device="cpu"):
    """Read a snapshot. Verifies the checksum and the version."""
    with open(path, "rb") as f:
        length = int.from_bytes(f.read(2), "big")
        stored = f.read(length).decode()
        raw = f.read()

    found = hashlib.sha256(raw).hexdigest()
    if found != stored:
        raise ValueError(
            f"snapshot {path} is corrupted: checksum does not match\n"
            f"  expected: {stored}\n  found: {found}"
        )

    # map_location: never restore onto the device it came from. That is
    # exactly what would rivet a snapshot to one machine.
    content = torch.load(io.BytesIO(raw), map_location=device,
                         weights_only=False)

    if content.get("versie") != VERSION:
        raise ValueError(
            f"snapshot {path} has version {content.get('versie')}, "
            f"this code expects {VERSION}"
        )
    return content


def restore(content, model=None, optimizer=None, device="cpu"):
    """Put a read snapshot back into a model and optimizer.

    Runs the key bridge on the model weights: a snapshot written under the
    Dutch attribute names loads straight into the English core, bit for bit
    — proven in toets-sleutelbrug.py. English snapshots pass unchanged.
    """
    if model is not None and content.get("model") is not None:
        model.load_state_dict(bridge.translate_state(content["model"]))
        model.to(device)
    if optimizer is not None and content.get("optimizer") is not None:
        optimizer.load_state_dict(content["optimizer"])
    return content["stap"]
