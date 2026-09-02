#!/bin/bash
# Verzamelt elke 30 s de gezondheid van de Z490 (lokaal) en de DL380 (ssh) → /home/arch/rapport/machines.json
# Voor het vak "Machines" in het venster (Cley, 27 aug 2026: "op welke machine ik druk, wil ik alle details").
DL380="arch@192.168.1.51"
UIT=/home/arch/rapport/machines.json
PEIL='echo up=$(cut -d" " -f1 /proc/uptime)
echo load=$(cut -d" " -f1-3 /proc/loadavg)
echo mt=$(awk "/MemTotal/{print \$2}" /proc/meminfo)
echo ma=$(awk "/MemAvailable/{print \$2}" /proc/meminfo)
echo temp=$( (sensors 2>/dev/null | grep -m1 Tdie || sensors 2>/dev/null | grep -m1 -E "Package id 0|temp1") | grep -o "+[0-9.]*" | head -1)
echo disk=$(df -h / | tail -1 | awk "{print \$2\" \"\$3\" \"\$5}")
nvidia-smi --query-gpu=name,temperature.gpu,power.draw,memory.used,memory.total,utilization.gpu,fan.speed --format=csv,noheader 2>/dev/null | sed "s/^/gpu=/"'
while true; do
  python3 - "$DL380" "$UIT" "$PEIL" <<'PY'
import json, subprocess, time, sys, os
dl, uit, peil = sys.argv[1], sys.argv[2], sys.argv[3]
def lees(argv, t):
    try:
        r = subprocess.run(argv, input=peil, capture_output=True, text=True, timeout=t)
        return r.stdout
    except Exception:
        return ""
def parse(txt):
    if not txt.strip(): return None
    d = {"gpu": []}
    for regel in txt.splitlines():
        if "=" not in regel: continue
        k, v = regel.split("=", 1)
        if k == "gpu": d["gpu"].append([x.strip() for x in v.split(",")])
        else: d[k] = v.strip()
    try:
        mt, ma = int(d.get("mt") or 0)//1024, int(d.get("ma") or 0)//1024
        return {"aan": True, "uptime_s": float(d.get("up") or 0), "load": (d.get("load") or "").split(),
                "ram_gebruikt_mb": mt-ma, "ram_totaal_mb": mt, "cpu_temp": (d.get("temp") or "").strip("+"),
                "schijf": (d.get("disk") or "").split(), "gpu": d["gpu"]}
    except Exception as e:
        return {"aan": True, "fout": str(e)}
z = parse(lees(["bash", "-s"], 15)) or {"aan": False}
d = parse(lees(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", dl, "bash", "-s"], 20)) or {"aan": False}
uitkomst = {"tijd": time.time(), "z490": z, "dl380": d}
with open(uit + ".deel", "w") as f: json.dump(uitkomst, f)
os.replace(uit + ".deel", uit)
PY
  # haar echte wereld: de laatste 'wereld_dieper' uit het logboek (diepste_per per familie) → wereld.json (27 aug 2026, Cley: "is dit wel up to date?")
  tac /home/arch/amber-werk/fase1/leven/logboek.jsonl 2>/dev/null | grep -m1 '"wereld_dieper"' > /home/arch/rapport/wereld.json.deel && mv /home/arch/rapport/wereld.json.deel /home/arch/rapport/wereld.json
  sleep 30
done
