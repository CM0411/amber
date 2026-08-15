"""
The key bridge — her Dutch past carried into the English code.

The codebase was written in Dutch and is being migrated to English. That
rename is not free: the model's attribute names *are* the keys in every
checkpoint she has ever written. `inbedding.weight` on disk must land in
`embedding.weight` in memory, or the load fails and her brain does not
survive the rename.

This module is that crossing, in one direction only: old Dutch keys are
translated on the way in, and everything written from now on is English.
toets-sleutelbrug.py proves on a real run-3 checkpoint that the translated
network produces bit-for-bit the same output as the Dutch original.
"""

# Order matters only for readability; each rule is a plain prefix/infix
# substitution and no rule's output overlaps another rule's input.
_WEIGHT_KEYS = [
    ("inbedding.", "embedding."),
    ("blokken.", "blocks."),
    (".aandacht.", ".attention."),
    (".naar_qkv.", ".to_qkv."),
    (".uitgang.", ".out."),
    (".voorwaarts.", ".feedforward."),
    (".omhoog.", ".up."),
    (".omlaag.", ".down."),
    (".alfa1", ".alpha1"),
    (".alfa2", ".alpha2"),
    ("slotnorm.", "final_norm."),
    ("uitbedding.", "unembedding."),
]

_SPEC_KEYS = {
    "lagen": "layers",
    "breedte": "width",
    "koppen": "heads",
    "kopgrootte": "head_size",
    "verborgen": "hidden",
    "venster": "window",
    "parameters": "parameters",
}


def is_dutch_state(state):
    return any(k.startswith(("inbedding.", "blokken.", "slotnorm.",
                             "uitbedding.")) for k in state)


def translate_state(state):
    """Dutch state_dict keys -> English. English input passes unchanged."""
    if not is_dutch_state(state):
        return state
    out = {}
    for key, value in state.items():
        for old, new in _WEIGHT_KEYS:
            key = key.replace(old, new)
        out[key] = value
    return out


def translate_spec(vorm):
    """Dutch checkpoint spec ('vorm') -> English spec. Idempotent."""
    if "layers" in vorm:
        return dict(vorm)
    return {_SPEC_KEYS[k]: v for k, v in vorm.items() if k in _SPEC_KEYS}
