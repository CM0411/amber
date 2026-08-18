"""Verhuis-draaiboek (18 aug 2026, Cley): een lopende run van de ene machine
naar de andere brengen — Z490 ↔ DL380 — zonder een stap te verliezen.

  python3 verhuis.py --naar DL380            # droog: laat elke stap zien
  python3 verhuis.py --naar DL380 --echt     # voert uit t/m de herhaalproef
  python3 verhuis.py --naar DL380 --echt --start   # … en start de trainer daar

Draai dit op de machine waar de run NU draait (de bron). Cleys regels: de
trainer stopt en start alleen op zijn woord — daarom doet --echt alles
behálve starten, en start --start pas na een gelijke herhaalproef.

De kijkkant (venster 8000/8001, kijker, rapport, tijdlijn, zelfrapport,
melder) blijft altijd op de Z490 (altijd aan): woont de trainer elders,
dan schrijft dit /home/arch/amber-machine.json op de Z490 en zet het de
spiegel-timer aan (rsync van leven.log/logboek/opname/run.json elke
minuut); de melder herstart de dienst dan via ssh. Terug naar de Z490:
spiegel uit, machine.json op "local".

Stappen:
  0  controles: bron = hier, doel bereikbaar, run.json klopt
  1  wachten tot de momentopname bij is (proefwerkregel = opname), dan
     melder + wachter uit en amber-train hier stoppen (--echt)
  2  opname, logboek, brievenbus, run.json (machine = doel) naar het doel
  3  herhaalproef op het doel (twee losse processen, 50 stappen; op de
     DL380 met torchrun = DDP): gelijk of niet — eerlijk gemeld
  4  amber-machine.json + spiegel op de Z490 zetten (of terug op local)
  5  (--start) amber-train op het doel starten; melder + wachter aan
"""
import argparse
import json
import os
import subprocess
import sys
import time

MACHINES = {
    "Z490": {"host": "arch@192.168.1.239", "kaarten": 1, "torchrun": False},
    "DL380": {"host": "arch@192.168.1.51", "kaarten": 2, "torchrun": True},
}
LEVEN = "/home/arch/amber-werk/fase1/leven"
BRIEVENBUS = "/home/arch/amber-werk/fase1/brievenbus.jsonl"
RUNJSON = "/home/arch/rapport/run.json"
Z490 = MACHINES["Z490"]["host"]

p = argparse.ArgumentParser()
p.add_argument("--naar", required=True, choices=MACHINES)
p.add_argument("--echt", action="store_true")
p.add_argument("--start", action="store_true")
p.add_argument("--stappen", type=int, default=50)
a = p.parse_args()
DOEL = a.naar
BRON = "DL380" if DOEL == "Z490" else "Z490"
doel = MACHINES[DOEL]


def zeg(s):
    print(s, flush=True)


def hier(cmd, check=True):
    zeg("  $ " + " ".join(cmd))
    if not a.echt:
        return ""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"mislukt: {r.stderr.strip()[:300]}")
    return r.stdout


def daar(host, cmd, check=True):
    return hier(["ssh", "-o", "BatchMode=yes", host, cmd], check)


zeg(f"=== verhuizing {BRON} → {DOEL} ({'ECHT' if a.echt else 'droog'}) ===")
zeg("--- 0. controles")
run = json.load(open(RUNJSON))
if run.get("machine") != BRON:
    sys.exit(f"run.json zegt machine {run.get('machine')!r}, niet {BRON} — draai dit op de bron")
r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", doel["host"], "echo ok"], capture_output=True, text=True)
zeg(f"  doel {doel['host']}: {'bereikbaar' if r.stdout.strip() == 'ok' else 'NIET bereikbaar'}")
if r.stdout.strip() != "ok":
    sys.exit("doel niet bereikbaar — staat hij aan? (Cleys woord)")
zeg(f"  run {run.get('naam')} doel {run.get('doel')} · opname {LEVEN}/momentopname.pt")

zeg("--- 1. stoppen (na de eerstvolgende opname)")
zeg("  wacht tot de proefwerkregel 'stap N |' in leven.log en de opname dezelfde N dragen")
hier(["sudo", "-n", "systemctl", "stop", "amber-melder"], check=False)
daar(MACHINES["DL380"]["host"], "echo arch | sudo -S -k -p '' systemctl stop amber-wachter", check=False)
hier(["sudo", "-n", "systemctl", "stop", "amber-train"])

zeg("--- 2. sporen over")
run_daar = dict(run); run_daar["machine"] = DOEL
if a.echt:
    with open("/tmp/run-verhuis.json", "w") as f:
        json.dump(run_daar, f)
daar(doel["host"], f"mkdir -p {LEVEN} /home/arch/rapport")
hier(["scp", "-q", f"{LEVEN}/momentopname.pt", f"{LEVEN}/logboek.jsonl", f"{doel['host']}:{LEVEN}/"])
hier(["scp", "-q", BRIEVENBUS, f"{doel['host']}:{BRIEVENBUS}"], check=False)
hier(["scp", "-q", "/tmp/run-verhuis.json", f"{doel['host']}:{RUNJSON}"])
zeg("  (de kern op het doel moet dezelfde zijn als hier: rungrens/git — controleer kern/world.py-hash)")
zeg("  " + (daar(doel["host"], "sha256sum amber-werk/kern/world.py | cut -c1-16") or "").strip()
    + " (doel)  vs  " + (hier(["sha256sum", "/home/arch/amber-werk/kern/world.py"]) or "")[:16] + " (bron)")

zeg("--- 3. herhaalproef op het doel")
if doel["torchrun"]:
    cmd = (f"cd amber-werk && AMBER_CHECKPOINTING=1 venv/bin/torchrun --standalone --nproc_per_node={doel['kaarten']} "
           f"fase1/herhaalproef.py {LEVEN}/momentopname.pt {a.stappen} 2>&1 | grep controlesom")
else:
    cmd = f"cd amber-werk && AMBER_CHECKPOINTING=1 python3 fase1/herhaalproef.py {LEVEN}/momentopname.pt {a.stappen} 2>&1 | grep controlesom"
s1 = daar(doel["host"], cmd); s2 = daar(doel["host"], cmd)
if a.echt:
    zeg(f"  1: {s1.strip()}\n  2: {s2.strip()}")
    zeg("  BIT VOOR BIT GELIJK" if s1.strip() and s1.strip() == s2.strip() else "  NIET GELIJK — niet starten, melden")

zeg("--- 4. kijkkant op de Z490 richten")
mj = {"trainer": "local" if DOEL == "Z490" else doel["host"]}
zeg(f"  /home/arch/amber-machine.json op de Z490 := {mj}")
daar(Z490, f"echo '{json.dumps(mj)}' > /home/arch/amber-machine.json")
if DOEL == "Z490":
    daar(Z490, "sudo -n systemctl disable --now amber-spiegel.timer", check=False)
else:
    daar(Z490, "sudo -n systemctl enable --now amber-spiegel.timer", check=False)
    daar(Z490, f"echo '{json.dumps(run_daar)}' > {RUNJSON}")
zeg("  melder herlezen (leest amber-machine.json bij elke ronde): systemctl restart amber-melder")

zeg("--- 5. starten (alleen met --start, op Cleys woord)")
if a.start:
    daar(doel["host"], "echo arch | sudo -S -k -p '' systemctl start amber-train")
    daar(Z490, "sudo -n systemctl start amber-melder", check=False)
    daar(MACHINES["DL380"]["host"], "echo arch | sudo -S -k -p '' systemctl start amber-wachter", check=False)
    zeg("  gestart; volg leven.log op het doel (HERVAT bij …)")
else:
    zeg(f"  ssh {doel['host']} sudo systemctl start amber-train   ← pas na Cleys woord")
zeg("=== klaar ===")
