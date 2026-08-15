#!/usr/bin/env bash
# Eén toetsknop: draait alle toetsen van de kern na elkaar en vat samen.
#
# Elke toets drukt onderaan "passed: N    failed: M" af en eindigt met
# afsluitcode 0 als er niets faalde. Dit script telt op, toont per toets
# één regel, en eindigt zelf met 1 zodra er ergens iets rood is — zodat
# rungrens.py en een mens hetzelfde zien.
#
#   ~/amber-werk/kern/toets-alles.sh            alle toetsen
#   ~/amber-werk/kern/toets-alles.sh world tasks    alleen die (namen zonder test-)
#
# Draait vanuit de kernmap met de venv. Kaartkeuze via CUDA_VISIBLE_DEVICES
# zoals altijd (test-learning en test-layer-growth gebruiken de GPU).
set -u
KERN="$(cd "$(dirname "$0")" && pwd)"
PY="$KERN/../venv/bin/python"
[ -x "$PY" ] || PY=python3            # op de trainer: systeem-python
cd "$KERN" || exit 1

if [ $# -gt 0 ]; then
    TOETSEN=()
    for n in "$@"; do TOETSEN+=("test-$n.py"); done
else
    TOETSEN=(test-*.py)
fi

LOG="${TMPDIR:-/tmp}/toets-alles.$$.log"
tot_ok=0; tot_fout=0; rood=0; begin=$(date +%s)
printf '%-24s %6s %6s %6s\n' "toets" "goed" "fout" "sec"
for t in "${TOETSEN[@]}"; do
    [ -f "$t" ] || { printf '%-24s  ontbreekt\n' "$t"; rood=1; continue; }
    t0=$(date +%s)
    "$PY" "$t" > "$LOG" 2>&1
    code=$?
    regel=$(grep -E '^passed: ' "$LOG" | tail -1)
    ok=$(echo "$regel" | sed -nE 's/passed: ([0-9]+).*/\1/p')
    fout=$(echo "$regel" | sed -nE 's/.*failed: ([0-9]+).*/\1/p')
    ok=${ok:-0}; fout=${fout:-?}
    if [ "$code" -ne 0 ] || [ "$fout" != "0" ]; then
        rood=1
        printf '%-24s %6s %6s %6s   <-- ROOD\n' "$t" "$ok" "$fout" "$(( $(date +%s) - t0 ))"
        grep -E 'FAIL|Error|Traceback' "$LOG" | head -5 | sed 's/^/        /'
    else
        printf '%-24s %6s %6s %6s\n' "$t" "$ok" "$fout" "$(( $(date +%s) - t0 ))"
    fi
    tot_ok=$(( tot_ok + ok ))
    [ "$fout" != "?" ] && tot_fout=$(( tot_fout + fout ))
done
rm -f "$LOG"
echo "------------------------------------------------"
printf 'samen: %d goed, %d fout, %d s' "$tot_ok" "$tot_fout" "$(( $(date +%s) - begin ))"
if [ "$rood" -ne 0 ]; then echo "   — ER IS IETS ROOD"; exit 1; fi
echo "   — alles groen"
