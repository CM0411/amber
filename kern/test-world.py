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
import hashlib
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


def _unwrap(problem):
    """Strip the conversational wrapper so Python can be the judge again.

    The wrapper is study clothing; underneath must sit a sum that eval
    computes to exactly the noted answer — also for spoken-word forms."""
    p = re.sub(r"^(Wat is |Hoeveel is |Reken uit: )", "", problem)
    p = p.rstrip("?")
    for word, op in (("plus", "+"), ("min", "-"), ("keer", "*")):
        p = p.replace(f" {word} ", f" {op} ")
    return p


wrong = []
for depth in range(2, 13):
    for n in range(60):
        t = world.make("rekenen", depth, n)
        if "wat is x?" in t.problem:
            continue                      # the equation brick has its own judge below
        if str(eval(_unwrap(t.problem).replace(" : ", " // "))) != t.solution:
            wrong.append(t.problem)       # the division brick writes ":" (18 Aug 2026)
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
    if t is None or t.problem.startswith(("regel: ", "controleer: ", "paren: ", "rooster")):
        continue                          # the which-rule kind (17 Aug 2026) and regelcheck (18 Aug), tested below
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
    probe = [t for t in (world.make("puzzel", depth, n) for n in range(300))
             if t and t.problem.startswith("Zet voort")][:200]   # rows only
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
            if task and family not in ("zeggen", "taal", "antwoord"):   # those answer in words
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
        for f in world.FAMILIES if f not in ("zeggen", "taal", "tellen", "antwoord")),
    "the space grows exponentially with depth instead of linearly with "
    "what is typed",
)
# zeggen and taal have a small fixed vocabulary by design (18 Aug 2026);
# their room opens up with depth — from 5 nearly every number is new
check("zeggen and taal: from depth 5 nearly every number gives a different problem",
      all(len({t.problem for n in range(2000) if (t := world.make(f, 5, n))}) > 1500
          for f in ("zeggen", "taal")))
# tellen: a third of the numbers gives no usable list (empty or too long)
# by design; the usable ones must still be plentiful
check("tellen: at depth 3 the usable numbers are nearly all different",
      len({t.problem for n in range(2000) if (t := world.make("tellen", 3, n))}) > 1200)

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
    if t is not None and not t.problem.startswith(("regel: ", "controleer: ", "paren: ", "rooster")):
        lengths.add(t.problem.count(","))
# since 15 Aug 2026 the keer-plus rows at depth 2 show two more (7-9)
check("puzzle rows vary in length (5, 6 and 7 shown; keer-plus 7-9)",
      lengths == {5, 6, 7, 8, 9},
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

# --- the compact puzzle working (13 Aug 2026) --------------------------------
# From depth 7 each layer writes its differences as one row ("verschillen:")
# instead of one equation per pair; depths 1-6 keep the wide form bit for
# bit. Without this latch someone can flip the boundary and silently change
# the shape of everything she already mastered.
wide_ok = compact_ok = True
compact_fit = compact_seen = 0
for depth in (1, 2, 3, 4, 5, 6):
    for n in range(200):
        t = world.make("puzzel", depth, n)
        if t and ("verschillen:" in t.working or "om en om: " in t.working):
            wide_ok = False
for depth in (7, 8, 9):
    for n in range(200):
        t = world.make("puzzel", depth, n)
        if t is None or t.problem.startswith(("regel: ", "controleer: ", "paren: ", "rooster")):
            continue                      # rows only; the rule kinds are tested below
        compact_seen += 1
        # Deep rows always carry at least one difference layer, so the
        # compact label must appear — and the answer must still be the
        # last number of the working (nakijk looks there).
        if "verschillen:" not in t.working:
            compact_ok = False
        if not t.working.rstrip().endswith(t.solution):
            compact_ok = False
        if len(t.problem) + len(t.to_learn()) + 3 <= 1024 - 112:
            compact_fit += 1
check("puzzle depth 1-6 keeps the wide working (no compact labels)", wide_ok)
check("puzzle depth 7-9 works compactly and ends on the answer",
      compact_ok and compact_seen > 0, f"{compact_seen} sampled")
# The world's own standard is 85% (the fence rule of 10 Aug 2026); until
# 15 Aug 2026 everything here fitted, since then the keer-plus rows at
# depth 9 run to ~1050 characters for one in ten. `fits()` filters those.
check("compact workings fit window 1024 (85% rule)",
      compact_seen > 0 and compact_fit >= 0.85 * compact_seen,
      f"{compact_fit}/{compact_seen} within 912")

# --- the keer-plus brick (15 Aug 2026) ---------------------------------------
# One in five puzzle numbers from depth 2 tries `x → 2x + b` under the usual
# layers (own seed split). The other four in five must stay bit for bit the
# world of before: this checksum was taken over them on 15 Aug 2026 before
# the brick existed (300 numbers per depth 1-10, minus the split numbers).
_h = hashlib.sha256()
_h6 = hashlib.sha256()
kp_numbers = []
regel_numbers = []
check_numbers = []
grid_numbers = []
for depth in range(1, 11):
    for n in range(300):
        seed = world._seed_of("puzzel", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.KEERPLUS_SEED))
        if depth >= world.KEERPLUS_MIN and k.integer(1, 5) == 1:
            kp_numbers.append((depth, n))
            continue
        # the regelcheck bridge stone (18 Aug 2026) takes one in four of
        # the rest, and the "which rule" split (17 Aug 2026) one in three
        # of what is left — those numbers changed on purpose; the others
        # must not
        if tasks.Picker(tasks._mix(seed ^ world.CHECK_SEED)).integer(1, 4) == 1:
            check_numbers.append((depth, n))
            continue
        # the grid puzzle (18 Aug 2026) one in four of what is left
        if tasks.Picker(tasks._mix(seed ^ world.GRID_SEED)).integer(1, 4) == 1:
            grid_numbers.append((depth, n))
            continue
        if tasks.Picker(tasks._mix(seed ^ world.REGEL_SEED)).integer(1, 3) == 1:
            regel_numbers.append((depth, n))
            continue
        t = world.make("puzzel", depth, n)
        (_h if depth <= 5 else _h6).update(
            (f"{depth}|{n}|{t.problem if t else ''}|"
             f"{t.working if t else ''}|{t.solution if t else ''}\n").encode())
# taken over exactly these numbers on 18 Aug 2026 before the bounded rows
# existed (a7d2547646bda49b was the sum over the keer-plus complement,
# 7fa9005221985a61 over the complement of keer-plus and rule,
# 5d6c2b866f2a9638 over depths 1-10 outside the three splits)
# (cbf9b57eb0d7dd85 / 678cd80eafbb2906 were the sums outside three splits,
# before the grid split took its quarter)
check("puzzle numbers depth 1-5 outside the four splits are bit for bit the "
      "world of 15 Aug 2026", _h.hexdigest()[:16] == "521237441d5c20cc",
      _h.hexdigest()[:16])
# depths 6-10 changed on purpose on 18 Aug 2026 (bounded rows, a noted
# measurement change: cbb00a89fcd2b07e was the sum before); pinned so a
# later edit cannot move them unnoticed
check("puzzle numbers depth 6-10 outside the four splits are the bounded "
      "world of 18 Aug 2026", _h6.hexdigest()[:16] == "27f96e949b85031c",
      _h6.hexdigest()[:16])
# and the bound itself: plain rows at 6-10 stay under ROW_BOUND, keer-plus
# rows (doubling by construction) are left alone, depth 5 and 11 untouched
_big = {d: 0 for d in range(5, 12)}
_rows = {d: 0 for d in range(5, 12)}
for depth in range(5, 12):
    for n in range(300):
        seed = world._seed_of("puzzel", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.KEERPLUS_SEED))
        if depth >= world.KEERPLUS_MIN and k.integer(1, 5) == 1:
            continue
        t = world.make("puzzel", depth, n)
        if t is None or not t.problem.startswith("Zet voort"):
            continue
        _rows[depth] += 1
        if world._row_top(t.problem) > world.ROW_BOUND:
            _big[depth] += 1
check("plain rows at depth 6-10 stay under ROW_BOUND (18 Aug 2026)",
      all(_big[d] == 0 and _rows[d] > 15 for d in range(6, 11)),
      ", ".join(f"d{d}: {_big[d]} of {_rows[d]} over" for d in range(6, 11)))
check("depth 5 keeps its unbounded rows (bit for bit)", _big[5] > 0)
# and the split numbers: a row that comes out ends on its answer, every
# equation holds, and the doubling shows in the working (a `: 2` ratio
# step or a `gedeeld: 2` row) for the plain brick at depth 2
kp_seen = kp_bad = kp_plain = kp_plain_ok = 0
for depth, n in kp_numbers:
    t = world.make("puzzel", depth, n)
    if t is None:
        continue
    kp_seen += 1
    if not t.working.rstrip().endswith(t.solution) or not _steps_hold(t):
        kp_bad += 1
    if depth == 2:
        kp_plain += 1
        if " : " in t.working and "= 2 ;" in t.working:
            kp_plain_ok += 1
check("keer-plus rows end on their answer with true steps",
      kp_seen > 100 and kp_bad == 0, f"{kp_seen} rows, {kp_bad} bad")
check("at depth 2 the keer-plus brick stands alone: differences, ratio 2",
      kp_plain > 0 and kp_plain_ok == kp_plain, f"{kp_plain_ok}/{kp_plain}")


# --- the conversational wrapper (13 Aug 2026) --------------------------------
# A fifth of arithmetic depth 2-8 appears as an everyday question ("Wat is
# 13 keer 8?"); spoken-word forms start their working with the bare sum.
# Outside that band, and in the other families, nothing changes shape.
wrapped = flat = 0
outside = 0
wrap_ok = True
for depth in range(1, 11):
    for n in range(400):
        t = world.make("rekenen", depth, n)
        if t is None:
            continue
        is_wrapped = ((t.problem.endswith("?") or t.problem.startswith("Reken"))
                      and "wat is x?" not in t.problem)     # equations end in "?" too
        if is_wrapped and not 2 <= depth <= 8:
            outside += 1
        if not is_wrapped:
            continue
        wrapped += 1
        # checking still reads the last number of the working
        if not t.check(t.working):
            wrap_ok = False
        # a spoken form carries its translation as the first step
        if "keer" in t.problem or "plus" in t.problem or "min" in t.problem:
            flat += 1
            head = t.working.split(" ; ")[0]
            if "=" in head or not _re.match(r"^-?\d+( [+*-] -?\d+)+$", head):
                wrap_ok = False
check("the wrapper only dresses arithmetic depth 2-8", outside == 0)
check("about a fifth is wrapped, and every working still checks out",
      wrap_ok and 0.15 < wrapped / 2800 < 0.27,
      f"{wrapped} wrapped, {flat} spoken")
check("spoken forms exist and keep their symbols in the working",
      flat > 50, f"{flat} spoken forms sampled")
other = 0
for fam in ("puzzel", "code"):
    for n in range(200):
        t = world.make(fam, 3, n)
        if t and (t.problem.startswith(("Wat is", "Hoeveel", "Reken uit"))):
            other += 1
check("puzzle and code stay unwrapped", other == 0)
wrap_fit = wrap_all = 0
for depth in range(2, 9):
    for n in range(400):
        t = world.make("rekenen", depth, n)
        if t is None or not (t.problem.endswith("?")
                             or t.problem.startswith("Reken")):
            continue
        wrap_all += 1
        if (len(t.to_learn()) <= _rf(depth, "rekenen", 768)
                and world.fits(t, 768 - 112)):
            wrap_fit += 1
check("wrapped problems fit the window and their writing space (768)",
      wrap_all > 0 and wrap_fit == wrap_all, f"{wrap_fit}/{wrap_all}")

# --- the big multiplication (14 Aug 2026) ------------------------------------
# A fifth of arithmetic depth 3-8 becomes a bare teen multiplication
# (`48 * 14`) with the split-over-tens working — the run-4 exam showed she
# guessed exactly this form, dropping the tens digit. Outside the band and
# for every untouched number: bit for bit the old world.
big = 0
big_bad = 0
for depth in range(3, 9):
    for n in range(400):
        t = world.make("rekenen", depth, n)
        if t is None:
            continue
        m = re.fullmatch(r"(\d+) \* (1[3-9])", _unwrap(t.problem))
        if not m:
            continue
        big += 1
        a, b = int(m.group(1)), int(m.group(2))
        tens, ones = a * 10, a * (b - 10)
        expected = (f"{a} * 10 = {tens} ; {a} * {b - 10} = {ones} ; "
                    f"{tens} + {ones} = {a * b}")
        if not t.working.endswith(expected) or t.solution != str(a * b):
            big_bad += 1
check("teen multiplications carry the split-over-tens working",
      big > 0 and big_bad == 0, f"{big} of 2400 sampled")
check("their share is around a fifth", 0.15 < big / 2400 < 0.27, f"{big}")
buiten = 0
for depth in (1, 2, 9, 10):
    for n in range(200):
        t = world.make("rekenen", depth, n)
        if t and re.fullmatch(r"\d+ \* 1[3-9]", _unwrap(t.problem)):
            buiten += 1
check("outside depth 3-8 no teen multiplications appear", buiten == 0)

# --- the teen multiplication with a tail (16 Aug 2026) -----------------------
# The exam's grade 4 asks `a * b ± c` with a teen factor; after run 5 she
# still guessed that product or did half the split (27 of 28 misses). One
# in five numbers at depth 4-10 now carries that form with the full
# working — applied before the bare split, so every bare teen
# multiplication stays bit for bit, and so does every untouched number.
staart = 0
staart_bad = 0
for depth in range(4, 11):
    for n in range(300):
        t = world.make("rekenen", depth, n)
        if t is None:
            continue
        m = re.fullmatch(r"(\d+) \* (1[3-9]) ([+-]) (\d+)", _unwrap(t.problem))
        if not m:
            continue
        staart += 1
        a, b, op, c = (int(m.group(1)), int(m.group(2)), m.group(3),
                       int(m.group(4)))
        tens, ones = a * 10, a * (b - 10)
        product = tens + ones
        result = product + c if op == "+" else product - c
        expected = (f"{a} * 10 = {tens} ; {a} * {b - 10} = {ones} ; "
                    f"{tens} + {ones} = {product} ; {product} {op} {c} = "
                    f"{result}")
        if (not t.working.endswith(expected) or t.solution != str(result)
                or not (2 <= a <= 40 and 1 <= c <= 99)):
            staart_bad += 1
check("teen multiplications with a tail carry the four-step working",
      staart > 0 and staart_bad == 0, f"{staart} of 2100 sampled")
# a fifth, minus the fifth the bare split takes back: about 16%
check("their share is around a sixth", 0.12 < staart / 2100 < 0.21,
      f"{staart}")
buiten = 0
for depth in (1, 2, 3, 11, 12):
    for n in range(200):
        t = world.make("rekenen", depth, n)
        if t and re.fullmatch(r"\d+ \* 1[3-9] [+-] \d+", _unwrap(t.problem)):
            buiten += 1
check("outside depth 4-10 no teen multiplications with a tail appear",
      buiten == 0)
# Every number the split does not touch must be bit for bit the world of
# before: this checksum was taken on 16 Aug 2026 before the form existed
# (300 numbers per depth 1-12, minus the split numbers).
_h = hashlib.sha256()
kc_numbers = vgl_numbers = deel_numbers = dial_numbers = 0
for depth in range(1, 13):
    for n in range(300):
        seed = world._seed_of("rekenen", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.KEERC_SEED))
        if world.KEERC_MIN <= depth <= world.KEERC_MAX and k.integer(1, 5) == 1:
            kc_numbers += 1
            continue
        # the equation brick (18 Aug 2026) takes one in four of the rest
        if (world.VGL_MIN <= depth <= world.VGL_MAX
                and tasks.Picker(tasks._mix(seed ^ world.VGL_SEED)).integer(1, 4) == 1):
            vgl_numbers += 1
            continue
        # and the division brick (18 Aug 2026) one in six of what is left
        if world._division_draws(seed, depth):
            deel_numbers += 1
            continue
        # and the dialect brick (run 8) one in five of what remains, except
        # where the big multiplication or the wrapper drew — those keep
        # their own splits, exactly as in make()
        keer = (world.KEER_MIN <= depth <= world.KEER_MAX
                and tasks.Picker(tasks._mix(seed ^ world.KEER_SEED)).integer(1, 5) == 1)
        converse = (world.CONVERSE_MIN <= depth <= world.CONVERSE_MAX
                    and tasks.Picker(tasks._mix(seed ^ world.CONVERSE_SEED)).integer(1, 5) == 1)
        if (world.DIALECT_MIN <= depth <= world.DIALECT_MAX
                and not keer and not converse
                and tasks.Picker(tasks._mix(seed ^ world.DIALECT_SEED)).integer(1, 5) == 1):
            dial_numbers += 1
            continue
        t = world.make("rekenen", depth, n)
        p = t.problem if t else ""
        w = t.working if t else ""
        s = t.solution if t else ""
        _h.update(f"{depth}|{n}|{p}|{w}|{s}\n".encode())
# 5f4eee0d46fcfe25 was the sum over the KEERC complement (16 Aug 2026);
# taken again over the complement of both splits on 18 Aug 2026 before the
# equation brick existed
# and 9e6f98e443403dfe over the complement of keerc and equation, taken on
# 18 Aug 2026 before the division brick existed
# and 4511e954860bd6b3 over that same complement while division still drew
# one in six, taken on 20 Aug 2026 before division went to one in three:
# deling had stalled at 15% because it hardly came up (run 7.3, Cleys woord)
# and b7484d5c06a9ea82 over the complement of keerc, equation and division,
# taken on 30 Aug 2026 before the dialect brick existed (run 8) — verified
# then that old and new world hash identically over the new complement
check("untouched arithmetic numbers depth 1-12 are bit for bit the old world",
      _h.hexdigest()[:16] == "bcc29d57adc3d350",
      f"{_h.hexdigest()[:16]}, {kc_numbers} + {vgl_numbers} + {deel_numbers}"
      f" + {dial_numbers} split numbers")

# --- the division brick (18 Aug 2026) ---------------------------------------
# Bare divisions with an exact outcome, worked out through the table
# ("7 * 12 = 84 ; 84 : 7 = 12"): the puzzle audit found division nowhere in
# her world while the rule puzzles asked for it.
deel_seen = deel_bad = deel_out = 0
for depth in range(1, 16):
    for n in range(300):
        t = world.make("rekenen", depth, n)
        if t is None:
            continue
        m = re.fullmatch(r"(\d+) : (\d+)", t.problem)
        if m:
            deel_seen += 1
            a, b = int(m[1]), int(m[2])
            if not (2 <= b <= 12 and a % b == 0 and a // b == int(t.solution)
                    and _steps_hold(t) and t.check(t.working)
                    and t.working.startswith(f"{b} * ")):
                deel_bad += 1
            if not world.DEEL_MIN <= depth <= world.DEEL_MAX:
                deel_out += 1
check("bare divisions: exact, divisor 2-12, worked out through the table, "
      "on the answer", deel_seen > 200 and deel_bad == 0,
      f"{deel_seen} seen, {deel_bad} wrong")
check("bare divisions live only at depth 3-12", deel_out == 0)

# --- the long loop with a compact working (14 Aug 2026) ----------------------
# The exam's loops run to twenty rounds; the wide working for those never
# fit any writing space, so she computed flawlessly and fell off the page —
# every code-3/5 miss of run 4. A quarter of code depth 5+ now carries the
# exam's full loop sizes with the compact working: terms as one row, the
# running sum as one row, the last number the answer. Short loops keep the
# wide working she already masters.
lang = 0
lang_bad = 0
lang_fit = 0
kort_bad = 0
for depth in range(1, 12):
    for n in range(300):
        t = world.make("code", depth, n)
        if t is None:
            continue
        m = re.search(r"range\(1, (\d+)\)", t.problem)
        rondes = int(m.group(1)) - 1 if m else 0
        if " ; som: " in t.working:
            lang += 1
            head, staart = t.working.rsplit(" ; som: ", 1)
            sums = [int(x) for x in staart.split()]
            terms = [int(x) for x in head.rsplit(": ", 1)[1].split()]
            goed = (depth >= 5 and rondes >= 12 and len(terms) == rondes
                    and len(sums) == rondes + 1
                    and all(sums[i + 1] - sums[i] == terms[i]
                            for i in range(rondes))
                    and str(sums[-1]) == t.solution)
            if not goed:
                lang_bad += 1
            if (world.fits(t, 1024 - 112)
                    and len(t.to_learn()) <= _rf(depth, "code", 1024)):
                lang_fit += 1
        elif rondes and ("i * 2" in t.problem or "i * i" in t.problem):
            # the wide loop she already masters: still eleven rounds at most
            if rondes > 11:
                kort_bad += 1
check("long loops (12-20 rounds) come with the compact working",
      lang > 0 and lang_bad == 0, f"{lang} sampled")
check("compact loop workings fit window 1024 and its writing space",
      lang > 0 and lang_fit == lang, f"{lang_fit}/{lang}")
check("wide 2i/i2 loops keep at most eleven rounds (unchanged shape)",
      kort_bad == 0)

# --- the stacked code forms (15 Aug 2026) ------------------------------------
# From depth 16 the code family stacks its blocks (filter in a loop, def
# over a list, loop in a loop, def calling def; three blocks from 20).
# Depths 1-15 must stay bit for bit what they were: this checksum was
# taken on 15 Aug 2026 before the stacked forms existed, over 300 numbers
# per depth. Anyone who changes it changes the shape of what she mastered.
_h = hashlib.sha256()
cd_dial = 0
for depth in range(1, 16):
    for n in range(300):
        # the dialect brick (run 8) takes one in five where the long loop
        # did not draw, exactly as in make(); the complement must stay bit
        # for bit. e6b79a906f84757f was the sum over ALL numbers, taken on
        # 15 Aug 2026 before the dialect brick existed; verified 30 Aug
        # 2026 that old and new world hash identically over the complement.
        seed = world._seed_of("code", depth, n)
        lus = (world.LUS_MIN <= depth <= world.LUS_MAX
               and tasks.Picker(tasks._mix(seed ^ world.LUS_SEED)).integer(1, 4) == 1)
        if (world.DIALECT_MIN <= depth <= world.DIALECT_MAX and not lus
                and tasks.Picker(tasks._mix(seed ^ world.DIALECT_SEED)).integer(1, 5) == 1):
            cd_dial += 1
            continue
        t = world.make("code", depth, n)
        _h.update((f"{depth}|{n}|{t.problem if t else ''}|"
                   f"{t.working if t else ''}|{t.solution if t else ''}\n")
                  .encode())
check("code depth 1-15 is bit for bit the world of 15 Aug 2026",
      _h.hexdigest()[:16] == "e5d0408003aee5c1",
      f"{_h.hexdigest()[:16]}, {cd_dial} dialect numbers skipped")

_STACK_MARKS = ("    if i > ", "for x in getallen", "    for j in ",
                "def g(x)")
_old_fence = world.MAX_DEPTH
world.MAX_DEPTH = max(world.MAX_DEPTH, 30)
stacked_seen = stacked_bad = stacked_fit = 0
forms_two, forms_three = set(), set()
three_bad = 0
for depth in range(16, 27):
    for n in range(150):
        t = world.make("code", depth, n)
        if t is None:
            stacked_bad += 1
            continue
        stacked_seen += 1
        marks = [m for m in _STACK_MARKS if m in t.problem]
        if not marks:
            stacked_bad += 1            # a plain form or a long loop leaked
        if not t.working.rstrip().endswith(t.solution):
            stacked_bad += 1
        if len(t.problem) + len(t.to_learn()) + 3 <= 1024 - 112:
            stacked_fit += 1
        # three blocks from 20: filter under the def-list, term under the
        # loop filter, filter in the inner loop, loop over g(i)
        three = (" if x > " in t.problem or "        totaal += i * 2" in t.problem
                 or "        totaal += i * i" in t.problem
                 or "        if j > " in t.problem or "totaal += g(i)" in t.problem)
        (forms_three if depth >= 20 else forms_two).add(marks[0] if marks else "?")
        if depth < 20 and three:
            three_bad += 1
        if depth >= 20 and not three:
            three_bad += 1
world.MAX_DEPTH = _old_fence
check("code depth 16-26: every problem is a stacked form, ends on its answer",
      stacked_seen > 0 and stacked_bad == 0, f"{stacked_bad} bad of {stacked_seen}")
check("all four stacked forms occur, two blocks below 20 and three from 20",
      len(forms_two) == 4 and len(forms_three) == 4 and three_bad == 0,
      f"{sorted(forms_two)} / {sorted(forms_three)} / {three_bad} wrong")
check("stacked forms fit window 1024",
      stacked_seen > 0 and stacked_fit == stacked_seen,
      f"{stacked_fit}/{stacked_seen}")
# and Python itself is the judge again: every stacked program really prints
# the noted answer, and every equation in the working holds
world.MAX_DEPTH = max(world.MAX_DEPTH, 30)
wrong_run = wrong_steps = 0
for depth in range(16, 27):
    for n in range(40):
        t = world.make("code", depth, n)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(t.problem, {})
        if out.getvalue().strip() != t.solution:
            wrong_run += 1
        if not _steps_hold(t):
            wrong_steps += 1
world.MAX_DEPTH = _old_fence
check("440 stacked programs really print what is noted as the answer",
      wrong_run == 0, f"{wrong_run} deviations")
check("every equation in a stacked working is a true operation",
      wrong_steps == 0, f"{wrong_steps} broken")

# --- code past 24: the stacked forms keep growing (17 Aug 2026) ---------------
# The caps of the stacked forms rise one notch per depth beyond 24 (see
# GROEI_VANAF): deeper must be longer, and it must still fit window 1536.
# Up to 24 nothing changes — the stapel checks above already prove that.
_old_code_fence = world.MAX_DEPTH_PER.get("code")
world.MAX_DEPTH_PER["code"] = 32
lengths_by_depth = {}
fit_past = fit_all = 0
for depth in (24, 26, 28, 30):
    ls = []
    for n in range(150):
        t = world.make("code", depth, n)
        if t is None:
            continue
        ls.append(len(t.problem) + len(t.to_learn()))
        if depth > 24:
            fit_all += 1
            if world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "code", 1536):
                fit_past += 1
    lengths_by_depth[depth] = sum(ls) / len(ls)
world.MAX_DEPTH_PER["code"] = _old_code_fence
check("code past 24 keeps getting longer with depth",
      lengths_by_depth[30] > lengths_by_depth[26] > lengths_by_depth[24],
      ", ".join(f"d{d}: {v:.0f}" for d, v in lengths_by_depth.items()))
check("code 25–30 fits window 1536 with its working (85% rule)",
      fit_all > 0 and fit_past >= 0.85 * fit_all, f"{fit_past}/{fit_all}")

# --- geheugen: the fourth family (16 Aug 2026) --------------------------------
# An answer that depends on something earlier in the sequence: a note to
# hold, distractions, then a question that reaches back. The judge here is
# an independent reader of the problem text — it follows every assignment
# in order (the last one counts) and answers the question itself. If the
# generator's answer and the reader's differ, the family lies.
print()
print("--- geheugen: the fourth family ---")
check("the world's families are the measured three, then geheugen — in that order",
      world.FAMILIES[:3] == tasks.FAMILIES and world.FAMILIES[3] == "geheugen")
check("the fence for geheugen stands at 12 or higher", world.max_depth("geheugen") >= 12)


def _read_memory(problem):
    """Follow the text like a careful reader; return the answer, or None."""
    lines = problem.split("\n")
    if len(lines) != 3:
        return None
    held = {}
    for line in lines[:2]:
        head, _, rest = line.partition(": ")
        if head not in ("onthoud", "tussendoor"):
            return None
        for piece in rest.split(" ; "):
            m = re.fullmatch(r"([a-z]) = (\d+)", piece)
            if m:
                held[m.group(1)] = int(m.group(2))
                continue
            # the memory brick (17 Aug 2026): computing updates and references
            m = re.fullmatch(r"([a-z]) = ([a-z]) ([-+*]) (\d+)", piece)
            if m:
                a, b, op, k = m.group(1), m.group(2), m.group(3), int(m.group(4))
                if b not in held:
                    return None
                held[a] = held[b] + k if op == "+" else held[b] - k if op == "-" else held[b] * k
                continue
            m = re.fullmatch(r"([a-z]) = ([a-z])", piece)
            if m:
                if m.group(2) not in held:
                    return None
                held[m.group(1)] = held[m.group(2)]
                continue
            m = re.fullmatch(r"(\d+) ([-+]) (\d+) = (-?\d+)", piece)
            if not m:
                return None                       # something we do not know
            a, op, b, out = int(m[1]), m[2], int(m[3]), int(m[4])
            if (a + b if op == "+" else a - b) != out:
                return None                       # a distraction that lies
    q = lines[2]
    m = re.fullmatch(r"wat is ([a-z])\?", q)
    if m:
        return held.get(m.group(1))
    m = re.fullmatch(r"wat is ([a-z]) ([-+]) ([a-z])\?", q)
    if m and m[1] in held and m[3] in held:
        return held[m[1]] + held[m[3]] if m[2] == "+" else held[m[1]] - held[m[3]]
    m = re.fullmatch(r"welke is groter, ([a-z]) of ([a-z])\? schrijf het getal", q)
    if m and m[1] in held and m[2] in held:
        return max(held[m[1]], held[m[2]])
    return None


mem_seen = mem_wrong = mem_unfit = 0
mem_updates = {d: 0 for d in range(1, 13)}
mem_combos = {d: 0 for d in range(1, 13)}
mem_forms = set()
mem_room_short = 0
for depth in range(1, 13):
    for n in range(300):
        t = world.make("geheugen", depth, n)
        if t is None:
            mem_wrong += 1
            continue
        mem_seen += 1
        if _read_memory(t.problem) != int(t.solution):
            mem_wrong += 1
        if not world.fits(t, 1536 - 112):
            mem_unfit += 1
        note, between, q = t.problem.split("\n")
        names = re.findall(r"([a-z]) = \d+", note)
        if any(re.search(rf"\b{c} = \d+", between) for c in names):
            mem_updates[depth] += 1
        if not q.startswith("wat is ") or " " in q[7:-1].strip():
            mem_combos[depth] += 1
        mem_forms.add(re.sub(r"[a-z]", "x", q))
        if len(t.working) + 8 > _rf(depth, "geheugen", 1536):
            mem_room_short += 1
check("3600 geheugen problems: an independent reader lands on the same answer",
      mem_seen == 3600 and mem_wrong == 0, f"{mem_wrong} disagreements")
check("all of them fit window 1536 with their working", mem_unfit == 0)
check("no held value changes on the way before depth 4",
      all(mem_updates[d] == 0 for d in (1, 2, 3)))
check("from depth 4 held values do change on the way — the last one counts",
      all(mem_updates[d] > 60 for d in range(4, 13)),
      ", ".join(f"d{d}:{mem_updates[d]}" for d in range(4, 13)))
check("depth 1–2 asks for one value; from depth 3 two values are combined",
      mem_combos[1] == 0 and mem_combos[2] == 0
      and all(mem_combos[d] > 60 for d in range(3, 13)),
      ", ".join(f"d{d}:{mem_combos[d]}" for d in range(1, 13)))
check("four question forms exist: one value, sum, difference, larger",
      len(mem_forms) == 4, str(sorted(mem_forms)))
check("the writing room for geheugen holds every working with margin",
      mem_room_short == 0)
check("a geheugen task is the same task every time",
      world.make("geheugen", 7, 4321) == world.make("geheugen", 7, 4321))

# --- the memory brick: a running state (17 Aug 2026) --------------------------
# One in three numbers from depth 4 keeps a running state: computing updates
# (k = k + 3) and references (p = k). The reader above follows them; the
# other two in three must be bit for bit the memory task of 16 Aug 2026.
_old_mem_fence = world.MAX_DEPTH_PER.get("geheugen")
world.MAX_DEPTH_PER["geheugen"] = 40
_h = hashlib.sha256()
st_numbers = st_seen = st_bad = st_refs = st_times = 0
for depth in range(1, 25):
    for n in range(300):
        seed = world._seed_of("geheugen", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.STEEN_SEED))
        t = world.make("geheugen", depth, n)
        if depth >= world.STEEN_MIN and k.integer(1, 3) == 1:
            st_numbers += 1
            st_seen += 1
            if _read_memory(t.problem) != int(t.solution):
                st_bad += 1
            tussen = t.problem.split("\n")[1]
            if re.search(r"\b[a-z] = [a-z]\b(?! [-+*])", tussen):
                st_refs += 1
            if re.search(r"\b[a-z] = [a-z] \* \d+", tussen):
                st_times += 1
            continue
        _h.update(f"{depth}|{n}|{t.problem}|{t.working}|{t.solution}\n".encode())
world.MAX_DEPTH_PER["geheugen"] = _old_mem_fence
check("memory numbers outside the brick split are bit for bit the world of "
      "16 Aug 2026", _h.hexdigest()[:16] == "b2dbe3913178e145", _h.hexdigest()[:16])
check("the brick takes about a third of the numbers from depth 4",
      0.28 < st_numbers / (21 * 300) < 0.38, f"{st_numbers} of 6300")
check("brick problems: the independent reader lands on the same answer "
      "(computing updates and references)", st_seen > 1500 and st_bad == 0,
      f"{st_bad} disagreements of {st_seen}")
check("references appear from depth 6 and products from depth 5",
      st_refs > 300 and st_times > 300, f"{st_refs} refs, {st_times} products")
# and the world of the other three did not move: the checksums above
# (arithmetic 5f4eee0d46fcfe25, code e6b79a906f84757f, puzzle) still hold
# because "geheugen" was appended, never inserted — see world.FAMILIES.

# --- the "which rule" puzzle (17 Aug 2026) ------------------------------------
# A hidden rule from bricks, shown through pairs, asked at a new input. The
# judge: an independent solver that fits linear first (equal steps) and
# square otherwise, and demands that exactly one of the two fits.
print()
print("--- the which-rule puzzle ---")


def _solve_rule(problem):
    head, q = problem.split("\n")
    pairs = [(int(a), int(b)) for a, b in re.findall(r"f\((\d+)\) = (-?\d+)", head)]
    asked = int(re.fullmatch(r"wat is f\((\d+)\)\?", q).group(1))
    fits = []
    for kind in ("lin", "kwad"):
        f = (lambda x: x) if kind == "lin" else (lambda x: x * x)
        (x1, y1), (x2, y2) = pairs[0], pairs[1]
        if f(x2) == f(x1):
            continue
        num = y2 - y1
        den = f(x2) - f(x1)
        if num % den:
            continue
        a = num // den
        c = y1 - a * f(x1)
        if all(a * f(x) + c == y for x, y in pairs) and a >= 1:
            fits.append((kind, a, c))
    if len(pairs) == 2:
        fits = [r for r in fits if r[0] == "lin"] or fits    # two pairs: linear by convention
    if len(fits) != 1:
        return None
    kind, a, c = fits[0]
    return a * (asked if kind == "lin" else asked * asked) + c


_old_puzzle_fence = world.MAX_DEPTH_PER.get("puzzel")
world.MAX_DEPTH_PER["puzzel"] = 20
rule_seen = rule_bad = rule_unfit = rule_div = 0
rule_steps_ok = True
rule_share = {}
check_share = {}
grid_share = {}
kwad_seen = 0
for depth in range(1, 21):
    n_rule = n_all = 0
    for n in range(150):
        t = world.make("puzzel", depth, n)
        if t is None:
            continue
        n_all += 1
        if t.problem.startswith(("controleer: ", "paren: ")):
            check_share[depth] = check_share.get(depth, 0) + 1
            continue
        if t.problem.startswith("rooster"):
            grid_share[depth] = grid_share.get(depth, 0) + 1
            continue
        if not t.problem.startswith("regel: "):
            continue
        n_rule += 1
        rule_seen += 1
        if _solve_rule(t.problem) != int(t.solution):
            rule_bad += 1
        if "kwadraten" in t.working:
            kwad_seen += 1
        if "/" in t.working:
            rule_div += 1
        if not (_steps_hold(t) and re.search(r"stap: -?\d+ ; ", t.working)):
            rule_steps_ok = False
        if not (world.fits(t, 1536 - 112)
                and len(t.to_learn()) <= _rf(depth, "puzzel", 1536)):
            rule_unfit += 1
    rule_share[depth] = (n_rule, n_all)
world.MAX_DEPTH_PER["puzzel"] = _old_puzzle_fence
check("which-rule puzzles: an independent solver finds exactly one rule and "
      "the same answer", rule_seen > 800 and rule_bad == 0,
      f"{rule_seen} puzzles, {rule_bad} disagreements")
check("which-rule workings find the step by multiplying, never by dividing "
      "(18 Aug 2026)", rule_div == 0 and rule_steps_ok,
      f"{rule_div} workings with a division")
check("squares exist from depth 7 and are told apart from lines", kwad_seen > 100)
check("all which-rule puzzles fit window 1536 with their working", rule_unfit == 0)
# share over all 150 numbers: a third at depth 1, and a third of the
# keer-plus complement (~27%) from depth 2 — the rows above become
# rarer with depth, so among *usable* puzzles the rules weigh more
# since the bridge stone (18 Aug 2026) the rule split takes a third of what
# keer-plus and regelcheck leave: ~20% below 11, ~75% above 10
check("above 10 rule puzzles, regelcheck and grids together fill nearly every "
      "usable number, rules the larger part (the odd keer-plus row may stay)",
      all(rule_share[d][0] + check_share[d] + grid_share.get(d, 0) >= 0.9 * rule_share[d][1]
          and rule_share[d][0] > 1.5 * check_share[d] and rule_share[d][0] > 50
          for d in range(11, 21)),
      ", ".join(f"d{d}:{a}+{check_share[d]}+{grid_share.get(d, 0)}/{b}" for d, (a, b) in rule_share.items() if d > 10))
check("below 11 the rule split takes about a sixth of the numbers",
      all(0.09 <= rule_share[d][0] / 150 <= 0.28 for d in range(1, 11)))

# --- regelcheck: the bridge stone (18 Aug 2026) --------------------------------
# Verify (1/0), choose (which of three rules fits every pair), later with
# squares. The judge is an independent reader: it parses the rule texts and
# the pairs, evaluates them itself and demands exactly one fitting rule.
print()
print("--- regelcheck: the bridge stone ---")


def _read_rule(text):
    m = re.fullmatch(r"(\d+) \* x( \* x)?(?: ([+-]) (\d+))?", text)
    a, kwad = int(m[1]), bool(m[2])
    c = int(m[4]) * (1 if m[3] == "+" else -1) if m[3] else 0
    return lambda x: a * (x * x if kwad else x) + c


def _judge_check(problem):
    lines = problem.split("\n")
    if lines[0].startswith("controleer: "):
        f = _read_rule(lines[0][len("controleer: f(x) = "):])
        x, y = map(int, re.fullmatch(r"klopt f\((\d+)\) = (-?\d+)\?", lines[1]).groups())
        return 1 if f(x) == y else 0
    pairs = [(int(a), int(b)) for a, b in re.findall(r"f\((\d+)\) = (-?\d+)", lines[0])]
    rules = [_read_rule(r[3:]) for r in lines[1][len("regels: "):].split(" ; ")]
    assert lines[2] == "welke regel past bij alle paren?"
    fits = [i + 1 for i, f in enumerate(rules) if all(f(x) == y for x, y in pairs)]
    return fits[0] if len(fits) == 1 else None


world.MAX_DEPTH_PER["puzzel"] = 20
ck_seen = ck_bad = ck_unfit = 0
ck_forms = {"controleer": 0, "paren": 0, "kwad": 0, "nee": 0, "ja": 0}
ck_share = {}
for depth in range(1, 21):
    n_ck = 0
    for n in range(150):
        t = world.make("puzzel", depth, n)
        if t is None or not t.problem.startswith(("controleer: ", "paren: ")):
            continue
        n_ck += 1
        ck_seen += 1
        if _judge_check(t.problem) != int(t.solution):
            ck_bad += 1
        if not (_steps_hold(t) and t.check(t.working)):
            ck_bad += 1
        if not (world.fits(t, 1536 - 112)
                and len(t.to_learn()) <= _rf(depth, "puzzel", 1536)):
            ck_unfit += 1
        ck_forms[t.problem.split(":")[0]] += 1
        if "* x * x" in t.problem:
            ck_forms["kwad"] += 1
        if t.problem.startswith("controleer"):
            ck_forms["ja" if t.solution == "1" else "nee"] += 1
        if depth <= 3 and not t.problem.startswith("controleer"):
            ck_bad += 1
        if depth >= 4 and not t.problem.startswith("paren"):
            ck_bad += 1
    ck_share[depth] = n_ck
world.MAX_DEPTH_PER["puzzel"] = _old_puzzle_fence
check("regelcheck: the independent judge lands on the same answer, every step "
      "holds, verify below 4 and choose from 4", ck_seen > 500 and ck_bad == 0,
      f"{ck_seen} seen, {ck_bad} wrong")
check("regelcheck: both verdicts occur (klopt / klopt niet), squares from depth 8",
      ck_forms["ja"] > 30 and ck_forms["nee"] > 30 and ck_forms["kwad"] > 100,
      str(ck_forms))
check("regelcheck takes about a fifth of the numbers at every depth",
      all(0.12 <= ck_share[d] / 150 <= 0.32 for d in range(1, 21)),
      ", ".join(f"d{d}:{a}" for d, a in ck_share.items()))
check("all regelcheck tasks fit window 1536 with their working", ck_unfit == 0)

# --- rooster: the grid puzzle (18 Aug 2026) -----------------------------------
# The judge reads the grid and solves the unknowns itself: latijn / som by
# constraint propagation over rows and columns (a cell whose row or column
# has exactly one missing value), keer through the headers. It demands
# that the propagation reaches "?" and agrees with the answer.
print()
print("--- rooster: the grid puzzle ---")


def _judge_grid(problem):
    lines = problem.split("\n")
    head, body, q = lines[0], lines[1:-1], lines[-1]
    assert q == "wat is ?"
    if head == "rooster: rij keer kolom":
        cols = [int(x) for x in body[0].split()[1:]]
        for row in body[1:]:
            parts = row.split()
            r = int(parts[0])
            for j, cell in enumerate(parts[1:]):
                if cell == "?":
                    return r * cols[j]
        return None
    n = int(re.match(r"rooster (\d) bij \d", head).group(1))
    if "heeft 1 tot" in head:
        vals = set(range(1, n + 1))
    else:
        total = int(re.search(r"telt op tot (\d+)", head).group(1))
        vals = None
    G = [[None if c in "?*" else int(c) for c in row.split()] for row in body]
    asked = [(i, j) for i in range(n) for j in range(n) if body[i].split()[j] == "?"][0]
    if vals is None:
        # the value set follows from any complete row
        full = [r for r in G if all(v is not None for v in r)]
        vals = set(full[0])
        assert sum(vals) == total
    for _ in range(n * n):
        changed = False
        for i in range(n):
            for j in range(n):
                if G[i][j] is not None:
                    continue
                row_known = [v for v in G[i] if v is not None]
                col_known = [G[x][j] for x in range(n) if G[x][j] is not None]
                for known in (row_known, col_known):
                    if len(known) == n - 1:
                        G[i][j] = (vals - set(known)).pop()
                        changed = True
                        break
        if not changed:
            break
    return G[asked[0]][asked[1]]


world.MAX_DEPTH_PER["puzzel"] = 20
gr_seen = gr_bad = gr_unfit = 0
gr_forms = {"latijn": 0, "som": 0, "keer": 0, "ketting": 0}
gr_share = {}
for depth in range(1, 21):
    n_gr = 0
    for n in range(150):
        t = world.make("puzzel", depth, n)
        if t is None or not t.problem.startswith("rooster"):
            continue
        n_gr += 1
        gr_seen += 1
        if _judge_grid(t.problem) != int(t.solution) or not t.check(t.working):
            gr_bad += 1
        if not (world.fits(t, 1536 - 112)
                and len(t.to_learn()) <= _rf(depth, "puzzel", 1536)):
            gr_unfit += 1
        head = t.problem.split("\n")[0]
        gr_forms["keer" if "keer kolom" in head else "latijn" if "heeft 1 tot" in head else "som"] += 1
        if "*" in t.problem:
            gr_forms["ketting"] += 1
        if depth <= 6 and "*" in t.problem:
            gr_bad += 1
        if depth >= 7 and "*" not in t.problem:
            gr_bad += 1
    gr_share[depth] = n_gr
world.MAX_DEPTH_PER["puzzel"] = _old_puzzle_fence
check("rooster: the independent solver reaches ? and agrees; chains only from "
      "depth 7", gr_seen > 400 and gr_bad == 0, f"{gr_seen} seen, {gr_bad} wrong")
check("rooster: all three forms and the chained kind exist",
      all(v > 15 for v in gr_forms.values()), str(gr_forms))
check("rooster takes about a sixth of the numbers at every depth",
      all(0.08 <= gr_share[d] / 150 <= 0.28 for d in range(1, 21)),
      ", ".join(f"d{d}:{a}" for d, a in gr_share.items()))
check("all rooster tasks fit window 1536 with their working", gr_unfit == 0)

# --- logica: the fifth family (17 Aug 2026) ------------------------------------
# If-then chains, true = 1 / false = 0. The judge is an independent forward
# chainer over the text: it fires rules to a fixpoint and answers the
# question itself. Every asked name must be determined and agree.
print()
print("--- logica: the fifth family ---")
check("the world's families are the measured three, geheugen, logica, … — in that order",
      world.FAMILIES[:5] == tasks.FAMILIES + ("geheugen", "logica"))
check("the fence for logica stands at 12 or higher", world.max_depth("logica") >= 12)


def _chain(problem):
    g, r, q = problem.split("\n")
    vals = {}
    for piece in g[len("gegeven: "):].split(" ; "):
        name, v = piece.split(" = ")
        vals[name] = int(v)
    rules = r[len("regels: "):].split(" ; ")

    def val(x):
        if x.startswith("niet "):
            return None if x[5:] not in vals else 1 - vals[x[5:]]
        return vals.get(x)

    changed = True
    while changed:
        changed = False
        for rule in rules:
            m = re.fullmatch(r"als (.+) dan (niet )?(\w+)", rule)
            if not m:
                return None
            ante, neg, concl = m.group(1), m.group(2), m.group(3)
            if concl in vals:
                continue
            if " en " in ante:
                a, b = ante.split(" en ")
                fires = val(a) == 1 and val(b) == 1
            elif " of " in ante:
                a, b = ante.split(" of ")
                fires = val(a) == 1 or val(b) == 1
            else:
                fires = val(ante) == 1
            if fires:
                vals[concl] = 0 if neg else 1
                changed = True
    return vals.get(re.fullmatch(r"wat is (\w+)\?", q).group(1))


_old_logic_fence = world.MAX_DEPTH_PER.get("logica")
world.MAX_DEPTH_PER["logica"] = 24
lg_seen = lg_bad = lg_unfit = lg_room = 0
lg_zero = {d: 0 for d in range(1, 25)}
lg_not = {d: 0 for d in range(1, 25)}
lg_andor = {d: 0 for d in range(1, 25)}
for depth in range(1, 25):
    for n in range(150):
        t = world.make("logica", depth, n)
        lg_seen += 1
        if _chain(t.problem) != int(t.solution):
            lg_bad += 1
        if t.solution == "0":
            lg_zero[depth] += 1
        if "als niet " in t.working:
            lg_not[depth] += 1
        if " en " in t.working or " of " in t.working:
            lg_andor[depth] += 1
        if not world.fits(t, 1536 - 112):
            lg_unfit += 1
        if len(t.working) + 8 > _rf(depth, "logica", 1536):
            lg_room += 1
world.MAX_DEPTH_PER["logica"] = _old_logic_fence
check("3600 logica problems: an independent forward chainer lands on the same answer",
      lg_seen == 3600 and lg_bad == 0, f"{lg_bad} disagreements")
check("all of them fit window 1536; the writing room holds every working",
      lg_unfit == 0 and lg_room == 0, f"{lg_unfit} unfit, {lg_room} too little room")
check("no false conclusion before depth 7; from 7 about a third answers 0",
      all(lg_zero[d] == 0 for d in range(1, 7)) and all(lg_zero[d] > 25 for d in range(7, 25)),
      ", ".join(f"d{d}:{lg_zero[d]}" for d in (6, 7, 12, 24)))
check("negation enters at depth 3, en/of at depth 5",
      lg_not[2] == 0 and lg_not[3] > 0 and lg_andor[4] == 0 and lg_andor[5] > 0)
check("a logica task is the same task every time",
      world.make("logica", 9, 4321) == world.make("logica", 9, 4321))

# --- the equation brick (18 Aug 2026) -----------------------------------------
# One in four plain arithmetic numbers at depth 3–20 becomes an equation to
# undo. The judge: read the equation, solve it independently (all forms are
# linear in x with a whole answer), compare; and the special splits (teen
# multiplication, tail, wrapper) must be untouched — the counts above stay.
print()
print("--- the equation brick ---")
_T = tasks.Task(family="rekenen", grade=1, number=0, problem="", solution="0")


def _solve_eq(problem):
    eq = problem.split("\n")[0].replace(" ", "")
    left, right = eq.split("=")
    def lin(expr):
        # returns (a, b) with expr = a*x + b, for the forms the world writes
        m = re.fullmatch(r"(\d+)\*\(x\+(\d+)\)", expr)
        if m:
            a, b = int(m[1]), int(m[2]); return a, a * b
        a = b = 0
        for sign, term in re.findall(r"([+-]?)([0-9x*]+)", expr):
            sg = -1 if sign == "-" else 1
            if term == "x":
                a += sg
            elif "*x" in term:
                a += sg * int(term.replace("*x", ""))
            else:
                b += sg * int(term)
        return a, b
    a1, b1 = lin(left); a2, b2 = lin(right)
    if a1 == a2:
        return None
    num, den = b2 - b1, a1 - a2
    return num // den if num % den == 0 else None


eq_seen = eq_bad = eq_share = 0
eq_forms = {"een": 0, "twee": 0, "beide": 0, "haakjes": 0}
for depth in range(3, 21):
    for n in range(200):
        t = world.make("rekenen", depth, n)
        if t is None or "wat is x?" not in t.problem:
            continue
        eq_seen += 1
        if _solve_eq(t.problem) != int(t.solution):
            eq_bad += 1
        head = t.problem.split("\n")[0]
        if "(" in head:
            eq_forms["haakjes"] += 1
        elif head.count("x") == 2:
            eq_forms["beide"] += 1
        elif "*" in head and ("+" in head or "-" in head):
            eq_forms["twee"] += 1
        else:
            eq_forms["een"] += 1
check("equations: an independent solver finds the same x every time",
      eq_seen > 500 and eq_bad == 0, f"{eq_bad} disagreements of {eq_seen}")
check("all four equation forms exist (one step, two steps, x on both sides, parentheses)",
      all(v > 20 for v in eq_forms.values()), str(eq_forms))
check("outside depth 3–20 no equations appear",
      not any("wat is x?" in (world.make("rekenen", d, n) or _T).problem
              for d in (1, 2, 21, 22) for n in range(150)))

# --- volgorde: the sixth family (18 Aug 2026) ----------------------------------
# Steps in a scrambled numbering, rules that fix one order, a place asked.
# The judge: an independent topological sorter that demands exactly one
# order and reads the question itself.
print()
print("--- volgorde: the sixth family ---")
check("the world's families are the measured three, geheugen, logica, volgorde, … — in that order",
      world.FAMILIES[:6] == tasks.FAMILIES + ("geheugen", "logica", "volgorde"))
check("the fence for volgorde stands at 12 or higher", world.max_depth("volgorde") >= 12)


def _sort_order(problem):
    steps_line, rules_line, q = problem.split("\n")
    labels = [int(x) for x in re.findall(r"(?:^|; )(\d+) ", steps_line[len("stappen: "):] + " ")]
    n = len(labels)
    before = set()                        # (a, b): a before b
    for rule in rules_line[len("regels: "):].split(" ; "):
        m = re.fullmatch(r"(\d+) na (\d+)", rule)
        if m: before.add((int(m[2]), int(m[1]))); continue
        m = re.fullmatch(r"(\d+) direct na (\d+)", rule)
        if m: before.add((int(m[2]), int(m[1]))); continue
        m = re.fullmatch(r"(\d+) voor (\d+)", rule)
        if m: before.add((int(m[1]), int(m[2]))); continue
        m = re.fullmatch(r"(\d+) tussen (\d+) en (\d+)", rule)
        if m: before.add((int(m[2]), int(m[1]))); before.add((int(m[1]), int(m[3]))); continue
        return None
    # all topological orders (n ≤ 12, but the chain makes it one): count them
    orders = []
    def grow(done, left):
        if len(orders) > 1:
            return
        if not left:
            orders.append(list(done)); return
        for x in sorted(left):
            if all(a in done for a, b in before if b == x):
                grow(done + [x], left - {x})
    grow([], set(labels))
    if len(orders) != 1:
        return None
    order = orders[0]
    m = re.fullmatch(r"welke stap komt op plaats (\d+)\?", q)
    if m: return order[int(m[1]) - 1]
    m = re.fullmatch(r"op welke plaats komt stap (\d+)\?", q)
    if m: return order.index(int(m[1])) + 1
    return None


_old_order_fence = world.MAX_DEPTH_PER.get("volgorde")
world.MAX_DEPTH_PER["volgorde"] = 24
vo_seen = vo_bad = vo_unfit = vo_room = 0
vo_forms = {"voor": 0, "direct": 0, "tussen": 0, "plaats_van": 0}
vo_first = {d: 0 for d in range(1, 25)}
for depth in range(1, 25):
    for n in range(150):
        t = world.make("volgorde", depth, n)
        vo_seen += 1
        if _sort_order(t.problem) != int(t.solution):
            vo_bad += 1
        if " voor " in t.problem: vo_forms["voor"] += 1
        if "direct na" in t.problem: vo_forms["direct"] += 1
        if " tussen " in t.problem: vo_forms["tussen"] += 1
        if "op welke plaats" in t.problem: vo_forms["plaats_van"] += 1
        if depth < 4 and ("voor" in t.problem.split("\n")[1] or "direct" in t.problem):
            vo_first[depth] += 1
        if not world.fits(t, 1536 - 112):
            vo_unfit += 1
        if len(t.working) + 8 > _rf(depth, "volgorde", 1536):
            vo_room += 1
world.MAX_DEPTH_PER["volgorde"] = _old_order_fence
check("3600 volgorde problems: exactly one order fits and the sorter lands on the same answer",
      vo_seen == 3600 and vo_bad == 0, f"{vo_bad} disagreements")
check("all rule forms and both question forms exist",
      all(v > 100 for v in vo_forms.values()), str(vo_forms))
check("below depth 4 only plain 'na' rules; the place question only from 6",
      all(vo_first[d] == 0 for d in (1, 2, 3)))
check("all volgorde problems fit window 1536; the writing room holds every working",
      vo_unfit == 0 and vo_room == 0, f"{vo_unfit} unfit, {vo_room} too little room")
check("a volgorde task is the same task every time",
      world.make("volgorde", 9, 4321) == world.make("volgorde", 9, 4321))

# --- tekst: the seventh family (18 Aug 2026) -----------------------------------
# Patterns in words, counted. The judge: Python's own string operations on
# the text — the operation first (reverse, sort, drop a letter), then the
# question — must land on the same number.
print()
print("--- tekst: the seventh family ---")
check("the world's families continue with volgorde, tekst — appended, never inserted",
      world.FAMILIES[5:7] == ("volgorde", "tekst") and world.FAMILIES[:5] == tasks.FAMILIES + ("geheugen", "logica"))
check("the fence for tekst stands at 12 or higher", world.max_depth("tekst") >= 12)
check("the word list is fixed, lowercase a–z, without doubles",
      len(world.TEXT_WORDS) >= 150 and len(set(world.TEXT_WORDS)) == len(world.TEXT_WORDS)
      and all(w.isalpha() and w.islower() and w.isascii() for w in world.TEXT_WORDS))

VOW = "aeiou"


def _count_text(problem):
    lines = problem.split("\n")
    words = lines[0][len("woorden: "):].split()
    q = lines[-1]
    for op in lines[1:-1]:
        if op == "keer elk woord om":
            words = [w[::-1] for w in words]
        elif op.startswith("zet de woorden op lengte"):
            words = sorted(words, key=lambda w: (len(w), words.index(w)))
        elif op.startswith("haal alle letters "):
            L = op[len("haal alle letters "):].split()[0]
            words = [w.replace(L, "") for w in words]
        else:
            return None
    dbl = lambda w: any(a == b for a, b in zip(w, w[1:]))
    m = re.fullmatch(r"hoeveel letters heeft (\S+)\?", q)
    if m: return len(m[1])
    m = re.fullmatch(r"hoeveel keer komt (\S) voor in (\S+)\?", q)
    if m: return m[2].count(m[1])
    m = re.fullmatch(r"de hoeveelste letter van (\S+) is de eerste (\S)\?", q)
    if m: return m[1].index(m[2]) + 1
    tests = {
        "hoeveel woorden hebben een dubbele letter?": dbl,
        "hoeveel woorden beginnen met een klinker?": lambda w: bool(w) and w[0] in VOW,
        "hoeveel woorden hebben een even aantal letters?": lambda w: len(w) % 2 == 0,
        "hoeveel woorden eindigen op en?": lambda w: w.endswith("en"),
        "hoeveel woorden beginnen met een klinker en hebben een dubbele letter?": lambda w: bool(w) and w[0] in VOW and dbl(w),
        "hoeveel woorden zijn een palindroom?": lambda w: len(w) > 1 and w == w[::-1],
        "hoeveel woorden hebben meer klinkers dan medeklinkers?": lambda w: sum(c in VOW for c in w) > sum(c not in VOW for c in w),
    }
    if q in tests: return sum(bool(tests[q](w)) for w in words)
    if q == "hoeveel letters heeft het langste woord?": return max(len(w) for w in words)
    if q.startswith("het hoeveelste woord is het langste?"):
        ls = [len(w) for w in words]; return ls.index(max(ls)) + 1
    m = re.fullmatch(r"hoeveel keer komt (\S) voor in alle woorden samen\?", q)
    if m: return sum(w.count(m[1]) for w in words)
    return None


_old_text_fence = world.MAX_DEPTH_PER.get("tekst")
world.MAX_DEPTH_PER["tekst"] = 24
tx_seen = tx_bad = tx_unfit = tx_room = 0
tx_ops = {d: 0 for d in range(1, 25)}
tx_forms = set()
for depth in range(1, 25):
    for n in range(150):
        t = world.make("tekst", depth, n)
        tx_seen += 1
        if _count_text(t.problem) != int(t.solution):
            tx_bad += 1
        if len(t.problem.split("\n")) == 3:
            tx_ops[depth] += 1
        tx_forms.add(re.sub(r"(heeft |voor in |van |eerste |komt )[a-z]+", r"\1w",
                            t.problem.split("\n")[-1]))
        if not world.fits(t, 1536 - 112):
            tx_unfit += 1
        if len(t.working) + 8 > _rf(depth, "tekst", 1536):
            tx_room += 1
world.MAX_DEPTH_PER["tekst"] = _old_text_fence
check("3600 tekst problems: Python's string operations land on the same number",
      tx_seen == 3600 and tx_bad == 0, f"{tx_bad} disagreements")
check("no operation before depth 8; from 8 about half of the problems have one",
      all(tx_ops[d] == 0 for d in range(1, 8)) and all(tx_ops[d] > 40 for d in range(8, 25)))
check("many question forms exist", len(tx_forms) >= 12, f"{len(tx_forms)} forms")
check("all tekst problems fit window 1536; the writing room holds every working",
      tx_unfit == 0 and tx_room == 0, f"{tx_unfit} unfit, {tx_room} too little room")
check("a tekst task is the same task every time",
      world.make("tekst", 9, 4321) == world.make("tekst", 9, 4321))

# --- zeggen: the eighth family (18 Aug 2026, Cley) ----------------------------
# Her own sentence from a fixed vocabulary, checked as text. The judge
# re-applies the rules from the problem text alone.
print()
print("--- zeggen: the eighth family ---")
check("the world's families continue with zeggen, taal, machine, tellen — appended",
      world.FAMILIES[7:11] == ("zeggen", "taal", "machine", "tellen"))


def _judge_saying(problem):
    lines = problem.split("\n")
    q = lines[-1]
    stand = {f: int(v) for f, v in re.findall(r"(\w+) (\d+)", lines[0][len("cijfers: "):])}
    edge = {}
    keuzes = {}
    for line in lines[1:-1]:
        if line.startswith("wereld: "):
            edge = {f: (int(a), int(b)) for f, a, b in re.findall(r"(\w+) (\d+)/(\d+)", line)}
        if line.startswith("keuzes: "):
            keuzes = {f: int(v) for f, v in re.findall(r"(\w+) (\d+)", line)}
    lowest = min(stand, key=stand.get)
    highest = max(stand, key=stand.get)
    verdict = lambda f: f"{f} gaat goed" if stand[f] >= 90 else f"{f} gaat" if stand[f] >= 60 else f"{f} is moeilijk"
    if q == "hoe gaat het?":
        return verdict(next(iter(stand)))
    if q == "wat is moeilijk?":
        return f"{lowest} is moeilijk"
    if q == "wat gaat goed?":
        return f"{highest} gaat goed"
    if q == "wat wil je oefenen?":
        return f"ik wil meer {lowest} oefenen"
    deeper = [f for f in stand if stand[f] >= 90 and edge.get(f, (0, 0))[0] < edge.get(f, (0, 0))[1]]
    if keuzes and keuzes.get(lowest, 0) >= 25:
        wish = f"{lowest} blijft moeilijk"
    elif deeper:
        wish = f"ik wil dieper in {max(deeper, key=stand.get)}"
    else:
        wish = f"ik wil meer {lowest} oefenen"
    if len(stand) >= 4 and keuzes and problem.count("\n") >= 3 and _two_sentences:
        return f"{verdict(highest)} en {wish}"
    return wish


zg_seen = zg_bad = zg_unfit = 0
zg_forms = set()
for depth in range(1, 13):
    _two_sentences = depth >= 11
    for n in range(200):
        t = world.make("zeggen", depth, n)
        zg_seen += 1
        if _judge_saying(t.problem) != t.solution or not t.check(t.working):
            zg_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "zeggen", 1536)):
            zg_unfit += 1
        zg_forms.add(re.sub(r"\b(" + "|".join(world.ZEG_ONDERWERPEN) + r")\b", "X", t.solution))
check("zeggen: the independent judge writes the same sentence every time",
      zg_seen == 2400 and zg_bad == 0, f"{zg_bad} disagreements")
check("zeggen: the sentence forms exist (verdicts, wishes, deeper, blijft, en)",
      {"X gaat goed", "X gaat", "X is moeilijk", "ik wil meer X oefenen",
       "ik wil dieper in X", "X blijft moeilijk"} <= zg_forms
      and any(" en " in f for f in zg_forms), str(sorted(zg_forms))[:300])
check("zeggen: solutions carry no number (checked as text) and fit the room",
      zg_unfit == 0 and all(not re.search(r"\d", world.make("zeggen", d, 3).solution) for d in range(1, 13)))
check("a zeggen task is the same task every time",
      world.make("zeggen", 9, 77) == world.make("zeggen", 9, 77))


# --- zeggen 13-24 (19 Aug 2026, Cley: "ik wil dat ze meer kan gaan praten") ---
# An independent judge: parses the stand/gisteren/wereld/keuzes lines
# itself and answers the question by its own reading of the rules.
def _judge_saying_deep(problem):
    lines = problem.split("\n")
    q = lines[-1]
    blocks = {}
    for line in lines[:-1]:
        key, _, rest = line.partition(": ")
        if key == "wereld":
            blocks[key] = {f: (int(a), int(b)) for f, a, b in re.findall(r"(\w+) (\d+)/(\d+)", rest)}
        else:
            blocks[key] = {f: int(v) for f, v in re.findall(r"(\w+) (\d+)", rest)}
    stand = blocks["cijfers"]
    fams = list(stand)
    lowest = min(fams, key=stand.get)
    highest = max(fams, key=stand.get)
    edge = blocks.get("wereld", {})
    before = blocks.get("gisteren", {})
    keuzes = blocks.get("keuzes", {})
    verdict = lambda f: f"{f} gaat goed" if stand[f] >= 90 else f"{f} gaat" if stand[f] >= 60 else f"{f} is moeilijk"
    trend = lambda f: (f"{f} gaat beter dan gisteren" if stand[f] > before[f]
                       else f"{f} gaat slechter dan gisteren" if stand[f] < before[f]
                       else f"{f} gaat zoals gisteren")
    deeper = [f for f in fams if stand[f] >= 90 and edge.get(f, (0, 0))[0] < edge.get(f, (0, 0))[1]]
    vraag = (f"mag ik dieper in {max(deeper, key=stand.get)}?" if deeper
             else f"mag ik meer {lowest} oefenen?")
    m = re.match(r"wat gaat beter, (\w+) of (\w+)\?", q)
    if m:
        a, b = m.groups()
        w, l = (a, b) if stand[a] > stand[b] else (b, a)
        return f"{w} gaat beter dan {l}"
    m = re.match(r"hoe gaat (\w+) nu\?", q)
    if m:
        return trend(m.group(1))
    if q == "waarom gaat het zo?":
        busy = max(fams, key=keuzes.get)
        return (f"ik oefen veel {busy} maar het gaat langzaam" if stand[busy] < 60
                else f"ik oefen veel {busy} en het gaat goed")
    if q == "wat vraag je aan cley?":
        return vraag
    m = re.match(r"hoe staat (\w+) ervoor\?", q)
    if m:
        f = m.group(1)
        vol = edge[f][0] >= edge[f][1]
        return f"{f} is {'vol' if vol else 'niet vol'} en {verdict(f).split(' ', 1)[1]}"
    if q == "vertel hoe het gaat":
        return f"{verdict(highest)} en {trend(lowest)} en {vraag}"
    return None


zd_seen = zd_bad = zd_unfit = 0
zd_forms = set()
for depth in range(13, 25):
    for n in range(200):
        t = world.make("zeggen", depth, n)
        zd_seen += 1
        if _judge_saying_deep(t.problem) != t.solution or not t.check(t.working):
            zd_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "zeggen", 1536)):
            zd_unfit += 1
        zd_forms.add(re.sub(r"\b(" + "|".join(world.ZEG_ONDERWERPEN) + r")\b", "X", t.solution))
check("zeggen 13-24: the independent judge writes the same sentence every time",
      zd_seen == 2400 and zd_bad == 0, f"{zd_bad} disagreements")
check("zeggen 13-24: comparing, change, cause, a question to Cley, her world, three sentences",
      any(f.startswith("X gaat beter dan X") for f in zd_forms)
      and any("dan gisteren" in f for f in zd_forms)
      and any(f.startswith("ik oefen veel X") for f in zd_forms)
      and any(f.startswith("mag ik") for f in zd_forms)
      and any(" is vol en " in f or " is niet vol en " in f for f in zd_forms)
      and any(f.count(" en ") >= 2 for f in zd_forms), str(sorted(zd_forms))[:400])
check("zeggen 13-24: no number in the solution and everything fits the room", zd_unfit == 0
      and all(not re.search(r"\d", world.make("zeggen", d, 3).solution) for d in range(13, 25)))
_h = hashlib.md5()
for _d in range(1, 13):
    for _n in range(0, 300):
        _t = world.make("zeggen", _d, _n)
        _h.update(f"{_t.problem}|{_t.solution}|{_t.working}".encode())
check("zeggen 1-12 is bit for bit untouched by the 13-24 extension (3600 tasks, md5 pinned 19 Aug)",
      _h.hexdigest() == "f7a0cfadc631192fe583d98ec691a57e", _h.hexdigest())


# --- antwoord: twelfth family (19 Aug 2026, Cley: "ik wil terug kunnen praten") --
# She asked, Cley answered; the judge reads the turns itself and says what
# the LAST answer means. No answer is a no (CLAUDE.md).
def _judge_answer(problem):
    m = re.match(r"gesprek: mag ik (dieper in|meer) (\w+)( oefenen)?\? / (.*) / wat betekent dat\?", problem)
    assert m, problem
    deeper = m.group(1) == "dieper in"
    fam = m.group(2)
    turns = [t[len("cley: "):] for t in m.group(4).split(" / ")]
    ant = turns[-1]
    if ant == "ja":
        return f"ik mag dieper in {fam}" if deeper else f"ik mag meer {fam} oefenen"
    if ant == "nee":
        return f"ik mag niet dieper in {fam}" if deeper else f"ik mag niet meer {fam} oefenen"
    if ant in ("later", "-"):
        return "ik wacht"
    if ant.startswith("eerst "):
        return f"ik moet eerst {ant[6:]} oefenen"
    return f"cley zegt {ant}"


an_bad = an_unfit = 0
an_forms = set()
for depth in range(1, 13):
    for n in range(200):
        t = world.make("antwoord", depth, n)
        if _judge_answer(t.problem) != t.solution or not t.check(t.working):
            an_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "antwoord", 1536)):
            an_unfit += 1
        an_forms.add(re.sub(r"\b(" + "|".join(world.ZEG_ONDERWERPEN) + r")\b", "X", t.solution))
check("antwoord: the independent judge reads Cley's last answer the same way (2400 tasks)",
      an_bad == 0, f"{an_bad} disagreements")
check("antwoord: ja / nee / later / no answer / eerst X — and silence means she waits",
      {"ik mag dieper in X", "ik mag niet dieper in X", "ik mag meer X oefenen",
       "ik mag niet meer X oefenen", "ik wacht", "ik moet eerst X oefenen"} <= an_forms
      and any("cley is bezig ; ik wacht" in world.make("antwoord", 5, n).working for n in range(60)),
      str(sorted(an_forms)))
check("antwoord: no number in the solution and everything fits the room", an_unfit == 0
      and all(not re.search(r"\d", world.make("antwoord", d, 3).solution) for d in range(1, 13)))
check("antwoord: at depth 10-12 the LAST of two answers counts",
      all("het laatste geldt" in world.make("antwoord", d, n).working for d in (10, 11, 12) for n in range(30)))
check("the world's families end with onbekend — appended, the older streams untouched",
      world.FAMILIES[-1] == "onbekend" and world.FAMILIES[7:12] == ("zeggen", "taal", "machine", "tellen", "antwoord"))

# --- taal: the ninth family (18 Aug 2026, Cley) -------------------------------
# Short sentences from a fixed vocabulary; the judge parses them with the
# grammar and answers the question itself; for "maak de zin" it rebuilds
# the only sentence the words allow.
print()
print("--- taal: the ninth family ---")
_A = set(world.TAAL_DIEREN); _D = set(world.TAAL_DINGEN); _K = set(world.TAAL_KLEUREN)
_V = set(world.TAAL_WERKWOORDEN) | {"zit", "ligt", "staat", "hangt", "wacht"}
_KV = {v: k for k, v in world.TAAL_VERBOGEN.items()}
_P = set(world.TAAL_PLAATS)


def _parse(line):
    w = line.split()
    z = {}
    if w[0] == "hij":                     # hij is <kleur>
        return {"ref": "hij", "kleur": w[2]}
    if w[0] == "daar":                    # daar <v> ook de <dier>
        return {"ref": "daar", "werk": w[1], "dier": w[4]}
    i = 1
    if w[i] in _KV:
        z["bijv"] = _KV[w[i]]; i += 1
    z["dier"] = w[i]; i += 1
    if w[i] == "is":
        z["kleur"] = w[i + 1]; return z
    z["werk"] = w[i]; i += 1
    if i < len(w):
        z["waar"] = w[i]; z["ding"] = w[i + 2]
    return z


def _judge_language(problem):
    lines = problem.split("\n")
    if lines[0].startswith("woorden: "):
        words = lines[0][len("woorden: "):].split()
        dier = [x for x in words if x in _A][0]
        bijv = [x for x in words if x in _KV]
        if "is" in words:
            return f"de {dier} is {[x for x in words if x in _K][0]}"
        werk = [x for x in words if x in _V][0]
        head = f"de {bijv[0] + ' ' if bijv else ''}{dier} {werk}"
        if any(x in _P for x in words):
            waar = [x for x in words if x in _P][0]
            ding = [x for x in words if x in _D][0]
            return f"{head} {waar} de {ding}"
        return head
    q = lines[-1]
    zs = [_parse(l) for l in lines[:-1]]
    plain = [z for z in zs if "ref" not in z]
    m = re.fullmatch(r"wie (\w+)\?", q)
    if m:
        c = [z for z in zs if z.get("werk") == m[1]]
        return c[0]["dier"] if len(c) == 1 else None
    m = re.fullmatch(r"wat doet de (\w+)\?", q)
    if m:
        return [z["werk"] for z in plain if z["dier"] == m[1]][0]
    m = re.fullmatch(r"waar (\w+) de (\w+)\?", q)
    if m:
        for i, z in enumerate(zs):
            if z.get("ref") == "daar" and z["dier"] == m[2] and z["werk"] == m[1]:
                return zs[i - 1]["ding"]
        c = [z for z in plain if z["dier"] == m[2] and z.get("werk") == m[1]]
        return c[0]["ding"] if len(c) == 1 else None
    m = re.fullmatch(r"wat (\w+) (\w+) de (\w+)\?", q)
    if m:
        c = [z for z in plain if z.get("werk") == m[1] and z.get("waar") == m[2] and z.get("ding") == m[3]]
        return c[0]["dier"] if len(c) == 1 else None
    m = re.fullmatch(r"welke kleur heeft de (\w+)\?", q)
    if m:
        for i, z in enumerate(zs):
            if z.get("ref") == "hij" and zs[i - 1]["dier"] == m[1]:
                return z["kleur"]
        c = [z for z in plain if z["dier"] == m[1]]
        return c[0].get("kleur") or c[0].get("bijv")
    m = re.fullmatch(r"wat is (\w+)\?", q)
    if m:
        c = [z for z in plain if z.get("kleur") == m[1]]
        return c[0]["dier"] if len(c) == 1 else None
    return None


tl_seen = tl_bad = tl_unfit = 0
tl_kinds = set()
for depth in range(1, 13):
    for n in range(200):
        t = world.make("taal", depth, n)
        tl_seen += 1
        if _judge_language(t.problem) != t.solution or not t.check(t.working):
            tl_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "taal", 1536)):
            tl_unfit += 1
        tl_kinds.add(t.problem.split("\n")[-1].split()[0])
        if depth >= 9 and ("\nhij is" in t.problem or "\ndaar " in t.problem):
            tl_kinds.add("verwijzing")
        if depth >= 11 and t.problem.startswith("woorden: "):
            tl_kinds.add("maken")
check("taal: the independent parser answers every question the same way "
      "(one answer, never ambiguous)", tl_seen == 2400 and tl_bad == 0, f"{tl_bad} disagreements")
check("taal: questions wie/wat/waar/welke, references and building exist",
      {"wie", "wat", "waar", "welke", "verwijzing", "maken"} <= tl_kinds, str(sorted(tl_kinds)))
check("taal: only de-words, correct adjective forms",
      all(w not in ("paard", "schaap", "bed", "dak") for w in world.TAAL_DIEREN + world.TAAL_DINGEN)
      and world.TAAL_VERBOGEN["rood"] == "rode" and world.TAAL_VERBOGEN["wit"] == "witte")
check("taal: everything fits the room", tl_unfit == 0)
check("a taal task is the same task every time",
      world.make("taal", 9, 77) == world.make("taal", 9, 77))


# --- machine: the tenth family (18 Aug 2026) -----------------------------------
# The judge executes the program from the text and compares the asked
# register; the trace must hold at every step (steps recomputed).
print()
print("--- machine: the tenth family ---")


def _run_machine(problem):
    # run 8: the noise line is no part of the machine — the judge skips it,
    # which is exactly what she must learn to do
    lines = [l for l in problem.split("\n") if not l.startswith("tussendoor: ")]
    vals = {c: int(v) for c, v in re.findall(r"(\w) = (-?\d+)", lines[0])}
    steps = lines[1][len("stappen: "):].split(" ; ")
    rounds = 1
    for l in lines:
        m = re.fullmatch(r"herhaal (\d+) keer", l)
        if m: rounds = int(m[1])
    asked = re.fullmatch(r"wat is (\w)\?", lines[-1])[1]
    for _ in range(rounds):
        for st in steps:
            m = re.fullmatch(r"als (\w) > (\w) dan (\w) = \w ([-+]) (\d+)", st)
            if m:
                if vals[m[1]] > vals[m[2]]:
                    vals[m[3]] = vals[m[3]] + int(m[5]) if m[4] == "+" else vals[m[3]] - int(m[5])
                continue
            m = re.fullmatch(r"(\w) = \w ([-+*]) (\w+)", st)
            amt = int(m[3]) if m[3].lstrip("-").isdigit() else vals[m[3]]
            v = vals[m[1]]
            vals[m[1]] = v + amt if m[2] == "+" else v - amt if m[2] == "-" else v * amt
    return vals[asked]


def _trace_holds(working):
    for piece in re.split(r" ; |: ", working):
        m = re.fullmatch(r"\w = (-?\d+) ([-+*]) (-?\d+) = (-?\d+)", piece.strip())
        if m:
            a, op, b, out = int(m[1]), m[2], int(m[3]), int(m[4])
            if (a + b if op == "+" else a - b if op == "-" else a * b) != out:
                return False
    return True


mc_seen = mc_bad = mc_unfit = mc_cond = mc_ruis = 0
for depth in range(1, 13):
    for n in range(200):
        t = world.make("machine", depth, n)
        if t is None:
            continue
        mc_seen += 1
        if _run_machine(t.problem) != int(t.solution) or not t.check(t.working) or not _trace_holds(t.working):
            mc_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "machine", 1536)):
            mc_unfit += 1
        if "als " in t.problem:
            mc_cond += 1
            if depth < 7:
                mc_bad += 1
        if "tussendoor: " in t.problem:
            mc_ruis += 1
            if depth < world.MACHINE_RUIS_MIN:
                mc_bad += 1
            if re.search(r"\b[xyz] =", t.problem.split("\n")[1]):
                mc_bad += 1
check("machine: the executed program lands on her answer and every trace step holds",
      mc_seen > 2000 and mc_bad == 0, f"{mc_seen} seen, {mc_bad} wrong")
check("machine: conditional steps exist from depth 7 only", mc_cond > 100)
check("machine: noise lines from MACHINE_RUIS_MIN only, never touching a register (run 8)",
      mc_ruis > 100, f"{mc_ruis} with tussendoor")
check("machine: everything fits the room", mc_unfit == 0)
check("a machine task is the same task every time",
      world.make("machine", 9, 77) == world.make("machine", 9, 77))

# --- tellen: the eleventh family (18 Aug 2026) ---------------------------------
# The judge enumerates in Python from the question text.
print()
print("--- tellen: the eleventh family ---")


def _count(problem):
    m = re.fullmatch(r"hoe vaak komt het cijfer (\d) voor in de getallen van (\d+) tot (\d+)\?", problem)
    if m:
        c, lo, hi = m[1], int(m[2]), int(m[3])
        return sum(str(n).count(c) for n in range(lo, hi + 1))
    m = re.fullmatch(r"tel de getallen van (\d+) tot (\d+) die (.+)", problem)
    lo, hi = int(m[1]), int(m[2])
    preds = []
    for c in m[3].split(" en "):
        if (k := re.fullmatch(r"deelbaar zijn door (\d+)", c)):
            preds.append(lambda n, k=int(k[1]): n % k == 0)
        elif c == "even zijn":
            preds.append(lambda n: n % 2 == 0)
        elif c == "oneven zijn":
            preds.append(lambda n: n % 2 == 1)
        elif (k := re.fullmatch(r"eindigen op (\d)", c)):
            preds.append(lambda n, k=int(k[1]): n % 10 == k)
        elif (k := re.fullmatch(r"een cijfersom van (\d+) hebben", c)):
            preds.append(lambda n, k=int(k[1]): sum(int(d) for d in str(n)) == k)
        elif (k := re.fullmatch(r"het cijfer (\d) bevatten", c)):
            preds.append(lambda n, k=k[1]: k in str(n))
        elif (k := re.fullmatch(r"groter zijn dan (\d+)", c)):
            preds.append(lambda n, k=int(k[1]): n > k)
        else:
            return None
    return sum(1 for n in range(lo, hi + 1) if all(p(n) for p in preds))


tc_seen = tc_bad = tc_unfit = tc_digit = tc_two = 0
for depth in range(1, 13):
    for n in range(200):
        t = world.make("tellen", depth, n)
        if t is None:
            continue
        tc_seen += 1
        if _count(t.problem) != int(t.solution) or not t.check(t.working):
            tc_bad += 1
        listed = [int(x) for x in t.working.split(" ; ")[0].split(", ")]
        if len(listed) > world.TEL_MAX_LIST or len(listed) < 1:
            tc_bad += 1
        if not (world.fits(t, 1536 - 112) and len(t.to_learn()) <= _rf(depth, "tellen", 1536)):
            tc_unfit += 1
        tc_digit += t.problem.startswith("hoe vaak")
        tc_two += " en " in t.problem
check("tellen: Python's enumeration lands on her count; the list is 1–25 long",
      tc_seen > 1500 and tc_bad == 0, f"{tc_seen} seen, {tc_bad} wrong")
check("tellen: two-condition questions and digit counting exist", tc_two > 300 and tc_digit > 50)
check("tellen: everything fits the room", tc_unfit == 0)
check("a tellen task is the same task every time",
      world.make("tellen", 9, 77) == world.make("tellen", 9, 77))

# --- a sheet frozen for a wider window is skipped, not sat (17 Aug 2026) -----
# venster2048.json holds rekenen 62–78 and code 32–40 for the day the window
# grows; at 1536 its problems do not fit and answering would fall over. So
# exams.take leaves any sheet whose `venster` is wider than hers alone.
class _Stub:
    class core:
        window = 1536
    @staticmethod
    def answer(batch, at_most=None):
        return [""] * len(batch)
if exams.exists("venster2048"):
    _sat = exams.take(_Stub(), "venster2048")
    check("a sheet with venster 2048 is skipped at window 1536",
          _sat == {}, str(_sat))
    _Stub.core.window = 2048
    _sat = exams.take(_Stub(), "venster2048", at_most=4)
    check("… and sat once the window is 2048", "venster2048" in _sat)
    check("the sheet says which window it needs",
          exams.load("venster2048").window == 2048)
else:
    print("         (venster2048.json not here — a trainer copy before the rungrens; "
          "the mother copy has it)")

# --- the two pages know every family (17 Aug 2026) ---------------------------
# index.html (8000) and mobiel.html (8001) carry the family list by hand —
# fences, entrances, the rows of "haar wereld". Twice the phone page fell
# behind and Cley did not see the new family. So: every family of the world
# must appear in both pages' fence dictionary and world loop, or this is red.
import os as _os
_brein = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "brein")
for page in ("index.html", "mobiel.html"):
    try:
        html = open(_os.path.join(_brein, page), encoding="utf-8").read()
    except OSError:
        check(f"{page} is there to check", False)
        continue
    m = re.search(r"const grens = \{([^}]*)\}", html)
    fence_names = set(re.findall(r"(\w+):", m.group(1))) if m else set()
    loops = re.findall(r'for \(const f of \[([^\]]*)\]\)', html)
    loop_names = [set(re.findall(r'"(\w+)"', l)) for l in loops]
    missing = [f for f in world.FAMILIES
               if f not in fence_names or any(f not in ln for ln in loop_names)]
    check(f"{page} knows every family of the world in its fences and world rows",
          not missing and loop_names, f"missing: {missing}" if missing else "")

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
