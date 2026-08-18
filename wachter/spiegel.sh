#!/usr/bin/env bash
# amber-spiegel (18 aug 2026): als de trainer op een andere machine draait
# (zie /home/arch/amber-machine.json), haalt dit elke minuut haar sporen
# hierheen — leven.log, logboek, momentopname, brievenbus, run.json —
# zodat venster, kijker, rapport, tijdlijn, zelfrapport en melder op de
# altijd-aan-machine (Z490) ongewijzigd blijven werken. Woont de trainer
# hier ("local" of geen bestand), dan doet dit niets.
set -u
HOST=$(python3 -c 'import json; print(json.load(open("/home/arch/amber-machine.json")).get("trainer","local"))' 2>/dev/null || echo local)
[ "$HOST" = "local" ] || [ -z "$HOST" ] && exit 0
RS="rsync -az --timeout=30 -e ssh -o BatchMode=yes"
$RS "$HOST:leven.log" /home/arch/leven.log
$RS "$HOST:amber-werk/fase1/leven/logboek.jsonl" /home/arch/amber-werk/fase1/leven/logboek.jsonl
$RS "$HOST:amber-werk/fase1/leven/momentopname.pt" /home/arch/amber-werk/fase1/leven/momentopname.pt
$RS "$HOST:amber-werk/fase1/brievenbus.jsonl" /home/arch/amber-werk/fase1/brievenbus.jsonl 2>/dev/null
$RS "$HOST:rapport/run.json" /home/arch/rapport/run.json 2>/dev/null
exit 0
