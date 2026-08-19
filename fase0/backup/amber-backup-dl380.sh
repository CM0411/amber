#!/usr/bin/env bash
# Back-up van de Amber-projectmap.
#
# Schrijft een momentopname naar elke bestemming die aanwezig en beschrijfbaar is,
# en slaat bestemmingen die er niet zijn stilzwijgend over. Zo blijft de back-up
# doorlopen als de NAS even weg is, en klaagt hij wel als er niets over blijft.
#
# Draait zonder root. De koppelpunten aanmaken en koppelen vraagt dat wel.
#
# 19 aug 2026 (Cley: "de meest recente back-ups bewaren"): het opruimen zit nu
# in ~/.local/bin/amber-snap-opruimen.sh, met per bestemming een aantal én een
# ruimtegrens. Zie de kop van dat script voor het waarom.

set -uo pipefail

# Twee bronnen: het papierwerk en de code. De venv gaat er bewust niet in —
# 5 GB aan bibliotheken die met één pip-opdracht terug te halen zijn, en die
# elke momentopname onbruikbaar groot zouden maken.
BRONNEN=(
    /home/arch/amber            # roadmap, besluitenregister, sessieverslagen
    /home/arch/amber-werk       # de kern, de fase 0-scripts, meetverslagen
)
UITSLUITEN=(
    --exclude=amber-werk/venv
    --exclude=amber-werk/tmp
    --exclude=__pycache__
    --exclude=amber/uren-live.json     # ververst elke 5 min; waardeloos in een archief
)

OPRUIMER=/home/arch/.local/bin/amber-snap-opruimen.sh
PREFIX=amber-dl380              # alleen de eigen archieven; de Z490 ruimt de hare

# Hoeveel er blijft staan, per bestemming: aantal en gigabyte.
# Eén archief weegt hier ±6,6 GB (de run-checkpoints in fase1 lopen mee) en
# groeit met ±1,4 GB per knip. Daarom is de ruimtegrens de echte rem.
BEWAAR_AANTAL=48                # de RAID en de NAS: twee dagen bij één per uur
BEWAAR_GB=360                   # ruimte laten voor het halffabricaat én de Z490
BEWAAR_AANTAL_THUIS=6           # het vangnet staat op dezelfde schijf als de bron
BEWAAR_GB_THUIS=60              # — dat is geen back-up, dus houd het klein

BESTEMMINGEN=(
    /home/arch/amber-snapshots      # zelfde schijf: vangnet, geen back-up
    /mnt/opslag/amber               # de RAID10-array van vier Seagates (11 aug 2026)
    /mnt/truenas/amber              # de NAS op 192.168.1.149
)

namen=()
for b in "${BRONNEN[@]}"; do
    if [[ ! -d $b ]]; then
        echo "FOUT: bronmap $b bestaat niet" >&2
        exit 1
    fi
    namen+=("$(basename "$b")")
done

naam="$PREFIX-$(date +%Y-%m-%d_%H%M).tar.gz"   # machinenaam erin: de Z490 schrijft naar dezelfde mappen

opruim_fout=0

# Opruimen met controle op de afloop. Gaat het mis (de opruimer ontbreekt, is
# niet uitvoerbaar, of struikelt), dan gaat de back-up wél door — een back-up
# is meer waard dan een nette map — maar het script eindigt rood, zodat het
# opvalt in plaats van jarenlang geluidloos de schijf vol te laten lopen.
opruim() {
    local doel=$1 aantal=$2 gb=$3 code
    if [[ ! -x $OPRUIMER ]]; then
        echo "FOUT: opruimer $OPRUIMER ontbreekt of is niet uitvoerbaar" >&2
        opruim_fout=1
        return 1
    fi
    "$OPRUIMER" "$doel" "$PREFIX" "$aantal" "$gb"
    code=$?
    if (( code != 0 )); then
        echo "FOUT: opruimen van $doel mislukt (code $code)" >&2
        opruim_fout=1
        return 1
    fi
    return 0
}

# EERST opruimen, DAARNA pas inpakken. Dit is de belangrijkste les van 19 aug
# 2026: het halffabricaat weegt evenveel als het archief (±6,6 GB) en landt op
# een schijf die zelf bestemming is. Stond die vol, dan mislukte tar en werd de
# opruimer nooit bereikt — het script kon zichzelf niet meer losmaken, en elk
# uur herhaalde de timer dezelfde doodloop. Opruimen kost geen ruimte, dus het
# hoort vóór alles te gebeuren wat ruimte vráágt.
for doel in "${BESTEMMINGEN[@]}"; do
    [[ -d $doel && -w $doel ]] || continue
    houd=$BEWAAR_AANTAL
    houd_gb=$BEWAAR_GB
    if [[ $doel == /home/arch/amber-snapshots ]]; then
        houd=$BEWAAR_AANTAL_THUIS
        houd_gb=$BEWAAR_GB_THUIS
    fi
    # één plek minder, want het archief van deze ronde komt er zo bij
    opruim "$doel" "$(( houd > 1 ? houd - 1 : 1 ))" "$houd_gb"
done

# Restanten van een afgebroken vorige keer opruimen (de trap mist als het
# proces gedood wordt). Ouder dan zes uur, dus nooit een lopende back-up — ook
# niet die van de Z490, die haar halve overdrachten hier achterlaat en ze zelf
# niet kan opruimen als juist die verbinding wegviel. Vandaar amber-*, niet
# alleen de eigen $PREFIX.
for map in /tmp /mnt/opslag/amber "${BESTEMMINGEN[@]}"; do
    timeout 30 test -d "$map" 2>/dev/null || continue
    timeout 60 find "$map" -maxdepth 1 -type f \
        \( -name '.amber-backup.*.tar.gz' -o -name 'amber-backup.*.tar.gz' \
           -o -name 'amber-*.tar.gz.deel' \) \
        -mmin +360 -delete 2>/dev/null
done

# Het halffabricaat komt op de RAID te staan, niet op de systeemschijf. Het
# weegt evenveel als het archief zelf (±6,6 GB) en stond tot nu toe in /tmp —
# op precies de schijf die op 19 aug volliep. Tijdens elke ronde vroeg de
# back-up daar dus een dubbele portie: het halffabricaat én de kopie in
# /home/arch/amber-snapshots.
if timeout 15 test -w /mnt/opslag/amber 2>/dev/null; then
    tijdelijk=$(mktemp /mnt/opslag/amber/.amber-backup.XXXXXX.tar.gz) || exit 1
else
    tijdelijk=$(mktemp /tmp/amber-backup.XXXXXX.tar.gz) || exit 1
fi
trap 'rm -f "$tijdelijk"' EXIT

# Eén keer inpakken, daarna naar elke bestemming kopiëren. Verandert er
# onderweg iets (de kijker schrijft elke paar seconden in brein/, de
# brievenbus, een checkpoint-hernoeming), dan meldt tar "file changed as we
# read it" met afsluitcode 1: even wachten en nog eens, tot drie keer.
#
# Blijft het botsen, dan geven we het NIET op: bij code 1 is het archief
# gewoon compleet (code 2 = echt kapot), en de leesproef hieronder is de
# echte keuring. De Z490 doet dit al zo sinds 19 aug; tot dan liet de DL380
# juist tijdens drukke uren de back-up helemaal vallen.
gelukt=0
for poging in 1 2 3; do
    tar -czf "$tijdelijk" --warning=no-file-changed "${UITSLUITEN[@]}" \
        -C /home/arch "${namen[@]}" 2>/tmp/amber-backup.tar.err
    code=$?
    if (( code == 0 )); then gelukt=1; break; fi
    if (( code == 1 )); then
        if (( poging < 3 )); then
            echo "inpakken botste (poging $poging), even wachten en opnieuw"
            sleep 5
            continue
        fi
        echo "inpakken bleef botsen; het archief gaat langs de leesproef"
        gelukt=1
        break
    fi
    if grep -q "No space left on device" /tmp/amber-backup.tar.err; then
        echo "FOUT: schijf vol tijdens inpakken (het opruimen was al gedaan)" >&2
    fi
    cat /tmp/amber-backup.tar.err >&2
    break
done
if (( gelukt == 0 )); then
    echo "FOUT: inpakken mislukt" >&2
    exit 1
fi

# Controleer dat het archief leesbaar is voordat we het ergens neerzetten.
if ! tar -tzf "$tijdelijk" >/dev/null 2>&1; then
    echo "FOUT: archief is niet leesbaar, niets weggeschreven" >&2
    exit 1
fi

geslaagd=0
for doel in "${BESTEMMINGEN[@]}"; do
    if [[ ! -d $doel ]]; then
        echo "overgeslagen (bestaat niet): $doel"
        continue
    fi
    if [[ ! -w $doel ]]; then
        echo "overgeslagen (niet beschrijfbaar): $doel"
        continue
    fi

    if cp "$tijdelijk" "$doel/$naam.deel" && mv "$doel/$naam.deel" "$doel/$naam"; then
        # sync, want er is geen batterij op de controller die dit opvangt
        sync -f "$doel/$naam" 2>/dev/null
        echo "geschreven: $doel/$naam"
        geslaagd=$((geslaagd + 1))
    else
        echo "FOUT: schrijven naar $doel mislukt" >&2
        rm -f "$doel/$naam.deel"
        continue
    fi
done

if (( geslaagd == 0 )); then
    echo "FOUT: geen enkele bestemming beschikbaar, er is niets weggeschreven" >&2
    exit 1
fi

echo "klaar: $geslaagd van ${#BESTEMMINGEN[@]} bestemmingen"

if (( opruim_fout )); then
    echo "LET OP: het opruimen is niet gelukt — zonder opruimen loopt de schijf vol" >&2
    exit 1
fi
