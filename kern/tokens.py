"""
The character set — how a task becomes a sequence of numbers.

**This is fixed forever.** Change the character set later and every embedding
points at something else, making every checkpoint worthless. The same kind of
requirement as determinism and the bottleneck, and for the same reason done
right from the start.

WHY BYTES
---------
Zero through 255 are the bytes of the text itself, in UTF-8. That is the only
choice that never needs revisiting:

  * there is nothing to choose, so nothing that should have been different
  * Dutch with accents — and later anything she pulls off the internet —
    fits without ever extending the set
  * digits stay separate. A common tokenizer glues digit groups together,
    which makes `47 * 13` artificially hard because "47" is one chunk
  * and a borrowed tokenizer would violate "what learns, we build ourselves"

Above that, four own tokens — and none get added without it being a decision:

  256 QUESTION   a task starts here
  257 ANSWER     the answer starts here — only after this does the loss count
  258 END        done
  259 PAD        padding, counts nowhere

THE LOSS COUNTS ONLY OVER THE ANSWER
------------------------------------
`task_to_sequence` returns a mask marking which positions count. Only the
answer and the END token are on. Otherwise she learns to predict questions
instead of answering them — good at inventing sums, not at solving them.

This file is the English successor of tekens.py; toets-migratie.py enforces
that both encode and decode bit for bit identically.
"""

QUESTION = 256
ANSWER = 257
END = 258
PAD = 259

VOCAB = 260           # the character set counts 260 tokens, forever

NAMES = {QUESTION: "<question>", ANSWER: "<answer>", END: "<end>", PAD: "<pad>"}


def encode(text):
    """Text to a sequence of numbers."""
    return list(text.encode("utf-8"))


def decode(codes):
    """Sequence of numbers back to text. Own tokens are skipped."""
    bytes_ = bytes(c for c in codes if c < 256)
    return bytes_.decode("utf-8", errors="replace")


def show(codes):
    """Readable rendering with the own tokens visible, for inspection."""
    parts, buffer = [], []
    for c in codes:
        if c < 256:
            buffer.append(c)
        else:
            if buffer:
                parts.append(bytes(buffer).decode("utf-8", errors="replace"))
                buffer = []
            parts.append(NAMES.get(c, f"<{c}>"))
    if buffer:
        parts.append(bytes(buffer).decode("utf-8", errors="replace"))
    return "".join(parts)


def task_to_sequence(task):
    """A task as a sequence of numbers, with the mask saying what counts.

    Shape:  QUESTION  problem  ANSWER  solution  END

    The mask is on only for the solution and END. The problem itself does not
    count toward the loss: she must learn to answer, not to invent questions.
    """
    # `te_leren()` rather than the bare solution: when there is a worked
    # solution she is expected to write it. Grading looks at the last number,
    # so working out is allowed — and without that room she would have to
    # compute everything in a single pass.
    target = task.to_learn()
    seq = ([QUESTION] + encode(task.problem)
           + [ANSWER] + encode(target) + [END])
    counts = ([False] * (1 + len(encode(task.problem)) + 1)
              + [True] * (len(encode(target)) + 1))
    return seq, counts


def question_to_sequence(task):
    """Only the question, up to and including the ANSWER token.

    This is what you hand her when you want to know what she makes of it:
    from here she continues on her own.
    """
    return [QUESTION] + encode(task.problem) + [ANSWER]


def answer_from_sequence(codes):
    """Extract the answer from what she wrote.

    Everything between ANSWER and END. If either is missing there is no
    answer and nothing comes back — better empty than half.
    """
    try:
        start = codes.index(ANSWER) + 1
    except ValueError:
        return ""
    codes = list(codes[start:])
    if END in codes:
        codes = codes[:codes.index(END)]
    return decode(codes)


def batch(seqs, masks, length=None):
    """Put sequences of unequal length into one rectangle.

    Padding uses PAD with the mask off there — padding must count nowhere,
    or she learns to predict PAD and the loss looks fine while nothing
    happens.
    """
    length = length or max(len(s) for s in seqs)
    out, out_mask = [], []
    for seq, mask in zip(seqs, masks):
        if len(seq) > length:
            raise ValueError(
                f"sequence of {len(seq)} does not fit a window of {length}"
            )
        short = length - len(seq)
        out.append(list(seq) + [PAD] * short)
        out_mask.append(list(mask) + [False] * short)
    return out, out_mask
