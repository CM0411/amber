#!/bin/bash
# Zet de NAS (TrueNAS op de tweede DL380 Gen9, 192.168.1.149) netjes uit
# via zijn iLO (192.168.1.113, Redfish). "PushPowerButton" is een korte
# druk op de aan/uit-knop: TrueNAS vangt dat op als ACPI-signaal en sluit
# zelf af, dus geen harde stroomonderbreking. Wacht daarna tot de iLO
# "Off" meldt. De inlog staat in ~/.amber-ilo-nas (regel 1 gebruiker,
# regel 2 wachtwoord), buiten de repo — zelfde patroon als dl380-aan.sh.
GEHEIM=/home/arch/.amber-ilo-nas
ILO=192.168.1.113
LOG=/home/arch/amber-werk/stroom/nas.log

U=$(sed -n 1p "$GEHEIM"); P=$(sed -n 2p "$GEHEIM")

stand() {
    curl -sk -u "$U:$P" --max-time 20 "https://$ILO/redfish/v1/Systems/1/" \
        | python3 -c 'import json,sys;print(json.load(sys.stdin).get("PowerState","?"))' \
        2>/dev/null
}

s=$(stand)
if [ "$s" != "On" ]; then
    echo "$(date '+%F %H:%M') niets gedaan (stand: $s)" | tee -a "$LOG"
    exit 0
fi

# Eerst de NFS-koppeling loslaten, anders blijft elke ls op /mnt/truenas
# hangen zodra de NAS weg is. Mislukt dat (geen root), dan verloopt de
# autofs-koppeling vanzelf na tien minuten stilte.
umount /mnt/truenas 2>/dev/null || sudo -n umount /mnt/truenas 2>/dev/null

curl -sk -u "$U:$P" --max-time 20 -X POST \
     -H "Content-Type: application/json" -d '{"ResetType":"PushPowerButton"}' \
     "https://$ILO/redfish/v1/Systems/1/Actions/ComputerSystem.Reset/" > /dev/null
echo "$(date '+%F %H:%M') aan/uit-knop ingedrukt, wachten op Off" | tee -a "$LOG"

for i in $(seq 1 36); do          # hooguit 3 minuten
    sleep 5
    s=$(stand)
    if [ "$s" = "Off" ]; then
        echo "$(date '+%F %H:%M') NAS staat uit" | tee -a "$LOG"
        exit 0
    fi
done
echo "$(date '+%F %H:%M') na 3 min nog niet uit (stand: $s) — kijk zelf" | tee -a "$LOG"
exit 1
