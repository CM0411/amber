#!/bin/bash
# Zet de DL380 aan via de iLO (Redfish). Draait op de Z490, elke dag om
# 17:00 (amber-dl380-aan.timer). Idempotent: staat hij al aan, dan
# gebeurt er niets. De inlog staat in ~/.amber-ilo (regel 1 gebruiker,
# regel 2 wachtwoord), buiten de repo — zelfde patroon als .amber-ntfy.
GEHEIM=/home/arch/.amber-ilo
ILO=192.168.1.44
LOG=/home/arch/amber-werk/stroom/dl380-aan.log

U=$(sed -n 1p "$GEHEIM"); P=$(sed -n 2p "$GEHEIM")

stand=$(curl -sk -u "$U:$P" --max-time 20 "https://$ILO/redfish/v1/Systems/1/" \
        | python3 -c 'import json,sys;print(json.load(sys.stdin).get("PowerState","?"))' \
        2>/dev/null)

if [ "$stand" = "Off" ]; then
    curl -sk -u "$U:$P" --max-time 20 -X POST \
         -H "Content-Type: application/json" -d '{"ResetType":"On"}' \
         "https://$ILO/redfish/v1/Systems/1/Actions/ComputerSystem.Reset/" \
         > /dev/null
    echo "$(date '+%F %H:%M') aangezet (stand was Off)" >> "$LOG"
else
    echo "$(date '+%F %H:%M') niets gedaan (stand: $stand)" >> "$LOG"
fi
