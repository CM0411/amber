"""
Tasks — the measurement rig of phase 1.

"Measuring is not optional. Every task gets a family and a difficulty grade
from day one. Without that you cannot later measure whether she forgets, and
then you do not know whether the system works."

Three families, as fixed: **code, rekenen (arithmetic), puzzel (puzzle).**
The family names — like every task text — stay Dutch on purpose: they are
data in her checkpoints, her memories and the frozen exams, and she is a
Dutch-speaking agent. The code around her world is English; the world itself
speaks Dutch.

FOUR CHOICES FIXED HERE
-----------------------
**1. Tasks are made, never stored.** A task follows entirely from
`(family, grade, number)`. So there is no problem file that can go stale,
drift between machines, or half-survive a move. Task 400 of family
"rekenen" grade 3 is the same task on another card five years from now.

**2. The task seed is separate from the learning seed.** If the task
universe moved along with a learning run's seed, two runs could no longer be
compared — you would not know whether a difference came from the learning or
from different sums. Hence its own fixed constant that never changes.

**3. The test set is fenced off in code, not by agreement — and by content,
not just by number.** Numbers below TEST_UPTO are the benchmark. Fencing by
number alone is not enough: the same problem can surface under a learning
number and a benchmark number. Different numbers, same sum — and whoever
memorizes their learning tasks scores benchmark points without being able to
do anything. So the problem text is compared too. Found on 8 Aug 2026
because a learner that does nothing but memorize did not score zero. As with
T and U: once the benchmark is contaminated the measurement is gone for
good, and that is not something to leave to discipline.

**4. Grading is exact.** No "almost right". Every family produces an answer
that can be compared literally, because a score that depends on judgement is
not a measurement.

THE DIFFICULTY GRADE
--------------------
Grades 1 through 5, increasing in the number and weight of operations.

Honest about what that is not: **it is not a strictly ordered scale.**
Grade 3 in arithmetic is one multiplication and grade 2 one addition with
bigger numbers — a different operation, not provably a heavier one. For what
the grade serves that is fine: for C you want to know whether grade 2 slips
while grade 4 improves, and for that the grades only need to be **stable**
and **mutually distinguishable** — not perfectly calibrated. What is hard:
grades 4 and 5 demand several operations in a row and are thereby provably
heavier than 1 through 3.

English successor of taken.py; toets-migratie.py enforces that both build
bit-for-bit identical tasks.
"""

import re
from dataclasses import dataclass

FAMILIES = ("code", "rekenen", "puzzel")
GRADES = (1, 2, 3, 4, 5)

# Numbers 0 through 199 are the benchmark and are never learned.
#
# Deliberately not wider. The benchmark is fenced off by content too, and
# every problem it occupies is one that can no longer be learned. In the
# tightest families — rekenen grade 1 is single digits and naturally has
# only a thousand-odd — a benchmark of a thousand would eat most of the
# study material.
TEST_UPTO = 200

# Fixed, and never changes. See choice 2 above.
TASK_SEED = 0x416D626572          # "Amber"

_MASK64 = (1 << 64) - 1


def _mix(x):
    """SplitMix64 — the same mixer as in determinism.py.

    Deliberately not hash() or random: those are not guaranteed equal across
    Python versions or machines, and then the task universe silently shifts
    beneath your measurements.
    """
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return (z ^ (z >> 31)) & _MASK64


class Picker:
    """A tiny random-drawer on SplitMix64.

    Own implementation rather than random.Random, for the same reason as
    above: portability across versions and machines. What comes out of this
    must still be exactly the same years from now.

    The Dutch method names remain as aliases until the migration completes,
    so Dutch and English modules can hand pickers to each other.
    """

    def __init__(self, seed):
        self._s = seed & _MASK64

    def _next(self):
        self._s = _mix(self._s)
        return self._s

    def integer(self, low, high):
        """An integer in [low, high]."""
        return low + self._next() % (high - low + 1)

    def choice(self, options):
        return options[self._next() % len(options)]

    # migration aliases — drop when the Dutch modules are gone
    geheel = integer
    keuze = choice


def _seed_of(family, grade, number):
    core = _mix(TASK_SEED ^ _mix(FAMILIES.index(family) * 1_000_003))
    return _mix(core ^ _mix(grade * 7919 + number))


_NUMBER = re.compile(r"-?\d+")


@dataclass(frozen=True)
class Task:
    family: str
    grade: int
    number: int
    problem: str
    solution: str
    working: str = None

    @property
    def is_benchmark(self):
        return self.number < TEST_UPTO

    def to_learn(self):
        """What she is expected to write: the working when there is one.

        Computing `13 * 8 * 11` in one go must happen in a single pass
        through the network, and there is no room for that. A person writes
        `13 * 8 = 104` and then `104 * 11 = 1144`. On 8 Aug 2026 that proved
        to be the difference between 4% and usable: without intermediate
        steps she was systematically just off — she estimated, she did not
        compute.
        """
        return self.working or self.solution

    def check(self, answer):
        """The last number she wrote, against the solution.

        So working out is allowed. What counts is where she lands — the last
        number. For tasks without a working nothing changes: that single
        number is the answer, and the frozen exams keep working.
        """
        found = _NUMBER.findall(str(answer))
        if not found:
            return False
        right = _NUMBER.findall(self.solution)
        return bool(right) and found[-1] == right[-1]

    # --- migration aliases — drop when the Dutch modules are gone ----------

    @property
    def familie(self):
        return self.family

    @property
    def graad(self):
        return self.grade

    @property
    def nummer(self):
        return self.number

    @property
    def opgave(self):
        return self.problem

    @property
    def oplossing(self):
        return self.solution

    @property
    def uitwerking(self):
        return self.working

    @property
    def is_meetlat(self):
        return self.is_benchmark

    def te_leren(self):
        return self.to_learn()

    def nakijk(self, answer):
        return self.check(answer)


# --- rekenen (arithmetic) ----------------------------------------------------
# Increasing in the number of operations and the size of the numbers. The
# generated texts are identical to taken.py's, character for character.

def _arithmetic(t, grade):
    if grade == 1:
        # Single digits remain this grade's signature, but with two or three
        # terms and with plus and minus. Just a+b would yield 81 problems and
        # she knows those after one afternoon.
        a, b = t.integer(1, 9), t.integer(1, 9)
        form = t.choice(("+", "-", "+3", "-3"))
        if form == "+":
            return f"{a} + {b}", a + b
        if form == "-":
            return f"{a} - {b}", a - b
        c = t.integer(1, 9)
        if form == "+3":
            return f"{a} + {b} + {c}", a + b + c
        return f"{a} + {b} - {c}", a + b - c
    if grade == 2:
        a, b = t.integer(10, 99), t.integer(10, 99)
        if t.choice((True, False)):
            return f"{a} + {b}", a + b
        return f"{a} - {b}", a - b
    if grade == 3:
        a, b = t.integer(2, 99), t.integer(2, 19)
        return f"{a} * {b}", a * b
    if grade == 4:
        a, b, c = t.integer(2, 25), t.integer(2, 19), t.integer(1, 99)
        if t.choice((True, False)):
            return f"{a} * {b} + {c}", a * b + c
        return f"{a} * {b} - {c}", a * b - c
    a, b, c, d = (t.integer(2, 40), t.integer(1, 40),
                  t.integer(2, 12), t.integer(1, 60))
    return f"({a} + {b}) * {c} - {d}", (a + b) * c - d


# --- puzzel (puzzle) ---------------------------------------------------------
# One kind: continue a row. Rising from a fixed difference to a rule you only
# find by looking two steps back.

def _puzzle(t, grade):
    if grade == 1:
        # Falling rows too, or "it goes up" is already half the solution.
        start, step = t.integer(1, 99), t.integer(2, 19)
        if t.choice((True, False)):
            step = -step
        row = [start + i * step for i in range(5)]
    elif grade == 2:
        start, factor = t.integer(1, 150), t.integer(2, 6)
        length = t.choice((4, 5))
        row = [start * factor**i for i in range(length)]
    elif grade == 3:
        # Two rows woven together.
        a, sa = t.integer(1, 15), t.integer(2, 7)
        b, sb = t.integer(20, 40), t.integer(2, 7)
        row = []
        for i in range(3):
            row.append(a + i * sa)
            row.append(b + i * sb)
        row = row[:6]
    elif grade == 4:
        # The difference itself grows: second order.
        start, step, growth = t.integer(1, 60), t.integer(1, 15), t.integer(1, 9)
        row, value, current = [], start, step
        for _ in range(5):
            row.append(value)
            value += current
            current += growth
    else:
        # Every number is the sum of the two before it.
        a, b = t.integer(1, 40), t.integer(1, 40)
        row = [a, b]
        for _ in range(4):
            row.append(row[-1] + row[-2])

    following = _next_of(row, grade)
    shown = ", ".join(str(x) for x in row)
    return f"Zet voort: {shown}, ?", following


def _next_of(row, grade):
    if grade == 1:
        return row[-1] + (row[1] - row[0])
    if grade == 2:
        return row[-1] * (row[1] // row[0])
    if grade == 3:
        return row[-2] + (row[2] - row[0])
    if grade == 4:
        first = [row[i + 1] - row[i] for i in range(len(row) - 1)]
        second = first[1] - first[0]
        return row[-1] + first[-1] + second
    return row[-1] + row[-2]


# --- code --------------------------------------------------------------------
# First form: "what does this print?" — the program is built together with its
# outcome, so nothing needs executing to know the answer. Exact and safe.
# Having her write code herself is a later form; that first needs something
# that can write code.

def _code(t, grade):
    if grade == 1:
        a, b = t.integer(1, 99), t.integer(1, 99)
        if t.choice((True, False)):
            return f"a = {a}\nb = {b}\nprint(a + b)", a + b
        return f"a = {a}\nb = {b}\nprint(a - b)", a - b
    if grade == 2:
        a, b = t.integer(1, 99), t.integer(1, 99)
        program = (f"a = {a}\nb = {b}\n"
                   f"if a > b:\n    print(a - b)\nelse:\n    print(b - a)")
        return program, abs(a - b)
    if grade == 3:
        # The loop itself varies too, not just its numbers — otherwise it is
        # one shape with a different digit and she memorizes the shape.
        n, start = t.integer(3, 20), t.integer(0, 50)
        form = t.choice(("i", "2i", "i2"))
        if form == "i":
            body, outcome = "totaal += i", start + sum(range(1, n + 1))
        elif form == "2i":
            body, outcome = "totaal += i * 2", start + sum(2 * i for i in range(1, n + 1))
        else:
            body, outcome = "totaal += i * i", start + sum(i * i for i in range(1, n + 1))
        program = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
                   f"    {body}\nprint(totaal)")
        return program, outcome
    if grade == 4:
        numbers = [t.integer(1, 40) for _ in range(t.integer(4, 8))]
        threshold = t.integer(5, 30)
        if t.choice((True, False)):
            program = (f"getallen = {numbers}\n"
                       f"print(len([x for x in getallen if x > {threshold}]))")
            return program, len([x for x in numbers if x > threshold])
        program = (f"getallen = {numbers}\n"
                   f"print(sum([x for x in getallen if x > {threshold}]))")
        return program, sum(x for x in numbers if x > threshold)
    n, f, k = t.integer(2, 15), t.integer(2, 20), t.integer(0, 9)
    program = (f"def f(x):\n    return x * {f} + {k}\n\n"
               f"totaal = 0\nfor i in range(1, {n + 1}):\n"
               f"    totaal += f(i)\nprint(totaal)")
    return program, sum(i * f + k for i in range(1, n + 1))


_MAKERS = {"rekenen": _arithmetic, "puzzel": _puzzle, "code": _code}


def make(family, grade, number):
    """Make one task. Fully determined by the three arguments."""
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; choose from {FAMILIES}")
    if grade not in GRADES:
        raise ValueError(f"grade {grade} does not exist; choose from {GRADES}")
    if number < 0:
        raise ValueError("number must be zero or higher")

    t = Picker(_seed_of(family, grade, number))
    problem, solution = _MAKERS[family](t, grade)
    return Task(family=family, grade=grade, number=number,
                problem=problem, solution=str(solution))


_benchmark_texts = {}


def _benchmark_of(family, grade):
    """The problem texts the benchmark occupies. Built once."""
    key = (family, grade)
    if key not in _benchmark_texts:
        _benchmark_texts[key] = frozenset(
            make(family, grade, n).problem for n in range(TEST_UPTO)
        )
    return _benchmark_texts[key]


def is_contaminated(task):
    """Does this problem also occur in the benchmark?

    By number a task can fall outside the benchmark and by text still sit in
    it — the same sum under another number. Learning such tasks scores
    benchmark points without being able to do anything.
    """
    return task.problem in _benchmark_of(task.family, task.grade)


def learning_task(family, grade, number):
    """A task to learn from. Refuses anything that touches the benchmark.

    This is the latch behind choice 3: contamination is an error that breaks
    immediately, not something discovered months later when the measurement
    is already worthless. For a series use `learning_tasks()` — it skips
    contaminated tasks instead of tripping over them.
    """
    if number < TEST_UPTO:
        raise ValueError(
            f"number {number} belongs to the benchmark (everything below "
            f"{TEST_UPTO}) and must never be learned.\n"
            f"Use numbers from {TEST_UPTO} up, or make() when you knowingly "
            f"want to look at a benchmark task."
        )
    task = make(family, grade, number)
    if is_contaminated(task):
        raise ValueError(
            f"{family} grade {grade} number {number} falls outside the "
            f"benchmark by number, but its problem is in it:\n"
            f"  {task.problem!r}\n"
            f"Learning it contaminates the measurement. Use learning_tasks(), "
            f"which skips such tasks."
        )
    return task


def benchmark(family, grade, count=100):
    """The benchmark. Always the same tasks, in the same order."""
    if count > TEST_UPTO:
        raise ValueError(f"the benchmark only has {TEST_UPTO} tasks per grade")
    return [make(family, grade, n) for n in range(count)]


def learning_tasks(family, grade, count, start=TEST_UPTO):
    """A series of learning tasks. Contaminated tasks are skipped.

    Searches on until there are `count` clean tasks. If that runs too far,
    this family and grade's supply is too small for what is asked, and it
    says so instead of searching forever.
    """
    found = []
    number = start
    bound = start + count * 20 + 1000
    while len(found) < count:
        if number > bound:
            raise ValueError(
                f"{family} grade {grade}: not enough clean learning tasks.\n"
                f"{len(found)} of the requested {count} found between "
                f"{start} and {number}. This grade's supply is too small "
                f"beside a benchmark of {TEST_UPTO}."
            )
        task = make(family, grade, number)
        if not is_contaminated(task):
            found.append(task)
        number += 1
    return found
