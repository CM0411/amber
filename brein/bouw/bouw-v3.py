"""Bouwt index-v3.html, de Sterrenwacht: v3-kop.html (glas, kop, rail,
instrumenten, vensters) + v3-ruimte.js (het brein in de ruimte en de
microscoop) + de bewezen tekenfuncties uit v2-kop.html (cijfers, kaarten,
gesprek, antwoord, stem), letterlijk overgenomen.
"""
import pathlib, re

HIER = pathlib.Path(__file__).parent
v2 = (HIER / "v2-kop.html").read_text()
a = v2.index("/* ---- toast ---- */")
b = v2.index("/* ---- de kraan: stand.json elke 5 s ---- */")
functies = v2[a:b].rstrip() + "\n"
assert "function tekenGesprek" in functies and "function antwoordCley" in functies and "function meterHtml" in functies

kop = (HIER / "v3-kop.html").read_text()
ruimte = (HIER / "v3-ruimte.js").read_text()
assert kop.count("/*__RUIMTE__*/") == 1 and kop.count("/*__V2_FUNCTIES__*/") == 1
uit = kop.replace("/*__RUIMTE__*/", ruimte).replace("/*__V2_FUNCTIES__*/", functies)

# alles wat de functies aanspreken moet er als id in staan
ids = set(re.findall(r'\$\("([a-z0-9-]+)"\)', uit))
aanwezig = set(re.findall(r'id="([a-z0-9-]+)"', uit))
dyn = {"lv-stap", "lv-balk", "lv-nog", "lv-klaar"}          # komen uit tekenCijfers zelf
mis = sorted(ids - aanwezig - dyn)
assert not mis, f"ids die ontbreken: {mis}"
(HIER / "index-v3.html").write_text(uit)
print(f"index-v3.html: {len(uit)} tekens (ruimte {len(ruimte)}, v2-functies {len(functies)}); alle {len(ids)} ids aanwezig")
