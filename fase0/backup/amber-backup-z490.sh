#!/usr/bin/env bash
# Back-up van Amber, draaiend op de Z490 — de altijd-aan-machine (14 aug 2026).
#
# Schrijft een momentopname naar elke bestemming die aanwezig en beschrijfbaar
# is, en slaat bestemmingen die er niet zijn stilzwijgend over. De NAS kan uit
# staan en de DL380 is er alleen als Cley hem aanzet; de back-up klaagt pas als
# er helemaal níéts overblijft.
#
# Geleerd van de DL380-versie:
# - tar klapt om als er tijdens het inpakken iets verandert (de urenteller
#   schrijft elke vijf minuten). Daarom: vluchtige bestanden uitsluiten en bij
#   een botsing één keer opnieuw proberen.
# - een NFS-koppeling die wegvalt kan een schrijfactie eeuwig laten hangen
#   (12 aug: bijna 24 uur). Daarom: elke aanraking van een netwerkpad achter
#   een timeout.
#
# 19 aug 2026 (Cley: "de meest recente back-ups bewaren"): het opruimen zit nu
# in ~/.local/bin/amber-snap-opruimen.sh, met per bestemming een aantal én een
# ruimtegrens. Zie de kop van dat script voor het waarom.

set -uo pipefail

# De bronnen: het papierwerk (de git-kloon), de werkmap met kern én het
# levende checkpoint, en de rungeschiedenis. Geen venv's — die zijn met één
# pip-opdracht terug te halen.
BRONNEN=(amber amber-werk leven.log)
UITSLUITEN=(
    --exclude=amber-werk/venv
    --exclude=amber-werk/tmp
    --exclude=__pycache__
    --exclude=amber/uren-live.json     # ververst elke 5 min; waardeloos in een archief
)

OPRUIMER=/home/arch/.local/bin/amber-snap-opruimen.sh
PREFIX=amber-z490               # alleen de eigen archieven; de DL380 ruimt de zijne

# Hoeveel er blijft staan: aantal en gigabyte. Eén archief weegt hier ±0,65 GB
# (het levende checkpoint loopt mee) en groeit langzaam mee met haar brein.
# 168 stuks is een week bij één per uur; de ruimtegrens vangt de groei op.
BEWAAR_AANTAL=168
BEWAAR_GB=150
# één plek minder houden, want het archief van deze ronde komt er zo bij
houd_nu=$(( BEWAAR_AANTAL > 1 ? BEWAAR_AANTAL - 1 : 1 ))

# Bestemmingen op volgorde van nabijheid.
DATA=/mnt/data/amber-snapshots         # de NVMe-spiegel in deze machine
NAS=/mnt/truenas/amber                 # de NAS — kan uit staan
NAS_HOST=192.168.1.149                 # eerst kloppen, dan pas het pad aanraken
DL360=/mnt/dl360/amber/snapshots       # de DL360-opslagmachine (RAID6, NFS)
DL380=arch@192.168.1.51                # staat alleen aan als Cley hem aanzet
DL380_DOEL=/mnt/opslag/amber           # de RAID10-array daar

naam="$PREFIX-$(date +%Y-%m-%d_%H%M).tar.gz"   # machinenaam erin: de DL380 schrijft naar dezelfde mappen
tijdelijk=$(mktemp /home/arch/.amber-backup.XXXXXX.tar.gz) || exit 1
trap 'rm -f "$tijdelijk"' EXIT

opruim_fout=0

# Opruimen met controle op de afloop. Gaat het mis (de opruimer ontbreekt, is
# niet uitvoerbaar, of struikelt), dan gaat de back-up wél door — een back-up
# is meer waard dan een nette map — maar het script eindigt rood, zodat het
# opvalt in plaats van geluidloos de schijf vol te laten lopen.
opruim() {
    local doel=$1 code
    if [[ ! -x $OPRUIMER ]]; then
        echo "FOUT: opruimer $OPRUIMER ontbreekt of is niet uitvoerbaar" >&2
        opruim_fout=1
        return 1
    fi
    "$OPRUIMER" "$doel" "$PREFIX" "$houd_nu" "$BEWAAR_GB"
    code=$?
    if (( code != 0 )); then
        echo "FOUT: opruimen van $doel mislukt (code $code)" >&2
        opruim_fout=1
        return 1
    fi
    return 0
}

# Staat de NAS aan? Eén keer kloppen, en dat antwoord hieronder overal
# gebruiken. Élke aanraking van /mnt/truenas start de automount, en die loopt
# dan 90 s in een timeout en zet `mnt-truenas.mount` op **failed** — waarna
# een échte storing niet meer opvalt in `systemctl --failed`. Dus ook een
# onschuldige `test -d` in de opruimlus hieronder mag er niet aan zitten
# (19 aug 2026: precies daar ging het mis nadat de schrijfkant al geklopt had).
nas_aan=0
timeout 5 ping -c 1 -W 2 "$NAS_HOST" >/dev/null 2>&1 && nas_aan=1

# Restanten van een afgebroken vorige keer opruimen (de trap mist als het
# proces gedood wordt). Ouder dan zes uur, dus nooit de lopende back-up.
timeout 60 find /home/arch -maxdepth 1 -type f -name '.amber-backup.*.tar.gz' \
    -mmin +360 ! -samefile "$tijdelijk" -delete 2>/dev/null
opruimmappen=("$DATA" "$DL360")
(( nas_aan )) && opruimmappen+=("$NAS")
for map in "${opruimmappen[@]}"; do
    timeout 30 test -d "$map" 2>/dev/null || continue
    timeout 60 find "$map" -maxdepth 1 -type f -name "$PREFIX-*.tar.gz.deel" \
        -mmin +360 -delete 2>/dev/null
done

pak_in() {
    # 19 aug 2026: de kijker schrijft brein/*-stand.json elke paar seconden;
    # tar meldt dan "file changed as we read it" en eindigt met code 1 — het
    # archief is dan wél compleet (code 2 = echt kapot). Code 1 laten we door;
    # de leesproef hieronder vangt een kapot archief alsnog.
    tar -czf "$tijdelijk" --warning=no-file-changed "${UITSLUITEN[@]}" -C /home/arch "${BRONNEN[@]}"
    local rc=$?
    [[ $rc -eq 1 ]] && rc=0
    return $rc
}

# Eén keer inpakken; verandert er onderweg iets (checkpoint-hernoeming,
# urenteller), dan vijf tellen wachten en nog één keer.
if ! pak_in; then
    echo "inpakken botste, tweede poging over 5 s"
    sleep 5
    if ! pak_in; then
        echo "FOUT: inpakken twee keer mislukt" >&2
        exit 1
    fi
fi
if ! tar -tzf "$tijdelijk" >/dev/null 2>&1; then
    echo "FOUT: archief niet leesbaar, niets weggeschreven" >&2
    exit 1
fi

geslaagd=0

# Lokale of gekoppelde bestemming — elke stap achter een timeout, want een
# hangende NFS-koppeling mag deze dienst nooit gijzelen.
schrijf_map() {
    local doel=$1
    if ! timeout 15 test -d "$doel" 2>/dev/null; then
        # bestaat hij niet maar zijn ouder wel (NAS aan, map nog leeg): aanmaken
        if ! timeout 15 mkdir -p "$doel" 2>/dev/null; then
            echo "overgeslagen (niet bereikbaar): $doel"
            return 1
        fi
    fi
    # Eerst opruimen, dan schrijven: op een volle schijf is er anders geen plek
    # voor het nieuwe archief. De opruimer houdt de nieuwste drie altijd.
    opruim "$doel"
    if timeout 600 cp "$tijdelijk" "$doel/$naam.deel" \
            && timeout 60 mv "$doel/$naam.deel" "$doel/$naam"; then
        timeout 60 sync -f "$doel/$naam" 2>/dev/null
        echo "geschreven: $doel/$naam"
        geslaagd=$((geslaagd + 1))
    else
        echo "FOUT: schrijven naar $doel mislukt" >&2
        timeout 30 rm -f "$doel/$naam.deel" 2>/dev/null
        return 1
    fi
}

schrijf_map "$DATA"

# De NAS staat meestal uit; er is bovenaan al één keer geklopt.
if (( nas_aan )); then
    schrijf_map "$NAS"
else
    echo "overgeslagen (uit): de NAS"
fi

schrijf_map "$DL360"

# De DL380, als hij aan is: eerst daar de eigen resten en oude archieven
# opruimen, dan het nieuwe archief erheen.
if timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=5 "$DL380" true 2>/dev/null; then
    # Halve overdrachten van eerdere keren. Alleen wij maken amber-z490-*.deel
    # daar, en alleen wij kunnen ze opruimen — de DL380 kijkt naar zijn eigen
    # naam. Ouder dan zes uur, dus nooit een lopende overdracht.
    timeout 60 ssh -o BatchMode=yes "$DL380" \
        "find $DL380_DOEL -maxdepth 1 -type f -name '$PREFIX-*.tar.gz.deel' -mmin +360 -delete" \
        2>/dev/null
    # De opruimer daarginds, niet die van ons: code 127 betekent dat hij daar
    # nog niet geïnstalleerd is, en dat moet opvallen.
    timeout 180 ssh -o BatchMode=yes "$DL380" \
        "$OPRUIMER $DL380_DOEL $PREFIX $houd_nu $BEWAAR_GB"
    code=$?
    if (( code != 0 )); then
        echo "FOUT: opruimen op de DL380 mislukt (code $code)" >&2
        opruim_fout=1
    fi
    if timeout 600 scp -q "$tijdelijk" "$DL380:$DL380_DOEL/$naam.deel" \
            && timeout 30 ssh -o BatchMode=yes "$DL380" \
                "mv $DL380_DOEL/$naam.deel $DL380_DOEL/$naam"; then
        echo "geschreven: $DL380:$DL380_DOEL/$naam"
        geslaagd=$((geslaagd + 1))
    else
        echo "FOUT: schrijven naar de DL380 mislukt" >&2
        timeout 30 ssh -o BatchMode=yes "$DL380" "rm -f $DL380_DOEL/$naam.deel" 2>/dev/null
    fi
else
    echo "overgeslagen (uit): de DL380"
fi

if (( geslaagd == 0 )); then
    echo "FOUT: geen enkele bestemming beschikbaar, er is niets weggeschreven" >&2
    exit 1
fi
echo "klaar: $geslaagd bestemming(en)"

if (( opruim_fout )); then
    echo "LET OP: het opruimen is niet gelukt — zonder opruimen loopt de schijf vol" >&2
    exit 1
fi
