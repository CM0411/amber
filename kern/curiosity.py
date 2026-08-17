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

import tasks


class Curiosity:
    def __init__(self, families=None, grades=None, fade=6.0, floor=0.05):
        self.kinds = [(f, g)
                      for f in (families or tasks.FAMILIES)
                      for g in (grades or tasks.GRADES)]
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
            # Clamped at both ends (17 Aug 2026): a `last` in the future —
            # it happened, through a restore that handed the optimizer's
            # step count instead of the run step — gave a negative weight,
            # and a negative weight in a proportional walk makes every
            # topic after it unreachable. Never again: nothing pulls below
            # the floor.
            elapsed = max(0.0, min(1.0, (step - self.last[kind]) / 500.0))
            out[kind] = self.floor + incompetence + 0.5 * elapsed
        return out

    def _draw(self, weights, picker):
        """Draw one key from {key: weight}, proportionally, with integers."""
        total = sum(weights.values())
        # The picker yields integers; drawing proportionally that way avoids
        # floating point — and so avoids choices differing per machine.
        point = picker.integer(0, 1_000_000) / 1_000_000 * total
        walker = 0.0
        last_key = None
        for key, weight in weights.items():
            walker += weight
            last_key = key
            if point <= walker:
                return key
        return last_key

    def pick(self, step, picker):
        """Pick a topic. Proportionally, never the maximum.

        Picking the maximum would pin her to one topic until she masters it,
        and then every C measurement measures that ordering instead of
        forgetting.

        In two steps since 17 Aug 2026 (Cley's choice): first the family,
        weighed by the MEAN attraction of its open rooms, then a room within
        it, proportionally. Before, every room weighed on its own, and a
        family with sixty open rooms (rekenen) drew two thirds of her
        choices while a new family with two rooms starved — a new family
        should pull hard exactly while she cannot do it, and fade when she
        can. The price: each deep rekenen room gets fewer visits of her
        own; the replay and the elapsed term keep the old rooms alive.
        """
        weights = self.attraction(step)
        per_family = {}
        for (family, grade), weight in weights.items():
            per_family.setdefault(family, []).append(weight)
        family_weights = {f: sum(ws) / len(ws) for f, ws in per_family.items()}
        family = self._draw(family_weights, picker)
        rooms = {kind: w for kind, w in weights.items() if kind[0] == family}
        return self._draw(rooms, picker)

    def snapshot_view(self):
        return {f"{f}/{g}": round(self.score[(f, g)], 3)
                for f, g in self.kinds}

    # --- carried in the snapshot ------------------------------------------

    def carry(self):
        """`last` travels too, not just the scores.

        Without `last` she believes after a restart that she has just seen
        everything, and elapsed time pulls nowhere until the clock rebuilds —
        a subtly different Amber than before the restart.

        The dict keys are Dutch on purpose. One rule across the migration:
        **code is English, her state is Dutch** — these keys live in every
        checkpoint she has ever written, and translating stored state would
        buy nothing but a bridge that must never break.
        """
        return {"soorten": [list(s) for s in self.kinds],
                "score": {f"{f}/{g}": self.score[(f, g)] for f, g in self.kinds},
                "laatst": {f"{f}/{g}": self.last[(f, g)] for f, g in self.kinds}}

    def restore(self, carried):
        self.kinds = [tuple(s) for s in carried["soorten"]]
        self.score, self.last = {}, {}
        for key, value in carried["score"].items():
            f, g = key.rsplit("/", 1)
            self.score[(f, int(g))] = value
        for key, value in carried["laatst"].items():
            f, g = key.rsplit("/", 1)
            self.last[(f, int(g))] = value
