"""
Her real brain against the Decoder (25 Aug 2026): the ordinary answering
path and the Decoder on the same tasks, per character with identical inputs
(how often a different character would be chosen; the largest logit
difference) and end to end through the Learner (answers word for word, and
the scores). Needs a card and a snapshot.

Run:  python3 kern/test-snel-brein.py fase1/leven/momentopname.pt
Result on the DL380 (P100, fp16, snapshot of step 448.500): 0 other choices
in 39.375 characters, 384/384 answers equal, same scores, max logit
difference 0,047.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import determinism, torch, network, tokens, snapshot, bridge, world
from learning import Learner, bf16_usable, room_for
if not torch.cuda.is_available():
    print("geen kaart — deze test vergelijkt op de kaart; overgeslagen")
    print("passed: 0    failed: 0"); sys.exit(0)
pad = sys.argv[1] if len(sys.argv) > 1 else "fase1/leven/momentopname.pt"
modus = sys.argv[2] if len(sys.argv) > 2 else "graaf"   # "graaf" of "snij" (26 aug 2026)
assert modus in ("graaf", "snij"), modus
if not os.path.exists(pad):
    print(f"geen momentopname op {pad} — overgeslagen (geef er een als argument)")
    print("passed: 0    failed: 0"); sys.exit(0)
dev = "cuda"
core = network.Core(layers=20, width=384, heads=6, hidden=1536, window=2048)
learner = Learner(core=core, device=dev, batch_size=64, bf16=False)
content = snapshot.read(pad, device=dev)
vorm = (content.get("extra") or {}).get("vorm")
if vorm: learner.adopt_shape(bridge.translate_spec(vorm))
stap = snapshot.restore(content, learner.core, None, dev)
core = learner.core.eval(); del content
print(f"brein van stap {stap}, {len(core.blocks)} lagen, venster {core.window}, decoder-modus {modus}")
soort = torch.bfloat16 if bf16_usable(dev) else torch.float16   # the card's own half precision, as in the run
totaal = flips = 0; maxd = 0.0; eind_gelijk = eind_n = 0; score_oud = score_nieuw = 0
for family, depth in (("rekenen", 12), ("puzzel", 3), ("taal", 4), ("code", 10), ("geheugen", 8), ("logica", 6)):
    tasks_ = world.learning_tasks(family, depth, 64, start=12345, room=core.window - 112, exclude=set())
    at_most = min(room_for(depth, family, core.window), 400)
    prompts = [tokens.question_to_sequence(t) for t in tasks_]
    longest = max(len(p) for p in prompts); capacity = longest + at_most; B = len(tasks_)
    q = torch.full((B, longest), tokens.PAD, dtype=torch.long, device=dev)
    for i, p in enumerate(prompts): q[i, longest - len(p):] = torch.tensor(p, device=dev)
    mask = torch.zeros(B, capacity, dtype=torch.bool, device=dev); mask[:, :longest] = q == tokens.PAD
    with torch.no_grad(), torch.autocast("cuda", dtype=soort):
        # 1. per character, identical inputs (the ordinary path decides)
        cache = core.new_cache(capacity)
        s, cache = core.advance(q, cache=cache, key_mask=mask[:, :longest])
        dec = network.Decoder(core, B, capacity, mask, use_graph=(modus == "graaf"))
        s2 = dec.prefill(q, mask[:, :longest])
        f = s[:, -1].argmax(-1); done = torch.zeros(B, dtype=torch.bool, device=dev)
        for step in range(at_most - 1):
            f = torch.where(done, torch.full_like(f, tokens.PAD), f); done = done | (f == tokens.END)
            if bool(done.all()): break
            s, cache = core.advance(f[:, None], cache=cache, offset=longest + step, key_mask=mask[:, :longest + step + 1])
            a = s[:, -1]; b = dec.step(f)
            live = ~done
            flips += int((a.argmax(-1) != b.argmax(-1))[live].sum()); totaal += int(live.sum())
            maxd = max(maxd, float((a.float() - b.float()).abs()[live].max()))
            f = a.argmax(-1)
        del cache, dec
        # 2. end to end: each path on its own, through the Learner
        os.environ["AMBER_GRAAF"] = "0"; oud = learner.answer(tasks_, at_most=at_most)
        os.environ["AMBER_GRAAF"] = ("1" if modus == "graaf" else "snij")
        nieuw = learner.answer(tasks_, at_most=at_most)
    gelijk = sum(1 for x, y in zip(oud, nieuw) if x == y); eind_gelijk += gelijk; eind_n += B
    so = sum(t.check(x) for t, x in zip(tasks_, oud)); sn = sum(t.check(x) for t, x in zip(tasks_, nieuw)); score_oud += so; score_nieuw += sn
    print(f"  {family:9s}/{depth:<2d} antwoorden gelijk {gelijk}/{B}, goed oud {so} nieuw {sn}")
print(f"per teken (gelijke invoer): {flips} andere keuzes op {totaal} tekens = {100*flips/max(1,totaal):.3f}%, max logit-verschil {maxd:.3f}")
print(f"einde: {eind_gelijk}/{eind_n} antwoorden woordelijk gelijk; goed oud {score_oud}, nieuw {score_nieuw}")
assert flips == 0 and eind_gelijk == eind_n, "de Decoder kiest andere tekens dan de gewone weg"
print("passed: 1    failed: 0")
print("alles goed")
