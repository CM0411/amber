"""
Exams — frozen, multiple, extensible.

Cley, 8 Aug 2026: *"in the human world you have several exams, differing in
the material they hold."* Spot on. The benchmark tested each family apart —
a hundred sums, then a hundred rows — and no real exam works like that. A
sheet mixes everything, and you must also see *which* kind you are looking
at. None of that was being measured.

THREE RULES
-----------
**An exam stores the problems themselves, not a recipe.** If
`world.make(...)` stood here, the exam would shift along whenever the
grammar is ever adjusted — and last year's marks could no longer be
compared with today's. The world may grow, an exam never.

**Exams may be added, never removed.** When her world grows, a new exam
covers the new material. The old ones stay untouched so you can look back
across the entire lifetime.

**No exam may ever be practiced on.** `material()` yields every problem
text of every exam; whoever builds study material excludes them. The same
latch that caught 789 contaminated problems out of 3000 at `taken.py` on
8 Aug 2026 — a quarter, and nobody had seen it.

English successor of proefwerken.py. Same files, same directory, same
stored keys (her state is Dutch); both sides read each other's exams.
"""

import json
import os

FOLDER = "/home/arch/amber-werk/proefwerken"


class Exam:
    def __init__(self, name, description, problems):
        self.name = name
        self.description = description
        self.problems = problems        # list of {opgave, oplossing, familie, graad}

    def __len__(self):
        return len(self.problems)

    def as_tasks(self):
        """The problems as tasks, so the measuring loop can handle them."""
        from tasks import Task
        return [Task(family=p["familie"], grade=p["graad"], number=-1,
                     problem=p["opgave"], solution=p["oplossing"])
                for p in self.problems]


def _path(name):
    return os.path.join(FOLDER, f"{name}.json")


def exists(name):
    return os.path.exists(_path(name))


def freeze(name, description, tasks_):
    """Freeze a new exam. Refuses to overwrite an existing one.

    The refusal is the whole point. An exam that can be silently overwritten
    is not a benchmark but a snapshot, and every comparison over time is
    then worthless.
    """
    os.makedirs(FOLDER, exist_ok=True)
    if exists(name):
        raise FileExistsError(
            f"exam {name!r} already exists and will not be overwritten.\n"
            f"An exam is frozen. To test different material, freeze a new "
            f"exam under its own name; the old ones remain."
        )
    content = {
        "naam": name,
        "beschrijving": description,
        "opgaven": [{"familie": t.family, "graad": t.grade,
                     "opgave": t.problem, "oplossing": t.solution}
                    for t in tasks_],
    }
    temporary = _path(name) + ".deel"
    with open(temporary, "w") as f:
        json.dump(content, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, _path(name))
    fd = os.open(FOLDER, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return len(tasks_)


def load(name):
    with open(_path(name)) as f:
        content = json.load(f)
    return Exam(content["naam"], content["beschrijving"], content["opgaven"])


def names():
    if not os.path.isdir(FOLDER):
        return []
    return sorted(n[:-5] for n in os.listdir(FOLDER) if n.endswith(".json"))


def all_exams():
    return {name: load(name) for name in names()}


_material_cache = None


def material():
    """Every problem text of every exam. This is the lock.

    Whoever builds study material passes this as `exclude`. Built once,
    because every series of study material consults it.
    """
    global _material_cache
    if _material_cache is None:
        texts = set()
        for exam in all_exams().values():
            texts.update(p["opgave"] for p in exam.problems)
        _material_cache = frozenset(texts)
    return _material_cache


def forget_material():
    """Re-read after freezing a new exam."""
    global _material_cache
    _material_cache = None


def take(learner, name=None, at_most=None):
    """Have a learner sit an exam. Returns the mark per exam.

    Measuring must never teach: only answering is used here, never
    learning.
    """
    from learning import room_for
    answer = learner.answer
    window = learner.core.window

    out = {}
    for exam_name, exam in all_exams().items():
        if name is not None and exam_name != name:
            continue
        problems = exam.as_tasks()
        if at_most and len(problems) > at_most:
            # Evenly across the whole sheet, not the first so-many.
            #
            # The problems are ordered by family and grade. The first 150
            # of `grondslag` are all code from the same corner, and then
            # you test one cell while the mark looks like the whole exam.
            # On 8 Aug 2026 that put 0% where 17% belonged.
            step = len(problems) / at_most
            problems = [problems[int(i * step)] for i in range(at_most)]
        # Per family separately, because the room to work out differs: a
        # puzzle working is around 90 characters even at depth 1. Taking
        # everything at the arithmetic measure cut the puzzles off and gave
        # them zero while she could do them.
        given = [None] * len(problems)
        per_family = {}
        for i, t in enumerate(problems):
            per_family.setdefault(t.family, []).append(i)
        for family, indices in per_family.items():
            batch = [problems[i] for i in indices]
            deepest = max(t.grade for t in batch)
            answers = answer(batch, at_most=room_for(deepest, family, window))
            for i, a in zip(indices, answers):
                given[i] = a
        right = sum(1 for t, a in zip(problems, given) if t.check(a))
        out[exam_name] = right / len(problems)
    return out
