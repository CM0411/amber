"""
The learning core — a transformer that can grow.

Hand-written, not pulled from a library, for the reason stated in the
roadmap: *"a network that grows while running can only be built if you hold
every layer in your own hands."*

THREE CHOICES THAT ARE FIXED
----------------------------
**1. Growing never changes the function.** Every residual branch has its own
learned gate that starts at zero:

    x = x + alpha * branch(norm(x))

Inserting a new block with alpha = 0 leaves the output **bit for bit**
identical; the block then learns itself in. Without this, growth is a jump
that shifts everything she could already do — and then E measures damage,
not growth.

**2. Positions by rotation (RoPE), not a learned position table.** A table
freezes the window forever: extending it means new parameters in places
where nothing was ever learned. Rotation has no parameters and stretches
along. The window grew from 512 to 768 between run 3 and run 4 and the
checkpoints moved with it — this is why.

**3. Attention is written out by hand**, not `scaled_dot_product_attention`.
That call picks an implementation per invocation and its backward pass is
not always deterministic. Writing it out costs some speed and buys the
requirement that outweighs it: repeatability.

ON PADDING
----------
Padding sits at the end and attention is causal, so a real token never looks
at padding that comes after it. Only padding positions see padding, and they
do not count toward the loss. No separate mask is needed for this.

This file is the English successor of netwerk.py; bridge.py translates
checkpoints written under the Dutch attribute names. Both nets compute the
same function — toets-sleutelbrug.py proves it bit for bit on her real
checkpoint.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from tokens import VOCAB
except ImportError:                        # until tokens.py exists (migration)
    from tekens import OMVANG as VOCAB


def _angles(length, head_size, device, offset=0):
    """RoPE angles. Computed in fp32 even when the rest runs fp16 — angles
    are cheap and precision here is noticeable.

    `offset` shifts the positions. When she writes an answer, one token is
    added at a time, and it must get the angle of its own position — not
    that of position zero.
    """
    step = torch.arange(0, head_size, 2, device=device, dtype=torch.float32)
    freq = 1.0 / (10000.0 ** (step / head_size))
    pos = torch.arange(offset, offset + length,
                       device=device, dtype=torch.float32)
    angle = torch.outer(pos, freq)
    return torch.cos(angle), torch.sin(angle)


def _rotate(x, cos, sin):
    """Rotate each pair of numbers by the angle of its position.

    x is (batch, heads, length, head_size).
    """
    even, odd = x[..., 0::2], x[..., 1::2]
    cos = cos.to(x.dtype)[None, None, :, :]
    sin = sin.to(x.dtype)[None, None, :, :]
    return torch.stack((even * cos - odd * sin,
                        even * sin + odd * cos), dim=-1).flatten(-2)


class Attention(nn.Module):
    def __init__(self, width, heads):
        super().__init__()
        if width % heads:
            raise ValueError(f"width {width} not divisible by {heads} heads")
        self.heads = heads
        self.head_size = width // heads
        if self.head_size % 2:
            raise ValueError("head size must be even for the rotation")
        self.to_qkv = nn.Linear(width, 3 * width, bias=False)
        self.out = nn.Linear(width, width, bias=False)

    def forward(self, x, cos, sin, cache=None, key_mask=None):
        """Returns (output, new cache).

        `cache` holds the keys and values of everything already written.
        While she writes an answer this saves everything: without it, every
        new token pushes the whole line through all layers again.

        `key_mask` marks positions holding nothing real. Answering pads on
        the left — otherwise the questions end at different positions and
        the cache breaks — and that padding must never count anywhere.
        """
        batch, length, width = x.shape
        qkv = self.to_qkv(x)
        q, k, v = qkv.chunk(3, dim=-1)
        shape = (batch, length, self.heads, self.head_size)
        q = q.view(shape).transpose(1, 2)
        k = k.view(shape).transpose(1, 2)
        v = v.view(shape).transpose(1, 2)

        q = _rotate(q, cos, sin)
        k = _rotate(k, cos, sin)

        if cache is not None and cache[0] is not None:
            k = torch.cat((cache[0], k), dim=2)
            v = torch.cat((cache[1], v), dim=2)
        new_cache = (k, v)

        scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_size)

        # A causal ban only when query and key are equally long — that is
        # the full pass. When she writes one token against a filled cache,
        # that token may see everything before it.
        if q.shape[2] == k.shape[2]:
            ban = torch.ones(length, length,
                             device=x.device, dtype=torch.bool).triu(1)
            scores = scores.masked_fill(ban, float("-inf"))
        if key_mask is not None:
            scores = scores.masked_fill(key_mask[:, None, None, :], float("-inf"))

            # A padding position may look at nothing: every score is then
            # minus infinity, and its softmax is NaN. That NaN creeps through
            # the residual stream and breaks every answer in the batch, also
            # the healthy ones. Such rows get equal weights instead; their
            # output is nonsense but finite, and it is never read.
            empty = torch.isinf(scores).all(dim=-1, keepdim=True)
            scores = scores.masked_fill(empty, 0.0)

        weight = torch.softmax(scores, dim=-1)
        out = weight @ v
        out = out.transpose(1, 2).reshape(batch, length, width)
        return self.out(out), new_cache


class FeedForward(nn.Module):
    def __init__(self, width, factor=4):
        super().__init__()
        self.up = nn.Linear(width, factor * width, bias=False)
        self.down = nn.Linear(factor * width, width, bias=False)

    def forward(self, x):
        return self.down(F.gelu(self.up(x)))


class Block(nn.Module):
    """One layer. Two residual branches, each with its own gate.

    Both gates start at zero: on insertion this block does nothing and
    leaves the output exactly untouched.
    """

    def __init__(self, width, heads):
        super().__init__()
        self.norm1 = nn.LayerNorm(width)
        self.attention = Attention(width, heads)
        self.alpha1 = nn.Parameter(torch.zeros(1))

        self.norm2 = nn.LayerNorm(width)
        self.feedforward = FeedForward(width)
        self.alpha2 = nn.Parameter(torch.zeros(1))

    def forward(self, x, cos, sin, cache=None, key_mask=None):
        out, new_cache = self.attention(self.norm1(x), cos, sin,
                                        cache, key_mask)
        x = x + self.alpha1 * out
        x = x + self.alpha2 * self.feedforward(self.norm2(x))
        return x, new_cache


class Core(nn.Module):
    def __init__(self, layers=8, width=384, heads=6, window=512):
        super().__init__()
        self.width = width
        self.heads = heads
        self.window = window

        self.embedding = nn.Embedding(VOCAB, width)
        self.blocks = nn.ModuleList(Block(width, heads) for _ in range(layers))
        self.final_norm = nn.LayerNorm(width)
        self.unembedding = nn.Linear(width, VOCAB, bias=False)

        nn.init.normal_(self.embedding.weight, std=0.02)
        nn.init.normal_(self.unembedding.weight, std=0.02)

    def forward(self, codes):
        """codes is (batch, length). Returns the scores per token."""
        return self.advance(codes)[0]

    def advance(self, codes, cache=None, offset=0, key_mask=None):
        """Returns (scores, cache).

        `offset` is the position where these tokens start. While writing an
        answer the cache already holds text, and the new token must get the
        angle of its own position — not that of position zero.
        """
        batch, length = codes.shape
        if offset + length > self.window:
            raise ValueError(
                f"position {offset + length} falls outside window {self.window}")

        x = self.embedding(codes)
        cos, sin = _angles(length, self.blocks[0].attention.head_size,
                           codes.device, offset)
        new = []
        for i, block in enumerate(self.blocks):
            x, block_cache = block(x, cos, sin,
                                   cache[i] if cache else None, key_mask)
            new.append(block_cache)
        return self.unembedding(self.final_norm(x)), new

    # --- growing ----------------------------------------------------------

    def add_block(self, position=None):
        """Insert a layer. The output does not change.

        The new block has both gates at zero and passes the residual stream
        through exactly. That is not an approximation: `x + 0 * f(x)` is
        bit for bit `x`. The block then learns itself in.

        Note for phase 5: the optimizer does not know these parameters yet.
        Whoever grows the net must also update the optimizer — see the
        roadmap, "a network that grows breaks the optimizer's state".
        """
        position = len(self.blocks) if position is None else position
        new = Block(self.width, self.heads).to(self.embedding.weight.device)
        blocks = list(self.blocks)
        blocks.insert(position, new)
        self.blocks = nn.ModuleList(blocks)
        return new

    def grow_window(self, new):
        """Enlarge the window. The output does not change.

        This cashes in the day-one design: positions go by rotation, which
        has no parameters, so the window is known in exactly one place — as
        the bound in `advance`. Growing is moving that bound. For anything
        that fits the old window the angles are identical, so the output is
        bit for bit the same; toets-venstergroei.py enforces that.

        Shrinking refuses: a smaller window can make experiences she already
        lived through unreadable, and there is no reason it should ever
        happen.
        """
        if new < self.window:
            raise ValueError(
                f"cannot shrink window from {self.window} to {new}")
        self.window = new

    # --- bookkeeping ------------------------------------------------------

    def parameter_count(self):
        return sum(p.numel() for p in self.parameters())

    def spec(self):
        """Everything needed to rebuild this network.

        Travels in the checkpoint: without the spec you cannot know how many
        layers there were, and after growth that differs every time.
        """
        return {
            "layers": len(self.blocks),
            "width": self.width,
            "heads": self.heads,
            "window": self.window,
            "parameters": self.parameter_count(),
        }

    @staticmethod
    def from_spec(spec):
        return Core(layers=spec["layers"], width=spec["width"],
                    heads=spec["heads"], window=spec["window"])
