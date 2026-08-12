"""
Tests the world and the exams.

The two things that weigh heaviest here:

  * **depth must really make it harder**, not merely longer. The first
    version had a "second order" rule that ignored the rule beneath it, so
    depth 5 and 8 gave nearly the same row. That is a flag draped over it,
    not stacking
  * **nothing from the world may collide with an exam** — not by number
    and not by text. At `taken.py` that turned out to be a quarter of the
    study material

Run:  venv/bin/python kern/test-world.py
"""

import contextlib
import io
import re
import sys

import exams
import tasks
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
print("Test — the world and the exams")
print("=" * 70)
print()

# --- 1. Are the answers right? ---------------------------------------------
# For rekenen and code there is an independent source: Python itself.

print("--- Are the answers right? ---")
wrong = []
for depth in range(2, 13):
    for n in range(60):
        t = world.make("rekenen", depth, n)
        if str(eval(t.problem)) != t.solution:
            wrong.append(t.problem)
check("660 expressions match what Python itself computes",
      not wrong, f"{len(wrong)} deviations" if wrong else "not a single deviation")

wrong = []
for depth in range(1, 13):
    for n in range(25):
        t = world.make("code", depth, n)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(t.problem, {})
        if out.getvalue().strip() != t.solution:
            wrong.append(t.problem)
check("300 programs really print what is noted as the answer",
      not wrong, "every program actually executed")

# The rows have no second source of truth. But the simplest layer can be
# verified: at depth 1 the difference is fixed, the ratio is fixed, or
# each number is the sum of its two predecessors (since 11 Aug 2026).
wrong = []
kinds = set()
for n in range(200):
    t = world.make("puzzel", 1, n)
    if t is None:
        continue
    row = [int(x) for x in re.findall(r"-?\d+", t.problem)] + [int(t.solution)]
    diffs = {row[i + 1] - row[i] for i in range(len(row) - 1)}
    ratios = {row[i + 1] / row[i] for i in range(len(row) - 1) if row[i]}
    prev_two = all(row[i] == row[i - 2] + row[i - 1]
                   for i in range(2, len(row)))
    if len(diffs) == 1:
        kinds.add("plus")
    elif len(ratios) == 1:
        kinds.add("maal")
    elif prev_two:
        kinds.add("beide-vorige")
    else:
        wrong.append(t.problem)
check("the simplest rows: fixed difference, fixed ratio or sum of the "
      "previous two", not wrong,
      "for the composed rows no independent source exists; those are "
      "tested below on their behaviour")
check("and all three kinds really occur",
      kinds == {"plus", "maal", "beide-vorige"},
      "grondslag puzzle 5 sat at 0% because the third kind did not exist")

print()

# --- 2. Does depth really make it harder? ----------------------------------
# A solver that knows only the simplest rule should do well shallow and
# drown deep. If it does equally well everywhere, depth is just a
# different look.

print("--- Does depth make it harder? ---")


def dumb_solver(task):
    """Knows one rule: add the last difference on once more."""
    row = [int(x) for x in re.findall(r"-?\d+", task.problem)]
    if len(row) < 2:
        return None
    return row[-1] + (row[-1] - row[-2])


scores = []
for depth in (1, 2, 3, 4, 5):
    probe = [t for t in (world.make("puzzel", depth, n) for n in range(300)) if t][:200]
    good = sum(1 for t in probe if t.check(dumb_solver(t)))
    scores.append(good / len(probe))
    print(f"         depth {depth:>2}: dumb solver scores {good / 2:>5.0f}%")
check("the dumb rule works shallow and drowns deeper",
      scores[0] > 0.3 and max(scores[2:]) < 0.15,
      "so depth really asks something different and is not just a "
      "different look — this was the mistake in the first version")

lengths = [sum(len(world.make("rekenen", d, n).problem) for n in range(50)) / 50
           for d in (1, 4, 8, 12)]
check("the expressions grow longer with depth",
      lengths == sorted(lengths),
      "on average " + ", ".join(f"{x:.0f}" for x in lengths) + " characters")


# Every step in a working must be a true operation, and the last must
# produce the answer. The first version glued the answer on loosely:
#   ... ; 797 - 397 = 400 ; 797 + 800 = 1597
# That 800 came from nowhere. So she learned a method that does not
# come out.
import re as _re                                                    # noqa: E402


def _steps_hold(task):
    for step in task.working.split(" ; "):
        found = _re.fullmatch(r"(-?\d+) ([-+*:]) (-?\d+) = (-?\d+)", step.strip())
        if not found:
            continue                    # descriptive line, not an operation
        a, op, b, out = int(found[1]), found[2], int(found[3]), int(found[4])
        real = (a + b if op == "+" else a - b if op == "-"
                else a * b if op == "*" else (a // b if b else None))
        if real != out:
            return False
    return True


for family in world.FAMILIES:
    piece = [t for t in (world.make(family, d, n)
                         for d in range(1, 6) for n in range(120)) if t]
    wrong = [t for t in piece if not _steps_hold(t)]
    off = [t for t in piece if not t.check(t.working)]
    check(f"every step in a {family} working is a true operation",
          not wrong, f"{len(piece)} workings recomputed")
    check(f"and the {family} working lands on the answer",
          not off,
          "the first version glued the puzzle answer on loosely — the "
          "method did not come out" if family == "puzzel" else "")

print()

# --- 3. Does it stay manageable? -------------------------------------------

print("--- Does it stay manageable? ---")
longest_answer = 0
for family in world.FAMILIES:
    for depth in range(1, 13):
        for n in range(100):
            task = world.make(family, depth, n)
            if task:
                longest_answer = max(longest_answer, len(task.solution))
check("the answers stay short enough to be meaningful",
      longest_answer <= 16,
      f"longest answer {longest_answer} characters — in the first version "
      f"that was sixteen at depth 8, and then you measure copying")

degenerate = [t.problem for d in range(1, 13) for n in range(100)
              if (t := world.make("code", d, n))]
check("no pointless pieces stand in the programs",
      not any(re.search(r"\((\w+) [-] \1\)", p) for p in degenerate),
      "no (a - a) and no (14 - 14): that makes a problem longer without "
      "making it harder")

series = world.learning_tasks("code", 11, 40)
check("what does not fit the window is skipped",
      all(world.fits(t) for t in series) and len(series) == 40,
      f"at depth 11 far from everything fits; learning_tasks searches on "
      f"until {len(series)} usable ones are found")

print()

# --- 4. Does the world run out? --------------------------------------------

print("--- Does the world run out? ---")
for family in world.FAMILIES:
    row = []
    for depth in (1, 3, 6, 12):
        unique = len({t.problem for n in range(2000) if (t := world.make(family, depth, n))})
        row.append(f"d{depth}:{unique:>5}")
    print(f"         {family:8} " + "  ".join(row))
check(
    "from depth 3 nearly every number gives a different problem",
    all(len({t.problem for n in range(2000) if (t := world.make(f, 3, n))}) > 1500
        for f in world.FAMILIES),
    "the space grows exponentially with depth instead of linearly with "
    "what is typed",
)

print()

# --- 5. Reproducible -------------------------------------------------------

print("--- Reproducible ---")
check("the same three arguments give the same task",
      world.make("rekenen", 7, 123) == world.make("rekenen", 7, 123))
check("the world stands apart from taken.py",
      world.make("rekenen", 3, 5000).problem
      != tasks.make("rekenen", 3, 5000).problem,
      "its own seed, so the world and the exams are two separate things")

print()

# --- 6. The exams ----------------------------------------------------------

print("--- The exams ---")
all_ = exams.all_exams()
needed = {"grondslag", "gemengd", "diepte", "diepte2", "ladder"}
check(
    "not a single exam has vanished",
    needed <= set(all_),
    ", ".join(f"{n} ({len(p)})" for n, p in sorted(all_.items()))
    + " — more is allowed, fewer never: an exam does not vanish, not even "
      "when it is superseded",
)

# diepte was minted before the notation correction and still stands. As it
# should: an exam never vanishes, not even when superseded.
def _per_family(exam_name, family):
    return {p["opgave"] for p in all_[exam_name].problems
            if p["familie"] == family}


check(
    "the superseded exam still stands, beside its successor",
    not (_per_family("diepte", "rekenen") & _per_family("diepte2", "rekenen"))
    and not (_per_family("diepte", "code") & _per_family("diepte2", "code")),
    "for rekenen and code, diepte shares not one problem with diepte2 — "
    "there the notation changed, and precisely that made diepte "
    "unreachable",
)
check(
    "and where the notation did not change, they are equal",
    _per_family("diepte", "puzzel") == _per_family("diepte2", "puzzel"),
    "the rows write unchanged, so those problems are identical — showing "
    "the difference really sat in the notation and not in something else",
)

try:
    exams.freeze("grondslag", "x", [])
    refused = False
except FileExistsError:
    refused = True
check("an existing exam is not overwritten", refused,
      "an exam that can be silently overwritten is not a benchmark")

mixed = all_["gemengd"].as_tasks()
kinds = {(t.family, t.grade) for t in mixed}
check("the mixed exam has all kinds on one sheet",
      len(kinds) == len(tasks.FAMILIES) * len(tasks.GRADES),
      f"{len(kinds)} different kinds on one sheet — this was missing, and "
      f"it also tests whether she sees which kind is in front of her")
consecutive = sum(1 for a, b in zip(mixed, mixed[1:])
                  if a.family == b.family)
check("and they really are mixed, not grouped",
      consecutive < len(mixed) * 0.5,
      f"{consecutive} of the {len(mixed) - 1} times the same family "
      f"follows itself; grouped it would be nearly always")

deep = all_["diepte"].as_tasks()
check("the depth exam tests material that does not exist in taken.py",
      {t.grade for t in deep} == {3, 6, 9}
      and max(t.grade for t in deep) > max(tasks.GRADES),
      f"depths {sorted({t.grade for t in deep})}, while taken.py stops at "
      f"grade {max(tasks.GRADES)}")

print()

# --- 7. The lock -----------------------------------------------------------

print("--- The lock ---")
lock = exams.material()
check("the lock holds the problems of all the exams",
      len(lock) > 1500,
      f"{len(lock)} different problems that must never be learned")

for exam in all_.values():
    missing = [p["opgave"] for p in exam.problems if p["opgave"] not in lock]
    if missing:
        break
check("not a single problem is missing from the lock", not missing)

# And the proof of the pudding: study material must never yield an exam
# problem.
contaminated = []
for family in world.FAMILIES:
    for depth in (3, 6, 9):
        if depth > world.max_depth(family):
            continue          # no usable material exists there
        # The run-4 room (768 - 112): at puzzle depth 6 the conservative
        # default of 400 fits so little that 200 clean tasks do not exist
        # within the search bound — the fence at 6 presumes the window
        # that opened it.
        for t in world.learning_tasks(family, depth, 200, exclude=lock,
                                      room=768 - 112):
            if t.problem in lock:
                contaminated.append(t.problem)
check("study material never yields an exam problem", not contaminated,
      "1800 tasks checked against all the exams")

# Counter-proof: without the lock it must be able to collide, or the above
# proves nothing.
# (Revised 10 Aug 2026: the old counter-proof leaned on the coincidence
# that number 900,000 gave the same texts as the minted exam; any growth
# of the world broke that. Now the collision itself is laid out.)
known = world.make("rekenen", 3, 700_000)
with_latch = world.learning_tasks("rekenen", 3, 40, start=700_000,
                                  exclude={known.problem})
without_latch = world.learning_tasks("rekenen", 3, 40, start=700_000)
check("without the lock it would go wrong",
      known.problem in {t.problem for t in without_latch}
      and known.problem not in {t.problem for t in with_latch},
      "the same stream, with the latch it misses exactly the prepared "
      "problem")
check("and the lock itself is well filled", len(lock) >= 1700,
      f"{len(lock)} exam problems behind the latch")

# --- the language of the grondslag: endings and lengths (10 Aug 2026) ------

endings = {"alsdan": 0, "reken_negatief": 0, "gewoon": 0}
for n in range(2000, 2600):
    t = world.make("code", 3, n)
    if t is None:
        continue
    if "if " in t.problem:
        endings["alsdan"] += 1
    elif int(t.solution) < 0:
        endings["reken_negatief"] += 1
    else:
        endings["gewoon"] += 1
    if not t.check(t.working):
        endings = None
        break
check("code knows if/else, and the working lands on the answer",
      endings is not None and endings["alsdan"] > 50,
      "material that never occurs in the world she can only unlearn")
check("code knows negative outcomes, and marking accepts them",
      endings is not None and endings["reken_negatief"] > 20)

lengths = set()
for n in range(2000, 2400):
    t = world.make("puzzel", 2, n)
    if t is not None:
        lengths.add(t.problem.count(","))
check("puzzle rows vary in length (5, 6 and 7 shown)",
      lengths == {5, 6, 7},
      "with always six she learns the rhythm instead of the stopping point")

# The three exam forms of code (loop, list, def) exist and fit their
# writing space — the bug of 10 Aug (working larger than the room) must
# not come back.
from learning import room_for as _rf
forms_seen = set()
forms_fit = True
for d in (3, 4, 5, 6, 8):
    for n in range(3000, 3500):
        t = world.make("code", d, n)
        if t is None:
            continue
        if "def f" in t.problem:
            kind = "def"
        elif "getallen" in t.problem:
            kind = "lijst"
        elif "totaal" in t.problem and "range" in t.problem:
            kind = "lus"
        else:
            continue
        forms_seen.add(kind)
        # Every form must fit the window of its own era: through ten
        # def-rounds is run-4 material (768); the exam-size defs above
        # that belong to 1024 and are filtered by fits() until then.
        rounds = 0
        if kind == "def":
            m = re.search(r"range\(1, (\d+)\)", t.problem)
            rounds = int(m.group(1)) - 1 if m else 0
        era = 1024 if (kind == "def" and rounds > 10) else 768
        if not t.check(t.working) or len(t.working) > _rf(d, "code", era):
            forms_fit = False
check("the three exam forms of code exist in the world",
      forms_seen == {"lus", "lijst", "def"})
check("and every working fits its writing space", forms_fit)

# The exam-size def (up to fifteen rounds) exists for the 1024 era and
# fits its writing space there; at 768 `fits()` keeps it out of her
# batches, so minting it today is harmless (12 Aug 2026).
big_def = correct = 0
for n in range(6000, 6800):
    t = world.make("code", 8, n)
    if t is None or "def f" not in t.problem:
        continue
    import re as _re2
    m = _re2.search(r"range\(1, (\d+)\)", t.problem)
    if m and int(m.group(1)) >= 13:
        big_def += 1
        if t.check(t.working) and len(t.working) <= _rf(8, "code", 1024):
            correct += 1
check("exam-size defs (13+ rounds) exist and fit window 1024",
      big_def > 0 and correct == big_def,
      f"{big_def} large defs sampled, all correct and fitting")

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
