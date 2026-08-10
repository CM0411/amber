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
        # Dutch aliases for the transition — wachter/kijker still read these.
        self.tekens_in_de_set = charset
        self.lengte = length

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
        raw = ([tokens.QUESTION] + tokens.encode(task.opgave)
               + [tokens.ANSWER] + tokens.encode(task.te_leren())
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
            "familie": task.familie,
            "graad": task.graad,
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


class ReplayMemory:
    """A stock of experiences to come back to.

    Stores only what has passed the bottleneck. When full, the oldest of the
    largest cell yields (balanced forgetting, 10 Aug 2026) — rare cells keep
    a floor, frequent ones stay fresh.
    """

    def __init__(self, capacity=20000, bottleneck=None):
        self.capacity = capacity
        self.bottleneck = bottleneck or Bottleneck()
        self._content = []
        self._tally = {}
        self.refused = 0

    def remember(self, task, answer, correct):
        try:
            stored = self.bottleneck.encode(task, answer, correct)
        except Refused:
            self.refused += 1
            return False
        self._content.append(stored)
        cell = (stored["familie"], stored["graad"])
        self._tally[cell] = self._tally.get(cell, 0) + 1
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

    def replay(self, how_many, picker):
        """Fetch experiences to revisit.

        `picker` decides which — passed in, never invented here, so the
        choice follows from (seed, step number) and the whole stream stays
        repeatable.
        """
        if not self._content:
            return []
        chosen = [self._content[picker.geheel(0, len(self._content) - 1)]
                  for _ in range(min(how_many, len(self._content)))]
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
            "inhoud": [dict(s) for s in self._content],
        }

    def restore(self, carried):
        """Put a carried memory back exactly. Reads run-3-era checkpoints."""
        self.capacity = int(carried["ruimte"])
        self.refused = int(carried["geweigerd"])
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
                    "bezetting_gemiddeld": None, "bezetting_hoogste": None}
        occ = [self.bottleneck.occupancy(s) for s in self._content]
        graded = [s["goed"] for s in self._content if s["goed"] is not None]
        return {
            "aantal": len(self._content),
            "geweigerd": self.refused,
            "bezetting_gemiddeld": sum(occ) / len(occ),
            "bezetting_hoogste": max(occ),
            "nagekeken": len(graded),
            "goed_deel": (sum(graded) / len(graded)) if graded else None,
        }
