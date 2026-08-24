"""De kijker rust langer tussen twee rondes (24 aug 2026, gemeten: de fijne
kijker op vier draden kostte de training 13% -- leren 3,40 s tegen 2,95 s
zonder kijker). Rust in seconden via AMBER_KIJKER_RUST; standaard blijft 6."""
import sys, ast, shutil, time
pad = sys.argv[1]; s = open(pad).read()
a = 'EENMAAL = os.environ.get("AMBER_KIJKER_EENMAAL") == "1"     # proef: één ronde, dan stoppen\n'
b = a + 'RUST = int(os.environ.get("AMBER_KIJKER_RUST", "6"))       # seconden tussen twee rondes (24 aug: 120 op de Z490, de training gaat voor)\n'
assert s.count(a) == 1 and s.count("    time.sleep(6)\n") == 1
s = s.replace(a, b).replace("    time.sleep(6)\n", "    time.sleep(RUST)\n")
ast.parse(s)
shutil.copy2(pad, pad + ".voor-rust-" + time.strftime("%Y%m%d-%H%M"))
open(pad, "w").write(s); print("kijker.py: rust instelbaar (AMBER_KIJKER_RUST), leest goed")
