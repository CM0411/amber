#!/bin/bash
# Zet de NAS (TrueNAS op de tweede DL380 Gen9) aan via zijn iLO
# (192.168.1.113, Redfish). Idempotent: staat hij al aan, dan gebeurt er
# niets. Opstarten duurt een paar minuten; /mnt/truenas koppelt daarna
# vanzelf weer (autofs) zodra iemand erin kijkt.
GEHEIM=/home/arch/.amber-ilo-nas
ILO=192.168.1.113
LOG=/home/arch/amber-werk/stroom/nas.log

U=$(sed -n 1p "$GEHEIM"); P=$(sed -n 2p "$GEHEIM")

stand=$(curl -sk -u "$U:$P" --max-time 20 "https://$ILO/redfish/v1/Systems/1/" \
        | python3 -c 'import json,sys;print(json.load(sys.stdin).get("PowerState","?"))' \
        2>/dev/null)

if [ "$stand" = "Off" ]; then
    curl -sk -u "$U:$P" --max-time 20 -X POST \
         -H "Content-Type: application/json" -d '{"ResetType":"On"}' \
         "https://$ILO/redfish/v1/Systems/1/Actions/ComputerSystem.Reset/" > /dev/null
    echo "$(date '+%F %H:%M') aangezet (stand was Off)" | tee -a "$LOG"
else
    echo "$(date '+%F %H:%M') niets gedaan (stand: $stand)" | tee -a "$LOG"
fi
