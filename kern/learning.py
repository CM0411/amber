"""
The learning loop — where the core actually learns.

Brings together what already stands on its own: the network, the tasks with
their benchmark, the replay memory with its bottleneck, the curiosity that
picks what she works on, and the journal beneath it.

The `Learner` fits the two things the measuring loop asks — answering and
learning — so the C measurement handles it without ceremony.

THREE THINGS THAT MUST BE RIGHT HERE
------------------------------------
**The loss counts only over the answer.** The mask from `tokens.py` does
that. Shift one position and she learns to predict questions instead of
answering them — and the loss curve looks fine while she does.

**Answering happens in one batch.** A hundred tasks one by one is a hundred
passes through the network; together it is one. That is the difference
between measuring whenever you want and measuring you start avoiding.

**Replay is off by default.** Deliberate: first the C baseline must exist —
how badly she forgets with nothing against it. Switch it on from the start
and you never know how big the problem was, so neither whether you solved
it or merely covered it.

English successor of leren.py; toets-migratie.py runs both side by side
through real learning steps and demands bit-for-bit equal weights at the
end.
"""

import os
import threading

import bridge
import determinism
import exams
import parallel
import tasks as tasks_module
import tokens
import torch
import torch.nn.functional as F
import world
import replay_memory
from replay_memory import ReplayMemory, Bottleneck
import network
from network import Core
from curiosity import Curiosity

# How many characters she may write for an answer.
#
# Not a detail. With 48, from depth 4 on **no** working fit: on average 58
# characters at depth 4, 75 at 5, 91 at 6. She was always cut off, and
# grading took an intermediate step for the final answer. It looked like
# guessing while she simply lacked the room.
#
# 128 covers depth 6 with margin. Every character is a pass through the
# network, so wider costs time — but too narrow costs the measurement, and
# that is worse.
ROOM = 128

# batch × length² per chunk. Measured on 11 Aug 2026 at window 768: groups
# of 16 make the probe round ~10% faster than groups of 8 (10.3 -> 9.3 s),
# larger is flat, and the VRAM peak did not move. Chunking never changes
# outcomes — test-learning proves batched answering equals one-by-one.
_CHUNK_BUDGET = 10_000_000
# A row shorter than this share of its group's longest starts a new
# group (24 Aug 2026): keeps the padding in every group under ~30%,
# while groups stay large enough to keep the card busy.
_GROUP_SPAN = 0.8


def bf16_usable(device):
    """Does this card have bf16 in hardware?

    **Not** `torch.cuda.is_bf16_supported()`: it returned `True` on the
    P100 too, where bf16 is emulated and slower than fp32. Measured on
    8 Aug 2026. The card's generation is the honest answer — from 8.0
    (Ampere) there are tensor cores that truly can.
    """
    if not str(device).startswith("cuda") or not torch.cuda.is_available():
        return False
    major, _ = torch.cuda.get_device_capability(0)
    return major >= 8


# One-off lessons (17 Aug 2026): a lesson that must not enter the memory is
# learned at delivery until she can say it — ONCE_TARGET of the group right,
# checked after every pass — with a ceiling of ONCE_MAX_PASSES; then never
# seen again. A fixed three passes (the first version) left her at 0% on the
# twelve week-1 seeds: nothing was learned, so nothing could be retained.
ONCE_TARGET = 0.8
ONCE_MAX_PASSES = 30


# --- the honest "?" and the play hour (25 Aug 2026, Claude's wishes 1 and 3, on Cley's word) --
def score_of(right):
    """A self-test mark from a list of check() results.

    True is right, False is wrong, None is an honest "?" (see tasks.Task.check).
    A "?" counts neither right nor wrong; a wrong answer weighs half a point
    against. So guessing costs more than admitting: ten right and ten wrong
    give 0,25, ten right and ten "?" give 0,5. Never below zero.
    """
    n = len(right)
    if not n:
        return 0.0
    goed = sum(1 for r in right if r is True)
    fout = sum(1 for r in right if r is False)
    return max(0.0, (goed - 0.5 * fout) / n)


def telling(right):
    """(goed, fout, weetniet) — for the journal."""
    return (sum(1 for r in right if r is True), sum(1 for r in right if r is False),
            sum(1 for r in right if r is None))


# One hour a day without a mark: she picks (curiosity picks, as always) and
# learns, but nothing is measured — no self-test, no curiosity update, no
# gate that opens. In steps, not by the clock, so the stream stays
# repeatable: one block of SPEL_DUUR steps in every SPEL_PERIODE (about
# an hour in a day at five seconds a step).
SPEL_PERIODE = 17_000
SPEL_DUUR = 700


def speelt(step):
    return (step % SPEL_PERIODE) < SPEL_DUUR


# --- her day (25 Aug 2026, Cley: a real answer to "hoe was je dag") -----------
# A day is DAG_STAPPEN steps (the play hour's period). Through the day the
# Learner tallies what she did — which families, how the self-tests went,
# what she played, where the world opened — and at the end of the day the
# tally becomes a few lessons in her own idiom (family gesprek, the same
# doorway as Cley's lessons): "dag 3: wat oefende je?" → "ik oefende
# rekenen, taal en code". Step-based and carried in the snapshot, so the
# stream stays repeatable. The diary question "hoe was je dag?" gets the
# latest day's line, so the kijker's evening question can land on it.
DAG_STAPPEN = SPEL_PERIODE


def _lege_dag():
    return {"geoefend": {}, "gespeeld": {}, "scores": {}, "open": []}


def _oordeel(fam, score):                 # her "zeggen" idiom, see world._verdict
    return (f"{fam} gaat goed" if score >= 0.9 else f"{fam} gaat" if score >= 0.6
            else f"{fam} is moeilijk")


def _lijst(fams):
    return fams[0] if len(fams) == 1 else ", ".join(fams[:-1]) + " en " + fams[-1]


def dag_lessen(dag, nummer):
    """(vraag, antwoord) pairs from a day's tally; [] for an empty day."""
    uit = []
    top = sorted(dag["geoefend"], key=lambda f: (-dag["geoefend"][f], f))[:3]
    if top:
        uit.append((f"dag {nummer}: wat oefende je?", f"ik oefende {_lijst(top)}"))
    gem = {f: s / n for f, (s, n) in dag["scores"].items() if n}
    if gem:
        beste = max(sorted(gem), key=gem.get)
        slechtste = min(sorted(gem), key=gem.get)
        uit.append((f"dag {nummer}: wat gaat goed?", _oordeel(beste, gem[beste])))
        uit.append((f"dag {nummer}: wat is moeilijk?", _oordeel(slechtste, gem[slechtste])))
    spel = sorted(dag["gespeeld"], key=lambda f: (-dag["gespeeld"][f], f))[:3]
    if spel:
        uit.append((f"dag {nummer}: wat speelde je?", f"ik speelde {_lijst(spel)}"))
    if dag["open"]:
        uit.append((f"dag {nummer}: wat ging open?",
                    " ; ".join(f"ik mag dieper in {f}" for f in dag["open"][:3])))
    if uit:
        samen = " ; ".join(a for q, a in uit if "speelde" not in q and "open" not in q)
        uit.append((f"dag {nummer}: hoe was je dag?", samen))
        uit.append(("hoe was je dag?", samen))
    return uit


def room_for(depth, family=None, window=512):
    """How many characters a working needs here.

    **Per family, not just per depth.** The first version was calibrated on
    arithmetic, where the working grows with depth: 50 characters at depth
    3, 110 at 6. For puzzles that is wrong — six differences always stand
    beneath each other, so a working is around 90 characters even at depth
    1. With the arithmetic measure puzzle depth 1 got 34 characters for a
    working of 89: cut off everywhere, scoring zero on her whole family
    while she was learning it. Found on 9 Aug 2026.
    """
    if family == "puzzel":
        # Recalibrated 10 Aug 2026, after the varying row lengths: a row
        # showing seven numbers works out longer than the old fixed six —
        # longest 391 at depth 3, 379 at 5, where 336 stood. Too narrow
        # costs the whole family, as 9 Aug 2026 showed.
        #
        # Ceiling = window - 112: the margin follows the longest puzzle
        # problem, and since the compact working opened depth 7-9 (13 Aug
        # 2026) problems run to 104 characters — the old margin of 72 dated
        # from fence 6. 112 is the same margin the learning loop uses for
        # its material. Measured 13 Aug 2026 at window 1024: longest
        # working 782 at depth 9, ceiling 912 covers it.
        return min(window - 112, 120 * depth + 40)
    if family == "code":
        # Recalibrated 10 Aug 2026, after the three endings: even a depth-1
        # problem now writes `a = 11 ; b = 94 ; 11 - 94 = -83` — 62
        # characters where 24 of room stood, so every new ending was cut
        # off during probing. And depth 3–4 was already too narrow before
        # the endings (81 and 157 measured against 48 and 144): the same
        # disease as the bottleneck, a number calibrated on an older world.
        if depth <= 2:
            return 72
        # Ceiling = window - 192: code problems are the longest (173
        # characters at depth 11). At 512 the old 320; at 768 it becomes
        # 576 and covers the measured 452 of depth 11 (10 Aug 2026).
        #
        # The slope was doubled on 11 Aug 2026 (was 80·d − 144): the exam
        # forms at true size write far more than the old lines form — a
        # squares loop with nine rounds is ~280 characters at depth 3,
        # where 96 stood, and a def with ten rounds ~480 at depth 5. The
        # same disease as always: a number calibrated on an older world.
        #
        # Raised again on 14 Aug 2026, after the error analysis of run 4:
        # every code-3/5 miss was a long loop computed flawlessly and cut
        # off by this bound. An eleven-round squares loop she has genuinely
        # seen writes ~370 characters where grade 3 gave 320, and a
        # fifteen-round def writes ~750 where grade 5 gave 640 — the cap
        # was below her own learned material. 200·d − 200 covers both
        # (400 at grade 3, 800 at grade 5); the ceiling still guards the
        # window.
        return min(window - 192, 200 * depth - 200)
    if family == "machine":
        # Machine (18 Aug 2026): the trace — rounds × steps × ~18
        # characters, ~420 at depth 10. Room 96 + 36·d.
        return min(window - 112, 96 + 36 * depth)
    if family == "tellen":
        # Counting (18 Aug 2026): the list (≤ 25 numbers) and the count,
        # ~120 characters at most. Room 72 + 8·d.
        return min(window - 112, 72 + 8 * depth)
    if family == "taal":
        # Language (18 Aug 2026): a sentence and a word, or the built
        # sentence — under 60 characters everywhere. Room 48 + 4·d.
        return min(window - 112, 48 + 4 * depth)
    if family == "antwoord":
        # Conversation (19 Aug 2026): one short sentence, ~40 chars. Room 48 + 4·d.
        return min(window - 112, 48 + 4 * depth)
    if family == "zeggen":
        # Saying (18 Aug 2026): one or two short lines of reasoning and the
        # sentence — ~120 characters at depth 12. Room 64 + 8·d.
        # 13-24 (19 Aug 2026): three sentences at 23-24, ~170 chars. Room 64 + 8·d still fits (256 at 24).
        return min(window - 112, 64 + 8 * depth)
    if family == "tekst":
        # Text (18 Aug 2026): one verdict per word plus the count, and from
        # depth 8 the operated list first — ~230 characters at depth 12
        # (eleven words), ~300 at 24. Room 48 + 20·d.
        return min(window - 112, 48 + 20 * depth)
    if family == "volgorde":
        # Order (18 Aug 2026): the working lists the chain (n−1 short
        # rules), the order line and the answer — ~110 characters at depth
        # 12 (8 steps), ~200 at 24. Room 48 + 12·d.
        return min(window - 112, 48 + 12 * depth)
    if family == "logica":
        # Logic (17 Aug 2026): the working is the derivation chain — one
        # short line per link (`als d en u dan w: w = 1`, ~25 characters)
        # plus the facts it looks up; measured longest 200 at depth 12,
        # ~450 at 24. Grows with depth because the chain does.
        return min(window - 112, 64 + 20 * depth)
    if family == "geheugen":
        # Memory (16 Aug 2026): the plain working is short at every depth —
        # look back, copy one or two held values, one operation: `c = 44 ;
        # g = 11 ; 44 - 11 = 33` is 27 characters. Since the memory brick
        # (17 Aug 2026) a name carries its history — `k = 7 ; k = 7 + 3 =
        # 10 ; k = 10 * 2 = 20` — and two names plus the sum run to ~160 at
        # depth 40. So 72 plus nine per depth: 108 at 4, 288 at 24, 432 at 40.
        return min(window - 112, 72 + 9 * depth)
    # Arithmetic. Longest working: 50 at depth 3, 110 at 6, 180 at 9, 247
    # at 12, and measured on 9 Aug 2026: 294 at 14, 356 at 16, 384 at 17.
    # The old bound of 280 cut depth 14+ — the same mistake as with puzzle
    # and code. Ceiling = window - 128 (margin: longest arithmetic problem,
    # 148 at depth 26): at 512 the old 384, at 768 it becomes 640 and
    # covers the measured 526 of depth 26 (10 Aug 2026).
    return min(window - 128, 20 * depth + 24)


class Learner:
    def __init__(self, core=None, device=None, learning_rate=3e-4,
                 batch_size=32, replay_share=0.375, brake=0.0, memory=None,
                 curiosity=None, deepest=2, edge_threshold=0.5,
                 probe_every=4, bf16=None, checkpointing=False):
        # Under torchrun (parallel.start() done) every process is pinned to
        # its own card and that card is the device — see parallel.py.
        self.device = (device or parallel.device()
                       or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.core = (core or Core()).to(self.device)
        self.bf16 = bf16_usable(self.device) if bf16 is None else bf16
        # Activation checkpointing (15 Aug 2026): a machine setting like
        # bf16, not part of who she is — it never enters the snapshot. Same
        # numbers bit for bit, less VRAM, ~30% more time on the learning
        # part. See Core.checkpointing and test-checkpointing.py.
        self.core.checkpointing = bool(checkpointing)

        # Both cards. They cannot reach each other's memory (no NVLink on
        # the PCIe build), so the batch splits and the gradients meet over
        # the PCIe bus. At 14 million parameters that is well worth it.
        #
        # Two ways to do that (16 Aug 2026):
        #
        # * **one process, DataParallel** — the old way, still what a plain
        #   `python life.py` gets on a two-card machine. One boss card that
        #   copies weights and gathers outputs every step; ×1.35 out of the
        #   second card, measured.
        # * **one process per card** (`parallel.active()`, launched by
        #   torchrun) — every process holds a whole Learner and takes the
        #   same step; only the gradient is computed in shares and summed
        #   over the bus. Then there is no DataParallel and no answer copy:
        #   this process has one card, and answering is shared the same
        #   way (see `answer`). Nothing else in here needs to know.
        #
        # `self.core` stays the bare network: the snapshot must not know
        # how many cards happen to sit in the machine, nor how many
        # processes drive them. The same demand as "store state
        # hardware-independently".
        self._compute_core = self.core
        self._answer_core = self.core
        self._answer_device = self.device
        self._weights_fresh = True

        if (not parallel.active() and self.device == "cuda"
                and torch.cuda.device_count() > 1):
            self._compute_core = torch.nn.DataParallel(self.core)

            # Answering happens on the second card. Two reasons:
            #
            # It is by now the most expensive part — one pass per character
            # — and it ran entirely on card 0, which under DataParallel
            # already carries the main copy and all gathered output. Cley
            # saw that as 4670 MB against 1336 MB.
            #
            # And DataParallel is exactly wrong here: it recopies the
            # weights to both cards on every call, and with eighty
            # characters in a row that is eighty copies of 57 MB. One own
            # copy on card 1, refreshed once the weights changed, is far
            # cheaper.
            self._answer_device = "cuda:1"
            self._answer_core = Core.from_spec(self.core.spec()).to("cuda:1")
            self._answer_core.eval()

        self.optimizer = torch.optim.AdamW(self.core.parameters(),
                                           lr=learning_rate)
        self.batch_size = batch_size
        self.replay_share = replay_share    # share of each batch from memory
        self.brake = brake                  # how hard important weights brake
        # The bottleneck follows the window (Cley's call, 10 Aug 2026). The
        # old fixed 128 came from the bare-answer era; with workings it
        # refused 5.5 million of her experiences — nearly everything from
        # rekenen 6 and code 4 could never be replayed. Wider than the
        # window is impossible too: what does not fit cannot be reread at
        # replay time. So: exactly the window, and when the window grows
        # (phase 2) the doorway grows along. Phase 4 squeezes from that
        # honest starting point.
        if memory is not None:
            self.memory = memory
        else:
            # capacity follows the world (18 Aug 2026): PER_FAMILY per family
            self.memory = ReplayMemory(
                capacity=replay_memory.PER_FAMILY * len(world.FAMILIES),
                bottleneck=Bottleneck(length=self.core.window))
        self.steps = 0

        # Lessons from Cley (13 Aug 2026): the highest journal line number
        # already taken into the memory. Travels in the snapshot, so a
        # lesson enters the memory exactly once — a resume from an older
        # snapshot replays the same lessons in the same order and lands on
        # the same memory, bit for bit.
        self.lessons_upto = 0

        # The edge of her world, per family. Grows as soon as she can
        # handle that family at the current edge — see open_deeper().
        self.deepest_per = {f: deepest for f in world.FAMILIES}
        self._entrance = deepest         # where a family starts (also one the snapshot does not know yet)
        self.last_once = None            # report of the last one-off lessons (learn_lessons)
        self.edge_threshold = edge_threshold
        # How often she first tries herself. Not every step: writing an
        # answer costs three times the learning step around it, and
        # curiosity does not need the score that often.
        #
        # And then the whole batch at once, not a sample: answering 128
        # tasks costs as much as 16. The time hangs on the number of
        # characters she writes, not on how many tasks go in together.
        self.probe_every = probe_every
        self.dag = _lege_dag()             # today's tally (25 Aug 2026), see dag_lessen
        self.curiosity = curiosity or Curiosity(
            families=world.FAMILIES,
            grades=tuple(range(world.MIN_DEPTH, deepest + 1)),
        )

        # The brake: where the weights stood when something was
        # consolidated, and how important each weight proved.
        self._anchor = None
        self._importance = None

    # --- the brake: pinning important weights ------------------------------

    def consolidate(self, tasks_, batches=40):
        """Establish which weights mattered for this material.

        For every weight, measure how strongly the loss reacts to it — the
        squared gradient, averaged over a number of batches. Weights the
        loss is sensitive to were evidently important; they get braked.

        Costs a few batches of compute once, then only one multiplication
        per weight per step. **It costs no room in the batch** — exactly
        how this differs from replay.

        Where it founders: there must be a moment to consolidate, so there
        must be boundaries between topics. In an open world (F) there are
        none by themselves. Not a detail but the reason this approach does
        not scale into what comes later.

        Not shared over processes: in a group every process computes the
        whole thing itself, identically. Duplicated work, but the brake is
        off in every real run and this stays correct without a collective.
        """
        self.core.train()
        new_importance = {n: torch.zeros_like(p)
                          for n, p in self.core.named_parameters()}

        done = 0
        for start in range(0, len(tasks_), self.batch_size):
            if done >= batches:
                break
            chunk = list(tasks_[start:start + self.batch_size])
            if not chunk:
                continue
            codes, mask = self._make_batch(chunk)
            scores = self._compute_core(codes)
            predicted = scores[:, :-1].reshape(-1, tokens.VOCAB)
            target = codes[:, 1:].reshape(-1)
            counts = mask[:, 1:].reshape(-1)
            loss = F.cross_entropy(predicted[counts], target[counts])

            self.core.zero_grad(set_to_none=True)
            loss.backward()
            for name, p in self.core.named_parameters():
                if p.grad is not None:
                    new_importance[name] += p.grad.detach() ** 2
            done += 1

        if done == 0:
            return None
        for name in new_importance:
            new_importance[name] /= done

        # Add to what already stood: earlier material stays important too.
        # The anchor does move here — you brake toward where you stand now,
        # not toward where you once stood.
        if self._importance is None:
            self._importance = new_importance
        else:
            for name in new_importance:
                self._importance[name] = (self._importance[name]
                                          + new_importance[name])
        self._anchor = {n: p.detach().clone()
                        for n, p in self.core.named_parameters()}
        self.core.zero_grad(set_to_none=True)
        return {"partijen": done,
                "belang_gemiddeld": float(sum(b.sum()
                                              for b in self._importance.values()))}

    def _brake_penalty(self):
        """How far the weights stand from their anchor, weighed by importance."""
        if self._anchor is None or self.brake <= 0:
            return None
        penalty = None
        for name, p in self.core.named_parameters():
            part = (self._importance[name] * (p - self._anchor[name]) ** 2).sum()
            penalty = part if penalty is None else penalty + part
        return 0.5 * self.brake * penalty

    # --- answering ----------------------------------------------------------

    @torch.no_grad()
    def answer(self, tasks_, at_most=ROOM):
        """Answer a series of tasks in one batch.

        `at_most` must be roomy enough for a whole working. With 24 she
        could not finish her sum and every answer counted wrong, however
        well she computed.

        Pad right and track per task how far it is. That works because
        attention is causal: the last real position never looks at the
        padding behind it. Padding left would not work here without
        shifting the positions.
        """
        if parallel.active():
            # One process per card: every process answers its own share on
            # its own card, then everyone gets the whole list back in the
            # original order. Same shape as the two-thread version below,
            # only the threads are processes. A collective — every process
            # calls this with the same tasks, so nobody waits for nothing.
            mine = parallel.share(tasks_)
            done = (self._answer_on(mine, self.core, self.device, at_most)
                    if mine else [])
            return parallel.gather(done)

        cores = self._answer_cores()
        if len(cores) == 1 or len(tasks_) < 2 * len(cores):
            core, device = cores[0]
            return self._answer_on(tasks_, core, device, at_most)

        # Across both cards at once. Every thread drives its own card with
        # its own copy of the network; torch drops the GIL while computing,
        # so they truly run side by side.
        #
        # Before, card 1 answered while card 0 idled, and vice versa while
        # learning — taking turns, not together.
        part = (len(tasks_) + len(cores) - 1) // len(cores)
        chunks = [tasks_[i * part:(i + 1) * part] for i in range(len(cores))]
        outcomes = [None] * len(cores)

        def run(i):
            core, device = cores[i]
            outcomes[i] = self._answer_on(chunks[i], core, device, at_most)

        threads = [threading.Thread(target=run, args=(i,))
                   for i in range(len(cores)) if chunks[i]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return [a for chunk in outcomes if chunk for a in chunk]

    def _answer_cores(self):
        """The network copies answering can run on, one per card.

        The copy on card 1 refreshes once learning happened since last
        time: one transfer of 57 MB over the bus. DataParallel would redo
        that for every character, and there are eighty in a row.
        """
        if self._answer_core is self.core:
            return [(self.core, self.device)]
        if self._weights_fresh:
            self._answer_core.load_state_dict(self.core.state_dict())
            self._weights_fresh = False
        return [(self.core, self.device),
                (self._answer_core, self._answer_device)]

    @torch.no_grad()
    def _answer_on(self, tasks_, core, device, at_most):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.bf16):
            return self._answer_real(tasks_, core, device, at_most)

    @torch.no_grad()
    def _answer_real(self, tasks_, core, device, at_most):
        """The actual loop, on one card."""
        core.eval()
        prompts = [tokens.question_to_sequence(t) for t in tasks_]
        longest = max(len(p) for p in prompts)
        # Shorten rather than fall over: a problem too long deserves a
        # lower mark, not a stranded measurement.
        room = core.window - longest
        if room < 4:
            raise ValueError(
                f"problem of {longest} characters leaves no room to answer "
                f"within a window of {core.window}")
        at_most = min(at_most, room)

        # Pad **left**, not right. All questions then end at the same
        # position, which is what makes the cache possible: one character
        # arrives at a time, at the same place for everyone. Padding right
        # would fill the cache with padding for short questions.
        question = torch.full((len(tasks_), longest), tokens.PAD,
                              dtype=torch.long, device=device)
        for i, prompt in enumerate(prompts):
            question[i, longest - len(prompt):] = torch.tensor(prompt,
                                                               device=device)
        # The mask at full length up front (15 Aug 2026): before, every
        # character grew it with torch.cat, like the cache. Beyond the
        # question everything is real, so False.
        capacity = longest + at_most
        mask_full = torch.zeros(len(tasks_), capacity, dtype=torch.bool,
                                device=device)
        mask_full[:, :longest] = question == tokens.PAD    # nothing real here

        # The question in one pass into a cache laid out at full length;
        # after that only each new character (see KVCache in network.py).
        # On a card the characters are written by the Decoder (25 Aug 2026,
        # see network.py): the same arithmetic with fixed shapes, every step
        # one captured CUDA graph instead of hundreds of separate kernels.
        # AMBER_GRAAF=0 takes the old road; off a card it is the old road.
        decoder = None
        wil = os.environ.get("AMBER_GRAAF", "1")          # "0": never; "snij": no graph, cut to n (bf16-safe); "altijd": also off a card (tests)
        if wil == "altijd" or (wil != "0" and torch.device(device).type == "cuda"):
            decoder = network.Decoder(core, len(tasks_), capacity, mask_full,
                                      use_graph=(wil != "snij"))
            scores = decoder.prefill(question, mask_full[:, :longest])
        else:
            cache = core.new_cache(capacity)
            scores, cache = core.advance(question, cache=cache,
                                         key_mask=mask_full[:, :longest])
        written = []
        done = torch.zeros(len(tasks_), dtype=torch.bool, device=device)
        following = scores[:, -1].argmax(dim=-1)

        for step in range(at_most):
            following = torch.where(done,
                                    torch.full_like(following, tokens.PAD),
                                    following)
            written.append(following)
            done = done | (following == tokens.END)
            if bool(done.all()) or step == at_most - 1:
                break
            if decoder is not None:
                following = decoder.step(following).argmax(dim=-1)
                continue
            scores, cache = core.advance(following[:, None], cache=cache,
                                         offset=longest + step,
                                         key_mask=mask_full[:, :longest + step + 1])
            following = scores[:, -1].argmax(dim=-1)

        answers = torch.stack(written, dim=1).tolist()
        return [tokens.answer_from_sequence([tokens.ANSWER] + row)
                for row in answers]

    def answer_one(self, task):
        return self.answer([task])[0]


    # --- learning -----------------------------------------------------------

    def _make_batch(self, chunk):
        seqs, masks = [], []
        for t in chunk:
            seq, mask = tokens.task_to_sequence(t)
            seqs.append(seq)
            masks.append(mask)
        seqs, masks = tokens.batch(seqs, masks)
        codes = torch.tensor(seqs, dtype=torch.long, device=self.device)
        mask = torch.tensor(masks, dtype=torch.bool, device=self.device)
        return codes, mask

    def _step(self, chunk):
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=self.bf16):
            return self._step_real(chunk)

    def _make_groups(self, chunk):
        """The batch as groups that each pad to their own longest row.

        Until 24 Aug 2026 the whole batch was one rectangle, every row
        padded to the longest of the 64. With replay drawn uniformly from
        her whole memory that longest is ~1000 characters while the average
        row is ~285 (measured on run 7.3): 3.5x the tokens, and attention
        pays length squared, all for padding that counts nowhere. The
        learning step was 90% of the 10 s per step, nearly constant across
        families -- that constant was the air.

        Sorted by length (longest first, ties by position) and cut into
        groups under the same budget (rows x longest^2 <= _CHUNK_BUDGET),
        the same sum costs a fraction. Mathematically nothing changes:
        padding sits on the right, attention is causal and the mask is off
        there, so no real position ever sees it, and the loss is the sum
        over counted positions divided by the whole batch's count whatever
        the grouping. test-batch-groups.py proves the step equal to the
        one-rectangle version. Grouping depends only on the lengths, so it
        is as repeatable as the rest (not bit for bit the old numbers: the
        kernels see other shapes -- a new baseline at a run boundary).
        """
        seqs, masks = [], []
        for t in chunk:
            seq, mask = tokens.task_to_sequence(t)
            seqs.append(seq)
            masks.append(mask)
        order = sorted(range(len(seqs)), key=lambda i: (-len(seqs[i]), i))
        groups, current, longest = [], [], 0
        for i in order:
            if not current:
                longest = len(seqs[i])
            elif ((len(current) + 1) * longest * longest > _CHUNK_BUDGET
                  or len(seqs[i]) < _GROUP_SPAN * longest):
                # a new group when the budget is full, or when this row is
                # so much shorter that padding it up would be mostly air
                groups.append(current)
                current, longest = [], len(seqs[i])
            current.append(i)
        if current:
            groups.append(current)
        total_counts = sum(sum(m[1:]) for m in masks)
        out = []
        for g in groups:
            s, m = tokens.batch([seqs[i] for i in g], [masks[i] for i in g])
            out.append((torch.tensor(s, dtype=torch.long, device=self.device),
                        torch.tensor(m, dtype=torch.bool, device=self.device)))
        return out, total_counts

    def _step_real(self, chunk):
        self.core.train()
        # Memory budget (9 Aug 2026): attention costs rows x length^2, and
        # when the deep material opened the X399's 8 GB card ran out of
        # memory thirty-four times in a row. The same sum, in groups:
        # gradients add up across groups, so the outcome is mathematically
        # equal to one big batch -- only the memory stays bounded. Since
        # 24 Aug 2026 the groups are cut by length (see _make_groups).
        groups, total_counts = self._make_groups(chunk)

        self.optimizer.zero_grad(set_to_none=True)
        # `total_counts` is over the WHOLE batch, also with one process per
        # card: every process divides its share's loss by the same number,
        # so the summed gradients equal the gradient of one big batch -- the
        # same identity the groups rely on, one level up.
        total_loss = torch.zeros((), device=self.device)
        for codes, mask in groups:
            # My rows. Alone that is all of them; in a group every `world`-th
            # row (parallel.share). Shares need not have the same shape: the
            # gradients meet per parameter, not per activation.
            codes_mine = parallel.share(codes)
            mask_mine = parallel.share(mask)
            if len(codes_mine) == 0:
                continue
            scores = self._compute_core(codes_mine)
            # The score at position j predicts the character at j+1. The
            # mask must therefore shift one along; one position off and she
            # learns to predict the question.
            predicted = scores[:, :-1].reshape(-1, tokens.VOCAB)
            target = codes_mine[:, 1:].reshape(-1)
            counts = mask_mine[:, 1:].reshape(-1)
            summed = F.cross_entropy(predicted[counts], target[counts],
                                     reduction="sum")
            (summed / max(1, total_counts)).backward()
            # Summed on the card, read once after the loop (25 Aug 2026):
            # `.item()` per group made Python wait for the card each time,
            # and the next group's launches waited with it. The gradient is
            # untouched; only the reported number is added up elsewhere.
            total_loss = total_loss + summed.detach()
        # Meet over the bus: the shares' gradients add up to the gradient of
        # the whole batch, and every process leaves with that total. From
        # here on both take exactly the same step. The measured loss is
        # summed too, so the number in the journal is the whole batch's.
        # Alone both calls do nothing.
        parallel.sum_grads(self.core.parameters())
        total_loss = parallel.sum_number(float(total_loss.item()))
        measured = total_loss / max(1, total_counts)

        # The brake (off by default — EWC, measured and rejected 8 Aug 2026)
        # is computed on every process alike, AFTER the sum: it depends only
        # on the weights, so adding it before the sum would count it twice.
        penalty = self._brake_penalty()
        if penalty is not None:
            penalty.backward()

        torch.nn.utils.clip_grad_norm_(self.core.parameters(), 1.0)
        self.optimizer.step()
        # Let the gradients go right away (15 Aug 2026): the next _step_real
        # rebuilds them from zero anyway, but between two learning steps she
        # answers — the probe every fourth step, the exams every 500th —
        # and 82 MB of dead fp32 gradients sat inside that peak. Bit for bit
        # the same learning; nothing reads .grad after the step (consolidate
        # and the brake compute their own, the snapshot never stores them).
        self.optimizer.zero_grad(set_to_none=True)
        self.steps += 1
        self._weights_fresh = True
        # The measured loss is the one *without* the brake: otherwise the
        # brake appears to worsen the learning while it is merely another
        # quantity.
        return measured

    @property
    def new_per_batch(self):
        """How many new tasks fit in a batch.

        The batch always stays the same size. Replay therefore comes **at
        the cost of** new material, not on top — otherwise you compare a
        run with more compute against one with less, and measure the
        amount instead of the mechanism. That mistake sat in the first C
        baseline of 8 Aug 2026.
        """
        if self.replay_share <= 0:
            return self.batch_size
        return max(1, self.batch_size - int(self.batch_size * self.replay_share))

    def learn(self, tasks_, remember=True):
        """Learn from a series of tasks. Satisfies the measuring loop.

        What is learned also enters the memory, through the bottleneck.
        Without that the memory stays empty and replay does nothing — then
        a comparison with and without replay appears to say something while
        both sides do the same.
        """
        losses = []
        step_size = self.new_per_batch
        for start in range(0, len(tasks_), step_size):
            chunk = list(tasks_[start:start + step_size])
            if remember:
                for t in chunk:
                    self.memory.remember(t, t.solution, None)
            if self.replay_share > 0 and len(self.memory):
                room = self.batch_size - len(chunk)
                picker = tasks_module.Picker(
                    determinism.seed_for_step(self.steps))
                for old in self.memory.replay(room, picker):
                    recovered = _as_task(old)
                    if recovered is not None:
                        chunk.append(recovered)
            if chunk:
                losses.append(self._step(chunk))
        return sum(losses) / len(losses) if losses else None


    # --- the long loop ------------------------------------------------------

    def open_deeper(self, step):
        """Open the world deeper once she can handle the edge — per family.

        Without an edge she immediately wanders at depth 12, where she can
        do nothing and so learns nothing. With an edge that grows along,
        the world always lies just above what she can.

        **Per family, not all at once.** The first version demanded she
        handle all three families at the current depth. On 8 Aug 2026
        arithmetic was stuck at 4% while code sat at 100% — and the whole
        world stayed shut, for code too. One slow family must not lock up
        the others.

        No rolling back. What is open stays open; if she slips, curiosity
        pulls her back there by itself.
        """
        opened = []
        for family in world.FAMILIES:
            edge = self.deepest_per[family]
            if edge >= world.max_depth(family):
                continue
            if self.curiosity.score.get((family, edge), 0.0) < self.edge_threshold:
                continue
            self.deepest_per[family] = edge + 1
            self.curiosity.add((family, edge + 1), step)
            opened.append((family, edge + 1))
        return opened

    @property
    def deepest(self):
        """The deepest layer open anywhere — reporting only."""
        return max(self.deepest_per.values())

    def work(self, step):
        """One step of the long loop: pick, practice, remember.

        This is what happens at night. Which topic, which tasks and which
        replays all follow from (seed, step number), so the whole stream is
        repeatable.
        """
        determinism.begin_step(step)
        picker = tasks_module.Picker(determinism.seed_for_step(step))

        family, depth = self.curiosity.pick(step, picker)
        start = picker.integer(0, 500_000)
        try:
            # The study-material bound follows the window, like the
            # bottleneck (10 Aug 2026): at window 512 this is exactly the
            # old 400, and with window growth the material grows along
            # instead of silently lagging as a fossilized number.
            chunk = world.learning_tasks(family, depth, self.batch_size,
                                         start=start,
                                         room=self.core.window - 112,
                                         exclude=exams.material())
        except ValueError:
            # A depth without enough problems must never kill the run.
            # Curiosity toward it fades (score 1: nothing left to gain),
            # the edge snaps back, and this step is skipped.
            self.curiosity.update((family, depth), 1.0, step)
            if self.deepest_per.get(family, 0) >= depth:
                self.deepest_per[family] = max(1, depth - 1)
            self.steps += 1
            return {"step": step, "family": family, "depth": depth,
                    "score": None, "loss": None, "skipped": True,
                    "deepest_per": dict(self.deepest_per), "deeper": []}

        # Every so many steps, see what she makes of it now — that steers
        # curiosity and enters the memory.
        #
        # Not every step: writing an answer costs three times the learning
        # step around it. And then the whole batch, because answering 128
        # tasks costs as much as 16: the time hangs on the characters she
        # writes, not on how many tasks go in.
        score = None
        goed = fout = weetniet = None
        spel = speelt(step)                # the play hour: no mark, no gate
        if step % self.probe_every == 0 and not spel:
            given = self.answer(chunk,
                                at_most=room_for(depth, family,
                                                   self.core.window))
            right = [t.check(a) for t, a in zip(chunk, given)]
            for t, a, r in zip(chunk, given, right):
                self.memory.remember(t, a, r)
            score = score_of(right)
            goed, fout, weetniet = telling(right)
            self.curiosity.update((family, depth), score, step)

        loss = self.learn(chunk)
        deeper = [] if spel else self.open_deeper(step)
        # the day's tally
        d = self.dag
        bak = d["gespeeld"] if spel else d["geoefend"]
        bak[family] = bak.get(family, 0) + 1
        if score is not None:
            som, n = d["scores"].get(family, (0.0, 0))
            d["scores"][family] = (som + score, n + 1)
        for f, _ in deeper:
            if f not in d["open"]:
                d["open"].append(f)
        return {"step": step, "family": family, "depth": depth,
                "score": score, "loss": loss, "spel": spel,
                "goed": goed, "fout": fout, "weetniet": weetniet,
                "deepest_per": dict(self.deepest_per), "deeper": deeper}

    # --- state --------------------------------------------------------------

    def spec(self):
        return self.core.spec()

    # --- her whole state travels in the snapshot ---------------------------
    # N: "Her state is more than weights." What is not in here is silently
    # gone after a restart — like her memory at the crash of 9 Aug 2026.
    # Keys are Dutch: they are her state, in every snapshot ever written.

    def learn_lessons(self, rows):
        """Lessons from Cley enter the memory — through the doorway, like
        everything else. There is no second entrance (U).

        A lesson is the question with the **right** answer, delivered via
        the mailbox on a run boundary (journal kind "les"). Never her own
        answer: the correction is the lesson (8 Aug 2026). Family "gesprek",
        grade 1 — the drawer labels, so the C measurement sees the family
        and balanced forgetting keeps it a floor.

        Idempotent on the journal line number: rows at or below
        `lessons_upto` are already in the memory (it travels in the
        snapshot). Returns (taken, refused) — refused means the doorway
        (the window) was too narrow, and that is a fact worth logging,
        not a crash.
        """
        taken = refused = 0
        once = []
        for row in sorted((r for r in rows
                           if int(r.get("nr", 0)) > self.lessons_upto),
                          key=lambda r: int(r["nr"])):
            lesson = tasks_module.Task(
                family="gesprek", grade=1, number=int(row["nr"]),
                problem=str(row["vraag"]), solution=str(row["antwoord"]),
                working=None)
            if row.get("eenmalig"):
                # A one-off lesson (17 Aug 2026, the week-1 memory test):
                # learned now, a few passes, and NOT kept in the memory —
                # so it is never replayed. What she still knows of it weeks
                # later is raw retention, without rehearsal.
                once.append(lesson)
            elif self.memory.remember(lesson, None, None):
                taken += 1
            else:
                refused += 1
            self.lessons_upto = int(row["nr"])
        self.last_once = None
        if once:
            room = min(self.core.window // 2,
                       max(len(t.solution) for t in once) + 8)
            passes = right = 0
            while passes < ONCE_MAX_PASSES:
                self.learn(once, remember=False)
                passes += 1
                answers = self.answer(once, at_most=room)
                right = sum(1 for t, a in zip(once, answers) if t.check(a))
                if right >= ONCE_TARGET * len(once):
                    break
            self.last_once = {"passes": passes, "goed": right, "van": len(once)}
        return taken, refused, len(once)

    def fingerprint(self):
        """A digest of everything that must be equal across processes:
        weights, optimizer moments, and the small state around them (the
        step, how many memories, the lesson counter, the open edge, the
        curiosity). life.py compares it over the group before every
        snapshot — parallel.same() — and refuses to go on if the two
        learners have drifted apart. Not the memory's content: millions of
        codes to hash every 500 steps, while its length and the curiosity
        it feeds catch any drift within a step or two."""
        return parallel.fingerprint(
            self.core, self.optimizer,
            extra=(self.steps, len(self.memory), self.lessons_upto,
                   sorted(self.deepest_per.items()),
                   sorted(self.curiosity.score.items()),
                   sorted(self.curiosity.last.items())))

    def dag_afsluiten(self, step):
        """End of a day (25 Aug 2026): the day's lessons into the memory,
        through the doorway like every lesson, and a fresh tally. Returns
        the lessons, for the journal."""
        nummer = step // DAG_STAPPEN
        lessen = dag_lessen(self.dag, nummer)
        for i, (vraag, antwoord) in enumerate(lessen):
            les = tasks_module.Task(family="gesprek", grade=1, number=step * 10 + i,
                                    problem=vraag, solution=antwoord, working=None)
            self.memory.remember(les, None, None)
        self.dag = _lege_dag()
        return lessen

    def carry(self):
        return {
            "geheugen": self.memory.carry(),
            "dag": self.dag,                   # today's tally (25 Aug 2026)
            "nieuwsgierig": self.curiosity.carry(),
            "les_tot": self.lessons_upto,
            "diepste_per": dict(self.deepest_per),
            # The optimizer-step counter (16 Aug 2026). It seeds the replay
            # picker, and it is NOT the loop's step number: one work() is
            # two optimizer steps (40 new + 24 replayed, then 24 + 40), so
            # setting it to "step - 1" on resume — what life.py did — gave
            # a resumed run other replay draws than a run straight through.
            # Repeatable, but not bit for bit the same as never having
            # stopped. Now it travels; snapshots without the key keep the
            # old behaviour.
            "leerstappen": self.steps,
            # Since 11 Aug 2026: the snapshot knows her shape, so a loader
            # can follow her window instead of assuming the default. Run-3
            # snapshots lack this key; loaders must cope with that.
            "vorm": self.core.spec(),
        }

    def grow_layer(self, position=None):
        """Grow one layer deep. The output stays bit for bit the same, and
        everything around the core follows (15 Aug 2026, phase-5 groundwork).

        The core's `add_block` puts in a block with both gates at zero —
        `x + 0 * f(x)` is exactly `x`. What the core cannot do itself is the
        rest of the machinery, and that is where growth breaks things
        quietly (roadmap: "a network that grows breaks the optimizer's
        state"):

        * **the optimizer.** AdamW's state (the two moments per weight) is
          kept per parameter. A fresh optimizer over the grown core would
          throw the moments of fourteen million weights away — the whole
          run's momentum. Adding a second parameter group would keep them,
          but a snapshot then carries a two-group optimizer that only loads
          into an optimizer built the same way — a shape nobody rebuilds
          from the spec. So: one fresh optimizer, one group, and the old
          moments transplanted by parameter identity. The new block starts
          with empty moments, which is right — it has learned nothing yet.
          The saved state dict then indexes the grown core's parameter
          order, and `Core.from_spec` rebuilds exactly that order.
        * **the answer copy on card 1** has the old shape: rebuild it from
          the spec and mark the weights for the next transfer.
        * **DataParallel** wraps `self.core` by reference and replicates on
          every call, so it picks the new block up by itself.

        Returns the new block. Shrinking does not exist, on purpose.
        """
        old_state = dict(self.optimizer.state)
        old_group = self.optimizer.param_groups[0]
        new_block = self.core.add_block(position)
        fresh = torch.optim.AdamW(self.core.parameters(),
                                  lr=old_group["lr"])
        for key, value in old_group.items():
            if key != "params":
                fresh.param_groups[0][key] = value
        for p in self.core.parameters():
            if p in old_state:
                fresh.state[p] = old_state[p]
        self.optimizer = fresh
        if self._answer_core is not self.core:
            self._answer_core = Core.from_spec(self.core.spec()).to(
                self._answer_device)
            self._answer_core.eval()
            self._weights_fresh = True
        return new_block

    def grow_width(self, heads=None, hidden=None):
        """Grow wider inside the blocks: to `heads` attention heads and/or a
        feedforward of `hidden` units. The output stays the same, and the
        machinery follows (16 Aug 2026, the second half of E).

        The core does the weight surgery (`grow_heads`, `grow_hidden`: new
        heads and units come in behind zero columns, so what she computes
        does not change). What has to follow, as with `grow_layer`:

        * **the optimizer.** Here the old parameters are *replaced* by
          bigger tensors, not merely joined by new ones. Their moments are
          carried over by the same `place` rule the core used for the
          weights: old moments in the old slots, zeros in the new — the new
          rows and columns have learned nothing yet. The step count is
          kept, so AdamW's bias correction stays where it was. Untouched
          parameters keep their moments by identity, as before.
        * **the answer copy** is rebuilt from the spec.
        * **DataParallel** picks the new modules up by itself.

        The residual width itself does not grow: LayerNorm averages over it,
        so no padding leaves the old numbers alone. That is why "wider"
        means heads and hidden units. Shrinking does not exist.
        """
        if heads is None and hidden is None:
            raise ValueError("grow_width: say how — heads=, hidden=, or both")
        old_state = dict(self.optimizer.state)
        old_group = self.optimizer.param_groups[0]
        transplants = []
        if heads is not None:
            transplants += self.core.grow_heads(heads - self.core.heads)
        if hidden is not None:
            transplants += self.core.grow_hidden(hidden)
        fresh = torch.optim.AdamW(self.core.parameters(),
                                  lr=old_group["lr"])
        for key, value in old_group.items():
            if key != "params":
                fresh.param_groups[0][key] = value
        for p in self.core.parameters():
            if p in old_state:
                fresh.state[p] = old_state[p]
        for old, new, place in transplants:
            if old not in old_state:
                continue
            was = old_state[old]
            carried = {}
            for key, value in was.items():
                if torch.is_tensor(value) and value.shape == old.shape:
                    moved = torch.zeros_like(new)
                    place(value, moved)
                    carried[key] = moved
                else:
                    carried[key] = value          # the step count
            fresh.state[new] = carried
        self.optimizer = fresh
        if self._answer_core is not self.core:
            self._answer_core = Core.from_spec(self.core.spec()).to(
                self._answer_device)
            self._answer_core.eval()
            self._weights_fresh = True
        return transplants

    def adopt_shape(self, spec):
        """Take the shape of a snapshot before its weights are loaded.

        A snapshot from a grown net has more blocks than a fresh Learner;
        `load_state_dict` would refuse it. So first grow to the snapshot's
        depth (blocks at the end — the snapshot's own order is kept, since
        the weights overwrite everything afterwards), then wider if the
        snapshot has more heads or hidden units, then follow its window.
        The residual width and the head size cannot change; a mismatch
        there is an error, not something to paper over.
        """
        if not spec:
            return
        spec = bridge.translate_spec(spec)
        head_size = spec.get("head_size") or spec.get("width", 0) // max(
            spec.get("heads", 1), 1)
        if spec.get("width", self.core.width) != self.core.width or \
                head_size != self.core.head_size:
            raise ValueError(
                f"snapshot has width {spec.get('width')} × head size "
                f"{head_size}, this net {self.core.width} × "
                f"{self.core.head_size} — that growth does not exist")
        while len(self.core.blocks) < spec.get("layers", 0):
            self.grow_layer()
        if len(self.core.blocks) > spec.get("layers", len(self.core.blocks)):
            raise ValueError(
                f"snapshot has {spec['layers']} layers, this net "
                f"{len(self.core.blocks)} — nets do not shrink")
        heads = spec.get("heads", self.core.heads)
        hidden = spec.get("hidden", self.core.hidden)
        if heads < self.core.heads or hidden < self.core.hidden:
            raise ValueError(
                f"snapshot has {heads} heads × {hidden} hidden, this net "
                f"{self.core.heads} × {self.core.hidden} — nets do not shrink")
        if heads > self.core.heads or hidden > self.core.hidden:
            self.grow_width(heads=heads if heads > self.core.heads else None,
                            hidden=hidden if hidden > self.core.hidden else None)
        self.adopt_window(spec.get("window") or 0)

    def adopt_window(self, window):
        """Follow a grown window: core, answer copy and doorway together.

        Growing changes nothing about the weights (test-window-growth.py);
        forgetting to grow the bottleneck would silently refuse every
        experience longer than the old window — the exact class of quiet
        failure this project hunts.
        """
        if not window:
            return
        for core in {self.core, self._answer_core}:
            if window > core.window:
                core.grow_window(window)
        if window > self.memory.bottleneck.length:
            self.memory.bottleneck.length = window

    def restore(self, carried, step=None):
        """`step` is the run step the snapshot stands at (life.py passes it,
        17 Aug 2026). Curiosity's clocks are run steps: a new family enters
        with `last = step`, and every `last` the snapshot carries is clamped
        to it — once, a restore handed the optimizer's count here (399.000
        for run step 384.500), and the future 'last' gave logica a negative
        weight that made it and every later room unreachable. Callers that
        do not know the step (measuring tools) leave it out: then the newest
        clock in the carried state stands in for it."""
        if not carried:
            return
        if carried.get("geheugen"):
            self.memory.restore(carried["geheugen"])
        # Snapshots from before 13 Aug 2026 lack this key: then no lesson
        # has ever been taken in, and 0 is exactly right.
        self.lessons_upto = int(carried.get("les_tot") or 0)
        if carried.get("nieuwsgierig"):
            self.curiosity.restore(carried["nieuwsgierig"])
        if carried.get("leerstappen") is not None:
            self.steps = int(carried["leerstappen"])
        if carried.get("dag"):                 # snapshots from before 25 Aug 2026 lack it: a fresh day
            d = carried["dag"]
            self.dag = {"geoefend": dict(d.get("geoefend", {})), "gespeeld": dict(d.get("gespeeld", {})),
                        "scores": {f: (float(v[0]), int(v[1])) for f, v in d.get("scores", {}).items()},
                        "open": list(d.get("open", []))}
        if carried.get("diepste_per"):
            # Bounded restore: a snapshot can carry a world open too deep
            # (code to 12, from before the fence of 8 existed).
            self.deepest_per = {f: min(d, world.max_depth(f))
                                for f, d in carried["diepste_per"].items()}
        # And curiosity can still know those too-deep topics. Leave them
        # and she knocks on empty rooms now and then: every pick there is
        # a skipped step. Measured on the run of 9 Aug 2026: code 9–12
        # kept pulling after the fence of 8.
        dead = [(f, g) for f, g in self.curiosity.kinds
                if g > world.max_depth(f)]
        for kind in dead:
            self.curiosity.kinds.remove(kind)
            self.curiosity.score.pop(kind, None)
            self.curiosity.last.pop(kind, None)
        # A family the snapshot does not know yet — the world grew after it
        # was written (16 Aug 2026: geheugen, on the rungrens to run 6.5) —
        # comes in at the entrance: its edge at the default depth, and its
        # first depths in curiosity at score zero, new and therefore
        # attractive. Without this the restored curiosity holds only the
        # old kinds and the new family would never be drawn: an empty
        # room nobody ever knocks on. Families the snapshot does know
        # keep exactly what they carried.
        now = int(step) if step is not None else max(
            [int(v) for v in self.curiosity.last.values()] or [0])
        if step is not None:
            for kind, last in list(self.curiosity.last.items()):
                if last > now:
                    self.curiosity.last[kind] = now
        for f in world.FAMILIES:
            if f not in self.deepest_per:
                self.deepest_per[f] = min(self._entrance, world.max_depth(f))
            for g in range(world.MIN_DEPTH, self.deepest_per[f] + 1):
                self.curiosity.add((f, g), now)


def _as_task(decoded):
    """Turn a memory back into something to practice on.

    In phase 1 the encoding is reversible and the task comes out whole.
    Once the bottleneck squeezes in phase 4, what comes out is no longer
    the original problem but what she retained of it — and this is where
    that difference becomes visible.
    """
    if not decoded["opgave"]:
        return None
    # What comes out of the memory *is* the working; the answer is its last
    # number. Replaying then teaches the same as first seeing, not a
    # shortcut.
    whole = decoded["oplossing"]
    numbers = tasks_module._NUMBER.findall(whole)
    solution = numbers[-1] if numbers else whole
    return tasks_module.Task(
        family=decoded["familie"],
        grade=decoded["graad"],
        number=-1,                       # a memory, not a task from stock
        problem=decoded["opgave"],
        solution=solution,
        # A working whenever the stored text is more than the bare answer —
        # not just when it contains "=". A lesson like "Parijs heeft 2
        # miljoen inwoners" would otherwise replay as its last number and
        # the sentence itself would silently vanish (13 Aug 2026).
        working=None if whole == solution else whole,
    )
