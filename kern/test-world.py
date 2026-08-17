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
        if str(eval(_unwrap(t.problem))) != t.solution:
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
    if t is None or t.problem.startswith("regel: "):
        continue                          # the which-rule kind (17 Aug 2026), tested below
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
    if t is not None and not t.problem.startswith("regel: "):
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
        if t is None or t.problem.startswith("regel: "):
            continue                      # rows only; the rule kind is tested below
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
kp_numbers = []
regel_numbers = []
for depth in range(1, 11):
    for n in range(300):
        seed = world._seed_of("puzzel", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.KEERPLUS_SEED))
        if depth >= world.KEERPLUS_MIN and k.integer(1, 5) == 1:
            kp_numbers.append((depth, n))
            continue
        # the "which rule" split (17 Aug 2026) takes one in three of the
        # rest — those numbers changed on purpose; the others must not
        if tasks.Picker(tasks._mix(seed ^ world.REGEL_SEED)).integer(1, 3) == 1:
            regel_numbers.append((depth, n))
            continue
        t = world.make("puzzel", depth, n)
        _h.update((f"{depth}|{n}|{t.problem if t else ''}|"
                   f"{t.working if t else ''}|{t.solution if t else ''}\n")
                  .encode())
# taken over exactly these numbers on 17 Aug 2026 before the rule split
# existed (a7d2547646bda49b was the sum over the keer-plus complement)
check("puzzle numbers outside both splits are bit for bit the world "
      "of 15 Aug 2026", _h.hexdigest()[:16] == "7fa9005221985a61",
      _h.hexdigest()[:16])
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
        is_wrapped = t.problem.endswith("?") or t.problem.startswith("Reken")
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
kc_numbers = 0
for depth in range(1, 13):
    for n in range(300):
        seed = world._seed_of("rekenen", depth, n)
        k = tasks.Picker(tasks._mix(seed ^ world.KEERC_SEED))
        if world.KEERC_MIN <= depth <= world.KEERC_MAX and k.integer(1, 5) == 1:
            kc_numbers += 1
            continue
        t = world.make("rekenen", depth, n)
        p = t.problem if t else ""
        w = t.working if t else ""
        s = t.solution if t else ""
        _h.update(f"{depth}|{n}|{p}|{w}|{s}\n".encode())
check("untouched arithmetic numbers depth 1-12 are bit for bit the old world",
      _h.hexdigest()[:16] == "5f4eee0d46fcfe25",
      f"{_h.hexdigest()[:16]}, {kc_numbers} split numbers")

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
for depth in range(1, 16):
    for n in range(300):
        t = world.make("code", depth, n)
        _h.update((f"{depth}|{n}|{t.problem if t else ''}|"
                   f"{t.working if t else ''}|{t.solution if t else ''}\n")
                  .encode())
check("code depth 1-15 is bit for bit the world of 15 Aug 2026",
      _h.hexdigest()[:16] == "e6b79a906f84757f", _h.hexdigest()[:16])

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
rule_seen = rule_bad = rule_unfit = 0
rule_share = {}
kwad_seen = 0
for depth in range(1, 21):
    n_rule = n_all = 0
    for n in range(150):
        t = world.make("puzzel", depth, n)
        if t is None:
            continue
        n_all += 1
        if not t.problem.startswith("regel: "):
            continue
        n_rule += 1
        rule_seen += 1
        if _solve_rule(t.problem) != int(t.solution):
            rule_bad += 1
        if "kwadraten" in t.working:
            kwad_seen += 1
        if not (world.fits(t, 1536 - 112)
                and len(t.to_learn()) <= _rf(depth, "puzzel", 1536)):
            rule_unfit += 1
    rule_share[depth] = (n_rule, n_all)
world.MAX_DEPTH_PER["puzzel"] = _old_puzzle_fence
check("which-rule puzzles: an independent solver finds exactly one rule and "
      "the same answer", rule_seen > 1000 and rule_bad == 0,
      f"{rule_seen} puzzles, {rule_bad} disagreements")
check("squares exist from depth 7 and are told apart from lines", kwad_seen > 100)
check("all which-rule puzzles fit window 1536 with their working", rule_unfit == 0)
# share over all 150 numbers: a third at depth 1, and a third of the
# keer-plus complement (~27%) from depth 2 — the rows above become
# rarer with depth, so among *usable* puzzles the rules weigh more
check("below 11 the rule split takes about a quarter of the numbers",
      all(0.18 <= rule_share[d][0] / 150 <= 0.40 for d in range(1, 11)),
      ", ".join(f"d{d}:{a}/150" for d, (a, b) in rule_share.items() if d <= 10))
check("above 10 nearly every usable puzzle is a rule puzzle — the empty room is "
      "filled (the odd keer-plus row that still comes out may stay)",
      all(rule_share[d][0] >= 0.9 * rule_share[d][1] and rule_share[d][0] > 100
          for d in range(11, 21)),
      ", ".join(f"d{d}:{a}/{b}" for d, (a, b) in rule_share.items() if d > 10))

# --- logica: the fifth family (17 Aug 2026) ------------------------------------
# If-then chains, true = 1 / false = 0. The judge is an independent forward
# chainer over the text: it fires rules to a fixpoint and answers the
# question itself. Every asked name must be determined and agree.
print()
print("--- logica: the fifth family ---")
check("the world's families are the measured three, geheugen, logica — in that order",
      world.FAMILIES == tasks.FAMILIES + ("geheugen", "logica"))
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

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
