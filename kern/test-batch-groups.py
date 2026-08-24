"""
Tests the length-grouped learning step (24 Aug 2026).

Until then the whole batch was one rectangle padded to its longest row;
with replay from her whole memory that longest was ~1000 characters while
the average row was ~285, and attention pays length squared. Since 24 Aug
the rows are sorted by length and cut into groups that each pad to their
own longest, under the same memory budget (rows x longest^2).

Enforced here:
  * the grouping respects the budget and loses no row
  * one learning step gives the same weights as the one-rectangle version
    (mathematically equal; numerically equal up to float rounding)
  * the measured loss is the same
  * the same step twice is bit for bit the same (repeatable)
  * the groups carry far fewer padded tokens than the one rectangle
Run:  venv/bin/python kern/test-batch-groups.py
"""
import determinism                         # MUST come before torch
determinism.lock(2468)
import copy
import torch
import torch.nn.functional as F
import learning
import network
import parallel
import tokens
import world

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
print("Test — batch groups")
print("=" * 70)
print()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def small_learner():
    core = network.Core(layers=2, width=64, heads=4, window=1024)
    return learning.Learner(core=core, device=DEVICE, batch_size=16,
                            replay_share=0.0, bf16=False)


def mixed_material():
    """Rows of very different lengths, like a real batch with replay."""
    rows = []
    for family, depth, n in (("rekenen", 1, 6), ("tekst", 1, 4),
                             ("logica", 10, 3), ("volgorde", 15, 3)):
        rows += world.learning_tasks(family, depth, n, start=777,
                                     room=1024 - 112)
    picker_order = [5, 0, 13, 9, 2, 15, 7, 11, 1, 14, 4, 8, 12, 3, 10, 6]
    return [rows[i] for i in picker_order]


def step_flat(learner, chunk):
    """The step as it was until 24 Aug 2026: one rectangle, chunks cut from
    it after padding. Kept here as the reference the new step must equal."""
    learner.core.train()
    codes, mask = learner._make_batch(chunk)
    n, length = codes.shape
    chunk_size = max(1, min(n, learning._CHUNK_BUDGET // max(1, length * length)))
    learner.optimizer.zero_grad(set_to_none=True)
    total_counts = int(mask[:, 1:].sum())
    total_loss = 0.0
    for i in range(0, n, chunk_size):
        c = codes[i:i + chunk_size]
        m = mask[i:i + chunk_size]
        scores = learner._compute_core(c)
        predicted = scores[:, :-1].reshape(-1, tokens.VOCAB)
        target = c[:, 1:].reshape(-1)
        counts = m[:, 1:].reshape(-1)
        summed = F.cross_entropy(predicted[counts], target[counts],
                                 reduction="sum")
        (summed / max(1, total_counts)).backward()
        total_loss += float(summed.item())
    torch.nn.utils.clip_grad_norm_(learner.core.parameters(), 1.0)
    learner.optimizer.step()
    learner.optimizer.zero_grad(set_to_none=True)
    learner.steps += 1
    return total_loss / max(1, total_counts), n * length


def weights(learner):
    return [p.detach().clone() for p in learner.core.parameters()]


def max_diff(a, b):
    return max(float((x - y).abs().max()) for x, y in zip(a, b))


material = mixed_material()
lengths = sorted(len(tokens.task_to_sequence(t)[0]) for t in material)
print(f"rows: {len(material)}, lengths {lengths[0]}..{lengths[-1]}")

# --- 1. The grouping itself --------------------------------------------------
print("--- Grouping ---")
L = small_learner()
groups, total_counts = L._make_groups(material)
rows = sum(len(c) for c, _ in groups)
check("no row is lost", rows == len(material), f"{rows} of {len(material)}")
budget_ok = all(len(c) * c.shape[1] * c.shape[1] <= learning._CHUNK_BUDGET
                or len(c) == 1 for c, _ in groups)
check("every group stays under the budget (rows x longest^2)", budget_ok)
longest = [c.shape[1] for c, _ in groups]
check("groups go from long to short", longest == sorted(longest, reverse=True),
      f"longest per group: {longest}")
flat_tokens = len(material) * lengths[-1]
group_tokens = sum(c.numel() for c, _ in groups)
check("far fewer padded tokens than one rectangle",
      group_tokens < 0.6 * flat_tokens,
      f"{group_tokens} tokens in groups vs {flat_tokens} in one rectangle "
      f"({group_tokens / flat_tokens:.0%})")
real = sum(len(tokens.task_to_sequence(t)[0]) for t in material)
check("the counted positions are those of the whole batch",
      total_counts == sum(sum(tokens.task_to_sequence(t)[1][1:]) for t in material))
print()

# --- 2. Same step as the one-rectangle version ------------------------------
print("--- Same learning step ---")
determinism.begin_step(1)
A = small_learner()
determinism.begin_step(1)
B = small_learner()
check("the two learners start identical", max_diff(weights(A), weights(B)) == 0)

determinism.begin_step(2)
loss_flat, _ = step_flat(A, material)
determinism.begin_step(2)
loss_groups = B._step(material)
check("the measured loss is the same",
      abs(loss_flat - loss_groups) < 1e-5,
      f"one rectangle {loss_flat:.6f}, groups {loss_groups:.6f}")
d = max_diff(weights(A), weights(B))
check("the weights after one step are the same (up to float rounding)",
      d < 1e-5, f"largest difference {d:.3g}")

for s in range(3, 8):
    determinism.begin_step(s)
    step_flat(A, material)
    determinism.begin_step(s)
    B._step(material)
d5 = max_diff(weights(A), weights(B))
check("and after five more steps they have not drifted apart",
      d5 < 1e-4, f"largest difference {d5:.3g}")
print()

# --- 3. Repeatable ------------------------------------------------------------
print("--- Repeatable ---")
determinism.begin_step(1)
C = small_learner()
determinism.begin_step(1)
D = small_learner()
for s in range(2, 6):
    determinism.begin_step(s)
    C._step(material)
    determinism.begin_step(s)
    D._step(material)
check("the same grouped step twice is bit for bit the same",
      max_diff(weights(C), weights(D)) == 0)
print()

print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
raise SystemExit(1 if failed else 0)
