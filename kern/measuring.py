"""
The measuring loop — measure whether she learns, and whether she forgets.

C is the part this project exists for: learning on without losing the old.
This module produces the number that settles it.

WHAT MEASURING MEANS
--------------------
Learn family A, measure. Then learn family B, measure again. What A gives
up in the process is the forgetting. Three numbers per family and grade:

    gain       = score after learning A  −  score at the start
    loss       = score after learning A  −  score after learning B
    retained   = 1 − loss / gain

`retained` is the number that counts. 1.0 means nothing of A was lost; 0.0
that it is completely gone. Without gain, retained is meaningless and is
not reported — you cannot forget what you never learned.

WHAT THE LEARNER MUST BE ABLE TO DO
-----------------------------------
Deliberately minimal, so everything fits in here — from a lookup table to
the eventual learning core:

    antwoord(taak) -> str      give an answer. Learns nothing.
    leer(taken)                learn from a series of tasks with solutions

Nothing more is needed. The measuring loop does not know and need not know
how the learning happens.

THREE RULES THAT HOLD HERE
--------------------------
1. **Measuring happens on the test set only**, never on learning tasks.
   `tasks.py` fences those numbers off, so contamination breaks here
   instead of silently continuing.
2. **Measuring never teaches.** Answering must not change the learner. Not
   enforceable from here, but it is in the test.
3. **Measurements enter the journal.** They are outcomes you do not want to
   earn twice — exactly what N says belongs there.

English successor of meetlus.py. Journal rows keep their Dutch kind and
field names ("meting", "fase", "scores") — they are her state.
"""

import tasks


def measure(learner, family, grade, count=100):
    """The score on the benchmark. A number between 0 and 1.

    If the learner can take a whole batch at once, that is used: a hundred
    tasks one by one is a hundred passes through the network, together it
    is one. That is the difference between measuring whenever you want and
    measuring you start avoiding — and "measuring is not optional".
    """
    test = tasks.benchmark(family, grade, count)
    answer_batch = (getattr(learner, "answer", None)
                    or getattr(learner, "antwoorden", None))
    if answer_batch is not None:
        given = answer_batch(test)
    else:
        answer_one = getattr(learner, "answer_one", None) or learner.antwoord
        given = [answer_one(t) for t in test]
    right = sum(1 for t, a in zip(test, given) if t.check(a))
    return right / len(test)


def measure_all(learner, families=None, grades=None, count=100):
    """The score on every combination of family and grade."""
    families = families or tasks.FAMILIES
    grades = grades or tasks.GRADES
    return {(f, g): measure(learner, f, g, count)
            for f in families for g in grades}


def _key(f, g):
    return f"{f}/{g}"


def c_measurement(learner, plan, learn_count=200, measure_count=100,
                  journal=None):
    """Run a learning plan and after every step measure what remains.

    `plan` is a list of (family, grade) in learning order. After every step
    *everything* is measured again, not just what was learned — because the
    question is precisely what happens to the rest.
    """
    learn = getattr(learner, "learn", None) or learner.leer
    log_write = None
    if journal is not None:
        log_write = getattr(journal, "write", None) or journal.schrijf

    measurements = [{"fase": "begin",
                     "scores": measure_all(learner, count=measure_count)}]
    if log_write:
        log_write("meting", fase="begin",
                  scores={_key(*k): v
                          for k, v in measurements[0]["scores"].items()})

    for family, grade in plan:
        material = tasks.learning_tasks(family, grade, learn_count)
        learn(material)
        phase = f"na {family}/{grade}"
        scores = measure_all(learner, count=measure_count)
        measurements.append({"fase": phase, "scores": scores})
        if log_write:
            log_write("meting", fase=phase,
                      scores={_key(*k): v for k, v in scores.items()})

    return {
        "plan": [list(p) for p in plan],
        "metingen": measurements,
        "vergeten": _forgotten(measurements, plan),
    }


def _forgotten(measurements, plan):
    """What was lost of what was learned earlier?

    For every step in the plan: how much that step gained, and how much of
    it was still there at the end.
    """
    start = measurements[0]["scores"]
    end = measurements[-1]["scores"]
    outcome = []

    for i, (family, grade) in enumerate(plan):
        key = (family, grade)
        after_this_step = measurements[i + 1]["scores"][key]
        gain = after_this_step - start[key]
        loss = after_this_step - end[key]

        row = {
            "familie": family,
            "graad": grade,
            "begin": start[key],
            "na_leren": after_this_step,
            "aan_het_eind": end[key],
            "winst": gain,
            "verlies": loss,
        }
        # Without gain, retained is meaningless: you cannot forget what you
        # never learned. Better nothing than a number that means nothing.
        row["behouden"] = (1 - loss / gain) if gain > 1e-9 else None
        outcome.append(row)

    return outcome


def table(outcome):
    """The outcome as a readable table."""
    rows = [
        "| familie | graad | begin | na leren | aan het eind | behouden |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in outcome["vergeten"]:
        retained = "—" if r["behouden"] is None else f"{r['behouden']:.0%}"
        rows.append(
            f"| {r['familie']} | {r['graad']} | {r['begin']:.0%} | "
            f"{r['na_leren']:.0%} | {r['aan_het_eind']:.0%} | {retained} |"
        )
    return "\n".join(rows)
