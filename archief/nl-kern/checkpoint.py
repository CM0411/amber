"""
Checkpoints — toestand die een herstart én een verhuizing overleeft.

Twee eisen uit de roadmap komen hier samen:

"Toestand hardware-onafhankelijk opslaan. Geen kaartspecifieke geheugenindeling
in bestanden. Anders is elke GPU-upgrade een nieuwe start in plaats van een
verhuizing."

"Alles is onderbreekbaar. De server gaat 's nachts soms uit vanwege warmte, en
Cley kan op elk moment een slaapstand afroepen."

En er is op 8 aug 2026 een derde bijgekomen, uit de hardware zelf: de controller
is een H240ar zonder cachemodule en zonder batterij. Er is dus niets dat opvangt
wat er onderweg was toen de stroom wegviel, en de bootschijf is bovendien een
consumenten-SSD zonder power-loss protection. Schrijfveiligheid moet daarom hier
vandaan komen en niet uit de hardware.

Hoe dat hier is opgelost:

  * schrijven naar een tijdelijk bestand, fsync, dan pas atomair hernoemen.
    Een onderbreking laat het oude checkpoint dus ongemoeid — je verliest
    hooguit de laatste, nooit de vorige
  * ook de map wordt gefsynct, anders kan de hernoeming zelf nog verdampen
  * een controlegetal over de inhoud, zodat stille beschadiging opvalt bij het
    lezen in plaats van veel later in de metingen

En hardware-onafhankelijk:

  * alle tensors gaan naar de CPU voordat ze worden weggeschreven
  * er gaat geen generatortoestand in; alleen (zaad, stapnummer), waaruit alles
    opnieuw af te leiden is — zie determinisme.py
  * wat er over de machine in staat is uitsluitend ter informatie. Niets ervan
    is nodig om het bestand te kunnen laden
"""

import hashlib
import io
import os

import torch

VERSIE = 1


def _naar_cpu(x):
    """Alles wat een tensor is naar de CPU, de rest ongemoeid.

    Loopt door lijsten en woordenboeken heen, want de toestand van een optimizer
    is genest en zit vol tensors die anders een apparaatnummer meedragen.
    """
    if torch.is_tensor(x):
        return x.detach().to("cpu").clone()
    if isinstance(x, dict):
        return {k: _naar_cpu(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        omgezet = [_naar_cpu(v) for v in x]
        return type(x)(omgezet) if isinstance(x, tuple) else omgezet
    return x


def schrijf(pad, stap, model=None, optimizer=None, stand=None, extra=None):
    """Schrijf een checkpoint weg. Onderbreekbaar op elk moment.

    `stand` is wat determinisme.stand() teruggeeft — meeschrijven zodat later
    vaststaat onder welke instellingen deze toestand is ontstaan.
    """
    pad = os.path.abspath(pad)
    map_ = os.path.dirname(pad)
    os.makedirs(map_, exist_ok=True)

    inhoud = {
        "versie": VERSIE,
        "stap": int(stap),
        "determinisme": stand,
        "model": _naar_cpu(model.state_dict()) if model is not None else None,
        "optimizer": _naar_cpu(optimizer.state_dict()) if optimizer is not None else None,
        "extra": _naar_cpu(extra) if extra is not None else None,
        # Uitsluitend ter informatie. Niets hiervan is nodig om te kunnen laden.
        "machine": {
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "kaarten": [torch.cuda.get_device_name(i)
                        for i in range(torch.cuda.device_count())],
        },
    }

    # Eerst naar geheugen, zodat we er een controlegetal over kunnen nemen
    # vóórdat er ook maar iets de schijf raakt.
    buffer = io.BytesIO()
    torch.save(inhoud, buffer)
    ruw = buffer.getvalue()
    controle = hashlib.sha256(ruw).hexdigest()

    tijdelijk = pad + ".deel"
    with open(tijdelijk, "wb") as f:
        f.write(len(controle).to_bytes(2, "big"))
        f.write(controle.encode())
        f.write(ruw)
        f.flush()
        os.fsync(f.fileno())          # de bytes staan nu écht op de schijf

    os.replace(tijdelijk, pad)        # atomair: of het oude, of het nieuwe

    # De hernoeming zelf moet ook duurzaam zijn, anders kan hij bij stroomverlies
    # alsnog verdwijnen terwijl het bestand er wel staat.
    fd = os.open(map_, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

    return {"pad": pad, "bytes": len(ruw), "controlegetal": controle}


def lees(pad, apparaat="cpu"):
    """Lees een checkpoint. Controleert het controlegetal en de versie."""
    with open(pad, "rb") as f:
        lengte = int.from_bytes(f.read(2), "big")
        opgeslagen = f.read(lengte).decode()
        ruw = f.read()

    gevonden = hashlib.sha256(ruw).hexdigest()
    if gevonden != opgeslagen:
        raise ValueError(
            f"checkpoint {pad} is beschadigd: controlegetal komt niet overeen\n"
            f"  verwacht: {opgeslagen}\n  gevonden: {gevonden}"
        )

    # map_location: nooit terugzetten op het apparaat waar het vandaan kwam.
    # Dat is precies wat een checkpoint aan één machine zou vastklinken.
    inhoud = torch.load(io.BytesIO(ruw), map_location=apparaat, weights_only=False)

    if inhoud.get("versie") != VERSIE:
        raise ValueError(
            f"checkpoint {pad} heeft versie {inhoud.get('versie')}, "
            f"deze code verwacht {VERSIE}"
        )
    return inhoud


def herstel(inhoud, model=None, optimizer=None, apparaat="cpu"):
    """Zet een gelezen checkpoint terug in een model en optimizer."""
    if model is not None and inhoud.get("model") is not None:
        model.load_state_dict(inhoud["model"])
        model.to(apparaat)
    if optimizer is not None and inhoud.get("optimizer") is not None:
        optimizer.load_state_dict(inhoud["optimizer"])
    return inhoud["stap"]
