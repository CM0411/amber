"""
Tests the measuring set-up.

Two kinds of control, and the second is the more important one:

  * does the set-up do what it promises — reproducible, fenced off, ordered
  * **is the answer actually right?** The problems are recomputed
    independently here: arithmetic with eval, code problems by really
    executing the program and comparing the output. Without that you only
    test whether the generator is consistent with itself — and a generator
    that systematically gives wrong answers is that too.

Run:  venv/bin/python kern/test-tasks.py
"""

import io
import contextlib
import re
import sys

import tasks

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
print("Test — the measuring set-up")
print("=" * 70)
print()

# --- 1. Are the answers right? ---------------------------------------------

print("--- Are the problems computed correctly? ---")

wrong = []
for grade in tasks.GRADES:
    for n in range(200):
        t = tasks.make("rekenen", grade, n)
        if str(eval(t.problem)) != t.solution:
            wrong.append((t.problem, t.solution, eval(t.problem)))
check("1000 arithmetic problems match what Python itself computes",
      not wrong, f"{len(wrong)} deviations" if wrong else "not a single deviation")

wrong = []
for grade in tasks.GRADES:
    for n in range(60):
        t = tasks.make("code", grade, n)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(t.problem, {})
        if out.getvalue().strip() != t.solution:
            wrong.append((t.problem, t.solution, out.getvalue().strip()))
check(
    "300 code problems really print what is noted as the answer",
    not wrong,
    f"{len(wrong)} deviations" if wrong else "every program actually executed",
)

# The puzzles have no second source of truth, so there the rule itself is
# verified on the row as shown.
wrong = []
for n in range(200):
    t = tasks.make("puzzel", 1, n)
    row = [int(x) for x in re.findall(r"-?\d+", t.problem)]
    diffs = {row[i + 1] - row[i] for i in range(len(row) - 1)}
    if len(diffs) != 1 or int(t.solution) != row[-1] + diffs.pop():
        wrong.append(t.problem)
check("the grade-1 rows really have a fixed difference", not wrong)

wrong = []
for n in range(200):
    t = tasks.make("puzzel", 5, n)
    row = [int(x) for x in re.findall(r"-?\d+", t.problem)]
    if any(row[i] + row[i + 1] != row[i + 2] for i in range(len(row) - 2)):
        wrong.append(t.problem)
    elif int(t.solution) != row[-1] + row[-2]:
        wrong.append(t.problem)
check("the grade-5 rows really are the sum of the two before", not wrong)

print()

# --- 2. Reproducible -------------------------------------------------------

print("--- Reproducible ---")
check("the same three arguments give the same task",
      tasks.make("rekenen", 3, 4242) == tasks.make("rekenen", 3, 4242))
check("a different number gives a different task",
      tasks.make("rekenen", 3, 4242) != tasks.make("rekenen", 3, 4243))
check("the same grade in a different family gives something else",
      tasks.make("code", 2, 5).problem != tasks.make("puzzel", 2, 5).problem)

# The task universe must not move with the seed of a learning run, or two
# runs can no longer be compared.
import determinism                                     # noqa: E402
before = tasks.make("rekenen", 4, 5000).problem
determinism.lock(999_999)
after = tasks.make("rekenen", 4, 5000).problem
check(
    "the tasks do not change when the learning seed changes",
    before == after,
    "otherwise a difference between two runs could be the learning or "
    "simply different sums",
)

print()

# --- 3. The benchmark is fenced off ----------------------------------------

print("--- The benchmark ---")
try:
    tasks.learning_task("rekenen", 1, tasks.TEST_UPTO - 1)
    refused = False
except ValueError as e:
    refused = "benchmark" in str(e)
check("learning a benchmark number is refused", refused,
      "contamination is thereby a programming error, not a matter of "
      "discipline")

# Fencing by number alone is not enough: the same problem can appear under
# a learning number and under a benchmark number.
texts = tasks._benchmark_of("rekenen", 1)
colliders = [n for n in range(tasks.TEST_UPTO, tasks.TEST_UPTO + 3000)
             if tasks.make("rekenen", 1, n).problem in texts]
check(
    "problems really collide across the number boundary",
    len(colliders) > 0,
    f"{len(colliders)} of the 3000 learning numbers give a problem that is "
    f"also in the benchmark — fencing by number alone would not be enough",
)

try:
    tasks.learning_task("rekenen", 1, colliders[0])
    refused = False
except ValueError as e:
    refused = "its problem is in it" in str(e)
check("such a collision is refused too, on content", refused)

series = tasks.learning_tasks("rekenen", 1, 300)
check(
    "learning_tasks delivers only clean tasks",
    not any(tasks.is_contaminated(t) for t in series) and len(series) == 300,
    "contaminated numbers are skipped instead of handed over",
)

check("the first permitted learning number works",
      tasks.learning_task("rekenen", 1, tasks.TEST_UPTO).number
      == tasks.TEST_UPTO)

bench = {t.number for t in tasks.benchmark("code", 3, 100)}
learn = {t.number for t in tasks.learning_tasks("code", 3, 100)}
check("benchmark and learning tasks overlap nowhere", not (bench & learn),
      f"benchmark 0–{max(bench)}, learning {min(learn)}–{max(learn)}")

check("the benchmark is the same every time, in the same order",
      [t.problem for t in tasks.benchmark("puzzel", 2, 50)]
      == [t.problem for t in tasks.benchmark("puzzel", 2, 50)])

print()

# --- 4. Marking ------------------------------------------------------------

print("--- Marking ---")
t = tasks.make("rekenen", 1, 7)
check("the right answer is approved", t.check(t.solution))
check("surrounding spaces do not matter", t.check(f"  {t.solution} "))
check("a wrong answer is rejected", not t.check("999999"))
check("almost right is wrong", not t.check(str(int(t.solution) + 1)),
      "a score that depends on judgement is not a measurement")

print()

# --- 5. Does the difficulty rise? ------------------------------------------
# A blunt rule of thumb — add up all the numbers in the problem — should do
# well at grade 1 and drown above it. That shows the grades really ask for
# something different, not merely something bigger.

print("--- Does the difficulty rise? ---")
print("  A rule of thumb that can only add, let loose on every grade.")
print("  Mind what this does and does not show — see the note below.")
print()


def rule_of_thumb(problem):
    return sum(int(x) for x in re.findall(r"-?\d+", problem))


scores = []
for grade in tasks.GRADES:
    probe = [tasks.make("rekenen", grade, n) for n in range(200)]
    good = sum(1 for t in probe if t.check(rule_of_thumb(t.problem)))
    scores.append(good / len(probe))
    print(f"         grade {grade}: rule of thumb scores {good / len(probe):>5.0%}")

check(
    "being able only to add takes you through grade 2, and no further",
    min(scores[:2]) > 0.3 and max(scores[2:]) < 0.1,
    "from grade 3 a different operation is needed; from 4 several in a row",
)

print()
print("         What this does NOT show: that the grades rise strictly.")
print("         Grade 2 scores higher than grade 1 here, and grade 3 is one")
print("         multiplication against one addition — a different operation,")
print("         not a heavier one. For C that is enough: the grades must be")
print("         stable and mutually distinguishable, not perfectly gauged.")

print()

# --- 6. How large is each supply? ------------------------------------------
# Important to know before phase 1: with a small supply she learns it by
# heart and you measure memory instead of ability.

print("--- How many different tasks exist? ---")
tight = []
for family in tasks.FAMILIES:
    row = []
    for grade in tasks.GRADES:
        unique = len({tasks.make(family, grade, n).problem for n in range(3000)})
        row.append(unique)
        if unique < 500:
            tight.append((family, grade, unique))
    print(f"         {family:8} " + "  ".join(f"g{g}:{u:>5}"
                                              for g, u in zip(tasks.GRADES, row)))

print()
if tight:
    print("         TIGHT — here she can learn the supply by heart:")
    for family, grade, unique in tight:
        print(f"           {family} grade {grade}: {unique} distinct problems")
    print("         Not an error, but something to know: on such a grade you")
    print("         eventually measure memory and not ability.")

check("every family has an ample supply at the highest grade",
      all(len({tasks.make(f, 5, n).problem for n in range(3000)}) > 1000
          for f in tasks.FAMILIES))

# --- answers in words (18 Aug 2026: the families zeggen and taal) -------------
print()
print("--- answers in words ---")
_w = tasks.Task(family="taal", grade=1, number=0, problem="de kat zit op de mat\nwie zit?",
                solution="kat", working="kat")
check("a solution without a number is checked on the last piece, exactly",
      _w.check("kat") and _w.check("de kat zit ; kat") and _w.check("Kat ")
      and not _w.check("de kat") and not _w.check("mat") and not _w.check("kat 1"))
_n = tasks.Task(family="rekenen", grade=1, number=0, problem="3 + 4", solution="7", working=None)
check("… and a numeric solution is still the last number, unchanged",
      _n.check("3 + 4 = 7") and _n.check("7") and not _n.check("kat")
      and not _n.check("7 ; 8"))

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
