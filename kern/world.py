"""
The world she lives in — building blocks that stack, not a catalogue.

From the roadmap: *"F is the heaviest design decision of the project: too
simple and she is done learning within a week, too rich and you can no
longer measure anything."* And among the risks, "F turns out chosen too
simple after a year" sits at 40%.

`tasks.py` is a catalogue: fifteen fixed kinds. Once she can do those her
world is finished, and extending it means someone inventing new kinds every
year. That does not scale across years.

Here instead are **building blocks you can stack on each other**. For
arithmetic those are numbers, plus, minus, times and parentheses — nothing
more. But you can stack them as deep as you want:

    depth 1:  47
    depth 2:  (3 + 7)
    depth 3:  ((3 + 7) * 4)
    depth 5:  (((3 + 7) * 4) - ((2 * 6) + 9))

Getting harder is stacking deeper, which makes difficulty a **dial** rather
than five steps you eventually fall off. The space grows exponentially with
depth instead of linearly with what gets typed.

TWO THINGS FIXED HERE
---------------------
**The world may grow, the exams never.** What is made here is study
material. The exams live in `proefwerken.py` and do not change — otherwise
today's measurements cannot be compared with last year's.

**Nothing from this world may collide with an exam.** Not by number and not
by text. The same latch as in `tasks.py`, and for the same reason: on 8 Aug
2026 a quarter of the study material there produced the same problems as
the benchmark.

Composability is moreover exactly the property U later asks of her
notation. A world that itself consists of compositions raises the odds her
notation becomes one too. No proof, but the right direction.

Her world speaks Dutch — every problem and working this module produces is
byte-identical to wereld.py's, which toets-migratie.py enforces. Only the
code around the world is English.
"""

from tasks import FAMILIES as _MEASURED_FAMILIES, Task, Picker, _mix

# The world's families: the three of the frozen measuring stick, and then
# what the world itself added. **Append only, never reorder**: the seed of
# every task carries the family's position in this tuple, so a family
# inserted in front would silently move every problem she ever saw. The
# measuring stick (tasks.py) keeps its own three — the world grows, an
# exam never does.
#   16 Aug 2026: "geheugen" — an answer that depends on something earlier
#   in the sequence (see _memory below).
#   17 Aug 2026: "logica" — if-then chains over true/false facts (_logic).
FAMILIES = _MEASURED_FAMILIES + ("geheugen", "logica")

# Own constant, separate from tasks.py's: the world and the exams are two
# separate things and must be so in their numbers too.
WORLD_SEED = 0x5765_7265_6C64          # "Wereld"

MIN_DEPTH = 1
# The fence follows the window, measured at the 85% standard (at least
# 85% of usable problems fit with their working). At 512 that gave 17
# (measured 9 Aug 2026: 100% through 15, 93% at 17, 66% at 18). At 768,
# measured 10-11 Aug 2026 for run 4: arithmetic fits 99% at depth 26.
MAX_DEPTH = 60

# Per family the fence can sit lower. Puzzle rows from depth 6 are woven so
# deep that no method comes out that delivers the answer — 16% usable at 6,
# 4% above. A problem that can only be guessed does not belong in her world,
# and without this fence curiosity does steer her there and it jams.
#
# Longer rows (measured 10 Aug 2026, see _row) rescue the explanation —
# depth 6 goes from 16% to 36% explainable, as much as depth 5 itself — but
# the working of such a deep weave runs 500–1200 characters and did not fit
# a 512 window. At 768 (run 4, measured 10-11 Aug 2026) puzzle 6 has 95% of
# its usable problems fitting and code 11 fits 100%; at 512 the fences
# stood at 5 and 8. Run 3 opened code to 12 on 9 Aug 2026 and crashed
# there six times on "1 of the 64 tasks found" — a depth without problems
# is not a world; hence fences, not hope.
#
# Puzzle 9 (was 6): the compact working (see _explain) broke the length
# wall — measured 13 Aug 2026 at window 1024, of the explainable problems
# 100% fits at depth 7, 8 and 9, and 80% at 10 (under the 85% standard,
# so the fence stops at 9). Explainability itself stays 21-30% at every
# depth, the fixed tax of deep weaves; learning_tasks' search bound
# handles that fine. NOTE: this fence belongs to window 1024 — run 5.
# Run 4 (768) keeps its own copy of this file with fence 6.
MAX_DEPTH_PER = {"puzzel": 20, "code": 30, "geheugen": 40, "logica": 12}


def max_depth(family):
    return MAX_DEPTH_PER.get(family, MAX_DEPTH)

# The conservative default for callers who do not know a window: 400 fitted
# the first 512 window with room for the own tokens. The learning loop and
# the kijker pass the real room themselves (window - 112); this default
# only bounds direct calls.
#
# Wider than the initial 200, because a working is much longer than a bare
# answer: at depth 12 it is already 247 characters. With a 256 window the
# loop jammed instantly on the longest exam problem.
MAX_CHARS = 400


def _seed_of(family, depth, number):
    core = _mix(WORLD_SEED ^ _mix(FAMILIES.index(family) * 1_000_003))
    return _mix(core ^ _mix(depth * 7919 + number))


# --- rekenen (arithmetic) ----------------------------------------------------
# An expression tree. Composite branches get parentheses only where
# precedence truly demands them.

# Precedence, to determine where parentheses are really needed.
_PRECEDENCE = {"+": 1, "-": 1, "*": 2}
_LEAF = 3


def _parens(text, own, needed, right_of_minus=False):
    """Wrap in parentheses, but only where precedence demands it.

    The first version parenthesized everything — "then nobody needs to know
    precedence rules". That looked careful and was a mistake: her world
    wrote everything as `(66 - 55)` while the frozen exam asks `8 + 2`. She
    had then never seen a sum without parentheses, and scored zero on them.
    A benchmark she cannot reach on principle is not a benchmark.
    """
    if own < needed or (right_of_minus and own <= needed):
        return f"({text})"
    return text


def _work_out(node, steps):
    """Evaluate the tree and write every operation down.

    This is the difference between estimating and computing. `13 * 8 * 11`
    in one pass through the network is too much to ask; `13 * 8 = 104`
    followed by `104 * 11 = 1144` is twice something easy. On 8 Aug 2026 she
    was stuck at 4% without workings, systematically just off.
    """
    if node[0] == "blad":
        return node[1]
    _, op, left, right = node
    lv = _work_out(left, steps)
    rv = _work_out(right, steps)
    value = (lv + rv if op == "+" else
             lv - rv if op == "-" else lv * rv)
    steps.append(f"{lv} {op} {rv} = {value}")
    return value


def _arith_tree(operations, t, small):
    """`operations` is how many operations may still go in.

    Depth counts operations, not layers: depth 1 is one operation, and that
    is `3 + 7`. This gives the world a real floor. In the first version even
    the easiest task was `(66 - 55)` — two digits and parentheses — and then
    there is no entrance for something starting from zero.
    """
    if operations <= 0:
        n = t.integer(1, small)
        return str(n), _LEAF, ("blad", n)

    op = t.choice(("+", "-", "*"))
    precedence = _PRECEDENCE[op]

    if op == "*":
        # One side always stays a small number. Multiplying two deep
        # branches lets the outcome run away exponentially.
        lt, lp, lnode = _arith_tree(operations - 1, t, small)
        right = t.integer(2, 12)
        return (f"{_parens(lt, lp, precedence)} * {right}",
                precedence, ("op", "*", lnode, ("blad", right)))

    left_part = t.integer(0, operations - 1)
    right_part = operations - 1 - left_part
    lt, lp, lnode = _arith_tree(left_part, t, small)
    rt, rp, rnode = _arith_tree(right_part, t, small)
    return (f"{_parens(lt, lp, precedence)} {op} "
            f"{_parens(rt, rp, precedence, right_of_minus=(op == '-'))}",
            precedence, ("op", op, lnode, rnode))


def _arithmetic(depth, t):
    # The numbers grow along with the depth gradually. The first version
    # jumped from single digits at depth 1 to 1–99 at depth 2, and then two
    # things change at once: an extra operation and bigger numbers. Her
    # score fell from 77% to 7% there. A dial must be gradual, or it is a
    # step after all.
    small = min(40, 9 * depth)
    text, _, node = _arith_tree(depth, t, small)
    steps = []
    value = _work_out(node, steps)
    return text, value, " ; ".join(steps)


# --- rijen (rows) -------------------------------------------------------------
# Rules made of rules. The base is "add something" or "multiply by
# something"; above that you can alternate two rules, or apply a rule to the
# differences instead of to the numbers themselves.

_BASES = ("maal", "plus", "plus", "beide-vorige")


def _row_series(depth, t, length, bases=_BASES):
    """Build a series of `length` numbers.

    A series, not a "next value" function — otherwise a rule cannot be
    applied to another rule. That was the mistake in the first version:
    "second order" ignored the rule beneath it, and depth 5 equalled
    depth 8.

    `bases` is the set of bricks at the bottom. The default is the world
    as it was; the keer-plus rows (15 Aug 2026) pass their own brick.
    """
    if depth <= 1:
        kind = t.choice(bases)
        if kind == "keer-plus":
            # x → 2x + b (or 2x − b): the differences double, so the
            # method she has peels it — differences, then the fixed ratio.
            # Factor 2 only: with 3 a seventeen-number strand runs past
            # forty million. Minus keeps the row rising (start > b).
            b = t.integer(1, 9) * t.choice((1, 1, -1))
            start = t.integer(1, 20) + (abs(b) if b < 0 else 0)
            out = [start]
            while len(out) < length:
                out.append(2 * out[-1] + b)
            return out
        if kind == "maal":
            # Up to ×6, as the grondslag exam asks — until 11 Aug 2026 this
            # was ×2/×3 and puzzle grade 2 sat at 30%: facing a ×5 row she
            # fell back to subtracting and got lost. The start shrinks with
            # the factor so the last number stays near the exam's (~400,000)
            # instead of exploding. Floor 30: the cap serves the short,
            # shown rows; long strands (depth 6+) would otherwise collapse
            # onto start 1–2 and kill variety (measured 11 Aug 2026, puzzle
            # d12 dropped from ~1900 to 135 distinct problems per 2000).
            factor = t.integer(2, 6)
            cap = max(30, min(150, 400_000 // factor ** max(1, length - 1)))
            start = t.integer(1, cap)
            return [start * factor ** i for i in range(length)]
        if kind == "beide-vorige":
            # Each number is the sum of its two predecessors — the form of
            # grondslag puzzle 5, which existed nowhere in the world until
            # 11 Aug 2026 (0% on the exam).
            out = [t.integer(1, 60), t.integer(1, 60)]
            while len(out) < length:
                out.append(out[-2] + out[-1])
            return out[:length]
        start = t.integer(1, 30)
        step = t.integer(2, 19) * t.choice((1, 1, -1))
        return [start + i * step for i in range(length)]

    if t.choice(("afwisselend", "opgeteld", "opgeteld")) == "afwisselend":
        # Two series woven together.
        a = _row_series(depth - 1, t, (length + 1) // 2, bases)
        b = _row_series(depth - 1, t, length // 2 + 1, bases)
        return [a[i // 2] if i % 2 == 0 else b[i // 2] for i in range(length)]

    # The series beneath is this one's differences. That is how stacking
    # really works: a row with a fixed difference becomes one with a growing
    # difference, and one more layer makes that growth itself grow.
    differences = _row_series(depth - 1, t, length - 1, bases)
    out = [t.integer(1, 30)]
    for d in differences:
        out.append(out[-1] + d)
    return out


def _explain(row, layer=0, compact=False):
    """Derive the last number from the row before it, with a working method.

    Returns (steps, success). The first version only showed the differences
    and glued the answer on:

        47 - 22 = 25 ; 97 - 47 = 50 ; ... ; 797 + 800 = 1597

    That 800 comes out of nowhere — nothing in the working says where. With
    a fixed difference it happened to work, above that it did not. She
    learned a method that does not produce the answer, and got stuck exactly
    where the difference starts changing. Found on 9 Aug 2026.

    Now the method is genuinely carried through: if the difference is not
    fixed, the next difference is derived the same way, for as long as it
    takes to come out.

    `compact` (depth 7 and up, 13 Aug 2026): each layer writes its
    differences as one row — `verschillen: 10, 38, 67` — instead of one
    subtraction equation per pair. Every number is still one easy step
    (both operands stand directly above), but the working of a deep weave
    shrinks by roughly half; at full width depth 8 fitted a 1024 window
    for only 30% of its problems. The additions on the way back up stay
    written in full: those produce the new numbers, and a number may
    never come out of nowhere. Depths 1-6 keep the wide form bit for bit,
    so nothing she already mastered changes shape.
    """
    # The layer bound must grow with the longest row: depth 8 needs seven
    # layers. For rows of seven nothing changes — the length bound (< 3)
    # always triggers before layer 5, so the material through depth 5 stays
    # bit for bit the same.
    if layer > 8 or len(row) < 3:
        return [], False

    visible, target = row[:-1], row[-1]
    differences = [visible[i + 1] - visible[i]
                   for i in range(len(visible) - 1)]

    # 1. Fixed difference: add and done.
    if len(set(differences)) == 1:
        step = differences[0]
        if compact:
            steps = ["verschillen: " + ", ".join(str(d) for d in differences)]
        else:
            steps = [f"{visible[i + 1]} - {visible[i]} = {step}"
                     for i in range(len(differences))]
        steps.append(f"{visible[-1]} + {step} = {target}")
        return steps, visible[-1] + step == target

    # 2. Fixed ratio: multiply.
    if all(x > 0 for x in visible):
        # **All** divisions must come out exactly, not most. With a filter
        # on "where it happens to divide", steps like `47 : 22 = 2` entered
        # the working — and then she learns a sum that is wrong. Positive
        # numbers only, because dividing by a negative rounds the wrong way.
        divisors = {visible[i + 1] // visible[i]
                    for i in range(len(visible) - 1)}
        exact = all(visible[i + 1] % visible[i] == 0
                    for i in range(len(visible) - 1))
        if exact and len(divisors) == 1:
            factor = divisors.pop()
            if compact:
                steps = ["gedeeld: " + ", ".join(str(factor)
                         for _ in range(len(visible) - 1))]
            else:
                steps = [f"{visible[i + 1]} : {visible[i]} = {factor}"
                         for i in range(len(visible) - 1)]
            steps.append(f"{visible[-1]} * {factor} = {target}")
            if visible[-1] * factor == target:
                return steps, True

    # 2b. Sum of the previous two (grondslag puzzle 5): each number is the
    #     sum of its two predecessors. This must sit before the difference
    #     recursion: the differences of such a row are again such a row —
    #     the recursion never gets out, and then this material would not
    #     exist.
    if len(visible) >= 3 and all(row[i] == row[i - 2] + row[i - 1]
                                 for i in range(2, len(row))):
        steps = [f"{row[i - 2]} + {row[i - 1]} = {row[i]}"
                 for i in range(2, len(row))]
        return steps, True

    # 3. The difference itself changes: the same method on the differences.
    following = target - visible[-1]
    if compact:
        steps = ["verschillen: " + ", ".join(str(d) for d in differences)]
    else:
        steps = [f"{visible[i + 1]} - {visible[i]} = {differences[i]}"
                 for i in range(len(differences))]
    inner, success = _explain(differences + [following], layer + 1, compact)
    if success:
        steps += inner
        steps.append(f"{visible[-1]} + {following} = {target}")
        return steps, True

    # 4. Two rows woven together. Then every other position skips, and it is
    #    really two separate rows. Without this every problem at depth 6
    #    drops out, because nearly everything there is woven.
    position = len(row) - 1
    own = row[position % 2::2]
    if len(own) >= 3:
        inner, success = _explain(own, layer + 1, compact)
        if success:
            om = ", ".join(str(x) for x in own[:-1])
            label = "om en om: " if compact else "om en om, dus kijk naar "
            return [label + om] + inner, True

    return [], False


def _row(depth, t, bases=_BASES, extra=0):
    # Varying length: five to seven numbers shown. With always six she
    # learns the rhythm instead of the stopping point — on the frozen exam
    # (five numbers) she computed every difference flawlessly on 10 Aug 2026
    # and then closed with `45 - 45 = 0 ; 45 + 0 = 45`: one difference too
    # many, because her world always showed six. The method must work at
    # every length, so the length must vary.
    shown = t.choice((5, 6, 7))
    # And deeper weaves ask longer rows: every "opgeteld" layer consumes one
    # element and every weave halves the strand; with seven numbers some 84%
    # at depth 6 is unexplainable — too little evidence on the table to peel
    # the layers off.
    # `extra`: the keer-plus brick is itself one layer deeper than a plus
    # brick (differences, then the ratio), so its rows get the length of one
    # depth more — measured 15 Aug 2026: without it depth 4 explained 32%,
    # with two more numbers 56%, the same profile as the world it joins.
    length = shown + 1 + 2 * max(0, depth - 5) + extra
    row = _row_series(max(1, depth - 1), t, length, bases)
    displayed = ", ".join(str(x) for x in row[:-1])
    # Compact working from depth 7: at full width nothing there fits the
    # window (30% at depth 8 on 1024). Depths 1-6 keep the wide form, so
    # her existing material and memories keep their exact shape.
    steps, success = _explain(row, compact=depth >= 7)
    if not success:
        # No method that comes out. Then this is not an honest problem:
        # there is nothing to work out, only to guess. `make()` drops it.
        return None, None, None
    return f"Zet voort: {displayed}, ?", row[-1], " ; ".join(steps)


# --- code ----------------------------------------------------------------------
# A program as a series of assignments, where every line is an expression
# over numbers and earlier variables. Deeper means more lines and deeper
# expressions. Nothing is executed to know the answer: the outcome is
# computed while building.

_NAMES = "abcdefghij"


def _code_expression(depth, t, known):
    """An expression over numbers and already-known variables.

    Returns (text, precedence, value, node). The node is the same tree shape
    as in arithmetic, so the working can show every step. The first version
    gave only the outcome per line — `b = 72` for `b = a * 4 - (a + 27)` —
    which asks her to do a three-step computation in her head at once. At
    depth 3 she reached 50% that way, at depth 4 she stayed flat at 1–2%
    after 28,000 tasks. The same disease as with the puzzles: a number that
    comes from nowhere. Found on 9 Aug 2026.
    """
    if depth <= 1 or not known:
        if known and t.choice((True, False)):
            name = t.choice(sorted(known))
            return name, _LEAF, known[name], ("blad", known[name])
        n = t.integer(1, 40)
        return str(n), _LEAF, n, ("blad", n)

    op = t.choice(("+", "-", "*"))
    precedence = _PRECEDENCE[op]

    if op == "*":
        lt, lp, lv, lnode = _code_expression(depth - 1, t, known)
        right = t.integer(2, 9)
        return (f"{_parens(lt, lp, precedence)} * {right}", precedence,
                lv * right, ("op", "*", lnode, ("blad", right)))

    lt, lp, lv, lnode = _code_expression(depth - 1, t, known)
    rt, rp, rv, rnode = _code_expression(depth - 1, t, known)

    # No `a - a` and no `14 - 14`: it looks complicated and is zero. Such
    # pieces make a problem longer without making it harder.
    if lt == rt:
        rv = t.integer(1, 40)
        rt, rp, rnode = str(rv), _LEAF, ("blad", rv)

    value = lv + rv if op == "+" else lv - rv
    return (f"{_parens(lt, lp, precedence)} {op} "
            f"{_parens(rt, rp, precedence, right_of_minus=(op == '-'))}",
            precedence, value, ("op", op, lnode, rnode))


def _loop_program(depth, t):
    """`totaal += i` and relatives — the form of grondslag code grade 3.

    The number of rounds scales with the depth and with the form: a square
    writes two steps per round and therefore fits fewer rounds in the same
    writing space. Measured 10 Aug 2026.
    """
    # All three forms from depth 3 — the grondslag asks `i * 2` and `i * i`
    # at grade 3 itself, and until 11 Aug 2026 the world only made those
    # from depth 4, with too few rounds (17% on the exam). The counts fit
    # window 768; `fits()` filters what falls out too large.
    form = t.choice(("i", "2i", "i2"))
    n = (t.integer(2, 4 + 2 * depth) if form == "i"
         else t.integer(2, min(11, 3 + 2 * depth)))
    start = t.integer(0, 50)
    body = {"i": "totaal += i", "2i": "totaal += i * 2",
            "i2": "totaal += i * i"}[form]
    steps, total = [], start
    for i in range(1, n + 1):
        if form == "i":
            extra = i
        elif form == "2i":
            extra = i * 2
            steps.append(f"{i} * 2 = {extra}")
        else:
            extra = i * i
            steps.append(f"{i} * {i} = {extra}")
        steps.append(f"{total} + {extra} = {total + extra}")
        total += extra
    program = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
               f"    {body}\nprint(totaal)")
    return program, total, " ; ".join(steps)


def _list_program(depth, t):
    """The list filter — the form of grondslag code grade 4."""
    # Element count and the sum variant were measured against the writing
    # space on 10 Aug 2026: at depth 4 counting only (the sum steps ran 74
    # characters over), from 5 also summing.
    numbers = [t.integer(1, 40) for _ in range(t.integer(4, min(9, 2 + depth)))]
    threshold = t.integer(5, 30)
    # Since window 768 the sum variant also fits at depth 4 (11 Aug 2026);
    # before that its steps ran 74 characters over the writing space there.
    count = True if depth <= 3 else t.choice((True, False))
    hits = [x for x in numbers if x > threshold]
    steps = [f"{x} > {threshold}, telt mee" if x > threshold
             else f"{x} > {threshold} is niet zo" for x in numbers]
    if count:
        program = (f"getallen = {numbers}\n"
                   f"print(len([x for x in getallen if x > {threshold}]))")
        steps.append(f"meegeteld: {len(hits)}")
        return program, len(hits), " ; ".join(steps)
    program = (f"getallen = {numbers}\n"
               f"print(sum([x for x in getallen if x > {threshold}]))")
    total = 0
    for x in hits:
        steps.append(f"{total} + {x} = {total + x}")
        total += x
    if not hits:
        steps.append("niets telt mee, dus 0")
    return program, total, " ; ".join(steps)


def _def_program(depth, t):
    """`def f(x)` plus a loop — the form of grondslag code grade 5.

    Few rounds: every round writes three steps. The exam's larger counts
    (up to fifteen rounds) only fit once the window grows.
    """
    # Up to fifteen rounds since 12 Aug 2026 — the exam's full size. That
    # working (~750 characters) only fits from window 1024 (measured: code
    # depth 15 fits 99% there); during run 4 at 768 `fits()` simply skips
    # what is too large, so the cap follows the exam and the window
    # decides per era what she actually sees.
    n, f, k = t.integer(2, min(15, 2 * depth)), t.integer(2, 20), t.integer(0, 9)
    steps, total = [], 0
    for i in range(1, n + 1):
        p = i * f
        steps.append(f"f({i}): {i} * {f} = {p}")
        steps.append(f"{p} + {k} = {p + k}")
        steps.append(f"{total} + {p + k} = {total + p + k}")
        total += p + k
    program = (f"def f(x):\n    return x * {f} + {k}\n\n"
               f"totaal = 0\nfor i in range(1, {n + 1}):\n"
               f"    totaal += f(i)\nprint(totaal)")
    return program, total, " ; ".join(steps)


# --- stacked forms (15 Aug 2026) ---------------------------------------------
# Beyond depth 15 the four forms stopped getting harder: `regels` caps at six
# lines, `lijst` at nine numbers, `def` at fifteen rounds — measured 15 Aug
# 2026 (fase1/hek-meting.md): at depth 30 everything fits and reads like
# depth 12. Fence 15 was the end of the world, not a window limit. Deeper
# therefore means what it means for the rows: building blocks stacked on
# each other. A filter inside a loop, a function over a list, a loop inside
# a loop, a function calling a function — from depth 16 two blocks, from
# depth 20 three. Nothing at or below depth 15 changes shape: these forms
# are only offered above the old fence, so her material and memories keep
# their exact form (the rule of 13 Aug 2026; test-world pins a checksum).
#
# The working stays in the language she has: one easy step per number, the
# filter lines of the list form, the `f(i): …` lines of the def form, and
# for long series the compact rows of the long loop (14 Aug 2026) — the
# terms as one row, the running sum as one row.

STAPEL_MIN = 16          # two blocks stacked
STAPEL3_MIN = 20         # three blocks stacked
# The stacked forms stopped growing at 24 — their sizes were capped for
# window 1024 (15 Aug 2026). At 1536 there is room, and on 17 Aug 2026 all
# four families stood against their fence: so from GROEI_VANAF the caps
# rise one notch per depth, and depths up to and including 24 stay bit for
# bit what they were (the frozen `stapel` exam and the checksums hold).
GROEI_VANAF = 24


def _extra(depth):
    """How many notches past the old ceiling this depth is (0 up to 24)."""
    return max(0, depth - GROEI_VANAF)


def _running(start, terms):
    """The compact sum row of the long loop: `som: 0 3 8 15`."""
    sums, total = [start], start
    for x in terms:
        total += x
        sums.append(total)
    return "som: " + " ".join(str(x) for x in sums), total


def _loop_filter(depth, t, three):
    """A filter inside a loop (lus + lijst): `if i > d: totaal += i`.

    Three blocks: the term under the filter is `i * 2` or `i * i`, so the
    filtered rounds still need a term row before the sum row.
    """
    n = t.integer(6, min(26 + _extra(depth), depth + 2))
    d = t.integer(1, n - 3)                     # at least three rounds pass
    start = t.integer(0, 50)
    form = t.choice(("2i", "i2")) if three else "i"
    body = {"i": "totaal += i", "2i": "totaal += i * 2",
            "i2": "totaal += i * i"}[form]
    hits = [i for i in range(1, n + 1) if i > d]
    program = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
               f"    if i > {d}:\n        {body}\nprint(totaal)")
    steps = ["telt mee: " + " ".join(str(i) for i in hits)]
    if form == "i":
        terms = hits
    elif form == "2i":
        terms = [2 * i for i in hits]
        steps.append("termen: " + " ".join(str(x) for x in terms))
    else:
        terms = [i * i for i in hits]
        steps.append("kwadraten: " + " ".join(str(x) for x in terms))
    row, total = _running(start, terms)
    steps.append(row)
    return program, total, " ; ".join(steps)


def _def_over_list(depth, t, three):
    """A function over a list (def + lijst): `sum([f(x) for x in getallen])`.

    Three blocks: with the list filter on top, `… if x > d]`.
    """
    count = t.integer(3, min(9 + _extra(depth), depth - 11))
    numbers = [t.integer(1, 40) for _ in range(count)]
    f, k = t.integer(2, 9), t.integer(0, 9)
    steps = []
    if three:
        d = t.integer(5, 30)
        chosen = [x for x in numbers if x > d]
        steps += [f"{x} > {d}, telt mee" if x > d
                  else f"{x} > {d} is niet zo" for x in numbers]
        tail = f" if x > {d}"
    else:
        chosen = numbers
        tail = ""
    program = (f"def f(x):\n    return x * {f} + {k}\n\n"
               f"getallen = {numbers}\n"
               f"print(sum([f(x) for x in getallen{tail}]))")
    total = 0
    for x in chosen:
        p = x * f
        steps.append(f"f({x}): {x} * {f} = {p}")
        steps.append(f"{p} + {k} = {p + k}")
        steps.append(f"{total} + {p + k} = {total + p + k}")
        total += p + k
    if not chosen:
        steps.append("niets telt mee, dus 0")
    return program, total, " ; ".join(steps)


def _nested_loop(depth, t, three):
    """A loop inside a loop (lus + lus): `totaal += i * j` or `i + j`.

    Three blocks: a filter on the inner loop, `if j > d`. The sum row runs
    on across the outer rounds, so the last number is the answer.
    """
    a = t.integer(2, min(6 + _extra(depth) // 3, depth - 13))
    b = t.integer(3, min(8 + _extra(depth) // 2, depth - 12))
    op = t.choice(("*", "+"))
    start = t.integer(0, 30)
    d = t.integer(1, b - 2) if three else 0
    inner = f"totaal += i {op} j"
    lines = [f"totaal = {start}", f"for i in range(1, {a + 1}):",
             f"    for j in range(1, {b + 1}):"]
    if three:
        lines += [f"        if j > {d}:", f"            {inner}"]
    else:
        lines.append(f"        {inner}")
    lines.append("print(totaal)")
    steps, total = [], start
    for i in range(1, a + 1):
        js = [j for j in range(1, b + 1) if j > d]
        terms = [i * j if op == "*" else i + j for j in js]
        row, total = _running(total, terms)
        head = f"i = {i}: termen " + " ".join(str(x) for x in terms)
        steps.append(head + " ; " + row)
    return "\n".join(lines), total, " ; ".join(steps)


def _def_chain(depth, t, three):
    """A function calling a function (def + def): `g(x) = f(x) + c`.

    Two blocks: `print(g(a) - g(b))`. Three blocks: a loop summing g(i)
    over the rounds (def + def + lus), with the compact rows.
    """
    f, c = t.integer(2, 9), t.integer(1, 20)
    op = t.choice(("+", "-"))
    g = (lambda x: x * f + c) if op == "+" else (lambda x: x * f - c)
    head = (f"def f(x):\n    return x * {f}\n\n"
            f"def g(x):\n    return f(x) {op} {c}\n\n")
    steps = []

    def call(x):
        p = x * f
        steps.append(f"f({x}): {x} * {f} = {p}")
        steps.append(f"g({x}): {p} {op} {c} = {g(x)}")
        return g(x)

    if not three:
        a, b = t.integer(2, 30), t.integer(2, 30)
        if a == b:
            b = a + 1
        va, vb = call(a), call(b)
        steps.append(f"{va} - {vb} = {va - vb}")
        return head + f"print(g({a}) - g({b}))", va - vb, " ; ".join(steps)

    n = t.integer(4, min(15 + _extra(depth), depth - 8))
    terms = [g(i) for i in range(1, n + 1)]
    call(1)
    # g(i+1) − g(i) = f: after the first, each next one is one small
    # addition — the long loop's own trick (14 Aug 2026).
    steps.append(f"daarna steeds +{f}: " + " ".join(str(x) for x in terms))
    row, total = _running(0, terms)
    steps.append(row)
    program = (head + f"totaal = 0\nfor i in range(1, {n + 1}):\n"
               f"    totaal += g(i)\nprint(totaal)")
    return program, total, " ; ".join(steps)


_STACKED = {"lus-filter": _loop_filter, "def-lijst": _def_over_list,
            "lus-lus": _nested_loop, "def-def": _def_chain}


def _code(depth, t):
    # The grondslag's language, part two (10 Aug 2026): three program forms
    # the exam asks and the world lacked — measured per cell, code grades
    # 3–5 sat at exactly 0% because of it. Each form from the depth where
    # its working fits the writing space.
    if depth >= STAPEL_MIN:
        # Above the old fence only the stacked forms: the four plain ones
        # stopped getting harder at 15, and a depth that repeats depth 12
        # is not deeper. Below STAPEL_MIN nothing here changes.
        form = t.choice(tuple(sorted(_STACKED)))
        return _STACKED[form](depth, t, depth >= STAPEL3_MIN)
    forms = ["regels", "regels"]
    if depth >= 3:
        forms.append("lus")
    if depth >= 4:
        forms.append("lijst")
    if depth >= 5:
        forms.append("def")
    form = t.choice(tuple(forms))
    if form == "lus":
        return _loop_program(depth, t)
    if form == "lijst":
        return _list_program(depth, t)
    if form == "def":
        return _def_program(depth, t)

    # Two bounds, both because a program otherwise grows faster than it gets
    # harder. At depth 12 the first version produced lines of a hundred and
    # fifty characters — that does not even fit her window of 256, and it
    # measures reading rather than understanding. Deeper therefore mostly
    # means more lines, with lines that stay modest themselves.
    line_count = min(6, 1 + depth // 3)
    expression_depth = min(4, max(1, depth - line_count + 1))

    known = {}
    lines = []
    steps = []
    for i in range(line_count):
        name = _NAMES[i]
        text, _, value, node = _code_expression(expression_depth, t, known)
        lines.append(f"{name} = {text}")
        known[name] = value
        # Walk line by line the way you trace a program by hand — but with
        # the computation attached. Writing only `name = value` hides a
        # multi-step sum in one number, and that is where she jammed at
        # depth 4.
        _work_out(node, steps)
        steps.append(f"{name} = {value}")

    # One loop on top as soon as there is room: that makes it a program
    # rather than a list of sums.
    last = _NAMES[line_count - 1]
    if depth >= 4:
        rounds = t.integer(2, 6)
        step = t.integer(1, 20)
        lines.append(f"for i in range({rounds}):")
        lines.append(f"    {last} = {last} + {step}")
        old = known[last]
        extra = rounds * step
        known[last] = old + extra
        steps.append(f"{rounds} * {step} = {extra}")
        # The addition was missing at first — "b = 82" came from nowhere,
        # while 72 + 10 = 82 is the whole lesson.
        steps.append(f"{old} + {extra} = {known[last]}")
        steps.append(f"{last} = {known[last]}")

    # Three endings. `print` with a bare name was the only ending, and that
    # left two gaps the frozen exam exposed on 10 Aug 2026: a `print` with a
    # sum inside was unknown to her (she bravely wrote `b = 42` at an
    # outcome of -42), and `if/else` did not exist in her world at all.
    # Material that occurs nowhere in the world can only be unlearned — the
    # world must keep speaking the grondslag's language.
    #
    # Only through depth 5: that is the grondslag's range, and at depth 7–8
    # the extra lines pushed 40% of problems out of the window (measured
    # 10 Aug 2026, fit fell from 85% to 60%).
    ending = (t.choice(("gewoon", "gewoon", "reken", "alsdan"))
              if depth <= 5 else "gewoon")
    if ending != "gewoon" and len(known) < 2:
        # A comparison or a sum needs two names.
        name2 = _NAMES[len(known)]
        extra = t.integer(1, 99)
        lines.append(f"{name2} = {extra}")
        known[name2] = extra
        steps.append(f"{name2} = {extra}")

    if ending == "reken":
        # print with a sum inside — the outcome may be negative.
        na, nb = sorted(known)[-2:]
        op = t.choice(("-", "-", "+"))
        value = known[na] - known[nb] if op == "-" else known[na] + known[nb]
        lines.append(f"print({na} {op} {nb})")
        steps.append(f"{known[na]} {op} {known[nb]} = {value}")
        return "\n".join(lines), value, " ; ".join(steps)

    if ending == "alsdan":
        na, nb = sorted(known)[-2:]
        wa, wb = known[na], known[nb]
        lines += [f"if {na} > {nb}:", f"    print({na} - {nb})",
                  "else:", f"    print({nb} - {na})"]
        if wa > wb:
            steps.append(f"{wa} > {wb}, dus {na} - {nb}")
            value = wa - wb
            steps.append(f"{wa} - {wb} = {value}")
        else:
            steps.append(f"{wa} > {wb} is niet zo, dus {nb} - {na}")
            value = wb - wa
            steps.append(f"{wb} - {wa} = {value}")
        return "\n".join(lines), value, " ; ".join(steps)

    lines.append(f"print({last})")
    return "\n".join(lines), known[last], " ; ".join(steps)


# --- geheugen (memory) — 16 Aug 2026 ------------------------------------------
# The fourth family, and the sharpest test of C: an answer that depends on
# something earlier in the sequence. All within one task — a note to hold,
# distractions in between, then a question that reaches back:
#
#     onthoud: k = 7 ; p = 12 ; m = 4
#     tussendoor: 5 + 9 = 14 ; z = 6 ; 8 - 3 = 5
#     wat is k + m?
#
# and the working she learns to write: `k = 7 ; m = 4 ; 7 + 4 = 11` — first
# look back and copy what was held, then compute. The last number is the
# answer, so nakijk stays what it is.
#
# Depth is two dials in one, building blocks that stack: how much to hold
# (`n` names, one more every two depths) and how far back (`depth` lines of
# distraction between the note and the question). From MEM_UPDATE_MIN a held
# name may be re-assigned on the way and the LAST value counts — letting go
# of the old and keeping the new, C in the small. From MEM_SUM_MIN the
# question may combine two held values (sum, difference), from MEM_MAX_MIN
# ask for the larger one. Names are single letters (bytes, no tokenizer),
# values 1–99. This measures memory *within* one task — the working memory
# over the sequence — the run-up to remembering across days, not that
# itself; that remains H and the replay.

MEM_NAMES = "abcdefghkmnpqrstuvwxyz"     # no i, j, l, o — they read as digits or as each other
MEM_HOLD_MAX = 12
MEM_UPDATE_MIN = 4                       # from here a held value may change on the way
MEM_SUM_MIN = 3                          # from here two held values may be combined
MEM_MAX_MIN = 5                          # from here "which is larger" may be asked


def _mem_names(t, n):
    names = []
    while len(names) < n:
        c = MEM_NAMES[t.integer(0, len(MEM_NAMES) - 1)]
        if c not in names:
            names.append(c)
    return names


def _memory(depth, t):
    n = min(MEM_HOLD_MAX, 1 + (depth - 1) // 2)
    names = _mem_names(t, n)
    values = {c: t.integer(1, 99) for c in names}
    lines = ["onthoud: " + " ; ".join(f"{c} = {values[c]}" for c in names)]

    others = [c for c in MEM_NAMES if c not in names]
    between = []
    for _ in range(depth):
        kind = t.integer(1, 3)
        if kind == 1 and depth >= MEM_UPDATE_MIN:
            c = names[t.integer(0, n - 1)]
            values[c] = t.integer(1, 99)          # the last one counts
            between.append(f"{c} = {values[c]}")
        elif kind == 2:
            c = others[t.integer(0, len(others) - 1)]
            between.append(f"{c} = {t.integer(1, 99)}")
        else:
            a, b = t.integer(1, 50), t.integer(1, 50)
            op = t.choice(("+", "-"))
            between.append(f"{a} {op} {b} = {a + b if op == '+' else a - b}")
    lines.append("tussendoor: " + " ; ".join(between))

    forms = ["een"]
    if n >= 2 and depth >= MEM_SUM_MIN:
        forms += ["som", "verschil"]
    if n >= 2 and depth >= MEM_MAX_MIN:
        forms += ["grootste"]
    form = t.choice(tuple(forms))
    if form == "een":
        c = names[t.integer(0, n - 1)]
        question = f"wat is {c}?"
        working = f"{c} = {values[c]}"
        answer = values[c]
    else:
        i = t.integer(0, n - 1)
        j = t.integer(0, n - 2)
        j = j if j < i else j + 1                 # two different held names
        c1, c2 = names[i], names[j]
        v1, v2 = values[c1], values[c2]
        if form == "som":
            question, answer = f"wat is {c1} + {c2}?", v1 + v2
            last = f"{v1} + {v2} = {answer}"
        elif form == "verschil":
            question, answer = f"wat is {c1} - {c2}?", v1 - v2
            last = f"{v1} - {v2} = {answer}"
        else:
            question, answer = f"welke is groter, {c1} of {c2}? schrijf het getal", max(v1, v2)
            last = f"groter: {answer}"
        working = f"{c1} = {v1} ; {c2} = {v2} ; {last}"
    return "\n".join(lines + [question]), answer, working


# --- the memory brick: a running state (17 Aug 2026) --------------------------
# The plain memory task ("find the last assignment") she ran through in
# ~1.200 steps. Harder is not farther back but a state she must keep up:
# updates that COMPUTE on the old value ("k = k + 3", "p = p * 2") and
# references that COPY a value at that moment ("p = k" — and when k changes
# later, p keeps what it took). Same three lines, same questions, so the
# working still looks back and then computes:
#
#     k = 7 ; k = 7 + 3 = 10 ; k = 10 * 2 = 20 ; p = k = 20 ; ...
#
# Own seed split, one in three numbers from STEEN_MIN, so two in three stay
# bit for bit the memory task of 16 Aug 2026 (checksum in test-world) and the
# frozen geheugen sheet keeps measuring what it measured. Depth: how many
# computing updates (1 + (d−4)//2), which operations (+/− from 4, × from
# STEEN_TIMES_MIN), references from STEEN_REF_MIN, chains of references
# from STEEN_CHAIN_MIN — and, as before, more to hold and more in between.

STEEN_SEED = 0x537465656E                # "Steen"
STEEN_MIN = 4
STEEN_TIMES_MIN = 5
STEEN_REF_MIN = 6
STEEN_CHAIN_MIN = 9


def _memory_state(depth, t):
    n = min(MEM_HOLD_MAX, 1 + (depth - 1) // 2)
    names = _mem_names(t, n)
    values = {c: t.integer(1, 99) for c in names}
    history = {c: [f"{c} = {values[c]}"] for c in names}
    lines = ["onthoud: " + " ; ".join(f"{c} = {values[c]}" for c in names)]

    others = [c for c in MEM_NAMES if c not in names]
    n_updates = 1 + (depth - STEEN_MIN) // 2
    n_refs = 0 if depth < STEEN_REF_MIN else 1 + (depth - STEEN_REF_MIN) // 3
    # the special lines, then the plain distractions around them
    specials = []
    for _ in range(n_updates):
        c = names[t.integer(0, n - 1)]
        ops = ["+", "-"] if depth < STEEN_TIMES_MIN else ["+", "-", "*"]
        op = ops[t.integer(0, len(ops) - 1)]
        amount = t.integer(2, 9) if op == "*" else t.integer(1, 30)
        specials.append(("update", c, op, amount))
    for i in range(n_refs):
        # a chain: two references in a row where the second copies the first
        src = names[t.integer(0, n - 1)]
        dst = names[t.integer(0, n - 1)]
        if dst == src:
            dst = names[(names.index(src) + 1) % n]
        specials.append(("ref", dst, src))
        if depth >= STEEN_CHAIN_MIN and i == 0 and n >= 3:
            third = names[(names.index(dst) + 1) % n]
            if third == src:
                third = names[(names.index(dst) + 2) % n]
            specials.append(("ref", third, dst))     # q = p right after p = k
    between = []
    plain = max(0, depth - len(specials))
    slots = list(range(plain + len(specials)))
    # scatter the specials over the slots, in their order
    positions = sorted(t.integer(0, len(slots) - 1) for _ in specials)
    # make positions distinct and ordered
    seen = set(); fixed = []
    for pos in positions:
        while pos in seen:
            pos = (pos + 1) % max(1, len(slots))
        seen.add(pos); fixed.append(pos)
    fixed.sort()
    sp = 0
    for slot in slots:
        if sp < len(specials) and slot == fixed[sp]:
            kind = specials[sp]; sp += 1
            if kind[0] == "update":
                _, c, op, amount = kind
                old = values[c]
                if op == "*" and abs(old) > 150:
                    op = "+"                     # keep the numbers within her reach
                new = old + amount if op == "+" else old - amount if op == "-" else old * amount
                values[c] = new
                between.append(f"{c} = {c} {op} {amount}")
                history[c].append(f"{c} = {old} {op} {amount} = {new}")
            else:
                _, dst, src = kind
                values[dst] = values[src]
                between.append(f"{dst} = {src}")
                history[dst].append(f"{dst} = {src} = {values[src]}")
        else:
            kind = t.integer(1, 2)
            if kind == 1 and others:
                c = others[t.integer(0, len(others) - 1)]
                between.append(f"{c} = {t.integer(1, 99)}")
            else:
                a, b = t.integer(1, 50), t.integer(1, 50)
                op = t.choice(("+", "-"))
                between.append(f"{a} {op} {b} = {a + b if op == '+' else a - b}")
    lines.append("tussendoor: " + " ; ".join(between))

    forms = ["een"]
    if n >= 2 and depth >= MEM_SUM_MIN:
        forms += ["som", "verschil"]
    if n >= 2 and depth >= MEM_MAX_MIN:
        forms += ["grootste"]
    form = t.choice(tuple(forms))
    # prefer asking a name that was touched by a special line
    touched = [c for c in names if len(history[c]) > 1] or names
    if form == "een":
        c = touched[t.integer(0, len(touched) - 1)]
        question = f"wat is {c}?"
        working = " ; ".join(history[c])
        answer = values[c]
    else:
        c1 = touched[t.integer(0, len(touched) - 1)]
        rest = [c for c in names if c != c1]
        c2 = rest[t.integer(0, len(rest) - 1)]
        v1, v2 = values[c1], values[c2]
        if form == "som":
            question, answer = f"wat is {c1} + {c2}?", v1 + v2
            last = f"{v1} + {v2} = {answer}"
        elif form == "verschil":
            question, answer = f"wat is {c1} - {c2}?", v1 - v2
            last = f"{v1} - {v2} = {answer}"
        else:
            question, answer = f"welke is groter, {c1} of {c2}? schrijf het getal", max(v1, v2)
            last = f"groter: {answer}"
        working = " ; ".join(history[c1] + history[c2] + [last])
    return "\n".join(lines + [question]), answer, working


# --- the "which rule" puzzle (17 Aug 2026) ------------------------------------
# The rows run out above depth 10: ten layers of differences and weaves on a
# short row is not a harder puzzle, and the method finds nothing (6–10%
# usable at 11–14). So the second puzzle kind: not "continue the row" but
# "which rule?" — a hidden rule built from bricks (+c, ×a, square), shown
# through a few pairs, asked at a new input:
#
#     regel: f(3) = 10 ; f(5) = 16
#     wat is f(8)?
#
# and the working derives it: `stap: (16 - 10) / (5 - 3) = 3 ; c: 10 - 3 * 3
# = 1 ; regel: 3 * x + 1 ; 3 * 8 = 24 ; 24 + 1 = 25`. Explainable by
# construction — the generator knows the rule — so there is no empty room at
# any depth. Two shapes: linear (a·x + c: every stack of + and × bricks) and
# square (a·x² + c). Two pairs mean linear (the simplest rule that fits);
# from REGEL_KWAD_MIN three pairs are shown and equal steps mean linear,
# unequal steps mean square — the working says which check it did.
#
# Own seed split, one in three puzzle numbers from depth 1, applied only
# where the keer-plus split did not draw (so every keer-plus row and every
# untouched row stays bit for bit); above ROW_MAX every number is a rule
# puzzle — the rows are an empty room there.

REGEL_SEED = 0x526567656C                # "Regel"
ROW_MAX = 10                             # above this only rule puzzles
REGEL_KWAD_MIN = 7                       # from here squares exist and three pairs are shown


def _rule_shape(depth, t):
    """Pick a rule for this depth: ("lin", a, c) or ("kwad", a, c), the
    number of pairs, and the range of the inputs."""
    if depth <= 2:
        return ("lin", 1, t.integer(1, 20 if depth == 1 else 50)), 2, 12
    if depth <= 4:
        a = t.integer(2, 9)
        c = 0 if depth == 3 else t.integer(1, 30)
        return ("lin", a, c), 2, 15
    if depth <= 6:
        a = t.integer(2, 9)
        c = t.integer(-30, 40)                # subtracting too
        return ("lin", a, c), 2, 20
    if depth <= 8:
        if t.integer(1, 2) == 1:
            return ("kwad", 1, t.integer(-20, 40)), 3, 9
        return ("lin", t.integer(2, 12), t.integer(-50, 99)), 3, 25
    if depth <= 12:
        if t.integer(1, 2) == 1:
            return ("kwad", t.integer(1, 4), t.integer(-50, 99)), 3, 12
        return ("lin", t.integer(2, 15), t.integer(-99, 199)), 3, 40
    # deeper: bigger numbers, four pairs from 17
    pairs = 3 if depth < 17 else 4
    if t.integer(1, 2) == 1:
        return ("kwad", t.integer(1, 3 + depth // 6), t.integer(-99, 199)), pairs, 12 + depth // 2
    return ("lin", t.integer(2, 10 + depth // 2), t.integer(-199, 399)), pairs, 30 + depth


def _apply(rule, x):
    kind, a, c = rule
    return a * x + c if kind == "lin" else a * x * x + c


def _rule_puzzle(depth, t):
    rule, n_pairs, top = _rule_shape(depth, t)
    xs = []
    while len(xs) < n_pairs + 1:
        x = t.integer(1, top)
        if x not in xs:
            xs.append(x)
    shown, asked = sorted(xs[:n_pairs]), xs[n_pairs]
    kind, a, c = rule
    ys = [_apply(rule, x) for x in shown]
    problem = ("regel: " + " ; ".join(f"f({x}) = {y}" for x, y in zip(shown, ys))
               + f"\nwat is f({asked})?")
    steps = []
    x1, x2 = shown[0], shown[1]
    y1, y2 = ys[0], ys[1]
    if kind == "lin":
        if n_pairs >= 3:
            # equal steps: the check that says "linear"
            st = " ; ".join(f"({ys[i + 1]} - {ys[i]}) / ({shown[i + 1]} - {shown[i]}) = {a}"
                            for i in range(n_pairs - 1))
            steps.append(f"stappen gelijk: {st}")
        else:
            steps.append(f"stap: ({y2} - {y1}) / ({x2} - {x1}) = {a}")
        steps.append(f"c: {y1} - {a} * {x1} = {c}")
        steps.append(f"regel: {a} * x {'+' if c >= 0 else '-'} {abs(c)}")
        p = a * asked
        steps.append(f"{a} * {asked} = {p}")
        steps.append(f"{p} {'+' if c >= 0 else '-'} {abs(c)} = {p + c}")
        answer = p + c
    else:
        sq = [x * x for x in shown]
        steps.append("stappen ongelijk, dus kwadraten: " + " ; ".join(f"{x} * {x} = {q}" for x, q in zip(shown, sq)))
        steps.append(f"stap: ({y2} - {y1}) / ({sq[1]} - {sq[0]}) = {a}")
        steps.append(f"c: {y1} - {a} * {sq[0]} = {c}")
        steps.append(f"regel: {a} * x * x {'+' if c >= 0 else '-'} {abs(c)}")
        q = asked * asked
        steps.append(f"{asked} * {asked} = {q}")
        p = a * q
        steps.append(f"{a} * {q} = {p}")
        steps.append(f"{p} {'+' if c >= 0 else '-'} {abs(c)} = {p + c}")
        answer = p + c
    return problem, answer, " ; ".join(steps)


def _rule_draws(seed, depth):
    """Does the rule split take this puzzle number? Above ROW_MAX always."""
    if depth > ROW_MAX:
        return True
    return Picker(_mix(seed ^ REGEL_SEED)).integer(1, 3) == 1


# --- logica (logic) — the fifth family (17 Aug 2026) ---------------------------
# If-then chains over true/false facts. True is written 1 and false 0, so
# nakijk stays what it is (the last number) and the measuring stick is not
# touched. Three lines: what is given, the rules, the question:
#
#     gegeven: a = 1 ; b = 0
#     regels: als b dan c ; als niet b dan d ; als d dan e
#     wat is e?
#
# and the working is the derivation: `b = 0 ; als niet b dan d: d = 1 ; als
# d dan e: e = 1`. Depth is, as always, two dials in one: the chain length
# (rules that lead to the answer, one more every two depths) and the number
# of premises and distraction rules (rules that do not fire, or lead
# somewhere else). Negation from LOGIC_NOT_MIN, "en"/"of" from
# LOGIC_ANDOR_MIN, a false conclusion ("dan niet z") from LOGIC_FALSE_MIN.
# Every asked name is determined by the given facts and the rules — no open
# world; each name is assigned at most once, so nothing contradicts. Rules
# are listed in a shuffled order: she must find the chain, not read down.

LOGIC_NAMES = "abcdefghkmnpqrstuvwxyz"
LOGIC_NAMES_MORE = "ABCDEFGHKMNPQRSTUVWXYZ"   # only when the 22 small ones run out (deep)
LOGIC_NOT_MIN = 3
LOGIC_ANDOR_MIN = 5
LOGIC_FALSE_MIN = 7
LOGIC_PREMISES_MAX = 8


def _logic(depth, t):
    chain = 1 + (depth - 1) // 2
    n_prem = min(LOGIC_PREMISES_MAX, 2 + depth // 2)
    pool = list(LOGIC_NAMES)
    more = list(LOGIC_NAMES_MORE)
    def fresh():
        if pool:
            return pool.pop(t.integer(0, len(pool) - 1))
        if more:
            return more.pop(t.integer(0, len(more) - 1))
        return "x" + str(len(more) + 1)          # beyond 44 names: never at any fence we run
    prem = [fresh() for _ in range(n_prem)]
    dead = [fresh() for _ in range(3)]            # never assigned: for rules that never fire
    values = {c: t.integer(0, 1) for c in prem}
    values[prem[0]] = 1                          # the chain needs a true start
    if not any(v == 0 for v in values.values()) and depth >= LOGIC_NOT_MIN:
        values[prem[-1]] = 0                     # and negation needs a false one
    trues = [c for c in prem if values[c] == 1]
    falses = [c for c in prem if values[c] == 0]
    rules, working = [], []
    cur = trues[t.integer(0, len(trues) - 1)]
    working.append(f"{cur} = 1")
    for i in range(chain):
        new = fresh()
        last = i == chain - 1
        form = "een"
        if depth >= LOGIC_ANDOR_MIN and t.integer(1, 3) == 1:
            form = t.choice(("en", "of"))
        elif i == 0 and depth >= LOGIC_NOT_MIN and falses and t.integer(1, 3) == 1:
            form = "niet"                        # only as the first link: the chain stays one chain
        neg_out = last and depth >= LOGIC_FALSE_MIN and t.integer(1, 3) == 1
        head = f"niet {new}" if neg_out else new
        if form == "een":
            rules.append(f"als {cur} dan {head}")
            working.append(f"als {cur} dan {head}: {new} = {0 if neg_out else 1}")
        elif form == "niet":
            q = falses[t.integer(0, len(falses) - 1)]
            rules.append(f"als niet {q} dan {head}")
            working.append(f"{q} = 0 ; als niet {q} dan {head}: {new} = {0 if neg_out else 1}")
        elif form == "en":
            others = [c for c in trues if c != cur] or trues
            other = others[t.integer(0, len(others) - 1)]
            rules.append(f"als {cur} en {other} dan {head}")
            working.append(f"{other} = 1 ; als {cur} en {other} dan {head}: {new} = {0 if neg_out else 1}")
        else:                                    # "of": partner may be false
            others = [c for c in prem if c != cur] or prem
            other = others[t.integer(0, len(others) - 1)]
            rules.append(f"als {cur} of {other} dan {head}")
            working.append(f"{other} = {values[other]} ; als {cur} of {other} dan {head}: {new} = {0 if neg_out else 1}")
        values[new] = 0 if neg_out else 1
        cur = new
    answer_name, answer = cur, values[cur]
    # distractions: rules that do not fire (false antecedent, or an
    # antecedent nobody ever assigns) and rules that fire into fresh names
    seen = set(rules)
    for _ in range(depth):
        kind = t.integer(1, 3)
        if kind == 1 and falses:
            q = falses[t.integer(0, len(falses) - 1)]
            rule = f"als {q} dan {dead[t.integer(0, 2)]}"
        elif kind == 2:
            src = trues[t.integer(0, len(trues) - 1)]
            new = fresh(); values[new] = 1
            rule = f"als {src} dan {new}"
        else:                                    # never assigned: never fires
            d1 = dead[t.integer(0, 2)]
            d2 = dead[t.integer(0, 2)]
            rule = f"als {d1} dan {d2 if d2 != d1 else dead[(dead.index(d1) + 1) % 3]}"
        if rule not in seen:                     # the same line twice teaches nothing
            seen.add(rule)
            rules.append(rule)
    # shuffle the rules (deterministically)
    order = []
    rest = list(rules)
    while rest:
        order.append(rest.pop(t.integer(0, len(rest) - 1)))
    problem = ("gegeven: " + " ; ".join(f"{c} = {values[c]}" for c in prem)
               + "\nregels: " + " ; ".join(order)
               + f"\nwat is {answer_name}?")
    return problem, answer, " ; ".join(working)


_MAKERS = {"rekenen": _arithmetic, "puzzel": _row, "code": _code,
           "geheugen": _memory, "logica": _logic}


# --- the conversational wrapper (13 Aug 2026) --------------------------------
# Since O closed the loop Cley can talk to her: whisper turns his voice into
# text like "Wat is 3 plus 4?". That wrapper did not exist in her world —
# on the first live conversation she read it as list-filter language and
# answered nonsense. So the world now teaches the wrapper itself: a fifth
# of the arithmetic problems (depth 2-8, the depths one would actually say
# aloud) appears as an everyday question, and with a spoken-word expression
# the working starts with the bare sum — first translate, then calculate.
#
# The wrapper draws from its own seed split. Unwrapped problems stay bit
# for bit what they were — same demand as the compact puzzle working of
# 13 Aug 2026: nothing she already masters changes shape.

CONVERSE_SEED = 0x4765_7370_7265_6B      # "Gesprek"
CONVERSE_MIN, CONVERSE_MAX = 2, 8

_SPOKEN_OP = {"+": "plus", "-": "min", "*": "keer"}
# Only a flat chain of positive numbers reads naturally as spoken words;
# anything with parentheses keeps its symbols ("3 haakje 7 sluit" is not
# a sentence anyone says).
import re as _re
_FLAT = _re.compile(r"^\d+( [+*-] \d+)+$")


def _converse(problem, working, depth, t):
    """Perhaps wrap an arithmetic problem in everyday question language."""
    if not CONVERSE_MIN <= depth <= CONVERSE_MAX or t.integer(1, 5) != 1:
        return problem, working
    spoken = None
    if _FLAT.match(problem) and t.integer(1, 2) == 1:
        spoken = " ".join(_SPOKEN_OP.get(p, p) for p in problem.split(" "))
    e = spoken or problem
    form = t.integer(1, 3)
    if form == 1:
        wrapped = f"Wat is {e}?"
    elif form == 2:
        wrapped = f"Hoeveel is {e}?"
    else:
        wrapped = f"Reken uit: {e}"
    if spoken:
        # The translation is the first step of the working: she learns to
        # write the sum in her own notation before calculating. nakijk()
        # still reads the last number, so checking stays unchanged.
        working = f"{problem} ; {working}" if working else problem
    return wrapped, working


# --- the big multiplication (14 Aug 2026) ------------------------------------
# The exam asks `48 * 14` (grade 3: factors up to 99 × 19) but the world
# only ever multiplied by 2–12 — the form did not exist in her material, so
# she answered it by guessing in one pass, systematically dropping the tens
# digit (79 * 19 answered as exactly 79 * 9; stuck at 65% for two runs).
# The cure is the same as on 8 Aug 2026: a working, here the split over
# tens: each step is one easy operation. Own seed split, like the
# conversational wrapper: untouched problems stay bit for bit what they were.

KEER_SEED = 0x4B65657273                 # "Keers"
KEER_MIN, KEER_MAX = 3, 8


def _big_multiplication(k):
    a = k.integer(2, 99)
    b = k.integer(13, 19)
    tens, ones = a * 10, a * (b - 10)
    working = (f"{a} * 10 = {tens} ; {a} * {b - 10} = {ones} ; "
               f"{tens} + {ones} = {tens + ones}")
    return f"{a} * {b}", a * b, working


# --- the teen multiplication with a tail (16 Aug 2026) -----------------------
# The bare form above went 65 → 99% in run 5. But the exam's grade 4 asks
# `a * b + c` and `a * b - c` with the same teen factor, and there she
# guessed the product in one pass again (`24 * 16 = 324`) or did half the
# split (`21 * 10 = 210 ; 210 + 19`): 27 of the 28 misses on rekenen 4
# after run 5. The tree never makes this form — it multiplies by 2–12 only —
# so the split-over-tens was, to her, something for a bare multiplication
# and not for a multiplication inside a sum. Same cure once more: the form
# with the full working, four easy steps, the last number the answer.
#
# Own seed split, one in five numbers at depth 4–10; applied *before* the
# bare split, so every bare teen multiplication stays bit for bit where it
# was and only plain tree problems get replaced. Ranges wrap the exam's
# (a up to 25, c up to 99): what the exam asks must exist in her material.

KEERC_SEED = 0x4B65657243                # "KeerC"
KEERC_MIN, KEERC_MAX = 4, 10


def _teen_multiplication_with_tail(k):
    a = k.integer(2, 40)
    b = k.integer(13, 19)
    c = k.integer(1, 99)
    op = k.choice(("+", "-"))
    tens, ones = a * 10, a * (b - 10)
    product = tens + ones
    result = product + c if op == "+" else product - c
    working = (f"{a} * 10 = {tens} ; {a} * {b - 10} = {ones} ; "
               f"{tens} + {ones} = {product} ; {product} {op} {c} = {result}")
    return f"{a} * {b} {op} {c}", result, working


# --- the long loop with a compact working (14 Aug 2026) ----------------------
# The exam's loops run to twenty rounds; the world stopped at eleven because
# the wide working (two or three equations per round, ~660 characters for
# eighteen rounds) fit no writing space. On the run-4 exam she computed
# those loops flawlessly and then fell off the page — every code-3/5 miss
# was a long loop cut short. Same cure as the puzzle wall of 13 Aug 2026:
# a compact working — the terms as one row, the running sum as one row,
# every number derivable from the row above or the program itself. Short
# loops keep the wide working she already masters; the long sizes were
# always filtered out by `fits()`, so nothing she has seen changes shape.

LUS_SEED = 0x4C616E67654C7573            # "LangeLus"
LUS_MIN = 5
# Not above the old fence: from STAPEL_MIN the stacked forms carry the depth
# (15 Aug 2026); a plain twenty-round loop at depth 22 would repeat depth
# 12. Below 16 nothing changes — the draw itself still happens.
LUS_MAX = 15


def _long_loop(depth, k):
    form = k.choice(("2i", "i2", "def"))
    if form == "def":
        n = k.integer(12, 15)            # the exam's full size
        f, c = k.integer(2, 20), k.integer(0, 9)
        terms = [i * f + c for i in range(1, n + 1)]
        program = (f"def f(x):\n    return x * {f} + {c}\n\n"
                   f"totaal = 0\nfor i in range(1, {n + 1}):\n"
                   f"    totaal += f(i)\nprint(totaal)")
        # f(i+1) − f(i) = f: after the first term, each next one is a
        # single small addition — no teen multiplication per round.
        head = (f"f(1) = 1 * {f} + {c} = {terms[0]} ; daarna steeds +{f}: "
                + " ".join(str(x) for x in terms))
        start = 0
    else:
        n = k.integer(12, 20)            # the exam's full size
        start = k.integer(0, 50)
        if form == "2i":
            terms = [2 * i for i in range(1, n + 1)]
            body = "totaal += i * 2"
            head = "termen: " + " ".join(str(x) for x in terms)
        else:
            terms = [i * i for i in range(1, n + 1)]
            body = "totaal += i * i"
            head = "kwadraten: " + " ".join(str(x) for x in terms)
        program = (f"totaal = {start}\nfor i in range(1, {n + 1}):\n"
                   f"    {body}\nprint(totaal)")
    sums, total = [start], start
    for x in terms:
        total += x
        sums.append(total)
    working = head + " ; som: " + " ".join(str(x) for x in sums)
    return program, total, working


# --- the keer-plus row (15 Aug 2026) -----------------------------------------
# The rows had three bricks at the bottom: a fixed step, a fixed factor, and
# the sum of the previous two. Deeper meant more layers on those bricks —
# and past depth 10 that road ends: ten layers of differences and weaves on
# a nineteen-number row is not a harder puzzle, and the method mostly finds
# nothing (5% usable) or a coincidence (measured 15 Aug 2026, fase1). So the
# world grows here the other way: a new brick, `x → 2x + b`, under the same
# layers. Her method already peels it — differences, then the fixed ratio —
# so nothing in `_explain` changes and no new coincidences appear.
#
# Own seed split, one in five numbers from depth 2 (at depth 1 a brick
# stands alone, and this one already asks two layers of working): the same
# form as the conversational wrapper and the big multiplication. Untouched
# numbers stay bit for bit what they were.

KEERPLUS_SEED = 0x4B656572506C7573       # "KeerPlus"
KEERPLUS_MIN = 2


# --- outward -----------------------------------------------------------------

def make(family, depth, number):
    """A task from the world. Fully determined by the three arguments.

    The depth lands in the task's grade field: it *is* the difficulty, only
    now a dial instead of a step.
    """
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; choose from {FAMILIES}")
    if not MIN_DEPTH <= depth <= MAX_DEPTH:
        raise ValueError(
            f"depth {depth} falls outside {MIN_DEPTH}–{MAX_DEPTH}"
        )
    seed = _seed_of(family, depth, number)
    t = Picker(seed)
    problem, solution, working = _MAKERS[family](depth, t)
    if family == "puzzel":
        # Before the emptiness check: one in five numbers tries the
        # keer-plus brick first. Comes a method out, the number carries
        # that row (also where the old row had none — the world grows);
        # otherwise it keeps its old row. The split may replace, never
        # remove, and the other four in five stay bit for bit.
        k = Picker(_mix(seed ^ KEERPLUS_SEED))
        kp_drawn = depth >= KEERPLUS_MIN and k.integer(1, 5) == 1
        if kp_drawn:
            kp = _row(depth, k, bases=("keer-plus",), extra=2)
            if kp[0] is not None:
                problem, solution, working = kp
        # The "which rule" puzzle (17 Aug 2026): one in three numbers where
        # keer-plus did not draw, and every number above ROW_MAX. Numbers
        # keer-plus took, and untouched rows, stay bit for bit.
        if not kp_drawn and _rule_draws(seed, depth):
            problem, solution, working = _rule_puzzle(depth, Picker(_mix(seed ^ REGEL_SEED ^ 0x1)))
    if family == "geheugen":
        # the memory brick (17 Aug 2026): one in three numbers from
        # STEEN_MIN keeps a running state; the other two stay bit for bit
        k = Picker(_mix(seed ^ STEEN_SEED))
        if depth >= STEEN_MIN and k.integer(1, 3) == 1:
            problem, solution, working = _memory_state(depth, k)
    if problem is None:
        # No working comes out — then there is nothing to learn, only to
        # guess. `learning_tasks` skips it.
        return None
    if family == "rekenen":
        # First the teen multiplication with a tail (16 Aug 2026), then the
        # bare one: the bare split wins where both hit, so every bare teen
        # multiplication she learned in run 5 stays bit for bit in place.
        k = Picker(_mix(seed ^ KEERC_SEED))
        if KEERC_MIN <= depth <= KEERC_MAX and k.integer(1, 5) == 1:
            problem, solution, working = _teen_multiplication_with_tail(k)
        k = Picker(_mix(seed ^ KEER_SEED))
        if KEER_MIN <= depth <= KEER_MAX and k.integer(1, 5) == 1:
            problem, solution, working = _big_multiplication(k)
        problem, working = _converse(problem, working, depth,
                                     Picker(_mix(seed ^ CONVERSE_SEED)))
    if family == "code":
        k = Picker(_mix(seed ^ LUS_SEED))
        if LUS_MIN <= depth <= LUS_MAX and k.integer(1, 4) == 1:
            problem, solution, working = _long_loop(depth, k)
    return Task(family=family, grade=depth, number=number,
                problem=problem, solution=str(solution), working=working)


def fits(task, room=MAX_CHARS):
    """Does this problem with its answer fit the window?

    A task that does not fit the window is one she cannot even read, and it
    must not end up in her study material. With a grammar that deepens
    itself that is no theoretical case: depth 12 produced programs of well
    over five hundred characters.
    """
    return len(task.problem) + len(task.to_learn()) + 3 <= room


def learning_tasks(family, depth, count, start=0, room=MAX_CHARS,
                   exclude=None):
    """Study material from the world.

    Skips two kinds of tasks: what does not fit the window, and what
    collides with an exam. The second is the same latch as in `tasks.py` —
    there, on 8 Aug 2026, a quarter of the study material produced the same
    problems as the benchmark, and nobody had seen it.

    `exclude` is a set of problem texts that must not be used.
    `proefwerken.py` supplies it; on its own this excludes nothing.
    """
    forbidden = exclude if exclude is not None else frozenset()
    found = []
    number = start
    bound = start + count * 20 + 1000
    while len(found) < count:
        if number > bound:
            raise ValueError(
                f"{family} depth {depth}: only {len(found)} of the "
                f"{count} requested tasks found between {start} and {number}"
            )
        task = make(family, depth, number)
        if task is not None and fits(task, room) and task.problem not in forbidden:
            found.append(task)
        number += 1
    return found
