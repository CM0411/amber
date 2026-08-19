#!/usr/bin/env bash
# Draait er ergens een dienst met oudere code in het geheugen dan er op schijf
# staat? Die scheefstand is stil: alles antwoordt 200 en toch klopt het niet.
# Gemaakt 19 aug 2026, nadat de rungrens de nieuwe venster-pagina neerzette
# terwijl de dienst de oude servercode bleef draaien en Cleys venster bevroor.
# Zoekt diensten die oudere code draaien dan er op schijf staat.
for u in $(systemctl list-units --all --no-legend 'amber-*.service' | awk '{print $1}' | sed 's/^●//;s/^ *//'); do
    act=$(systemctl is-active "$u")
    [[ $act == active ]] || continue
    start=$(systemctl show "$u" -p ActiveEnterTimestamp --value)
    [[ -n $start ]] || continue
    st=$(date -d "$start" +%s 2>/dev/null) || continue
    exe=$(systemctl show "$u" -p ExecStart --value | grep -oE '/[^ "]+\.(py|sh)' | head -1)
    [[ -n $exe && -f $exe ]] || continue
    mt=$(stat -c %Y "$exe")
    if (( mt > st )); then
        echo "SCHEEF: $u draait sinds $(date -d @$st +%H:%M:%S) maar $exe is van $(date -d @$mt +%H:%M:%S)"
    else
        printf "  ok   %-24s %s\n" "$u" "$(basename "$exe")"
    fi
done
