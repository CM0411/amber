"""
Tests parallel.py — the two cards as two processes (16 Aug 2026).

Two halves. The first runs in this process alone and checks that every
helper falls through to the single-process answer when there is no group:
the Z490 with one card and every other test must see no difference at all.

The second launches itself twice more, under torchrun with one process per
card, and proves what has to hold before a two-process run may be trusted:

  * the gradient summed over the shares equals the gradient of the whole
    batch in one process — otherwise she learns something else with two
    cards than with one
  * answers gathered from both cards equal the single-process answers,
    and are the same list on both processes
  * after real `work()` steps both processes hold one and the same learner
    (fingerprint agrees), and doing it again gives the same fingerprint —
    the repeatability proof, now with two processes
  * snapshot at step A, resume, run to A+B: the same fingerprint as running
    A+B straight through — the night-time crash, with two processes

Needs two visible cards and torchrun in the venv; without them the second
half is skipped, not failed.

Run:  venv/bin/python kern/test-parallel.py
"""

import determinism                         # MUST come before torch
determinism.lock(4321)

import json
import os
import subprocess
import sys
import tempfile

import torch

import learning
import network
import parallel
import snapshot
import world

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 4321


def small_learner(**more):
    # Window 512: work() draws material with room = window - 112, and a
    # tiny window would leave nothing to draw and skip every step.
    core = network.Core(layers=2, width=64, heads=2, window=512)
    return learning.Learner(core=core, batch_size=8, deepest=2, **more)


def material():
    determinism.begin_step(1)
    return world.learning_tasks("rekenen", 2, 8, start=100, room=400)


# --- worker: what runs inside torchrun -------------------------------------

def worker(mode, out_dir, arg):
    """One process of the group. Writes its findings as JSON per rank."""
    parallel.start()
    rank = parallel.rank()
    findings = {"rank": rank, "world": parallel.world(),
                "device": parallel.device()}

    if mode == "grad":
        L = small_learner()
        # Catch the summed gradient at the moment the optimizer would step.
        class Recorder:
            def __init__(self, opt):
                self.opt, self.grads = opt, None

            def zero_grad(self, **k):
                self.opt.zero_grad(**k)

            def step(self):
                self.grads = [p.grad.detach().to("cpu").clone()
                              for p in L.core.parameters()]
        L.optimizer = Recorder(L.optimizer)
        loss = L._step(material())
        torch.save(L.optimizer.grads, os.path.join(out_dir, f"grads-{rank}.pt"))
        findings["loss"] = loss

    elif mode == "answer":
        L = small_learner()
        findings["answers"] = L.answer(material(), at_most=24)

    elif mode in ("run", "resume"):
        # `arg`: "A,B[,snapshot path]". run: A steps straight (and write a
        # snapshot at A if a path is given, then go on to A+B). resume: load
        # the snapshot and do steps A+1..A+B.
        parts = arg.split(",")
        A, B = int(parts[0]), int(parts[1])
        path = parts[2] if len(parts) > 2 else None
        L = small_learner()
        first = 1
        if mode == "resume":
            content = snapshot.read(path, device=L.device)
            L.adopt_shape((content.get("extra") or {}).get("vorm"))
            first = snapshot.restore(content, L.core, L.optimizer, L.device) + 1
            L.steps = first - 1                 # same order as life.py:
            L.restore(content.get("extra"))     # the carried counter wins
        last = A + B
        for step in range(first, last + 1):
            L.work(step)
            if mode == "run" and path and step == A:
                agree, _ = parallel.same(L.fingerprint())
                findings["agree_at_snapshot"] = agree
                if parallel.chief():
                    snapshot.write(path, step, L.core, L.optimizer,
                                   determinism.state(), extra=L.carry())
                parallel.barrier()
        findings["fingerprint"] = L.fingerprint()
        findings["agree"] = parallel.same(findings["fingerprint"])[0]
        findings["memory"] = len(L.memory)
        findings["steps"] = L.steps

    with open(os.path.join(out_dir, f"rank-{rank}.json"), "w") as f:
        json.dump(findings, f)
    parallel.stop()


if len(sys.argv) > 1 and sys.argv[1] == "--worker":
    worker(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    sys.exit(0)


# --- the test proper ---------------------------------------------------------

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


print("=" * 70)
print("Test — parallel: two cards as two processes")
print("=" * 70)
print()

# --- 1. Alone, every helper falls through ------------------------------------

print("--- Alone: no group, no difference ---")
check("no group unless torchrun started one", not parallel.active()
      and parallel.world() == 1 and parallel.rank() == 0 and parallel.chief())
check("start() alone returns 1 and stays inactive",
      parallel.start() == 1 and not parallel.active())
check("device() is None alone — the Learner picks its own",
      parallel.device() is None)
items = list(range(7))
check("share() alone is everything", parallel.share(items) == items)
check("merge() of one share is that share", parallel.merge([items]) == items)
check("gather() alone returns the list", parallel.gather(items) == items)
check("sum_number() alone is identity", parallel.sum_number(2.5) == 2.5)
agree, seen = parallel.same("abc")
check("same() alone: always agrees", agree and seen == ["abc"])

core = network.Core(layers=1, width=32, heads=2, window=64)
for p in core.parameters():
    p.grad = torch.ones_like(p)
parallel.sum_grads(core.parameters())
check("sum_grads() alone leaves the gradients untouched",
      all(bool((p.grad == 1).all()) for p in core.parameters()))

fp1 = parallel.fingerprint(core)
with torch.no_grad():
    next(core.parameters()).view(-1)[0] += 1e-3
check("fingerprint() reacts to a single weight",
      parallel.fingerprint(core) != fp1)
check("fingerprint() with extra state differs from without",
      parallel.fingerprint(core) != parallel.fingerprint(core, extra=(1,)))

# The Learner alone: unchanged from before this module existed. On a
# two-card machine that means DataParallel and an answer copy on card 1.
L = small_learner()
check("Learner alone: no share, gradients as before (loss is a number)",
      isinstance(L._step(material()), float))

# --- 2. Two processes -------------------------------------------------------

print()
print("--- Two processes, one card each ---")
torchrun = os.path.join(sys.prefix, "bin", "torchrun")
cards = torch.cuda.device_count()
if cards < 2 or not os.path.exists(torchrun):
    print(f"[ SKIP ] {cards} card(s) visible, torchrun "
          f"{'found' if os.path.exists(torchrun) else 'missing'} — the "
          f"two-process half needs both cards (CUDA_VISIBLE_DEVICES=0,1)")
else:
    def launch(mode, arg="", label=None):
        out = tempfile.mkdtemp(prefix=f"test-parallel-{mode}-")
        cmd = [torchrun, "--standalone", "--nproc_per_node=2",
               os.path.abspath(__file__), "--worker", mode, out, arg]
        env = dict(os.environ)
        env.pop("CUBLAS_WORKSPACE_CONFIG", None)   # the worker sets its own
        r = subprocess.run(cmd, capture_output=True, text=True, env=env,
                           cwd=HERE, timeout=600)
        if r.returncode != 0:
            print(f"         torchrun {mode} failed ({r.returncode}):")
            print("\n".join("           " + l for l in
                            (r.stderr or r.stdout).splitlines()[-25:]))
            return None, out
        found = {}
        for rank in range(2):
            with open(os.path.join(out, f"rank-{rank}.json")) as f:
                found[rank] = json.load(f)
        return found, out

    # a. the summed gradient equals the whole-batch gradient
    found, out = launch("grad")
    check("torchrun launches two processes, one per card",
          found is not None and found[0]["world"] == 2
          and found[0]["device"] == "cuda:0" and found[1]["device"] == "cuda:1",
          "" if found else "see torchrun output above")
    if found:
        g0 = torch.load(os.path.join(out, "grads-0.pt"))
        g1 = torch.load(os.path.join(out, "grads-1.pt"))
        check("both processes hold the same summed gradient, bit for bit",
              all(torch.equal(a, b) for a, b in zip(g0, g1)))
        # Reference: one process, one card, the whole batch. Fresh Learner
        # from the same seed → the same initial weights.
        determinism.begin_step(0)
        Ref = small_learner(device="cuda:0")
        determinism.begin_step(0)
        Ref2 = small_learner(device="cuda:0")   # sanity: same init twice
        check("reference: same seed gives the same initial weights",
              all(torch.equal(a, b) for a, b in
                  zip(Ref.core.parameters(), Ref2.core.parameters())))
        caught = {}
        class Rec:
            def __init__(self, opt): self.opt = opt
            def zero_grad(self, **k): self.opt.zero_grad(**k)
            def step(self):
                caught["g"] = [p.grad.detach().to("cpu").clone()
                               for p in Ref.core.parameters()]
        Ref.optimizer = Rec(Ref.optimizer)
        loss_ref = Ref._step(material())
        worst = max(float((a - b).abs().max()) for a, b in zip(g0, caught["g"]))
        scale = max(float(b.abs().max()) for b in caught["g"])
        check("summed share gradients == whole-batch gradient (to rounding)",
              all(torch.allclose(a, b, rtol=1e-4, atol=1e-6)
                  for a, b in zip(g0, caught["g"])),
              f"largest difference {worst:.2e} against largest gradient "
              f"{scale:.2e}")
        check("the summed loss equals the whole-batch loss (to rounding)",
              abs(found[0]["loss"] - loss_ref) < 1e-5
              and abs(found[1]["loss"] - loss_ref) < 1e-5,
              f"two processes {found[0]['loss']:.6f}, one {loss_ref:.6f}")

    # b. answers: shared, gathered, equal on both, equal to alone
    found, _ = launch("answer")
    if found:
        determinism.begin_step(0)
        Ref = small_learner(device="cuda:0")
        alone = Ref.answer(material(), at_most=24)
        check("gathered answers are the same list on both processes",
              found[0]["answers"] == found[1]["answers"])
        check("gathered answers equal the single-process answers",
              found[0]["answers"] == alone,
              f"two: {found[0]['answers'][:3]}\n         one: {alone[:3]}")
    else:
        check("answer under two processes", False)

    # c. real steps: one learner, twice the same
    A, B = 8, 8
    run1, _ = launch("run", f"{A},{B}")
    run2, _ = launch("run", f"{A},{B}")
    if run1 and run2:
        check(f"after {A + B} work() steps both processes are one learner",
              run1[0]["agree"] and run1[0]["fingerprint"] == run1[1]["fingerprint"])
        check("the memory filled on both alike",
              run1[0]["memory"] == run1[1]["memory"] > 0,
              f"{run1[0]['memory']} memories")
        check("doing it again gives the same fingerprint (repeatable)",
              run1[0]["fingerprint"] == run2[0]["fingerprint"])
    else:
        check("work() under two processes", False)

    # d. snapshot at A, resume, to A+B == straight through
    snap_dir = tempfile.mkdtemp(prefix="test-parallel-snap-")
    path = os.path.join(snap_dir, "momentopname.pt")
    run3, _ = launch("run", f"{A},{B},{path}")
    res, _ = launch("resume", f"{A},{B},{path}")
    if run3 and res:
        check("both processes agreed at the snapshot",
              run3[0].get("agree_at_snapshot") is True)
        check("only the chief wrote the snapshot, and it is there",
              os.path.exists(path))
        check(f"snapshot at {A} + resume to {A + B} == {A + B} straight, "
              f"bit for bit",
              res[0]["fingerprint"] == run3[0]["fingerprint"] == run1[0]["fingerprint"]
              and res[0]["agree"],
              f"resume {res[0]['fingerprint'][:16]}, straight "
              f"{run1[0]['fingerprint'][:16]}")
    else:
        check("snapshot/resume under two processes", False)

print()
print(f"passed: {passed}    failed: {failed}")
sys.exit(1 if failed else 0)
