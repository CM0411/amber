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

Two cards as two processes (16 Aug 2026 — see kern/parallel.py):

      venv/bin/torchrun --standalone --nproc_per_node=2 fase1/life.py [steps]

Both processes walk the same road; only the gradient is computed in shares
and summed. Process 0 is the one that writes (snapshot, journal, report,
prints); the other computes and stays silent, so what lands on disk looks
like one learner — which it is. Without torchrun nothing changes: one
process, DataParallel on a two-card machine.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "kern"))

import determinism                         # MUST come before torch
determinism.lock(20260808)

import bridge
import exams
import journal
import parallel
import snapshot
from learning import Learner

# Join the process group if torchrun launched us (else this returns 1 and
# everything below is the plain single-process run). Before the Learner:
# it pins this process to its card and the Learner reads that.
parallel.start()
CHIEF = parallel.chief()


def say(*args, **kwargs):
    """print, but only from the process that writes."""
    if CHIEF:
        print(*args, **kwargs)


class _Quiet:
    """The journal as the silent process sees it: every write vanishes.
    Only the chief holds the real one; two processes appending to one file
    would interleave rows and double every event."""
    def write(self, *a, **k):
        return 0

    def rest(self, *a, **k):
        pass

    def clean_up(self, *a, **k):
        pass

    def close(self):
        pass

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
EXAM_EVERY = 500
PROBLEMS_PER_EXAM = 150
FOLDER = "/home/arch/amber-werk/fase1/leven"
REPORT = "/home/arch/amber-werk/fase1/leven.md"

os.makedirs(FOLDER, exist_ok=True)
log = journal.Journal(f"{FOLDER}/logboek.jsonl") if CHIEF else _Quiet()
# Activation checkpointing (15 Aug 2026): off until a bigger net needs it.
# A machine setting, not part of her state — set AMBER_CHECKPOINTING=1 in
# the service environment when she outgrows the card. Same numbers bit for
# bit (test-checkpointing.py), ~35% more time on the learning part.
learner = Learner(batch_size=64,
                  checkpointing=os.environ.get("AMBER_CHECKPOINTING") == "1")

# --- resuming --------------------------------------------------------------
# What everything is built around: the server can drop out at night from
# heat, and then she should continue where she was instead of starting
# over. Without this, a night of work is one crash away from nothing.

BEGIN = 1
SNAPSHOT = f"{FOLDER}/momentopname.pt"
if os.path.exists(SNAPSHOT):
    content = snapshot.read(SNAPSHOT, device=learner.device)
    extra = content.get("extra") or {}
    # Take the snapshot's shape BEFORE the weights go in (15 Aug 2026): a
    # grown net has more blocks than the Learner is built with, and
    # load_state_dict would refuse it. adopt_shape grows to the snapshot's
    # depth and follows its window (both change nothing about the weights
    # — test-layer-growth.py, test-window-growth.py — and take the answer
    # copy and the memory doorway along). Run-3 snapshots lack the key:
    # then the default shape is the shape.
    vorm = extra.get("vorm")
    if vorm:
        learner.adopt_shape(bridge.translate_spec(vorm))
    BEGIN = snapshot.restore(content, learner.core, learner.optimizer,
                             learner.device) + 1
    learner.steps = BEGIN - 1
    if "geheugen" in extra:
        learner.restore(extra, step=BEGIN - 1)
        say(f"  geheugen terug: {len(learner.memory):,} herinneringen")

    state = journal.resume(FOLDER, upto_step=BEGIN)
    gap = state["gap_seconds"]
    stilte = {"rest": "rust", "incident": "incident",
              "empty": "leeg"}.get(state["silence"], state["silence"])
    say(f"HERVAT bij stap {BEGIN}. Vorige keer eindigde met '{stilte}'"
          + (f", {gap / 60:.0f} minuten geleden." if gap else "."))
    log.write("hervat", stap=BEGIN, stilte=stilte, gat_seconden=gap)

if BEGIN > STEPS:
    # Klaar is klaar: een start voorbij het doel (bv. systemd na een
    # herstart terwijl de run al af is) doet níéts — geen proefwerk, geen
    # overschreven verslag, geen extra rustmarkering. De leegloop van 12
    # aug 2026 verving het run-3-verslag door een stomp van één regel.
    say(f"run is af (stap {BEGIN - 1:,} van {STEPS:,}) — niets te doen"
          .replace(",", "."))
    log.close()
    parallel.stop()
    sys.exit(0)

# --- lessen van Cley -------------------------------------------------------
# Bezorgd op een rungrens (bezorg-brievenbus.py), soort "les" in het
# logboek. `learn_lessons` is idempotent op het regelnummer: wat al in het
# geheugen zit (het reist mee in de momentopname) wordt overgeslagen, dus
# een hervatting vanaf een oudere opname komt bit voor bit gelijk uit.
# Ná de klaar-is-klaar-grendel: een herstart van een afgelopen run doet
# níets, ook dit niet.
try:
    # journal.read geeft (regels, stilte) terug — niet alleen de regels.
    # Fout gevonden 14 aug 2026, bij de allereerste echte draai van dit
    # blok: run 5 viel er drie keer op om vóór één stap gezet was.
    _les_rows, _ = journal.read(f"{FOLDER}/logboek.jsonl")
    _les_rows = [r for r in _les_rows if r.get("soort") == "les"]
except FileNotFoundError:
    _les_rows = []
if _les_rows:
    taken, refused, once = learner.learn_lessons(_les_rows)
    if taken or refused or once:
        say(f"  lessen van Cley: {taken} het geheugen in"
              + (f", {refused} geweigerd (te lang voor de doorgang)"
                 if refused else "")
              + (f", {once} eenmalig geleerd en niet onthouden" if once else ""))
        log.write("les_geleerd", stap=BEGIN, aantal=taken,
                  geweigerd=refused, eenmalig=once)

say("=" * 72)
say("Leven in de wereld")
say("=" * 72)
say(f"{learner.core.parameter_count():,} parameters op {learner.device}")
say(f"{STEPS} stappen, herhaling {learner.replay_share:.1%}, "
      f"wereld open tot diepte {learner.deepest}")
say(f"proefwerk elke {EXAM_EVERY} stappen, "
      f"{PROBLEMS_PER_EXAM} opgaven per stuk\n")


def exam(step):
    scores = exams.take(learner, at_most=PROBLEMS_PER_EXAM)
    log.write("proefwerk", stap=step, scores=scores,
              diepste=learner.deepest)
    return scores


measurements = [(0, exam(0), learner.deepest)]
say(f"  stap {0:>5} | " + "  ".join(
    f"{n} {v:>4.0%}" for n, v in sorted(measurements[0][1].items())))

start_time = time.perf_counter()
# Tempo en resttijd over de láátste 500 stappen, niet sinds de start. Op
# 14 aug 2026 stond na 50 stappen "1614 ms/st, klaar 18:00"; de run deed
# vanaf het begin 2216 en was pas 02:15 klaar — de eerste vijftig
# stappen zijn te weinig en het lopende gemiddelde bleef daar uren aan
# hangen. 500 stappen dekken precies één proefwerk plus momentopname, dus
# elk venster telt hetzelfde. Vóór 500 stappen: wel het tempo tot nu toe
# (het rapport leest die cijfers), maar géén eindtijd — "nog ?".
WINDOW_STEPS = 500
marks = [(BEGIN - 1, start_time)]        # (stap, kloktijd) elke 50 stappen
chosen = {}
for step in range(BEGIN, STEPS + 1):
    result = learner.work(step)
    chosen[(result["family"], result["depth"])] = \
        chosen.get((result["family"], result["depth"]), 0) + 1
    log.write("stap", stap=step, familie=result["family"],
              diepte=result["depth"], score=result["score"],
              fout=result["loss"])
    if result["deeper"]:
        say(f"  stap {step:>5} | wereld open: "
              + ", ".join(f"{f} tot {d}" for f, d in result["deeper"]))
        log.write("wereld_dieper", stap=step,
                  diepste_per=result["deepest_per"])

    # Every 50 steps a sign of life: how far, how fast, how much longer.
    if step % 50 == 0:
        now = time.perf_counter()
        marks.append((step, now))
        base_step, base_time = marks[0]
        for s_, t_ in reversed(marks):
            if step - s_ >= WINDOW_STEPS:
                base_step, base_time = s_, t_
                break
        per_step = (now - base_time) / max(1, step - base_step)
        if step - base_step >= WINDOW_STEPS:
            left = (STEPS - step) * per_step
            rest = f"{int(left // 3600)}u{int(left % 3600 // 60):02d}m"
        else:
            rest = "?"
        del marks[:-(WINDOW_STEPS // 50 + 1)]
        last_score = ("--" if result["score"] is None
                      else f"{result['score']:.0%}")
        say(f"  {time.strftime('%H:%M')}  stap {step:>6}/{STEPS}"
              f"  {step / STEPS:>4.0%}"
              f"  {per_step * 1000:>4.0f} ms/st"
              f"  nog {rest}"
              f"   {result['family']}/{result['depth']}  {last_score:>4}",
              flush=True)

    if step % EXAM_EVERY == 0:
        scores = exam(step)
        measurements.append((step, scores, learner.deepest))
        elapsed = time.perf_counter() - start_time
        say(f"  stap {step:>5} | "
              + "  ".join(f"{n} {v:>4.0%}" for n, v in sorted(scores.items()))
              + f"   | diepte tot {learner.deepest}"
              + f" | {elapsed / max(1, step - BEGIN + 1) * 1000:.0f} ms/stap")
        # With two processes: are they still one learner? Compare a
        # fingerprint of weights, moments and the small state around them.
        # Drifted apart means the summed gradients were of two different
        # networks — never write that down as a snapshot; stop loudly, and
        # the service restarts from the last good one.
        if parallel.active():
            agree, seen = parallel.same(learner.fingerprint())
            if not agree:
                log.write("uiteen", stap=step, vingerafdrukken=seen)
                log.close()
                raise RuntimeError(
                    f"processen lopen uiteen bij stap {step}: {seen} — "
                    f"momentopname niet geschreven")
        if CHIEF:
            snapshot.write(
                SNAPSHOT, step, learner.core, learner.optimizer,
                determinism.state(),
                extra=learner.carry())
            log.clean_up(step)

log.rest(stap=STEPS, reden="leven klaar")
log.close()
parallel.stop()
if not CHIEF:
    sys.exit(0)          # the report below is the chief's alone

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

say("\n" + "=" * 72)
say(table)
say("=" * 72)
say(f"\nWereld open tot diepte {learner.deepest}. "
      f"Geheugen: {len(learner.memory)} herinneringen.")

most = sorted(chosen.items(), key=lambda x: -x[1])[:6]
say("\nWaar ze zelf voor koos, de zes vaakst gekozen onderwerpen:")
for (family, depth), count in most:
    say(f"  {family}/{depth}: {count}× ({count / STEPS:.0%})")

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
say(f"\nVerslag: {REPORT}")
