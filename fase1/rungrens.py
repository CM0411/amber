"""Het rungrens-draaiboek — alles wat er op een rungrens moet gebeuren.

Draaien op de DL380 zodra een run af is (dienst inactive op de trainer):

  venv/bin/python fase1/rungrens.py --doel 470000
  venv/bin/python fase1/rungrens.py --doel 470000 --venster 1536 \
      --hek rekenen=38 --hek code=20 --hek puzzel=12 --lagen 9 --checkpointing

Sinds 15 aug 2026 algemeen: niets van een bepaald runnummer staat er
meer hard in. Het runnummer komt uit `run.json` op de trainer (de run die
zojuist afliep) plus één; `--run` overschrijft dat, en het draaiboek stopt
als de twee niet kloppen. Zonder `--venster` blijft het venster wat het
is; zonder `--hek` blijven de hekken van world.py staan; zonder `--lagen`
komt er geen laag bij (`Learner.grow_layer`, 15 aug 2026: optimizer en
antwoordkopie gaan mee). Alleen wat
verandert wordt gedaan — een rungrens zonder groei is dus ook geldig.

Het argument `--doel` is het absolute doel van de nieuwe run (Cleys
besluit). Het draaiboek stopt vóór het starten: een run begint alleen op
Cleys woord.

Volgorde: eindstand veiligstellen → nameting → brievenbus bezorgen →
hekken verzetten + toetsen → kern, life.py, gereedschap en proefwerken
deployen → startcheckpoint (venster gegroeid als gevraagd) bouwen en
plaatsen → tempoproef → herhaalbaarheidsbewijs → run.json en wrapper →
klaar voor "start run N".

Weg sinds 15 aug: de compile-proef (torch.compile is afgewezen; run 5
draaide zonder). De groeistap gaat altijd via `grow_window` en wordt
teruggecontroleerd op bit-voor-bit gelijke uitvoer.
"""
import argparse
import json
import re
import subprocess
import sys

DL = "/home/arch/amber-werk"
TRAINER = "arch@192.168.1.239"
VENV = f"{DL}/venv/bin/python"
WORLD = f"{DL}/kern/world.py"


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


def hekken_nu():
    """Lees MAX_DEPTH en MAX_DEPTH_PER uit world.py zoals ze er staan."""
    tekst = open(WORLD).read()
    m = re.search(r"^MAX_DEPTH = (\d+)$", tekst, re.M)
    per = re.search(r"^MAX_DEPTH_PER = (\{.*\})$", tekst, re.M)
    if not m or not per:
        sys.exit("MAX_DEPTH of MAX_DEPTH_PER niet gevonden in world.py")
    d = {"rekenen": int(m.group(1))}
    d.update(json.loads(per.group(1)))
    return d


def hekken_zet(hek):
    """Schrijf de hekken in world.py en lees terug wat er werkelijk staat —
    sed zwijgt bij een gemiste regel, dezelfde valstrik als nvidia-smi."""
    tekst = open(WORLD).read()
    per = {k: v for k, v in hek.items() if k != "rekenen"}
    per_tekst = "{" + ", ".join(f'"{k}": {v}' for k, v in per.items()) + "}"
    tekst, n1 = re.subn(r"^MAX_DEPTH = \d+$", f"MAX_DEPTH = {hek['rekenen']}",
                        tekst, flags=re.M)
    tekst, n2 = re.subn(r"^MAX_DEPTH_PER = \{.*\}$",
                        f"MAX_DEPTH_PER = {per_tekst}", tekst, flags=re.M)
    if n1 != 1 or n2 != 1:
        sys.exit("hekregels niet (eenduidig) gevonden in world.py — stop")
    open(WORLD, "w").write(tekst)
    if hekken_nu() != hek:
        sys.exit("hekverzetting niet teruggevonden in world.py — stop")


def hek_tekst(hek):
    return ", ".join(f"{k} {v}" for k, v in hek.items())


p = argparse.ArgumentParser()
p.add_argument("--doel", type=int, required=True,
               help="absoluut stapdoel van de nieuwe run, bv. 470000")
p.add_argument("--run", type=int, default=None,
               help="nummer van de nieuwe run (standaard: vorige + 1)")
p.add_argument("--venster", type=int, default=None,
               help="nieuw venster; weglaten = niet groeien")
p.add_argument("--hek", action="append", default=[],
               help="familie=diepte, herhaalbaar; weglaten = laten staan")
p.add_argument("--lagen", type=int, default=None,
               help="aantal lagen na de groei; weglaten = niet groeien")
p.add_argument("--zonder-herhaalproef", action="store_true",
               help="sla het herhaalbaarheidsbewijs op de trainer over")
p.add_argument("--checkpointing", action="store_true",
               help="activatie-checkpointing aan in de dienst op de trainer "
                    "(AMBER_CHECKPOINTING=1); blijft aan tot iemand het uitzet")
a = p.parse_args()

stap(0, "is de run echt af?")
# `is-active` geeft afsluitcode 3 bij "inactive" — dat is hier juist het
# goede antwoord. Alleen een lege uitkomst betekent onbereikbaar.
ok, dienst = ssh("systemctl is-active amber-train || true", 30)
if not dienst:
    sys.exit("trainer onbereikbaar")
if dienst == "active":
    sys.exit("de dienst draait nog — dit draaiboek hoort bij een rungrens")
ok, staart = ssh("tail -2 ~/leven.log", 30)
print(staart)

ok, rj = ssh("cat ~/rapport/run.json", 30)
if not ok:
    sys.exit("run.json niet leesbaar op de trainer")
vorige = json.loads(rj)
m = re.fullmatch(r"run(\d+)", vorige.get("naam", ""))
if not m:
    sys.exit(f"run.json noemt geen runN: {vorige}")
VORIG = int(m.group(1))
RUN = a.run if a.run is not None else VORIG + 1
if RUN != VORIG + 1:
    sys.exit(f"run.json zegt run{VORIG} is net afgelopen; --run {RUN} klopt "
             f"daar niet mee — stop")
if a.doel <= vorige.get("doel", 0):
    sys.exit(f"doel {a.doel} ligt niet voorbij het vorige doel "
             f"{vorige.get('doel')} — stop")
print(f"run{VORIG} afgelopen (doel {vorige.get('doel')}, venster "
      f"{vorige.get('venster')}, hek {vorige.get('hek')})")
print(f"nieuw: run{RUN}, doel {a.doel}")

# hekken: alleen wat gevraagd is verandert, de rest blijft staan
HEK_OUD = hekken_nu()
HEK = dict(HEK_OUD)
for h in a.hek:
    fam, _, diepte = h.partition("=")
    if fam not in HEK or not diepte.isdigit():
        sys.exit(f"--hek {h}: onbekende familie of geen getal "
                 f"(bekend: {', '.join(HEK)})")
    HEK[fam] = int(diepte)
for fam in HEK:
    if HEK[fam] < HEK_OUD[fam]:
        sys.exit(f"hek {fam} zou van {HEK_OUD[fam]} naar {HEK[fam]} — "
                 f"de wereld mag groeien, niet krimpen")

EIND = f"{DL}/fase1/run{VORIG}-eind.pt"
START = f"{DL}/fase1/run{RUN}-start.pt"

stap(1, "eindstand veiligstellen")
if not scp(f"{TRAINER}:amber-werk/fase1/leven/momentopname.pt", EIND):
    sys.exit("ophalen mislukt")
# Kopieën naar de array en de NAS, en teruglezen: een halve kopie valt
# anders pas op de dag dat je hem nodig hebt (15 aug 2026). De NAS is
# optioneel — staat hij uit of in onderhoud, dan melden en doorgaan.
import hashlib as _hl
def _md5(pad):
    h = _hl.md5()
    with open(pad, "rb") as f:
        for blok in iter(lambda: f.read(1 << 24), b""):
            h.update(blok)
    return h.hexdigest()
bron_md5 = _md5(EIND)
print(f"eindstand {bron_md5[:8]}")
naam = EIND.rsplit("/", 1)[-1]
hier(f"cp {EIND} /mnt/opslag/checkpoints/{naam}")
if _md5(f"/mnt/opslag/checkpoints/{naam}") == bron_md5:
    print("  array-kopie teruggelezen: gelijk")
else:
    sys.exit("  array-kopie ONGELIJK aan de eindstand — stop")
if hier(f"timeout 120 cp {EIND} /mnt/truenas/amber/{naam} 2>/dev/null"):
    # teruglezen ook met tijdslimiet: een halve NAS hangt (df hing op
    # 15 aug 2026 twee minuten op de automount)
    r = subprocess.run(["timeout", "120", "md5sum",
                        f"/mnt/truenas/amber/{naam}"],
                       capture_output=True, text=True)
    gelijk = r.returncode == 0 and r.stdout.startswith(bron_md5)
    print("  NAS-kopie teruggelezen: " + ("gelijk" if gelijk else
                                          "ONGELIJK of onleesbaar — niet vertrouwen"))
else:
    print("  NAS niet bereikbaar (uit of in onderhoud) — overgeslagen; de "
          "array-kopie is er")

stap(2, f"nameting per vakje (het eindrapport van run {VORIG})")
hier(f"cd {DL} && {VENV} fase1/nameting.py {EIND} "
     f"| tee fase1/nameting-run{VORIG}.txt")

stap(3, "de brievenbus bezorgen")
# sinds 14 aug 2026 wonen brievenbus én logboek op de Z490 — de bezorging
# draait daar, zonder ssh in het script zelf
ok, uit = ssh("python3 ~/amber-werk/fase1/bezorg-brievenbus.py || true")
print(uit)

stap(4, "hekken en de toetsen")
if HEK != HEK_OUD:
    hekken_zet(HEK)
    print(f"hekken {hek_tekst(HEK_OUD)} → {hek_tekst(HEK)}")
else:
    print(f"hekken blijven {hek_tekst(HEK)}")
# de toetsen draaien ook als de hekken niet verschuiven: de kern reist zo
# mee, en code die alleen op een rungrens reist, draait pas op de
# vólgende rungrens voor het eerst (14 aug 2026)
# de hele kern, niet alleen world en tasks (15 aug 2026: 11 toetsen, ~1 min)
if not hier(f"{DL}/kern/toets-alles.sh"):
    sys.exit("er is een toets rood — stop")
print("toetsen groen")

stap(5, "kern, life.py, gereedschap en proefwerken naar de trainer")
hier(f"cd {DL}/kern && for f in *.py; do sshpass -p {_geheim()} scp -q $f "
     f"{TRAINER}:amber-werk/kern/; done")
scp(f"{DL}/fase1/life.py", f"{TRAINER}:amber-werk/fase1/life.py")
# de meet- en dienstgereedschappen van de trainer reizen mee — de
# moederkopie woont hier, de Z490 draait alleen (14 aug 2026)
for f in ("nameting.py", "foutanalyse.py", "bezorg-brievenbus.py",
          "cijfers-bij-finish.py", "groei-advies.py", "herhaalproef.py"):
    scp(f"{DL}/fase1/{f}", f"{TRAINER}:amber-werk/fase1/{f}")
# het rapport en de toetsknop reizen ook mee (15 aug 2026)
scp(f"{DL}/rapport/maak-rapport.py", f"{TRAINER}:amber-werk/rapport/maak-rapport.py")
# de eindverslag-scripts reizen ook mee (16 aug 2026): het eindverslag
# wordt na de finish op de Z490 gemaakt en de moederkopie woont hier
for f in ("maak-eindverslag.py", "verhaal_run.py"):
    scp(f"{DL}/rapport/{f}", f"{TRAINER}:amber-werk/rapport/{f}")
scp(f"{DL}/brein/index.html", f"{TRAINER}:amber-werk/brein/index.html")
scp(f"{DL}/kern/toets-alles.sh", f"{TRAINER}:amber-werk/kern/toets-alles.sh")
# De proefwerken gaan alléén op een rungrens mee: take() draait elk
# json-bestand dat hij ziet, dus een nieuw proefwerk mid-run plaatsen
# zou de meting van een lopende run stil veranderen (gesprek, 13 aug).
hier(f"cd {DL}/proefwerken && for f in *.json; do sshpass -p {_geheim()} "
     f"scp -q $f {TRAINER}:amber-werk/proefwerken/; done")
ok, uit = ssh("ls ~/amber-werk/proefwerken/ | tr '\\n' ' '", 30)
print("proefwerken op de trainer:", uit)
# De kijker woont sinds 16 aug 2026 op de trainer zelf (Z490, CPU) en
# importeert dáár de kern: hij leidt zijn keuzelijst af uit world.max_depth
# en laadt de wereld alleen bij zijn start. Na het deployen dus herstarten
# — vóór de deploy zou hij de oude wereld inladen (14 aug 2026: het venster
# toonde tot de volgende dag de oude hekken).
scp(f"{DL}/brein/kijker.py", f"{TRAINER}:amber-werk/brein/kijker.py")
ok, uit = ssh(f"echo {_geheim()} | sudo -S systemctl restart amber-kijker "
              f"2>/dev/null; systemctl is-active amber-kijker", 60)
print("kijker op de trainer herstart:", uit.strip().splitlines()[-1] if uit else "?")

stap(6, "startcheckpoint bouwen en plaatsen")
# Via de Learner en niet via het kale netwerk (15 aug 2026): een laag erbij
# moet de optimizer meenemen (grow_layer plant de oude momenten over), en
# adopt_shape neemt eerst de vorm van de eindstand aan — anders weigert
# een gegroeide eindstand al bij het laden.
groei = f"""
import sys; sys.path.insert(0, "{DL}/kern")
import determinism; determinism.lock(515151)
import torch, bridge, learning, snapshot
inhoud = snapshot.read("{EIND}", device="cuda:1")
extra = dict(inhoud.get("extra") or {{}})
L = learning.Learner(device="cuda:1", bf16=False)
L.adopt_shape(extra.get("vorm"))
stapnr = snapshot.restore(inhoud, L.core, L.optimizer, "cuda:1")
core = L.core
core.eval(); determinism.begin_step(1)
oud_venster, oud_lagen = core.window, len(core.blocks)
nieuw_venster = {a.venster if a.venster else 'oud_venster'}
nieuw_lagen = {a.lagen if a.lagen else 'oud_lagen'}
if nieuw_venster < oud_venster:
    raise SystemExit(f"venster {{nieuw_venster}} < {{oud_venster}} — krimpen kan niet")
if nieuw_lagen < oud_lagen:
    raise SystemExit(f"lagen {{nieuw_lagen}} < {{oud_lagen}} — krimpen kan niet")
proef = torch.randint(0, 260, (2, oud_venster), device="cuda:1")
with torch.no_grad(): voor = core.advance(proef)[0].clone()
if nieuw_venster > oud_venster:
    L.adopt_window(nieuw_venster)
while len(core.blocks) < nieuw_lagen:
    L.grow_layer()
core.eval()
with torch.no_grad(): na = core.advance(proef)[0]
assert torch.equal(voor, na), "groei veranderde de uitvoer!"
print(f"venster {{oud_venster}} → {{core.window}}, lagen {{oud_lagen}} → "
      f"{{len(core.blocks)}}, uitvoer bit voor bit gelijk")
extra["vorm"] = core.spec()
snapshot.write("{START}", stapnr, core, L.optimizer,
               inhoud.get("determinisme"), extra=extra)
print("run{RUN}-start.pt:", stapnr, "vorm", core.spec())
import json as _j; _j.dump(core.spec(), open("/tmp/groei-uitkomst.json", "w"))
"""
open("/tmp/groei.py", "w").write(groei)
if not hier(f"{VENV} /tmp/groei.py"):
    sys.exit("startcheckpoint bouwen mislukt")
if not scp(START, f"{TRAINER}:amber-werk/fase1/leven/momentopname.pt"):
    sys.exit("startcheckpoint niet op de trainer gekomen")
VORM = json.load(open("/tmp/groei-uitkomst.json"))
VENSTER = VORM["window"]
LAGEN = VORM["layers"]

stap("6b", "checkpointing in de dienst op de trainer")
# Een machine-instelling, geen deel van haar: als omgevingsvariabele in
# een drop-in van amber-train, zodat ~/nacht → life.py hem erft. Alleen
# daemon-reload — starten blijft Cleys woord. Zonder de vlag blijft de
# bestaande instelling staan (uit, of wat een vorige rungrens zette).
DROPIN = "/etc/systemd/system/amber-train.service.d/checkpointing.conf"
if a.checkpointing:
    # één sudo-aanroep: bij een tweede `sudo -S` in dezelfde pijp zou het
    # wachtwoord uit de verkeerde stdin komen
    binnen = (f"mkdir -p $(dirname {DROPIN}) && printf "
              f"'[Service]\\nEnvironment=AMBER_CHECKPOINTING=1\\n' > {DROPIN} "
              f"&& systemctl daemon-reload")
    ok, uit = ssh(f"echo {_geheim()} | sudo -S bash -c \"{binnen}\" && "
                  f"systemctl show amber-train -p Environment", 60)
    if "AMBER_CHECKPOINTING=1" not in uit:
        sys.exit(f"checkpointing niet in de dienst gekomen: {uit!r}")
    print("  AMBER_CHECKPOINTING=1 staat in de dienst (teruggelezen)")
ok, uit = ssh("systemctl show amber-train -p Environment", 30)
CHECKPOINTING = "AMBER_CHECKPOINTING=1" in uit
print(f"  checkpointing in de dienst: {'aan' if CHECKPOINTING else 'uit'}")
ENV = ("PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "
       + ("AMBER_CHECKPOINTING=1 " if CHECKPOINTING else ""))

stap(7, "tempo- en geheugenproef op de trainer (past partij 64 nog?)")
# 13 aug 2026: het script stond in een tijdelijke jobmap die opgeruimd
# wordt; nu op een duurzame plek.
scp(f"{DL}/fase1/tempo-proef.py", f"{TRAINER}:/tmp/tempo-proef.py")
ok, uit = ssh(ENV + "python3 -u /tmp/tempo-proef.py 2>&1 | tail -4", 1800)
print(uit)

stap(8, "herhaalbaarheidsbewijs op de trainer (twee processen, 50 stappen)")
# Het meetpunt van fase 1, maar dan op de kaart die echt traint: bf16 op
# een 3070 Ti met een nieuwere torch is nooit op herhaalbaarheid getoetst
# (15 aug 2026). Twee losse processen vanaf het startcheckpoint; de
# controlesommen (gewichten + optimizer) moeten gelijk zijn. Ongelijk =
# luid melden; de run start toch pas op Cleys woord, en dan weet hij dit.
if a.zonder_herhaalproef:
    print("overgeslagen (--zonder-herhaalproef)")
else:
    scp(f"{DL}/fase1/herhaalproef.py", f"{TRAINER}:/tmp/herhaalproef.py")
    sommen = []
    for keer in (1, 2):
        ok, uit = ssh(ENV + "python3 -u /tmp/herhaalproef.py "
                      "~/amber-werk/fase1/leven/momentopname.pt 50 2>&1 "
                      "| tail -2", 1800)
        print(f"  proces {keer}: {uit.splitlines()[-1] if uit else '(niets)'}")
        m = re.search(r"controlesom na \d+ stappen: ([0-9a-f]+)", uit)
        sommen.append(m.group(1) if m else None)
    if sommen[0] and sommen[0] == sommen[1]:
        print("  BIT VOOR BIT GELIJK — herhaalbaar op de trainer")
    else:
        print("  !!! NIET GELIJK OF MISLUKT — de trainer is niet bewezen "
              "herhaalbaar; bespreek dit vóór run start !!!")

stap(9, "run.json en wrapper")
# run.json woont sinds 14 aug 2026 op de Z490: venster en rapport lezen
# hem daar. De kopie hier blijft alleen ter referentie staan.
# `start` (16 aug 2026): het vorige doel — de wachter start een gevallen
# run alleen weer als de teller daar al voorbij is; een run die nog moet
# beginnen is Cleys woord
json.dump({"naam": f"run{RUN}", "doel": a.doel, "start": vorige.get("doel"),
           "hek": hek_tekst(HEK), "venster": VENSTER, "lagen": LAGEN,
           "parameters": VORM.get("parameters"),
           "checkpointing": CHECKPOINTING, "machine": "Z490"},
          open("/home/arch/rapport/run.json", "w"))
if not scp("/home/arch/rapport/run.json", f"{TRAINER}:rapport/run.json"):
    sys.exit(f"run.json niet op de Z490 gekomen — venster zou run{VORIG} "
             f"blijven tonen")
ok, uit = ssh(f"sed -i 's|life.py [0-9]*|life.py {a.doel}|' ~/nacht && "
              f"grep -o 'life.py [0-9]*' ~/nacht", 30)
if uit.strip() != f"life.py {a.doel}":
    sys.exit(f"wrapper ~/nacht niet op {a.doel} gekomen: {uit!r}")

print(f"\nALLES KLAAR — run {RUN} wacht op Cleys woord:")
print(f"  doel {a.doel:,} · venster {VENSTER} · lagen {LAGEN} "
      f"({VORM.get('parameters', 0):,} parameters) · checkpointing "
      f"{'aan' if CHECKPOINTING else 'uit'} · hekken {hek_tekst(HEK)}"
      .replace(",", "."))
print("  starten = ssh trainer: sudo systemctl start amber-train")
