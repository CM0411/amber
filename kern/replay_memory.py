"""
The replay memory — and the bottleneck U hangs from.

This is the first version of H. Whatever goes in passes through a fixed,
narrow, discrete doorway; wide open in phase 1, squeezed in phase 4. Cley
approved that coupling on 8 Aug 2026.

WHY THE BOTTLENECK IS ALREADY HERE
----------------------------------
From `CLAUDE.md`: *"If it is in from the start, phase 4 only has to squeeze
it. If it is not, all memory from phases 1 through 3 must be converted or
thrown away."* The same category as determinism.

And from the reasoning behind U: the pressure must be real. *"The character
set does not grow with the world, the number of situations does. Then reuse
of characters across situations is the only way to stay inside the band."*
In phase 1 there is no pressure yet — the doorway is wider than needed. But
the path is laid, and squeezing later is changing one number instead of a
rebuild.

THE LATCH
---------
The memory stores **codes only**, never the experience itself. Whoever wants
to remember something must pass through `Bottleneck`; there is no other way
in. Deliberately: were there a second entrance, it would get used the
evening the bottleneck pinches, and nothing of U would remain.

An experience that does not fit the doorway is **refused**. Since 10 Aug
2026 the doorway follows the window (Cley's call): 128 was sized for the
bare-answer era and refused 5.5 million worked experiences — everything
from rekenen ~6 and code ~4 could never be replayed.

One rule across the migration: **code is English, her state is Dutch.** The
stored dicts keep their Dutch keys (code/familie/graad/goed) — they live in
every checkpoint she has ever written.
"""

import tokens

# Phase 1: wide open. The character set is the core's own, and the length
# follows the window at construction time (see learning). Phase 4 squeezes
# these two numbers. That is the entire work there — not laying the path,
# only narrowing it.
CHARSET = tokens.VOCAB
LENGTH = 128          # historical default; the learner passes the window


class Refused(Exception):
    """This experience does not fit through the doorway."""


class Bottleneck:
    """The only way into the memory.

    In phase 1 the encoding is a reversible mapping: nothing is lost,
    because there is no pressure yet. The *shape* is what counts — a fixed
    character set and a fixed maximum length — because that is what phase 4
    will squeeze.
    """

    def __init__(self, charset=CHARSET, length=LENGTH):
        self.charset = charset
        self.length = length

    def encode(self, task, given_answer, correct):
        """An experience becomes a sequence of characters. Nothing bigger
        goes in.

        What goes in is the problem with the **right** answer, not what she
        made of it. The lesson is the correction, not her attempt; store her
        own answer and every replay rehearses her mistakes. What she said is
        known — it determines `correct` — but it is not a memory to return
        to.

        Family, grade and `correct` are the labels on the drawer and
        deliberately do not pass through the doorway: they describe the
        memory, not the world. What must compress in phase 4 is the content.
        """
        # `te_leren()` and not the bare solution: the working is the lesson.
        # With only the answer stored, every memory teaches her to skip the
        # working — at 37.5% replay that is over a third of everything she
        # sees. Found on 9 Aug 2026 after a night of guessing at grade 4
        # while she could do it.
        raw = ([tokens.QUESTION] + tokens.encode(task.problem)
               + [tokens.ANSWER] + tokens.encode(task.to_learn())
               + [tokens.END])
        if len(raw) > self.length:
            raise Refused(
                f"experience of {len(raw)} characters does not fit a doorway "
                f"of {self.length}"
            )
        if any(c >= self.charset for c in raw):
            raise Refused(
                f"experience uses a character outside the set of "
                f"{self.charset}"
            )
        return {
            "code": raw,
            "familie": task.family,
            "graad": task.grade,
            # None means: not graded. That is different from wrong, and
            # mixing the two silently distorts the picture of how well she
            # is doing.
            "goed": None if correct is None else bool(correct),
        }

    def decode(self, stored):
        """Back from code to something usable.

        In phase 4, when the encoding turns lossy, what comes out is no
        longer the original text but what she retained of it. The callers
        must already cope with that.
        """
        codes = stored["code"]
        try:
            split = codes.index(tokens.ANSWER)
        except ValueError:
            return {"opgave": "", "oplossing": "", **stored}
        return {
            "opgave": tokens.decode(codes[1:split]),
            "oplossing": tokens.answer_from_sequence(codes),
            "familie": stored["familie"],
            "graad": stored["graad"],
            "goed": stored["goed"],
        }

    def occupancy(self, stored):
        """How much of the doorway is used?

        The number phase 4 will squeeze. As long as it stays well below 1
        there is no pressure, and so no reason for her to invent anything.
        """
        return len(stored["code"]) / self.length


# Since 18 Aug 2026 (Cley's call) the capacity grows with her world:
# PER_FAMILY memories per family in `world.FAMILIES`. Fixed 30,000 was set
# with three families; with seven the stock turned over every ~1,500 steps
# and puzzel kept ~100 memories per depth. Replays per memory over its
# lifetime stay the same (~1.2: 24 per step over a 7× longer horizon out
# of a 7× larger stock) — what grows is the horizon. `learning.py` does
# the multiplication; this module does not import world.
PER_FAMILY = 30000
LESSON_FAMILY = "gesprek"        # lessons from Cley enter under this family
LESSONS_PER_BATCH = 1            # replay slots reserved for lessons per batch


class ReplayMemory:
    """A stock of experiences to come back to.

    Stores only what has passed the bottleneck. When full, the oldest of the
    largest cell yields (balanced forgetting, 10 Aug 2026) — rare cells keep
    a floor, frequent ones stay fresh.
    """

    def __init__(self, capacity=30000, bottleneck=None):
        # 30,000 since 11 Aug 2026 (Cley's call: "she need not forget"):
        # run 4 opens 43 cells (26+11+6) and the balanced forgetting
        # divides capacity over the open cells — 30,000 keeps ~700 per
        # cell, the coverage run 3 had with 30 cells in 20,000. The cap
        # itself must stay: every step adds ~20 experiences, and a stack
        # that only grows dilutes replay until it protects nothing.
        self.capacity = capacity
        self.bottleneck = bottleneck or Bottleneck()
        self._content = []
        self._tally = {}
        self.refused = 0
        # Lifelong tally (27 Aug 2026, Cley's wish to watch her memory grow):
        # every experience that ever passes the doorway adds one, and it is
        # never decreased when balanced forgetting drops one — the working
        # memory rolls, but what she has *ever* learned only grows. Seeded
        # at the current fill for a checkpoint from before this counter, so
        # the number starts where the working memory sits (390.000) and
        # climbs from there. Carried like everything else in her state.
        self.onthouden_totaal = 0

    def remember(self, task, answer, correct):
        try:
            stored = self.bottleneck.encode(task, answer, correct)
        except Refused:
            self.refused += 1
            return False
        self._content.append(stored)
        cell = (stored["familie"], stored["graad"])
        self._tally[cell] = self._tally.get(cell, 0) + 1
        self.onthouden_totaal += 1
        if len(self._content) > self.capacity:
            self._forget_one()
        return True

    def _forget_one(self):
        """Balanced forgetting — the first preview of phase 4.

        The first version bluntly dropped the oldest. Measured on 10 Aug
        2026 (step 102,000): the whole stock then consisted of the last
        ~600 steps' cells — rare cells were gone but for three or four
        memories, and what is not in there replay cannot protect. Now the
        oldest of the *largest* cell yields: rare keeps a floor, frequent
        stays fresh. Within a cell forgetting stays oldest-first.

        Deterministic, ties included: the pick is on (count, cell), so the
        same stream always gives the same memory.
        """
        largest = max(self._tally.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for i, stored in enumerate(self._content):
            if (stored["familie"], stored["graad"]) == largest:
                del self._content[i]
                break
        self._tally[largest] -= 1
        if not self._tally[largest]:
            del self._tally[largest]

    def replay(self, how_many, picker, lessons=None):
        """Fetch experiences to revisit.

        `picker` decides which — passed in, never invented here, so the
        choice follows from (seed, step number) and the whole stream stays
        repeatable.

        Lessons from Cley (family "gesprek") get a floor (18 Aug 2026, the
        week-1 finding): drawn uniformly, twelve lessons among 30,000
        memories came up once per ~1,250 steps each — far too seldom to
        hold a four-digit code — and a stock growing to 210,000 would make
        that once per ~9,000. So the first LESSONS_PER_BATCH slots of every
        replay come from the lessons (when there are any), the rest stays
        uniform over the whole stock. Without lessons nothing changes.
        """
        if not self._content:
            return []
        if lessons is None:
            lessons = LESSONS_PER_BATCH
        chosen = []
        if lessons:
            les = [s for s in self._content if s["familie"] == LESSON_FAMILY]
            for _ in range(min(lessons, len(les), how_many)):
                chosen.append(les[picker.integer(0, len(les) - 1)])
        for _ in range(min(how_many - len(chosen), len(self._content))):
            chosen.append(self._content[picker.integer(0, len(self._content) - 1)])
        return [self.bottleneck.decode(s) for s in chosen]

    def __len__(self):
        return len(self._content)

    # --- carried in the snapshot ------------------------------------------
    # N: "Her state is more than weights: her grown memory too." On 9 Aug
    # 2026 the memory did *not* travel: after the X399 crash the run resumed
    # with her ability intact and her 20,000 memories gone — a silent memory
    # wipe on every restart.

    def carry(self):
        """Everything needed to rebuild this memory exactly.

        Lists and numbers only, nothing device-bound — the same requirement
        as the rest of the checkpoint, so it survives a move. Dutch keys:
        they are her state.
        """
        return {
            "ruimte": self.capacity,
            "geweigerd": self.refused,
            "onthouden_totaal": self.onthouden_totaal,
            "inhoud": [dict(s) for s in self._content],
        }

    def restore(self, carried):
        """Put a carried memory back exactly. Reads run-3-era checkpoints.

        Capacity is policy and follows the code, not the snapshot: on 11
        Aug 2026 the stack grew from 20,000 to 30,000 (Cley's call), and a
        restore must not quietly shrink it back to the run-3 value. The
        carried "ruimte" stays in the snapshot as documentation. Content
        is never dropped at load — should it ever exceed today's policy,
        the balanced forgetting trims on the next remember().
        """
        # A larger policy than the carried stock never trims anything;
        # a smaller one lets balanced forgetting trim on the next remember.
        self.capacity = max(self.capacity, len(carried["inhoud"]))
        self.refused = int(carried["geweigerd"])
        # An older checkpoint has no lifelong tally yet: start it at what she
        # currently holds, so the number never overclaims a history it did
        # not record, and never dips below the working memory.
        self.onthouden_totaal = int(carried.get("onthouden_totaal",
                                                len(carried["inhoud"])))
        self._content = [dict(s) for s in carried["inhoud"]]
        # The tally is not in the checkpoint but follows from the content —
        # so a checkpoint from before balanced forgetting loads unchanged.
        self._tally = {}
        for stored in self._content:
            cell = (stored["familie"], stored["graad"])
            self._tally[cell] = self._tally.get(cell, 0) + 1
        return len(self._content)

    def status(self):
        """What is in it, and how full the doorway sits."""
        if not self._content:
            return {"aantal": 0, "geweigerd": self.refused,
                    "onthouden_totaal": self.onthouden_totaal,
                    "bezetting_gemiddeld": None, "bezetting_hoogste": None}
        occ = [self.bottleneck.occupancy(s) for s in self._content]
        graded = [s["goed"] for s in self._content if s["goed"] is not None]
        return {
            "aantal": len(self._content),
            "geweigerd": self.refused,
            "onthouden_totaal": self.onthouden_totaal,
            "bezetting_gemiddeld": sum(occ) / len(occ),
            "bezetting_hoogste": max(occ),
            "nagekeken": len(graded),
            "goed_deel": (sum(graded) / len(graded)) if graded else None,
        }
