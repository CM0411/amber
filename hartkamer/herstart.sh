#!/bin/bash
# De Hartkamer-servers opnieuw starten (nohup; geen systemd): 8030 = de grote
# hartkamer, 8031 = de telefoon-versie (2 sep 2026). Vanuit een eigen script,
# zodat pkill niet de aanroepende shell raakt.
pkill -f "python3 hartkamer-server.py"
sleep 1
cd /home/arch/amber-werk/hartkamer || exit 1
nohup python3 hartkamer-server.py 8030 hartkamer.html > /dev/null 2>&1 < /dev/null &
nohup python3 hartkamer-server.py 8031 hartkamer-mobiel.html > /dev/null 2>&1 < /dev/null &
disown -a
sleep 2
for p in 8030 8031; do curl -s -o /dev/null -w "poort $p: HTTP %{http_code}\n" --max-time 5 http://127.0.0.1:$p/; done
