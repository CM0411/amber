#!/usr/bin/env bash
# De snapshot-opruimer van Amber — 19 aug 2026 (Cley: "de meest recente
# back-ups bewaren"). Staat op de Z490 én op de DL380; beide back-upscripts
# roepen hem aan, ook over ssh voor een bestemming op de andere machine.
#
#   amber-snap-opruimen.sh MAP PREFIX AANTAL GIGABYTE
#
# Houdt in MAP de nieuwste AANTAL archieven die met PREFIX beginnen, en samen
# nooit meer dan GIGABYTE. Wat daarbuiten valt gaat weg, oudste eerst.
#
# Twee grenzen, niet één. Tot 18 aug woog een archief tientallen KB en stonden
# er 168: een week geschiedenis voor een paar megabyte. Sinds de checkpoints
# meelopen weegt er één 6,6 GB — 168 stuks vroegen 1,1 TB op een schijf van
# 468 GB, en die liep vol tijdens de rungrens naar run 7.2. Een aantal alleen
# is dus niet genoeg: het gewicht groeit met elke knip mee, dus er hoort een
# ruimtegrens naast. De ruimtegrens is de echte rem, het aantal de bovengrens.
#
# De nieuwste ALTIJD_HOUDEN blijven staan wat er ook gebeurt: een grens die
# kleiner is dan één archief mag nooit de laatste back-up opeten.
#
# Raakt alleen bestanden die met PREFIX beginnen en op .tar.gz eindigen. De
# oude naamloze archieven van vóór 15 aug (amber-20*) horen bij geen enkele
# machine en worden hier met opzet niet aangeraakt.
#
# Proefstand: OPRUIM_PROEF=1 amber-snap-opruimen.sh ...
# Dan wist hij niets en vertelt hij alleen wat hij zou wissen. Handig vóór de
# eerste echte ronde, want een back-up terughalen kan niet.

set -uo pipefail

ALTIJD_HOUDEN=3
PROEF=${OPRUIM_PROEF:-0}

map=${1:-}
prefix=${2:-}
aantal=${3:-}
gigabyte=${4:-}

fout() { echo "FOUT: $*" >&2; exit 2; }

heel_getal() {
    case ${1:-} in
        "" | *[!0-9]*) return 1;;
        *) return 0;;
    esac
}

[[ -n $map ]] || fout "geen map opgegeven; gebruik: $(basename "$0") MAP PREFIX AANTAL GIGABYTE"
case $prefix in
    amber-*) : ;;
    *) fout "prefix '$prefix' moet met amber- beginnen";;
esac
case $prefix in
    *[/*?\[]*) fout "prefix '$prefix' mag geen / of jokerteken bevatten";;
esac
heel_getal "$aantal"   || fout "AANTAL '$aantal' is geen heel getal"
heel_getal "$gigabyte" || fout "GIGABYTE '$gigabyte' is geen heel getal"
(( aantal >= 1 ))      || fout "AANTAL moet minstens 1 zijn"
(( gigabyte >= 1 ))    || fout "GIGABYTE moet minstens 1 zijn"

# Een bestemming die er niet is (NAS uit, DL360 nog niet gekoppeld) is geen
# fout — dan valt er ook niets op te ruimen.
timeout 30 test -d "$map" 2>/dev/null || exit 0

mapfile -t bestanden < <(timeout 120 ls -1t -- "$map/$prefix"*.tar.gz 2>/dev/null)
(( ${#bestanden[@]} > 0 )) || exit 0

grens_kb=$(( gigabyte * 1024 * 1024 ))
totaal_kb=0
nummer=0
gehouden=0
weg=()

for f in "${bestanden[@]}"; do
    [[ -f $f ]] || continue
    nummer=$(( nummer + 1 ))
    kb=$(timeout 30 du -k -- "$f" 2>/dev/null | cut -f1)
    heel_getal "$kb" || kb=0
    totaal_kb=$(( totaal_kb + kb ))

    # De nieuwste paar staan buiten elke grens.
    if (( nummer <= ALTIJD_HOUDEN )); then
        gehouden=$(( gehouden + 1 ))
        continue
    fi
    if (( nummer > aantal || totaal_kb > grens_kb )); then
        weg+=("$f")
        totaal_kb=$(( totaal_kb - kb ))    # deze telt niet mee in wat blijft
    else
        gehouden=$(( gehouden + 1 ))
    fi
done

verwijderd=0
for f in ${weg[@]+"${weg[@]}"}; do
    if [[ $PROEF == 1 ]]; then
        verwijderd=$(( verwijderd + 1 ))
        echo "zou opruimen: $f"
        continue
    fi
    if timeout 60 rm -f -- "$f"; then
        verwijderd=$(( verwijderd + 1 ))
        echo "opgeruimd: $f"
    else
        echo "FOUT: $f kon niet weg" >&2
    fi
done

woord=opgeruimd
[[ $PROEF == 1 ]] && woord="zou opruimen"
echo "$map/$prefix: $gehouden gehouden ($(( totaal_kb / 1024 )) MB), $verwijderd $woord" \
     "[grens $aantal stuks / $gigabyte GB]"
