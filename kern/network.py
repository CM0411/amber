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
import torch.utils.checkpoint
import torch.nn as nn
import torch.nn.functional as F

from tokens import VOCAB


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


class KVCache:
    """The keys and values of everything already written, per layer — laid
    out once at full length and written into in place (15 Aug 2026).

    Before, every new character did `torch.cat` on the cache: a fresh,
    slightly larger block, everything copied over, the old one dropped. For
    a moment two caches stood side by side (measured: the answering peak
    was twice the cache, 7.3 GB at 12 layers × window 1536 × batch 64 in
    fp32), and each character copied the whole cache again — gigabytes of
    copying per answer round. Now one buffer of `capacity` positions per
    layer, `n` of them filled; the attention reads the first `n`. The
    numbers she computes are the same; only the copying is gone.
    """

    # Reserved in steps, not all at once (18 Aug 2026, Cley's VRAM
    # housekeeping): `capacity` is the ceiling — the question plus all the
    # room she may write — but most answers end long before it, and an exam
    # of 64 tasks at a room of 1224 held gigabytes of zeros. So the buffer
    # holds what is filled plus one GROW ahead, and grows by GROW when that
    # runs out: at most capacity/GROW copies per answer instead of one per
    # character. The values are the same tensors, moved exactly; test-cache
    # proves the scores are identical to the one-shot buffer.
    GROW = 256

    def __init__(self, capacity):
        self.capacity = capacity
        self.k = None
        self.v = None
        self.n = 0

    def _make_room(self, k, v, length):
        need = self.n + length
        if need > self.capacity:
            raise ValueError(
                f"cache full: {self.n} + {length} > capacity {self.capacity}")
        have = 0 if self.k is None else self.k.shape[2]
        if need <= have:
            return
        new = min(self.capacity, max(need, have + self.GROW))
        batch, heads, _, size = k.shape
        nk = k.new_zeros(batch, heads, new, size)
        nv = v.new_zeros(batch, heads, new, size)
        if self.k is not None and self.n:
            nk[:, :, :self.n] = self.k[:, :, :self.n]
            nv[:, :, :self.n] = self.v[:, :, :self.n]
        self.k, self.v = nk, nv

    def append(self, k, v):
        """Write (batch, heads, length, head_size) at the end; return the
        filled part of both buffers."""
        length = k.shape[2]
        self._make_room(k, v, length)
        self.k[:, :, self.n:self.n + length] = k
        self.v[:, :, self.n:self.n + length] = v
        self.n += length
        return self.k[:, :, :self.n], self.v[:, :, :self.n]


# --- writing one character at a time as one card instruction (25 Aug 2026) ---
# Measured on run 7.3 (step 448.500): the card was busy a quarter of the
# time and Python had one core at 100%. Writing an answer sends every layer's
# every operation to the card separately -- some nine hundred tiny kernels
# per character, each costing more to launch than to run. This decoder does
# the same arithmetic with fixed shapes: buffers laid out at full room, the
# position as a tensor instead of a Python number, the attention over the
# whole buffer with the unfilled part masked. Fixed shapes are what a CUDA
# graph needs: the whole step is captured once and then replayed per
# character as one instruction. The numbers are the eager path's within
# rounding (the softmax and the matmul see more masked columns, which changes
# the order of the additions, not the sum); test-snel.py checks both paths
# against each other and the graph against the eager step bit for bit.
# Learning is untouched: this is the answering loop only.


def _angles_at(pos, head_size, device):
    """The angles of one position given as a tensor (graph-safe `_angles`)."""
    step = torch.arange(0, head_size, 2, device=device, dtype=torch.float32)
    freq = 1.0 / (10000.0 ** (step / head_size))
    angle = pos.to(torch.float32).reshape(1, 1) * freq[None, :]
    return torch.cos(angle), torch.sin(angle)


class Decoder:
    """Answering with fixed shapes, per character one (captured) step.

    `prefill` runs the question through the ordinary path once and copies
    the keys and values into buffers of `room` positions (grown by GROW like
    KVCache, so an exam of 64 tasks does not hold gigabytes of zeros);
    `step` writes one character. On a card the step is a CUDA graph,
    captured anew whenever the buffers grow; elsewhere the same code runs
    eagerly.
    """

    GROW = KVCache.GROW

    def __init__(self, core, batch, capacity, key_mask_full, use_graph=True):
        self.core = core
        self.batch = batch
        self.capacity = capacity
        self.device = key_mask_full.device
        self.mask_full = key_mask_full        # (batch, capacity), True = nothing real
        att = core.blocks[0].attention
        self.heads, self.head_size = att.heads, att.head_size
        self.n = 0                            # positions filled
        self.room = 0                         # positions laid out
        self.k = self.v = None
        self.tok = torch.zeros(batch, 1, dtype=torch.long, device=self.device)
        self.pos = torch.zeros((), dtype=torch.long, device=self.device)
        self.graph = None
        self.out = None
        self.use_graph = use_graph and self.device.type == "cuda"

    def _make_room(self, need, like):
        if need > self.capacity:
            raise ValueError(f"decoder full: {need} > capacity {self.capacity}")
        if need <= self.room:
            return
        room = min(self.capacity, max(need, self.room + self.GROW))
        shape = (self.batch, self.heads, room, self.head_size)
        self.graph = None                     # new addresses: capture again
        if self.k is None:
            self.k = [like.new_zeros(shape) for _ in self.core.blocks]
            self.v = [like.new_zeros(shape) for _ in self.core.blocks]
        else:
            # layer by layer, like KVCache: old and new stand side by side
            # for one layer at a time, not for all twenty (measured 25 Aug
            # 2026 on the P100: 15,7 GB against 5,7 for the ordinary path)
            for i in range(len(self.k)):
                nk, nv = like.new_zeros(shape), like.new_zeros(shape)
                nk[:, :, :self.n].copy_(self.k[i][:, :, :self.n])
                nv[:, :, :self.n].copy_(self.v[i][:, :, :self.n])
                self.k[i], self.v[i] = nk, nv
        self.room = room

    def prefill(self, question, key_mask):
        """The question in one ordinary pass; returns its scores."""
        cache = self.core.new_cache(self.capacity)
        scores, cache = self.core.advance(question, cache=cache, key_mask=key_mask)
        length = question.shape[1]
        self._make_room(length, cache[0].k)
        for i, c in enumerate(cache):
            self.k[i][:, :, :length].copy_(c.k[:, :, :length])
            self.v[i][:, :, :length].copy_(c.v[:, :, :length])
        self.n = length
        self.pos.fill_(length)
        return scores

    def step_eager(self):
        """One character at position `pos`, from `tok`; returns (batch, 1, VOCAB)."""
        core, batch = self.core, self.batch
        x = core.embedding(self.tok)
        cos, sin = _angles_at(self.pos, self.head_size, self.device)
        col = torch.arange(self.room, device=self.device)
        mask = self.mask_full[:, :self.room] | (col > self.pos)[None, :]
        index = self.pos.reshape(1)
        for i, block in enumerate(core.blocks):
            att = block.attention
            qkv = att.to_qkv(block.norm1(x))
            q, k, v = qkv.chunk(3, dim=-1)
            shape = (batch, 1, att.heads, att.head_size)
            q = q.view(shape).transpose(1, 2)
            k = k.view(shape).transpose(1, 2)
            v = v.view(shape).transpose(1, 2)
            q = _rotate(q, cos, sin)
            k = _rotate(k, cos, sin)
            self.k[i].index_copy_(2, index, k.to(self.k[i].dtype))
            self.v[i].index_copy_(2, index, v.to(self.v[i].dtype))
            keys, values = self.k[i], self.v[i]
            if att._scale_folds and not torch.is_autocast_enabled():
                scores = (q * att._scale) @ keys.transpose(-2, -1)
            else:
                scores = (q @ keys.transpose(-2, -1)) / math.sqrt(att.head_size)
            scores.masked_fill_(mask[:, None, None, :], float("-inf"))
            empty = torch.isinf(scores).all(dim=-1, keepdim=True)
            scores.masked_fill_(empty, 0.0)
            weight = torch.softmax(scores, dim=-1)
            out = (weight @ values).transpose(1, 2).reshape(batch, 1, att.inner)
            x = x + block.alpha1 * att.out(out)
            x = x + block.alpha2 * block.feedforward(block.norm2(x))
        return core.unembedding(core.final_norm(x))

    def _capture(self):
        side = torch.cuda.Stream()
        side.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side):
            for _ in range(2):                # warm-up: the real step will overwrite this position anyway
                self.step_eager()
        torch.cuda.current_stream().wait_stream(side)
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph):
            self.out = self.step_eager()

    def step(self, following):
        """Write the character `following` (batch,) at the next position;
        returns the scores for the character after it, (batch, VOCAB)."""
        self.tok.copy_(following.reshape(self.batch, 1))
        self._make_room(self.n + 1, self.k[0])
        if self.use_graph:
            if self.graph is None:
                self._capture()
            self.graph.replay()
            # a copy: the graph writes the same buffer at every replay, and
            # a caller that keeps the scores must not see them change
            scores = self.out[:, -1].clone()
        else:
            scores = self.step_eager()[:, -1]
        self.n += 1
        self.pos.add_(1)
        return scores


# --- the slimmer attention (16 Aug 2026) ---------------------------------------
# On the P100 the softmax and the masks were a third of a learning step:
# every pass over the (batch, heads, length, length) scores is 900 million
# numbers at the run-6 shape, and the old path made twenty of them per
# layer — divide, mask, softmax and their backwards, each a separate kernel
# with its own copy. Three things are slimmer now, all bit for bit the same
# arithmetic (proven in test-attention.py, learning and answering, fp32 and
# bf16, with and without checkpointing):
#
# * **The scale is folded into q** (`q * (1 / sqrt(head_size))`) instead of
#   dividing the scores — in fp32. Exact because the head size is 64 and
#   its root 8 a power of two: scaling by 2^-3 shifts the exponent and
#   rounds nothing, so every product and every partial sum in the matmul
#   is the old one divided by eight, and the same holds for the gradients.
#   Not under bf16 autocast: there the backward matmuls came out different
#   (measured 16 Aug 2026 on the P100 — cuBLAS's bf16 GEMM with its
#   reduced-precision reductions is not the same kernel for the two
#   layouts autograd builds), so the trainer's bf16 path keeps dividing
#   the scores, which is the old computation by construction. Any other
#   head size takes the old road too.
# * **The causal ban is built once per length** and kept, not rebuilt in
#   every block of every step.
# * **Mask and softmax are one autograd node** (`_MaskedSoftmax`). Forward
#   is what it was; the backward runs only the softmax backward — the
#   masked weights are exactly zero, so their gradient is exactly zero
#   without a second pass that writes zeros over zeros.

_BAN = {}


def _causal_ban(length, device):
    key = (length, device)
    ban = _BAN.get(key)
    if ban is None:
        ban = torch.ones(length, length, device=device,
                         dtype=torch.bool).triu(1)
        _BAN[key] = ban
    return ban


class _MaskedSoftmax(torch.autograd.Function):
    """Softmax over the last axis after the bans, as one node.

    Forward is the old sequence: ban in place, padding in place, empty rows
    to equal weights, softmax. Backward is the softmax backward alone —
    torch's own kernel with the input dtype the softmax had (bf16 under
    autocast), exactly what autograd ran before. The old graph then also
    ran the backward of the in-place masks: gradient times zero at every
    banned place, which is what the softmax backward already produced.
    """

    @staticmethod
    def forward(ctx, scores, ban, key_mask):
        if ban is not None:
            scores.masked_fill_(ban, float("-inf"))
        if key_mask is not None:
            scores.masked_fill_(key_mask[:, None, None, :], float("-inf"))
            # A padding position may look at nothing: every score is then
            # minus infinity, and its softmax is NaN. That NaN creeps through
            # the residual stream and breaks every answer in the batch, also
            # the healthy ones. Such rows get equal weights instead; their
            # output is nonsense but finite, and it is never read.
            empty = torch.isinf(scores).all(dim=-1, keepdim=True)
            scores.masked_fill_(empty, 0.0)
        ctx.input_dtype = scores.dtype
        weight = torch.softmax(scores, dim=-1)
        ctx.save_for_backward(weight)
        return weight

    @staticmethod
    def backward(ctx, grad):
        (weight,) = ctx.saved_tensors
        # the same two steps autograd ran: the softmax backward in the
        # dtype of the weights, then — under autocast — the cast back to
        # the dtype the scores had. Not the fused half-to-float kernel: it
        # is bit for bit the old path by construction, this way
        g = torch._softmax_backward_data(grad, weight, -1, weight.dtype)
        if g.dtype != ctx.input_dtype:
            g = g.to(ctx.input_dtype)
        return g, None, None


class Attention(nn.Module):
    """`heads` heads of `head_size` each. By default heads × head_size is
    the width — the usual split, and the shape every snapshot before 16 Aug
    2026 has. Growing wider (E) adds heads while the width stays: then the
    inner size heads × head_size grows past the width, and only `to_qkv`
    and `out` change shape. The head size never changes — the rotation
    angles depend on it, and so does every key she has ever computed."""

    def __init__(self, width, heads, head_size=None):
        super().__init__()
        if head_size is None:
            if width % heads:
                raise ValueError(f"width {width} not divisible by {heads} heads")
            head_size = width // heads
        self.heads = heads
        self.head_size = head_size
        self.inner = heads * head_size
        if self.head_size % 2:
            raise ValueError("head size must be even for the rotation")
        self.to_qkv = nn.Linear(width, 3 * self.inner, bias=False)
        self.out = nn.Linear(self.inner, width, bias=False)
        # 1/sqrt(head_size) folded into q — exact only when that root is a
        # power of two (head size 64 → 8), see the note above _causal_ban
        root = math.sqrt(self.head_size)
        self._scale_folds = root == int(root) and (int(root) & (int(root) - 1)) == 0
        self._scale = 1.0 / root

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

        if cache is not None:
            k, v = cache.append(k, v)
            # In the cache path k and v now live in the buffers, and q was
            # replaced by its rotation: the qkv block is dead weight from
            # here (15 Aug 2026 — the answering peak sits in this layer's
            # scratch, measured 4411 → 4267 MB at the run-6 shape). In the
            # learning path v is still a view into qkv, so it stays.
            del qkv

        full_pass = q.shape[2] == k.shape[2]
        # A causal ban only when query and key are equally long — that is
        # the full pass. When she writes one token against a filled cache,
        # that token may see everything before it.
        ban = _causal_ban(length, x.device) if full_pass else None
        if self._scale_folds and not torch.is_autocast_enabled():
            # exact in fp32: see the note above _causal_ban
            scores = (q * self._scale) @ k.transpose(-2, -1)
        else:
            scores = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_size)
        del q
        # `scores` is a fresh tensor from the matmul and nothing keeps the
        # unmasked version, so the masks fill in place; the node saves only
        # the softmax output for its backward.
        weight = _MaskedSoftmax.apply(scores, ban, key_mask)
        del scores
        out = weight @ v
        del weight
        out = out.transpose(1, 2).reshape(batch, length, self.inner)
        return self.out(out), cache


class FeedForward(nn.Module):
    def __init__(self, width, hidden=None):
        super().__init__()
        self.hidden = 4 * width if hidden is None else hidden
        self.up = nn.Linear(width, self.hidden, bias=False)
        self.down = nn.Linear(self.hidden, width, bias=False)

    def forward(self, x):
        return self.down(F.gelu(self.up(x)))


class Block(nn.Module):
    """One layer. Two residual branches, each with its own gate.

    Both gates start at zero: on insertion this block does nothing and
    leaves the output exactly untouched.
    """

    def __init__(self, width, heads, head_size=None, hidden=None):
        super().__init__()
        self.norm1 = nn.LayerNorm(width)
        self.attention = Attention(width, heads, head_size)
        self.alpha1 = nn.Parameter(torch.zeros(1))

        self.norm2 = nn.LayerNorm(width)
        self.feedforward = FeedForward(width, hidden)
        self.alpha2 = nn.Parameter(torch.zeros(1))

    def forward(self, x, cos, sin, cache=None, key_mask=None):
        out, new_cache = self.attention(self.norm1(x), cos, sin,
                                        cache, key_mask)
        x = x + self.alpha1 * out
        x = x + self.alpha2 * self.feedforward(self.norm2(x))
        return x, new_cache


class Core(nn.Module):
    def __init__(self, layers=8, width=384, heads=6, window=512,
                 head_size=None, hidden=None):
        super().__init__()
        self.width = width
        self.heads = heads
        self.head_size = width // heads if head_size is None else head_size
        self.hidden = 4 * width if hidden is None else hidden
        self.window = window

        self.embedding = nn.Embedding(VOCAB, width)
        self.blocks = nn.ModuleList(
            Block(width, heads, self.head_size, self.hidden)
            for _ in range(layers))
        self.final_norm = nn.LayerNorm(width)
        self.unembedding = nn.Linear(width, VOCAB, bias=False)

        # Activation checkpointing (15 Aug 2026, groundwork for E). While
        # learning, every block keeps its intermediates for the backward
        # pass; at batch 64 × window 1024 that scratch work is most of the
        # VRAM, not the weights. With this on, a block keeps only its input
        # and recomputes the rest during backward: the same numbers, bit for
        # bit (test-checkpointing.py), for ~30% more time on the learning
        # part — and a net several times bigger fits the 8 GB of the Z490
        # without halving the batch. Off by default; the Learner switches it
        # on. Only acts while gradients are being tracked; answering (no
        # grad, with cache) is untouched.
        self.checkpointing = False

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

        `cache` is what `new_cache(capacity)` returned, or None for a plain
        pass (learning). Since 15 Aug 2026 the cache is a fixed buffer per
        layer, written into in place — see KVCache.
        """
        batch, length = codes.shape
        if offset + length > self.window:
            raise ValueError(
                f"position {offset + length} falls outside window {self.window}")

        x = self.embedding(codes)
        cos, sin = _angles(length, self.blocks[0].attention.head_size,
                           codes.device, offset)
        new = []
        recompute = (self.checkpointing and self.training
                     and torch.is_grad_enabled() and cache is None)
        for i, block in enumerate(self.blocks):
            if recompute:
                # non-reentrant: works with any output shape and keeps the
                # RNG state, so the recomputation is exactly the first pass
                x, block_cache = torch.utils.checkpoint.checkpoint(
                    block, x, cos, sin, None, key_mask, use_reentrant=False)
            else:
                x, block_cache = block(x, cos, sin,
                                       cache[i] if cache is not None else None,
                                       key_mask)
            new.append(block_cache)
        return self.unembedding(self.final_norm(x)), (cache if cache is not None
                                                      else new)

    def new_cache(self, capacity):
        """One KVCache per layer, laid out for `capacity` positions. Pass
        it to `advance` on the first call already — the question fills it,
        every character after that appends."""
        return [KVCache(capacity) for _ in self.blocks]

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
        new = Block(self.width, self.heads, self.head_size,
                    self.hidden).to(self.embedding.weight.device)
        blocks = list(self.blocks)
        blocks.insert(position, new)
        self.blocks = nn.ModuleList(blocks)
        return new

    def grow_heads(self, extra):
        """Add `extra` attention heads to every block. The output does not
        change (16 Aug 2026, the second half of E).

        The residual stream keeps its width; what grows is the inner size
        of the attention, heads × head_size. Every new head gets fresh
        rows in `to_qkv` and **zero columns in `out`**: it looks at the
        text like any other head, but what it sees is multiplied by zero
        before it reaches the stream. Mathematically the output is exactly
        the old one; the new columns then get a gradient and the head
        learns itself in — the same idea as the zero gate on a new block.
        (Growing the residual width itself is not on offer: LayerNorm
        averages over that width, so no padding leaves the old numbers
        alone. Only whole-block or inner growth is exact.)

        Returns the transplants: (old_param, new_param, place) triples,
        where `place(src, dst)` copies an old-shaped tensor into its slots
        of a new-shaped one. The Learner uses that to carry the optimizer's
        moments across — the weights here, the moments there, by the same
        rule.
        """
        if extra <= 0:
            raise ValueError(f"grow_heads wants a positive count, got {extra}")
        device = self.embedding.weight.device
        old_heads, hs = self.heads, self.head_size
        new_heads = old_heads + extra
        old_inner, new_inner = old_heads * hs, new_heads * hs
        transplants = []
        for block in self.blocks:
            old = block.attention
            new = Attention(self.width, new_heads, hs).to(device)

            def place_qkv(src, dst, oi=old_inner, ni=new_inner):
                # rows: [q | k | v], each old_inner long → same three
                # groups, each new_inner long, old rows first in each
                for g in range(3):
                    dst[g * ni:g * ni + oi] = src[g * oi:(g + 1) * oi]

            def place_out(src, dst, oi=old_inner):
                dst[:, :oi] = src

            with torch.no_grad():
                place_qkv(old.to_qkv.weight, new.to_qkv.weight)
                new.out.weight.zero_()
                place_out(old.out.weight, new.out.weight)
            transplants.append((old.to_qkv.weight, new.to_qkv.weight, place_qkv))
            transplants.append((old.out.weight, new.out.weight, place_out))
            block.attention = new
        self.heads = new_heads
        return transplants

    def grow_hidden(self, new_hidden):
        """Widen the feedforward of every block to `new_hidden` units. The
        output does not change (16 Aug 2026).

        New rows in `up` (fresh), **zero columns in `down`**: the new units
        compute, but add exactly nothing until they have learned to. Same
        rule and same return value as `grow_heads`.
        """
        if new_hidden <= self.hidden:
            raise ValueError(
                f"grow_hidden: {new_hidden} is not more than {self.hidden}")
        device = self.embedding.weight.device
        old_hidden = self.hidden
        transplants = []
        for block in self.blocks:
            old = block.feedforward
            new = FeedForward(self.width, new_hidden).to(device)

            def place_up(src, dst, oh=old_hidden):
                dst[:oh] = src

            def place_down(src, dst, oh=old_hidden):
                dst[:, :oh] = src

            with torch.no_grad():
                place_up(old.up.weight, new.up.weight)
                new.down.weight.zero_()
                place_down(old.down.weight, new.down.weight)
            transplants.append((old.up.weight, new.up.weight, place_up))
            transplants.append((old.down.weight, new.down.weight, place_down))
            block.feedforward = new
        self.hidden = new_hidden
        return transplants

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
            "head_size": self.head_size,
            "hidden": self.hidden,
            "window": self.window,
            "parameters": self.parameter_count(),
        }

    @staticmethod
    def from_spec(spec):
        # Snapshots before 16 Aug 2026 carry no head_size or hidden: then
        # the defaults (width ÷ heads, 4 × width) are exactly their shape.
        return Core(layers=spec["layers"], width=spec["width"],
                    heads=spec["heads"], window=spec["window"],
                    head_size=spec.get("head_size"),
                    hidden=spec.get("hidden"))
