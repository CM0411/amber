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

from tasks import FAMILIES, Task, Picker, _mix

# Own constant, separate from tasks.py's: the world and the exams are two
# separate things and must be so in their numbers too.
WORLD_SEED = 0x5765_7265_6C64          # "Wereld"

MIN_DEPTH = 1
# The fence follows the window, measured at the 85% standard (at least
# 85% of usable problems fit with their working). At 512 that gave 17
# (measured 9 Aug 2026: 100% through 15, 93% at 17, 66% at 18). At 768,
# measured 10-11 Aug 2026 for run 4: arithmetic fits 99% at depth 26.
MAX_DEPTH = 26

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
MAX_DEPTH_PER = {"puzzel": 9, "code": 11}


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

def _row_series(depth, t, length):
    """Build a series of `length` numbers.

    A series, not a "next value" function — otherwise a rule cannot be
    applied to another rule. That was the mistake in the first version:
    "second order" ignored the rule beneath it, and depth 5 equalled
    depth 8.
    """
    if depth <= 1:
        kind = t.choice(("maal", "plus", "plus", "beide-vorige"))
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
        a = _row_series(depth - 1, t, (length + 1) // 2)
        b = _row_series(depth - 1, t, length // 2 + 1)
        return [a[i // 2] if i % 2 == 0 else b[i // 2] for i in range(length)]

    # The series beneath is this one's differences. That is how stacking
    # really works: a row with a fixed difference becomes one with a growing
    # difference, and one more layer makes that growth itself grow.
    differences = _row_series(depth - 1, t, length - 1)
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


def _row(depth, t):
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
    length = shown + 1 + 2 * max(0, depth - 5)
    row = _row_series(max(1, depth - 1), t, length)
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


def _code(depth, t):
    # The grondslag's language, part two (10 Aug 2026): three program forms
    # the exam asks and the world lacked — measured per cell, code grades
    # 3–5 sat at exactly 0% because of it. Each form from the depth where
    # its working fits the writing space.
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


_MAKERS = {"rekenen": _arithmetic, "puzzel": _row, "code": _code}


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
    if problem is None:
        # No working comes out — then there is nothing to learn, only to
        # guess. `learning_tasks` skips it.
        return None
    if family == "rekenen":
        problem, working = _converse(problem, working, depth,
                                     Picker(_mix(seed ^ CONVERSE_SEED)))
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
