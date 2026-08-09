"""
Fase 0 — toetst de softwareaannames uit CLAUDE.md op deze machine.

Niet "draait torch", maar: klopt elke aanname waar de rest van het project op
rust? Elke toets meldt zelf of hij geslaagd is, en aan het eind staat er een
telling. Wat hier omvalt, valt liever nu om dan in fase 1.

Draaien:  venv/bin/python fase0/controleer-torch.py
"""

# Dit moet vóór de import van torch, anders pakt cuBLAS het niet op. Zonder deze
# instelling weigert torch determinisme aan te zetten voor matmul op de GPU.
import os
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import sys
import torch

geslaagd = 0
gefaald = 0


def toets(naam, verwacht, gevonden, goed):
    global geslaagd, gefaald
    if goed:
        geslaagd += 1
        merk = "  OK  "
    else:
        gefaald += 1
        merk = " FOUT "
    print(f"[{merk}] {naam}")
    print(f"         verwacht: {verwacht}")
    print(f"         gevonden: {gevonden}")


print("=" * 70)
print("Fase 0 — controle van de softwareaannames")
print("=" * 70)
print()

# --- 1. De versies ---------------------------------------------------------

print("--- Versies ---")
toets(
    "torch is 2.4.1 (de in CLAUDE.md genoteerde versie)",
    "2.4.1",
    torch.__version__,
    torch.__version__.startswith("2.4.1"),
)
toets(
    "torch is tegen CUDA 12.1 gebouwd",
    "12.1",
    torch.version.cuda,
    torch.version.cuda == "12.1",
)
toets(
    "Python valt binnen wat torch 2.4.1 ondersteunt (3.8 t/m 3.12)",
    "3.8 t/m 3.12",
    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    (3, 8) <= (sys.version_info.major, sys.version_info.minor) <= (3, 12),
)
print()

# --- 2. De kaarten ---------------------------------------------------------

print("--- De kaarten ---")
beschikbaar = torch.cuda.is_available()
toets("CUDA is bruikbaar", "True", beschikbaar, beschikbaar)

if not beschikbaar:
    print("\nZonder CUDA heeft de rest geen zin. Gestopt.")
    sys.exit(1)

aantal = torch.cuda.device_count()
toets("beide P100's worden gezien", "2", aantal, aantal == 2)

for i in range(aantal):
    naam = torch.cuda.get_device_name(i)
    grote, kleine = torch.cuda.get_device_capability(i)
    vram = torch.cuda.get_device_properties(i).total_memory / 1024**3
    toets(
        f"kaart {i}: Pascal, compute capability 6.0",
        "6.0, Tesla P100, ~16 GB",
        f"{grote}.{kleine}, {naam}, {vram:.1f} GB",
        (grote, kleine) == (6, 0) and "P100" in naam,
    )
print()

# --- 3. Rekenen klopt ------------------------------------------------------

print("--- Rekenen ---")
for i in range(aantal):
    apparaat = torch.device(f"cuda:{i}")
    a = torch.randn(512, 512, device=apparaat, dtype=torch.float32)
    b = torch.randn(512, 512, device=apparaat, dtype=torch.float32)
    op_gpu = (a @ b).cpu()
    op_cpu = a.cpu() @ b.cpu()
    afwijking = (op_gpu - op_cpu).abs().max().item()
    toets(
        f"kaart {i}: matmul fp32 komt overeen met de CPU",
        "afwijking < 1e-3",
        f"{afwijking:.2e}",
        afwijking < 1e-3,
    )
print()

# --- 4. De getalsoorten ----------------------------------------------------
# CLAUDE.md: goede fp16, géén bf16. Dat is geen detail — als bf16 stilzwijgend
# zou werken zou je het gaan gebruiken en pas veel later merken hoe traag het is.

print("--- Getalsoorten ---")
try:
    x = torch.randn(256, 256, device="cuda:0", dtype=torch.float16)
    (x @ x).sum().item()
    fp16 = "werkt"
    fp16_ok = True
except Exception as e:
    fp16 = f"mislukt: {type(e).__name__}"
    fp16_ok = False
toets("fp16 rekent op de GPU", "werkt", fp16, fp16_ok)

bf16_ondersteund = torch.cuda.is_bf16_supported()
toets(
    "bf16 wordt NIET ondersteund (Pascal heeft het niet)",
    "False",
    bf16_ondersteund,
    bf16_ondersteund is False,
)
print()

# --- 5. Determinisme -------------------------------------------------------
# Het meetpunt van fase 1 is: honderd stappen, afsluiten, herstarten, bit voor
# bit hetzelfde. Hier toetsen we alleen of het aan te zetten is en of de
# bewerkingen die we gaan gebruiken het overleven.

print("--- Determinisme ---")
toets(
    "CUBLAS_WORKSPACE_CONFIG staat gezet (nodig vóór de import van torch)",
    ":4096:8",
    os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
    os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":4096:8",
)

try:
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    aanzetten = "gelukt"
    aan_ok = True
except Exception as e:
    aanzetten = f"mislukt: {e}"
    aan_ok = False
toets("determinisme laat zich aanzetten", "gelukt", aanzetten, aan_ok)

# Twee keer exact dezelfde berekening vanaf hetzelfde zaad. Bit voor bit gelijk,
# niet "ongeveer" — dat is de eis.
def zelfde_berekening():
    torch.manual_seed(1234)
    torch.cuda.manual_seed_all(1234)
    laag = torch.nn.Conv2d(3, 8, 3, padding=1).cuda()
    invoer = torch.randn(4, 3, 32, 32, device="cuda")
    uit = laag(invoer).relu().sum()
    uit.backward()
    return uit.detach().clone(), laag.weight.grad.detach().clone()

try:
    uit1, grad1 = zelfde_berekening()
    uit2, grad2 = zelfde_berekening()
    identiek = torch.equal(uit1, uit2) and torch.equal(grad1, grad2)
    uitkomst = "bit voor bit gelijk" if identiek else "verschillend tussen twee runs"
except Exception as e:
    identiek = False
    uitkomst = f"mislukt: {type(e).__name__}: {e}"
toets(
    "conv voorwaarts én achterwaarts is herhaalbaar",
    "bit voor bit gelijk",
    uitkomst,
    identiek,
)

# scatter_add is het klassieke geval dat onder determinisme omvalt. Als dit
# hier al struikelt, weet je dat vóór het in de leerkern zit.
try:
    doel = torch.zeros(100, device="cuda")
    wijzers = torch.randint(0, 100, (1000,), device="cuda")
    waarden = torch.randn(1000, device="cuda")
    doel.scatter_add_(0, wijzers, waarden)
    scatter = "werkt onder determinisme"
    scatter_ok = True
except Exception as e:
    scatter = f"geweigerd: {type(e).__name__}"
    scatter_ok = False
toets(
    "scatter_add overleeft determinisme (anders: vermijden in de leerkern)",
    "werkt",
    scatter,
    scatter_ok,
)
print()

# --- 6. Samenwerken de kaarten? -------------------------------------------

print("--- De twee kaarten samen ---")
if aantal >= 2:
    p2p = torch.cuda.can_device_access_peer(0, 1)
    print(f"[ INFO ] rechtstreeks geheugen tussen kaart 0 en 1: {p2p}")
    print("         (False is normaal voor P100 in PCIe-uitvoering, geen NVLink)")
    t = torch.randn(1024, 1024, device="cuda:0")
    t2 = t.to("cuda:1")
    terug = t2.to("cuda:0")
    gelijk = torch.equal(t, terug)
    toets("tensor heen en weer tussen beide kaarten", "identiek", gelijk, gelijk)
print()

# --- Slot -----------------------------------------------------------------

print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
