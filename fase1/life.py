"""
Leven in de wereld — living in the world: she picks her own work, and sits
periodic exams.

This is the loop as intended: she chooses what to work on, draws her
material from the grammar instead of a catalogue, and the world opens one
step deeper as soon as she can handle the current edge.

Every step is: pick a topic, attempt a batch of tasks, remember what it
was, learn from it. The attempting costs roughly two thirds of the time
per step — she has to answer before there is anything to mark. That is
the price of "what she does unprompted is the signal": without an attempt
nobody knows where she stands.

Every so many steps the three frozen exams are taken. They are never
practised on — `world.study_series` excludes those problems.

The printed lines, the report and the journal keys are deliberately
Dutch: they are her state and Cley's reading material, and the watchers
(server, rapport, wachter) parse them. Code is English, her state is
Dutch — the migration rule of 10 Aug 2026.

Run:  venv/bin/python fase1/life.py [steps]
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinism                         # MUST come before torch
determinism.lock(20260808)

import exams
import journal
import snapshot
from learning import Learner

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
EXAM_EVERY = 500
PROBLEMS_PER_EXAM = 150
FOLDER = "/home/arch/amber-werk/fase1/leven"
REPORT = "/home/arch/amber-werk/fase1/leven.md"

os.makedirs(FOLDER, exist_ok=True)
log = journal.Journal(f"{FOLDER}/logboek.jsonl")
learner = Learner(batch_size=64)

# --- resuming --------------------------------------------------------------
# What everything is built around: the server can drop out at night from
# heat, and then she should continue where she was instead of starting
# over. Without this, a night of work is one crash away from nothing.

BEGIN = 1
SNAPSHOT = f"{FOLDER}/momentopname.pt"
if os.path.exists(SNAPSHOT):
    content = snapshot.read(SNAPSHOT, device=learner.device)
    BEGIN = snapshot.restore(content, learner.core, learner.optimizer,
                             learner.device) + 1
    learner.steps = BEGIN - 1
    extra = content.get("extra") or {}
    if "geheugen" in extra:
        learner.restore(extra)
        print(f"  geheugen terug: {len(learner.memory):,} herinneringen")

    state = journal.resume(FOLDER, upto_step=BEGIN)
    gap = state["gap_seconds"]
    stilte = {"rest": "rust", "incident": "incident",
              "empty": "leeg"}.get(state["silence"], state["silence"])
    print(f"HERVAT bij stap {BEGIN}. Vorige keer eindigde met '{stilte}'"
          + (f", {gap / 60:.0f} minuten geleden." if gap else "."))
    log.write("hervat", stap=BEGIN, stilte=stilte, gat_seconden=gap)

print("=" * 72)
print("Leven in de wereld")
print("=" * 72)
print(f"{learner.core.parameter_count():,} parameters op {learner.device}")
print(f"{STEPS} stappen, herhaling {learner.replay_share:.1%}, "
      f"wereld open tot diepte {learner.deepest}")
print(f"proefwerk elke {EXAM_EVERY} stappen, "
      f"{PROBLEMS_PER_EXAM} opgaven per stuk\n")


def exam(step):
    scores = exams.take(learner, at_most=PROBLEMS_PER_EXAM)
    log.write("proefwerk", stap=step, scores=scores,
              diepste=learner.deepest)
    return scores


measurements = [(0, exam(0), learner.deepest)]
print(f"  stap {0:>5} | " + "  ".join(
    f"{n} {v:>4.0%}" for n, v in sorted(measurements[0][1].items())))

start_time = time.perf_counter()
chosen = {}
for step in range(BEGIN, STEPS + 1):
    result = learner.work(step)
    chosen[(result["family"], result["depth"])] = \
        chosen.get((result["family"], result["depth"]), 0) + 1
    log.write("stap", stap=step, familie=result["family"],
              diepte=result["depth"], score=result["score"],
              fout=result["loss"])
    if result["deeper"]:
        print(f"  stap {step:>5} | wereld open: "
              + ", ".join(f"{f} tot {d}" for f, d in result["deeper"]))
        log.write("wereld_dieper", stap=step,
                  diepste_per=result["deepest_per"])

    # Every 50 steps a sign of life: how far, how fast, how much longer.
    if step % 50 == 0:
        elapsed = time.perf_counter() - start_time
        per_step = elapsed / (step - BEGIN + 1)
        left = (STEPS - step) * per_step
        last_score = ("--" if result["score"] is None
                      else f"{result['score']:.0%}")
        print(f"  {time.strftime('%H:%M')}  stap {step:>6}/{STEPS}"
              f"  {step / STEPS:>4.0%}"
              f"  {per_step * 1000:>4.0f} ms/st"
              f"  nog {int(left // 3600)}u{int(left % 3600 // 60):02d}m"
              f"   {result['family']}/{result['depth']}  {last_score:>4}",
              flush=True)

    if step % EXAM_EVERY == 0:
        scores = exam(step)
        measurements.append((step, scores, learner.deepest))
        elapsed = time.perf_counter() - start_time
        print(f"  stap {step:>5} | "
              + "  ".join(f"{n} {v:>4.0%}" for n, v in sorted(scores.items()))
              + f"   | diepte tot {learner.deepest}"
              + f" | {elapsed / step * 1000:.0f} ms/stap")
        snapshot.write(
            SNAPSHOT, step, learner.core, learner.optimizer,
            determinism.state(),
            extra=learner.carry())
        log.clean_up(step)

log.rest(stap=STEPS, reden="leven klaar")
log.close()

# --- report ----------------------------------------------------------------

names = sorted(measurements[0][1])
head = ("| stap | " + " | ".join(f"proefwerk {n}" for n in names)
        + " | wereld open tot |")
lines = [head, "|---:|" + "---:|" * (len(names) + 1)]
for step, scores, deepest in measurements:
    lines.append(f"| {step} | "
                 + " | ".join(f"{scores[n]:.0%}" for n in names)
                 + f" | diepte {deepest} |")
table = "\n".join(lines)

print("\n" + "=" * 72)
print(table)
print("=" * 72)
print(f"\nWereld open tot diepte {learner.deepest}. "
      f"Geheugen: {len(learner.memory)} herinneringen.")

most = sorted(chosen.items(), key=lambda x: -x[1])[:6]
print("\nWaar ze zelf voor koos, de zes vaakst gekozen onderwerpen:")
for (family, depth), count in most:
    print(f"  {family}/{depth}: {count}× ({count / STEPS:.0%})")

with open(REPORT, "w") as f:
    f.write("# Leven in de wereld\n\n")
    f.write(f"{STEPS} stappen, herhaling {learner.replay_share:.1%}, "
            f"partij {learner.batch_size}. Ze kiest zelf waar ze aan werkt.\n\n")
    f.write("## Proefwerken over de tijd\n\n" + table + "\n\n")
    f.write(f"Wereld open tot diepte {learner.deepest} "
            f"(begonnen bij 3).\n\n## Waar ze zelf voor koos\n\n")
    for (family, depth), count in most:
        f.write(f"- {family}/{depth}: {count}× ({count / STEPS:.0%})\n")
    f.flush()
    os.fsync(f.fileno())
print(f"\nVerslag: {REPORT}")
