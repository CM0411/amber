"""
Curiosity — what does she work on?

Phase 6 says it explicitly: *"S exists in raw form much earlier, and that is
deliberate. Phase 1 says initiative is the yardstick and that what she picks
up unprompted is the signal — then from day one something must steer that
choice, even if it is just curiosity that fades on familiar material."*

This is that raw form. One signal, two parts:

  **incompetence** — where she scores badly there is more to gain. Fades by
  itself once she can do it, which is exactly what "curiosity that fades"
  means.

  **elapsed time** — what has not come by in a while becomes attractive
  again. Without this she stays stuck on the hardest thing and never sees
  the rest again, and then C measures something the choice itself caused
  rather than forgetting.

Both are needed. Incompetence alone yields fixation; time alone yields a
round trip that might as well have been random.

IT MUST BE REPEATABLE
---------------------
The choice is drawn with a picker derived from (seed, step number). The same
run therefore gives the same sequence of topics — otherwise the learning
stream is not repeatable and phase 1's proof point is unreachable.

English successor of nieuwsgierigheid.py; toets-migratie.py enforces that
both make identical choices from identical streams.
"""

import taken


class Curiosity:
    def __init__(self, families=None, grades=None, fade=6.0, floor=0.05):
        self.kinds = [(f, g)
                      for f in (families or taken.FAMILIES)
                      for g in (grades or taken.GRADEN)]
        self.fade = fade                # how sharply incompetence steers
        self.floor = floor              # nothing ever drops all the way to zero
        self.score = {s: 0.0 for s in self.kinds}
        self.last = {s: 0 for s in self.kinds}

    def add(self, kind, step=0):
        """A topic that was not there before.

        Needed as soon as the world opens deeper: a difficulty appears that
        did not exist. A new topic starts at score zero and is therefore
        immediately attractive — exactly the intent.
        """
        if kind in self.score:
            return False
        self.kinds.append(kind)
        self.score[kind] = 0.0
        self.last[kind] = step
        return True

    def update(self, kind, score, step):
        """Report how well she is doing on this topic."""
        if kind not in self.score:
            self.add(kind, step)
        self.score[kind] = score
        self.last[kind] = step

    def attraction(self, step):
        """How attractive each topic is right now."""
        out = {}
        for kind in self.kinds:
            incompetence = (1.0 - self.score[kind]) ** 2
            elapsed = min(1.0, (step - self.last[kind]) / 500.0)
            out[kind] = self.floor + incompetence + 0.5 * elapsed
        return out

    def pick(self, step, picker):
        """Pick a topic. Proportionally, never the maximum.

        Picking the maximum would pin her to one topic until she masters it,
        and then every C measurement measures that ordering instead of
        forgetting.
        """
        weights = self.attraction(step)
        total = sum(weights.values())
        # The picker yields integers; drawing proportionally that way avoids
        # floating point — and so avoids choices differing per machine.
        point = picker.geheel(0, 1_000_000) / 1_000_000 * total
        walker = 0.0
        for kind, weight in weights.items():
            walker += weight
            if point <= walker:
                return kind
        return self.kinds[-1]

    def snapshot_view(self):
        return {f"{f}/{g}": round(self.score[(f, g)], 3)
                for f, g in self.kinds}

    # --- carried in the snapshot ------------------------------------------

    def carry(self):
        """`last` travels too, not just the scores.

        Without `last` she believes after a restart that she has just seen
        everything, and elapsed time pulls nowhere until the clock rebuilds —
        a subtly different Amber than before the restart.
        """
        return {"kinds": [list(s) for s in self.kinds],
                "score": {f"{f}/{g}": self.score[(f, g)] for f, g in self.kinds},
                "last": {f"{f}/{g}": self.last[(f, g)] for f, g in self.kinds}}

    def restore(self, carried):
        self.kinds = [tuple(s) for s in carried["kinds"]]
        self.score, self.last = {}, {}
        for key, value in carried["score"].items():
            f, g = key.rsplit("/", 1)
            self.score[(f, int(g))] = value
        for key, value in carried["last"].items():
            f, g = key.rsplit("/", 1)
            self.last[(f, int(g))] = value
