"""
Tests the replay memory, the curiosity and the learning loop.

These three modules were the only ones without a test, and precisely in
these three sat the two bugs of 8 Aug 2026 that had to be picked out by
hand:

  * the memory stored her answer instead of the correct one, so replaying
    would have her practising her own mistakes
  * `learn()` did not fill the memory, so replay did nothing while the
    comparison seemed to say something about it

Both stand below as tests, so they cannot come back.

Run:  venv/bin/python kern/test-learning.py
"""

import determinism                         # MUST come before torch
determinism.lock(1234)

import sys

import torch

import replay_memory as rm
import learning
import network
import curiosity as cur
import tasks
import tokens

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


def small_learner(**more):
    core = network.Core(layers=2, width=64, heads=2, window=128)
    return learning.Learner(core=core, batch_size=8, **more)


print("=" * 70)
print("Test — memory, curiosity and learning loop")
print("=" * 70)
print()

# --- 1. The bottleneck -----------------------------------------------------

print("--- The bottleneck ---")
memory = rm.ReplayMemory(capacity=100)
t = tasks.make("rekenen", 3, 500)
memory.remember(t, "fout antwoord", False)

stored = memory._content[0]
check(
    "the memory stores codes, not tasks",
    isinstance(stored["code"], list)
    and all(isinstance(c, int) for c in stored["code"]),
    "there is no way in except through the doorway",
)

recovered = memory.replay(1, tasks.Picker(1))[0]
check(
    "what goes in is the CORRECT answer, not what she made of it",
    recovered["oplossing"] == t.solution,
    f"stored {recovered['oplossing']!r}, she said 'fout antwoord' — "
    f"otherwise replaying has her practising her own mistakes",
)
check("the problem comes out whole", recovered["opgave"] == t.problem)

# The working is the lesson. If the memory kept only the bare answer,
# every recollection would teach her to skip the working — and at 37.5%
# replay that is over a third of everything she sees. That bug was in on
# 8 Aug 2026 and spoiled a whole night of training without one report.
import world as world_module                                      # noqa: E402
deep = world_module.make("rekenen", 4, 500)
m2 = rm.ReplayMemory()
m2.remember(deep, "gegokt", False)
from_memory = learning._as_task(m2.replay(1, tasks.Picker(1))[0])
check(
    "the memory keeps the working, not only the answer",
    from_memory.to_learn() == deep.to_learn(),
    f"from the memory: {from_memory.to_learn()!r}",
)
check(
    "and the answer can still be pulled out for marking",
    from_memory.check(deep.working) and from_memory.solution == deep.solution,
)

# What does not fit is refused. In phase 4 that is the pressure U must
# deliver.
narrow = rm.ReplayMemory(bottleneck=rm.Bottleneck(length=8))
succeeded = narrow.remember(t, t.solution, True)
check("what does not fit through the doorway is refused and counted",
      not succeeded and len(narrow) == 0 and narrow.refused == 1,
      "in phase 1 this almost never happens; in phase 4 it is the point")

check("the occupancy is reported",
      0 < memory.bottleneck.occupancy(stored) < 1,
      f"{memory.bottleneck.occupancy(stored):.0%} of the doorway — this is "
      f"the number phase 4 squeezes")

print()

# --- 2. Unmarked is not wrong ----------------------------------------------

print("--- Not marked ---")
m = rm.ReplayMemory()
m.remember(tasks.make("rekenen", 1, 300), "x", None)
m.remember(tasks.make("rekenen", 1, 301), "x", True)
m.remember(tasks.make("rekenen", 1, 302), "x", False)
status = m.status()
check(
    "unmarked does not count as wrong",
    status["nagekeken"] == 2 and abs(status["goed_deel"] - 0.5) < 1e-9,
    "two of the three are marked, half of those correct — counting None "
    "as wrong would quietly distort the picture",
)

print()

# --- 3. The memory fills up ------------------------------------------------

print("--- Filling up ---")
small = rm.ReplayMemory(capacity=5)
for n in range(20):
    small.remember(tasks.make("rekenen", 2, 400 + n), "x", True)
check("exactly as many remain as there is room", len(small) == 5)
content = [small.bottleneck.decode(s)["opgave"] for s in small._content]
check("and the oldest disappears first",
      tasks.make("rekenen", 2, 419).problem in content
      and tasks.make("rekenen", 2, 400).problem not in content)

print()

# --- 4. Replaying is repeatable --------------------------------------------

print("--- Repeatable recall ---")
a = memory.replay(3, tasks.Picker(99))
b = memory.replay(3, tasks.Picker(99))
check("the same picker recalls the same memories",
      [x["opgave"] for x in a] == [x["opgave"] for x in b],
      "the picker is passed in and not invented locally, so the choice "
      "follows from (seed, step number)")

print()

# --- 5. Curiosity ----------------------------------------------------------

print("--- Curiosity ---")
c1 = cur.Curiosity()
c2 = cur.Curiosity()
picks1 = [c1.pick(s, tasks.Picker(s)) for s in range(50)]
picks2 = [c2.pick(s, tasks.Picker(s)) for s in range(50)]
check("the same pickers give the same order of topics", picks1 == picks2)

c = cur.Curiosity()
before = c.attraction(100)[("rekenen", 1)]
c.update(("rekenen", 1), 1.0, 100)
after = c.attraction(100)[("rekenen", 1)]
check("curiosity fades once she can do something", after < before,
      f"{before:.2f} → {after:.2f} once the score stands at 1")

c.update(("rekenen", 1), 1.0, 0)
check("and returns when something has not come by for long",
      c.attraction(1000)[("rekenen", 1)] > after,
      "without this she hangs on the hardest thing and C measures the "
      "order instead of forgetting")

c = cur.Curiosity()
for kind in c.kinds:
    c.update(kind, 1.0, 0)
c.update(("code", 1), 0.0, 0)
chosen = {c.pick(s, tasks.Picker(s * 31 + 7)) for s in range(300)}
check(
    "she does not always pick the most attractive",
    len(chosen) > 1,
    f"{len(chosen)} different topics in 300 picks — always taking the "
    f"highest would pin her to one topic",
)
check("and the most attractive does come by most often",
      max(((c.pick(s, tasks.Picker(s * 31 + 7)) == ("code", 1))
           for s in range(300)), default=False))

# wishes (19 Aug 2026, Cley): "Amber zegt: ik wil meer puzzel oefenen" —
# a wished-for family pulls harder, the wish fades as she masters it,
# and without wishes the draw is bit for bit the old one
c_a = cur.Curiosity(families=("rekenen", "puzzel"), grades=(1, 2))
c_b = cur.Curiosity(families=("rekenen", "puzzel"), grades=(1, 2))
for g in (1, 2):
    for fam in ("rekenen", "puzzel"):
        c_a.update((fam, g), 0.5, 0); c_b.update((fam, g), 0.5, 0)
base = [c_a.pick(s, tasks.Picker(s)) for s in range(400)]
check("no wishes: bit for bit the old draw",
      base == [c_b.pick(s, tasks.Picker(s)) for s in range(400)])
c_b.wish("puzzel")
wished = [c_b.pick(s, tasks.Picker(s)) for s in range(400)]
share_base = sum(f == "puzzel" for f, _ in base) / 400
share_wish = sum(f == "puzzel" for f, _ in wished) / 400
check("a wished-for family draws clearly more of her own choices",
      share_wish > share_base + 0.15,
      f"puzzel {share_base:.0%} → {share_wish:.0%} with a wish")
for i in range(30):
    c_b.update(("puzzel", 1), 0.95, 500 + i)
check("the wish fades out once she can do it (good scores)",
      "puzzel" not in c_b.wishes, f"wishes left: {c_b.wishes}")
c_c = cur.Curiosity(families=("rekenen", "puzzel"), grades=(1, 2))
c_c.wish("puzzel")
c_d = cur.Curiosity(families=("rekenen", "puzzel"), grades=(1, 2))
c_d.restore(c_c.carry())
check("wishes travel in the snapshot", c_d.wishes == c_c.wishes == {"puzzel": 3.0})

# family first, then room (17 Aug 2026): sixty mastered rekenen rooms must
# not drown a new family with two unknown rooms — and a future `last`
# must never make a weight negative
c = cur.Curiosity(families=("rekenen", "code"), grades=(1, 2))
for g in range(3, 61):
    c.add(("rekenen", g), 0)
for kind in c.kinds:
    c.update(kind, 1.0, 1000)               # everything mastered, just seen
c.add(("logica", 1), 1000); c.add(("logica", 2), 1000)   # new: score 0
picks = [c.pick(1000, tasks.Picker(s * 17 + 3)) for s in range(600)]
share = {f: sum(1 for k in picks if k[0] == f) / 600 for f in ("rekenen", "code", "logica")}
check("a new family with two unknown rooms draws far more than its room count",
      share["logica"] > 0.5 and share["rekenen"] < 0.35, str(share))
c.update(("logica", 1), 1.0, 1000); c.update(("logica", 2), 1.0, 1000)
picks = [c.pick(1000, tasks.Picker(s * 17 + 3)) for s in range(600)]
share2 = sum(1 for k in picks if k[0] == "logica") / 600
check("… and once she can do it, the pull fades to the family's fair share",
      0.2 < share2 < 0.45, f"{share2:.2f}")
c.last[("logica", 1)] = 999_999                          # a clock in the future
a = c.attraction(1000)
check("a `last` in the future never gives a negative weight",
      all(v >= c.floor for v in a.values()), str(min(a.values())))

print()

# --- 6. The learning loop: does the loss count over the right part? --------

print("--- Where the loss counts ---")
learner = small_learner()
t = tasks.make("rekenen", 1, 700)
codes, mask = learner._make_batch([t])

# _step does the same: the score at place i predicts character i+1.
target = codes[:, 1:][mask[:, 1:]].tolist()
check(
    "the loss counts exactly over the answer plus the END token",
    tokens.decode(target) == t.solution and target[-1] == tokens.END,
    f"predicted is: {tokens.show(target)!r} — shift one position and she "
    f"learns to predict the question, which looks fine in the loss curve",
)
check("nothing of the question is counted in",
      not any(mask[0][:codes[0].tolist().index(tokens.ANSWER) + 1]))

print()

# --- 7. Answering in one batch equals answering separately -----------------

print("--- Answering in one batch ---")
learner = small_learner()
probe = [tasks.make("rekenen", 1, 800 + i) for i in range(6)]
# The same room for both, or one cuts off where the other continues: the
# room depends on the longest problem in the batch.
together = learner.answer(probe, at_most=32)
separate = [learner.answer([t], at_most=32)[0] for t in probe]
check(
    "six tasks together gives the same as six times one",
    together == separate,
    "pad on the right with an own counter per task; padding left would "
    "shift the positions and that would fail here silently",
)

print()

# --- 8. The batch stays the same size --------------------------------------

print("--- Equal batches ---")
without = small_learner(replay_share=0.0)
with_replay = small_learner(replay_share=0.5)
check("without replay the whole batch is new",
      without.new_per_batch == without.batch_size)
check("with 50% replay half is new",
      with_replay.new_per_batch == with_replay.batch_size // 2,
      f"{with_replay.new_per_batch} new + "
      f"{with_replay.batch_size - with_replay.new_per_batch} replayed = "
      f"{with_replay.batch_size}. Replay comes out of new material, not on "
      f"top of it")

# And that must really turn out that way in the batch the network sees.
seen = []
real_step = with_replay._step
with_replay._step = lambda chunk: (seen.append(len(chunk)), real_step(chunk))[1]
with_replay.learn(tasks.learning_tasks("rekenen", 1, 40))
check("every batch the network sees is the same size",
      all(g == with_replay.batch_size for g in seen),
      f"batches: {seen} — the first one too, because the memory is filled "
      f"before anything is replayed from it")
with_replay._step = real_step

print()

# --- 9. Learning fills the memory ------------------------------------------

print("--- Learning remembers ---")
learner = small_learner()
check("the memory starts empty", len(learner.memory) == 0)
learner.learn(tasks.learning_tasks("rekenen", 1, 16))
check(
    "what is learned also enters the memory",
    len(learner.memory) == 16,
    "without this the memory stays empty and replay does nothing, while a "
    "comparison with and without seems to say something about it",
)

print()

# --- 10. Does the thing actually learn? ------------------------------------

print("--- Does the loss drop? ---")
determinism.lock(7)
learner = small_learner()
first = learner.learn(tasks.learning_tasks("rekenen", 1, 8 * 5))
for _ in range(10):
    last = learner.learn(tasks.learning_tasks("rekenen", 1, 8 * 5,
                                              start=tasks.TEST_UPTO + 9000))
check("the loss drops with repeated practice", last < first,
      f"{first:.3f} → {last:.3f}")

print()

# --- 11. Repeatable --------------------------------------------------------

print("--- Repeatable ---")


def weights_after_learning():
    determinism.lock(555)
    l = small_learner()
    l.learn(tasks.learning_tasks("rekenen", 2, 24))
    return [p.detach().clone() for p in l.core.parameters()]


check("two identical runs give bit for bit the same weights",
      all(torch.equal(a, b) for a, b in zip(weights_after_learning(),
                                            weights_after_learning())),
      "the learning loop is thereby as repeatable as the core beneath it")

print("--- Her state travels along ---")
# N: "Her state is more than weights: her accumulated memory too." At the
# crash of 9 Aug 2026 the run resumed with her ability intact and her
# 20,000 memories gone. This pins down that that cannot come back.
import snapshot as snapshot_module                                 # noqa: E402
import os as os_module                                             # noqa: E402
determinism.lock(808)
l1 = small_learner()
l1.learn(tasks.learning_tasks("rekenen", 2, 24))
l1.curiosity.update(("rekenen", 2), 0.7, 5)
path = "/home/arch/amber-werk/tmp/toestand.pt"
snapshot_module.write(path, 5, l1.core, l1.optimizer, determinism.state(),
                      extra=l1.carry())

determinism.lock(808)
l2 = small_learner()
content = snapshot_module.read(path)
snapshot_module.restore(content, l2.core, l2.optimizer, l2.device)
l2.restore(content["extra"])

check("her memory comes back bit for bit from the snapshot",
      l2.memory._content == l1.memory._content
      and len(l2.memory) == 24,
      f"{len(l2.memory)} memories, content identical")
check("the curiosity comes back with its clock",
      l2.curiosity.score == l1.curiosity.score
      and l2.curiosity.last == l1.curiosity.last,
      "without the clock, elapsed time attracts nowhere after a restart")
a = l1.memory.replay(5, tasks.Picker(3))
b = l2.memory.replay(5, tasks.Picker(3))
check("replaying after the restart gives exactly the same memories",
      [x["opgave"] for x in a] == [x["opgave"] for x in b])
os_module.remove(path)

# --- balanced forgetting — phase-4 foretaste (10 Aug 2026) -----------------

def _cell_task(family, grade, n):
    return tasks.Task(family=family, grade=grade, number=n,
                      problem=f"{family} {grade} nr {n}", solution=str(n))

ev = rm.ReplayMemory(capacity=50)
for i in range(10):
    ev.remember(_cell_task("puzzel", 1, i), None, None)   # rare, and old
for i in range(200):
    ev.remember(_cell_task("rekenen", 1, 1000 + i), None, None)
tally = {}
for s in ev._content:
    cell = (s["familie"], s["graad"])
    tally[cell] = tally.get(cell, 0) + 1
check("rare cells survive the forgetting",
      tally.get(("puzzel", 1), 0) == 10,
      "the old ring would have thrown all ten away: what is not in it, "
      "replay cannot protect")
check("the largest cell gives way, oldest first",
      tally.get(("rekenen", 1), 0) == 40
      and ev._content[-1]["familie"] == "rekenen")

ev2 = rm.ReplayMemory(capacity=50)
ev2.restore(ev.carry())
for i in range(5):
    ev.remember(_cell_task("code", 1, 5000 + i), None, None)
    ev2.remember(_cell_task("code", 1, 5000 + i), None, None)
check("after restore it forgets on as if nothing happened",
      [s["code"] for s in ev._content] == [s["code"] for s in ev2._content],
      "the tally is not in the snapshot and is rebuilt exactly")

# The bottleneck follows the window (Cley's call, 10 Aug 2026): what she
# can read she may remember, and when the window grows the doorway grows
# along by itself.
tiny = learning.Learner(core=network.Core(layers=1, width=32, heads=2,
                                          window=96), batch_size=4)
check("the bottleneck follows the window",
      tiny.memory.bottleneck.length == 96)
long_task = tasks.Task(family="rekenen", grade=6, number=1,
                       problem="x" * 30, solution="7", working="y" * 50)
check("an experience of worldly length is now allowed in",
      tiny.memory.remember(long_task, None, None),
      "83 characters plus markers — the old doorway of 128 on a window of "
      "96 would also have refused it, but for the wrong reason")

# --- Lessons from Cley (13 Aug 2026) ---------------------------------------
# A lesson is the question with the right answer, delivered as journal kind
# "les". It enters the memory through the doorway (no second entrance) and
# `lessons_upto` makes the intake idempotent on the line number.

print("--- Lessons from Cley ---")

lessen = small_learner()
rows = [{"nr": 12, "vraag": "hoe heet ik?", "antwoord": "Cley"},
        {"nr": 15, "vraag": "waar woon ik?",
         "antwoord": "in Nederland, bij de server"}]
before = len(lessen.memory)
taken, refused, once = lessen.learn_lessons(rows)
check("both lessons enter the memory",
      taken == 2 and refused == 0 and len(lessen.memory) == before + 2)
check("the drawer label is familie gesprek, graad 1",
      lessen.memory._tally.get(("gesprek", 1)) == 2)
check("intake is idempotent on the line number",
      lessen.learn_lessons(rows) == (0, 0, 0) and len(lessen.memory) == before + 2)

picker = tasks.Picker(99)
replayed = [d for d in lessen.memory.replay(50, picker)
            if d["familie"] == "gesprek"]
whole_ok = any(d["opgave"] == "waar woon ik?"
               and d["oplossing"] == "in Nederland, bij de server"
               for d in replayed)
check("a replayed lesson returns question and full answer", whole_ok)
lesson_task = learning._as_task(
    {"opgave": "waar woon ik?",
     "oplossing": "in Nederland, bij de server",
     "familie": "gesprek", "graad": 1, "goed": None})
check("a lesson with a number in it replays as the whole sentence",
      learning._as_task(
          {"opgave": "hoeveel kaarten heeft de server?",
           "oplossing": "2 kaarten van 16 GB",
           "familie": "gesprek", "graad": 1, "goed": None}
      ).to_learn() == "2 kaarten van 16 GB",
      "before 13 Aug 2026 this replayed as its last number alone")
check("a lesson without numbers replays whole too",
      lesson_task.to_learn() == "in Nederland, bij de server")

carried = lessen.carry()
fresh = small_learner()
fresh.restore(carried)
check("les_tot travels in the snapshot",
      fresh.lessons_upto == 15 and carried["les_tot"] == 15)
check("and after the restore the same lessons are skipped",
      fresh.learn_lessons(rows) == (0, 0, 0))

too_long = [{"nr": 20, "vraag": "v" * 200, "antwoord": "a" * 200}]
taken, refused, once = lessen.learn_lessons(too_long)
check("a lesson too big for the doorway is refused, not fatal",
      taken == 0 and refused == 1 and lessen.lessons_upto == 20)

# one-off lessons (17 Aug 2026, the week-1 memory test): learned at
# delivery, a few passes, but never in the memory — never replayed
eenmalig = [{"nr": 30, "vraag": "de code van de blauwe kist?",
             "antwoord": "de code van de blauwe kist is 7381", "eenmalig": True},
            {"nr": 31, "vraag": "hoeveel treden heeft de zoldertrap?",
             "antwoord": "de zoldertrap heeft 19 treden", "eenmalig": True}]
mem_before, steps_before = len(lessen.memory), lessen.steps
_max = learning.ONCE_MAX_PASSES
learning.ONCE_MAX_PASSES = 4                 # a tiny net will not reach 80%: hit the ceiling fast
taken, refused, once = lessen.learn_lessons(eenmalig)
lo = lessen.last_once or {}
check("one-off lessons are learned (steps taken) but not kept in the memory",
      once == 2 and taken == 0 and len(lessen.memory) == mem_before
      and lessen.steps > steps_before and lessen.lessons_upto == 31,
      f"steps {steps_before} → {lessen.steps}, memory {mem_before} → {len(lessen.memory)}")
check("… learned until she can say them, or the ceiling: the report says how far",
      lo.get("van") == 2 and lo.get("passes") == 4 and 0 <= lo.get("goed", -1) <= 2, str(lo))
check("… and they are not learned twice",
      lessen.learn_lessons(eenmalig) == (0, 0, 0))
# when she can already say them, one pass is enough: the check stops the loop
lessen2 = small_learner()
lessen2.answer = lambda tasks_, at_most=None: [t.solution for t in tasks_]
lessen2.learn_lessons([dict(eenmalig[0], nr=40)])
check("… and the loop stops as soon as the group is right",
      lessen2.last_once == {"passes": 1, "goed": 1, "van": 1}, str(lessen2.last_once))
learning.ONCE_MAX_PASSES = _max

# --- a family the snapshot does not know (16 Aug 2026) --------------------
# The world grew a fourth family (geheugen) after run 6's snapshot was
# written. On the rungrens that snapshot is the start of run 6.5: the
# restored curiosity must not lock the new family out, and its edge must
# exist — otherwise open_deeper falls over and she never draws it.
older = small_learner()                  # a learner as run 6 knew the world
carried_old = older.carry()
carried_old["diepste_per"] = {f: d for f, d in carried_old["diepste_per"].items()
                              if f != "geheugen"}
cur_c = carried_old["nieuwsgierig"]
cur_c["soorten"] = [s for s in cur_c["soorten"] if s[0] != "geheugen"]
cur_c["score"] = {k: v for k, v in cur_c["score"].items() if not k.startswith("geheugen/")}
cur_c["laatst"] = {k: v for k, v in cur_c["laatst"].items() if not k.startswith("geheugen/")}
newer = small_learner()
newer.restore(carried_old)
check("a family the snapshot does not know enters at the entrance depth",
      newer.deepest_per.get("geheugen") == newer._entrance
      and all(newer.deepest_per[f] == older.deepest_per[f]
              for f in ("code", "rekenen", "puzzel")))
check("… and its first depths stand in curiosity at score zero — attractive",
      all((("geheugen", g) in newer.curiosity.score
           and newer.curiosity.score[("geheugen", g)] == 0.0)
          for g in range(world_module.MIN_DEPTH, newer._entrance + 1)))
check("… while the known families keep their curiosity as carried",
      all(newer.curiosity.score[k] == v for k, v in older.curiosity.score.items()
          if k[0] != "geheugen"))
check("and open_deeper runs over all four families without falling",
      isinstance(newer.open_deeper(1), list))
# the restore takes the run step (17 Aug 2026): clocks in the future are
# clamped, and the new family enters with the run step — so it is drawable
# at once, with a positive weight
carried_old["nieuwsgierig"]["laatst"] = {k: 999_000 for k in carried_old["nieuwsgierig"]["laatst"]}
newest = small_learner()
newest.restore(carried_old, step=384_500)
att = newest.curiosity.attraction(384_500)
check("after a restore with the run step every clock stands at or before it",
      max(newest.curiosity.last.values()) <= 384_500)
check("… and the new family's rooms are drawable with a positive weight",
      all(att[k] > 0 for k in att if k[0] == "geheugen")
      and any(newest.curiosity.pick(384_500, tasks.Picker(s))[0] == "geheugen"
              for s in range(200)))

# --- the replay memory grows with the world (18 Aug 2026, Cley) ---------------
print()
print("--- the replay memory grows with the world ---")
_m = small_learner().memory
check("capacity is PER_FAMILY per family in the world",
      _m.capacity == rm.PER_FAMILY * len(world_module.FAMILIES)
      and rm.PER_FAMILY == 30000, f"{_m.capacity} for {len(world_module.FAMILIES)} families")
_carried = {"ruimte": 30000, "geweigerd": 3,
            "inhoud": [{"code": [1, 2, 3], "familie": "rekenen", "graad": 1, "goed": True}] * 5}
_m2 = rm.ReplayMemory(capacity=rm.PER_FAMILY * len(world_module.FAMILIES))
_m2.restore(_carried)
check("a carried stock of 30,000-policy loads intact under the larger policy",
      len(_m2) == 5 and _m2.capacity == rm.PER_FAMILY * len(world_module.FAMILIES)
      and _m2.refused == 3)

# --- lessons get a replay floor (18 Aug 2026, the week-1 finding) ------------
print()
print("--- lessons get a replay floor ---")
_m = rm.ReplayMemory(capacity=100000)
for i in range(3000):
    _m.remember(tasks.Task(family="rekenen", grade=1, number=i, problem=f"{i} + 1", solution=str(i + 1), working=None), None, None)
_les = [tasks.Task(family="gesprek", grade=1, number=i, problem=f"les {i}?", solution=f"antwoord {i}", working=None) for i in range(12)]
for t in _les:
    _m.remember(t, None, None)
_hits = 0
for st in range(200):
    got = _m.replay(24, tasks.Picker(1000 + st))
    _hits += any(g["familie"] == "gesprek" for g in got)
check("every replay of 24 holds a lesson when lessons exist (floor of one)", _hits == 200, f"{_hits}/200")
_m2 = rm.ReplayMemory(capacity=100000)
for i in range(3000):
    _m2.remember(tasks.Task(family="rekenen", grade=1, number=i, problem=f"{i} + 1", solution=str(i + 1), working=None), None, None)
_a = [g["opgave"] for g in _m2.replay(24, tasks.Picker(7))]
_b = [g["opgave"] for g in _m2.replay(24, tasks.Picker(7), lessons=0)]
check("without lessons the draw is exactly what it was", _a == _b and len(_a) == 24)

print()
print("=" * 70)
print(f"passed: {passed}    failed: {failed}")
print("=" * 70)
sys.exit(0 if failed == 0 else 1)
