"""
Tests the measuring loop.

The core question: does this measurement see the difference between
something that forgets and something that does not? If it cannot, it
measures nothing, and every number that later comes out of it is
worthless — including the number this whole project revolves around.

Hence two fake learners with exactly the same curriculum, one of which
forgets everything by construction and the other nothing.

Run:  venv/bin/python kern/test-measuring.py
"""

import os
import shutil
import sys

import journal
import measuring
import fake_learners
import tasks

FOLDER = "/home/arch/amber-werk/tmp/meetlus"

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
print("Test — the measuring loop")
print("=" * 70)
print()

# --- 1. Is the benchmark truly fenced off? ---------------------------------

print("--- Is the benchmark fenced off? ---")
memorizer = fake_learners.MemorizerLearner()
memorizer.learn(tasks.learning_tasks("rekenen", 1, 500))
check(
    "who learns the learning tasks by heart scores zero on the benchmark",
    measuring.measure(memorizer, "rekenen", 1) == 0.0,
    f"{len(memorizer.table)} problems hammered in, and still zero — so the "
    f"benchmark really is unseen",
)

# And the other way round: if it does know the benchmark, it scores full.
# Without this counter-proof the above proves nothing — a learner that
# always scores zero would pass it too.
knower = fake_learners.MemorizerLearner()
knower.learn(tasks.benchmark("rekenen", 1, 100))
check("who does know the benchmark scores full",
      measuring.measure(knower, "rekenen", 1) == 1.0,
      "counter-proof: the measurement can come out high")

print()

# --- 2. Measuring must not learn -------------------------------------------

print("--- Measuring changes nothing ---")
learner = fake_learners.OneRuleLearner()
learner.learn(tasks.learning_tasks("rekenen", 3, 200))
first = measuring.measure(learner, "rekenen", 3)
second = measuring.measure(learner, "rekenen", 3)
third = measuring.measure(learner, "rekenen", 3)
check("measuring three times gives the same score three times",
      first == second == third, f"{first:.0%} every time")

print()

# --- 3. What it is all about: does the measurement see forgetting? ---------

print("--- Does it forget? ---")
print("  Two learners, the same plan: first rekenen grade 1, then rekenen "
      "grade 3.")
print()

plan = [("rekenen", 1), ("rekenen", 3)]

shutil.rmtree(FOLDER, ignore_errors=True)
os.makedirs(FOLDER, exist_ok=True)
log = journal.Journal(f"{FOLDER}/logboek.jsonl")

forgetful = measuring.c_measurement(fake_learners.OneRuleLearner(), plan,
                                    journal=log)
solid = measuring.c_measurement(fake_learners.RulePerKindLearner(), plan,
                                journal=log)
log.close()

r1 = forgetful["vergeten"][0]        # rekenen grade 1, forgetful learner
r2 = solid["vergeten"][0]            # rekenen grade 1, solid learner

print("  One rule for everything:")
print("  " + measuring.table(forgetful).replace("\n", "\n  "))
print()
print("  A rule per kind:")
print("  " + measuring.table(solid).replace("\n", "\n  "))
print()

check(
    "both really learn grade 1",
    r1["winst"] > 0.4 and r2["winst"] > 0.4,
    f"gain {r1['winst']:.0%} and {r2['winst']:.0%} — without gain, "
    f"forgetting says nothing. Around 50% is the ceiling here: rekenen "
    f"grade 1 has four forms and these learners hold only one rule",
)
check(
    "the one-rule learner loses grade 1 when it learns grade 3",
    r1["behouden"] is not None and r1["behouden"] < 0.1,
    f"retained: {r1['behouden']:.0%}",
)
check(
    "the rule-per-kind learner loses nothing",
    r2["behouden"] is not None and r2["behouden"] > 0.95,
    f"retained: {r2['behouden']:.0%}",
)
check(
    "so the measurement sees the difference between forgetting and not",
    r2["behouden"] - r1["behouden"] > 0.8,
    "this is the property everything rests on; without it C measures "
    "nothing",
)

print()

# --- 4. Nothing learned is not forgetting ----------------------------------

print("--- Where nothing was learned ---")
code_rows = [r for r in forgetful["metingen"][-1]["scores"] if r[0] == "code"]
check("the code family is measured too", len(code_rows) == len(tasks.GRADES))

# Grade 5 and not grade 1: `a = X / b = Y / print(a + b)` is an addition in
# disguise, and these little rules catch that. Grade 5 is a function in a
# loop and no rule over the loose numbers comes near it.
code_only = measuring.c_measurement(fake_learners.OneRuleLearner(),
                                    [("code", 5)])
rc = code_only["vergeten"][0]
check(
    "without gain no 'retained' is invented",
    rc["winst"] <= 1e-9 and rc["behouden"] is None,
    "you cannot forget what you never learned — better nothing than a "
    "number that means nothing",
)

print()

# --- 5. Everything is measured, not only what was just learned -------------

print("--- What gets measured ---")
everything = forgetful["metingen"][0]["scores"]
check("every family and grade appears in every measurement",
      len(everything) == len(tasks.FAMILIES) * len(tasks.GRADES),
      f"{len(everything)} combinations per phase — the question is exactly "
      f"what happens to the rest")
check("there is a measurement before learning and after every step",
      len(forgetful["metingen"]) == len(plan) + 1)

print()

# --- 6. The measurements are in the journal --------------------------------

print("--- Recorded ---")
rows, _ = journal.read(f"{FOLDER}/logboek.jsonl")
measurements = [r for r in rows if r["soort"] == "meting"]
check(
    "every measurement was written out",
    len(measurements) == 2 * (len(plan) + 1),
    f"{len(measurements)} rows — outcomes you do not want to earn twice",
)
check("and the scores are in them", "rekenen/1" in measurements[-1]["scores"])

shutil.rmtree(FOLDER, ignore_errors=True)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
