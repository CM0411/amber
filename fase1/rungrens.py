"""Het rungrens-draaiboek — alles wat er op een rungrens moet gebeuren.

Draaien op de DL380 zodra run 4 af is (dienst inactive op de trainer):

  venv/bin/python fase1/rungrens.py 470000

Het argument is het absolute doel van run 5 (Cleys besluit; run 4 stopte
op 320.000 — 470.000 betekent dus 150.000 nieuwe stappen). Het draaiboek
stopt vóór het starten: run 5 begint alleen op Cleys woord.

Volgorde: eindstand veiligstellen → nameting → brievenbus bezorgen →
compile-proef → hekken naar het 1024-tijdperk + toetsen → kern en life.py
deployen → groeicheckpoint (1024) bouwen en plaatsen → run.json en
wrapper → klaar voor "start run 5".
"""
import json
import os
import subprocess
import sys

DL = "/home/arch/amber-werk"
TRAINER = "arch@192.168.1.239"
VENV = f"{DL}/venv/bin/python"


def _geheim():
    return open("/home/arch/.amber-geheim").read().strip()


def ssh(opdracht, tijd=600):
    r = subprocess.run(["sshpass", "-p", _geheim(), "ssh",
                        "-o", "ConnectTimeout=8", TRAINER, opdracht],
                       capture_output=True, text=True, timeout=tijd)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def scp(bron, doel, tijd=600):
    return subprocess.run(["sshpass", "-p", _geheim(), "scp", "-q",
                           bron, doel], timeout=tijd).returncode == 0


def hier(cmd, tijd=1800):
    return subprocess.run(cmd, shell=True, timeout=tijd).returncode == 0


def stap(nr, titel):
    print(f"\n=== {nr}. {titel} " + "=" * max(1, 50 - len(titel)))


if len(sys.argv) < 2:
    sys.exit("gebruik: rungrens.py <absoluut doel van run 5, bv. 470000>")
DOEL5 = int(sys.argv[1])

stap(0, "is de run echt af?")
ok, dienst = ssh("systemctl is-active amber-train", 30)
if not ok:
    sys.exit("trainer onbereikbaar")
if dienst == "active":
    sys.exit("de dienst draait nog — dit draaiboek hoort bij een rungrens")
ok, staart = ssh("tail -2 ~/leven.log", 30)
print(staart)

stap(1, "eindstand veiligstellen")
if not scp(f"{TRAINER}:amber-werk/fase1/leven/momentopname.pt",
           f"{DL}/fase1/run4-eind.pt"):
    sys.exit("ophalen mislukt")
hier(f"cp {DL}/fase1/run4-eind.pt /mnt/opslag/checkpoints/ 2>/dev/null; "
     f"timeout 120 cp {DL}/fase1/run4-eind.pt /mnt/truenas/amber/ "
     f"2>/dev/null || echo 'TrueNAS overslaan (traag)'")
hier(f"md5sum {DL}/fase1/run4-eind.pt | cut -c1-8")

stap(2, "nameting per vakje (het eindrapport van run 4)")
hier(f"cd {DL} && {VENV} fase1/nameting.py fase1/run4-eind.pt "
     f"| tee fase1/nameting-run4.txt")

stap(3, "de brievenbus bezorgen")
hier(f"{VENV} {DL}/fase1/bezorg-brievenbus.py || true")

stap(4, "compile-proef op de trainer (meten, nog niets aanzetten)")
scp(f"{DL}/fase1/compile-proef.py", f"{TRAINER}:/tmp/compile-proef.py")
ok, uit = ssh("cd ~/amber-werk && PYTORCH_CUDA_ALLOC_CONF="
              "expandable_segments:True python3 /tmp/compile-proef.py",
              1800)
print(uit[-600:])

stap(5, "hekken naar het 1024-tijdperk en de toetsen")
# Puzzel staat sinds 13 aug 2026 al op 9 (compacte uitwerking); hier hoeft
# alleen nog rekenen 26 -> 38 en code 11 -> 15.
hier(f"sed -i 's/^MAX_DEPTH = 26/MAX_DEPTH = 38/; "
     f"s/MAX_DEPTH_PER = {{\"puzzel\": 9, \"code\": 11}}/"
     f"MAX_DEPTH_PER = {{\"puzzel\": 9, \"code\": 15}}/' {DL}/kern/world.py")
# Teruglezen wat er werkelijk staat — sed zwijgt bij een gemiste regel,
# dezelfde valstrik als nvidia-smi (8 aug 2026).
if not hier(f"grep -q '^MAX_DEPTH = 38' {DL}/kern/world.py && "
            f"grep -q 'MAX_DEPTH_PER = {{\"puzzel\": 9, \"code\": 15}}' "
            f"{DL}/kern/world.py"):
    sys.exit("hekverzetting niet teruggevonden in world.py — stop")
if not hier(f"cd {DL}/kern && {VENV} test-world.py > /tmp/tw.log 2>&1 "
            f"|| (tail -5 /tmp/tw.log; false)"):
    sys.exit("test-world faalt na de hekverzetting — stop")
print("hekken 38/15/9, toetsen groen")

stap(6, "kern, life.py en proefwerken naar de trainer")
hier(f"cd {DL}/kern && for f in *.py; do sshpass -p {_geheim()} scp -q $f "
     f"{TRAINER}:amber-werk/kern/; done")
scp(f"{DL}/fase1/life.py", f"{TRAINER}:amber-werk/fase1/life.py")
# De proefwerken gaan alléén op een rungrens mee: take() draait elk
# json-bestand dat hij ziet, dus een nieuw proefwerk mid-run plaatsen
# zou de meting van een lopende run stil veranderen (gesprek, 13 aug).
hier(f"cd {DL}/proefwerken && for f in *.json; do sshpass -p {_geheim()} "
     f"scp -q $f {TRAINER}:amber-werk/proefwerken/; done")

stap(7, "groeicheckpoint naar venster 1024 bouwen en plaatsen")
groei = f"""
import sys; sys.path.insert(0, "{DL}/kern")
import determinism; determinism.lock(515151)
import torch, bridge, network, snapshot
inhoud = snapshot.read("{DL}/fase1/run4-eind.pt", device="cuda:1")
vorm = (inhoud.get("extra") or {{}}).get("vorm")
core = network.Core.from_spec(bridge.translate_spec(vorm)).to("cuda:1")
opt = torch.optim.AdamW(core.parameters(), lr=3e-4)
stapnr = snapshot.restore(inhoud, core, opt, "cuda:1")
core.eval(); determinism.begin_step(1)
proef = torch.randint(0, 260, (2, core.window), device="cuda:1")
with torch.no_grad(): voor = core.advance(proef)[0].clone()
core.grow_window(1024)
with torch.no_grad(): na = core.advance(proef)[0]
assert torch.equal(voor, na), "groei veranderde de uitvoer!"
extra = dict(inhoud.get("extra") or {{}}); extra["vorm"] = core.spec()
snapshot.write("{DL}/fase1/run5-start.pt", stapnr, core, opt,
               inhoud.get("determinisme"), extra=extra)
print("run5-start.pt:", stapnr, "venster", core.spec()["window"])
"""
open("/tmp/groei5.py", "w").write(groei)
if not hier(f"{VENV} /tmp/groei5.py"):
    sys.exit("groei naar 1024 mislukt")
scp(f"{DL}/fase1/run5-start.pt",
    f"{TRAINER}:amber-werk/fase1/leven/momentopname.pt")

stap(8, "tempo- en geheugenproef op 1024 (past partij 64 nog?)")
# 13 aug 2026: het script stond in een tijdelijke jobmap die opgeruimd
# wordt; nu op een duurzame plek.
scp(f"{DL}/fase1/tempo-proef.py", f"{TRAINER}:/tmp/tempo-1024.py")
ok, uit = ssh("PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "
              "python3 -u /tmp/tempo-1024.py 2>&1 | tail -4", 1800)
print(uit)

stap(9, "run.json en wrapper")
json.dump({"naam": "run5", "doel": DOEL5,
           "hek": "rekenen 38, code 15, puzzel 9",
           "venster": 1024, "machine": "Z490"},
          open("/home/arch/rapport/run.json", "w"))
ssh(f"sed -i 's|life.py [0-9]*|life.py {DOEL5}|' ~/nacht && "
    f"grep -o 'life.py [0-9]*' ~/nacht", 30)

print("\nALLES KLAAR — run 5 wacht op Cleys woord:")
print(f"  doel {DOEL5:,} · venster 1024 · hekken rekenen 38, code 15, "
      f"puzzel 9".replace(",", "."))
print("  starten = ssh trainer: sudo systemctl start amber-train")
