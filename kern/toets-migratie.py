"""
Toetst de migratie — oud en nieuw moeten exact hetzelfde doen.

Elke vertaalde module krijgt hier zijn gelijkheids-toetsen: de Engelse
versie naast de Nederlandse, zelfde invoer, en het antwoord moet bit voor
bit gelijk zijn. Groeit mee met de migratie; als álles vertaald is en de
Nederlandse bestanden verdwijnen, vervalt dit bestand samen met hen.

De sleutelbrug (netwerk -> network) heeft zijn eigen toets:
toets-sleutelbrug.py, want die heeft het echte checkpoint nodig.

Draaien:  venv/bin/python kern/toets-migratie.py
"""

import determinisme                        # MOET vóór torch
determinisme.zet_vast(1234)

import sys

import determinism                         # mag ná determinisme: env staat al
import taken
import tekens
import tokens

geslaagd = 0
gefaald = 0


def toets(naam, goed, toelichting=""):
    global geslaagd, gefaald
    if goed:
        geslaagd += 1
        print(f"[  OK  ] {naam}")
    else:
        gefaald += 1
        print(f"[ FOUT ] {naam}")
    if toelichting:
        print(f"         {toelichting}")


print("=" * 70)
print("Toets — migratie (Nederlands en Engels doen exact hetzelfde)")
print("=" * 70)
print()

# --- tekens <-> tokens -----------------------------------------------------

print("--- tekens -> tokens ---")
toets("de vier eigen tekens en de omvang zijn dezelfde getallen",
      (tokens.QUESTION, tokens.ANSWER, tokens.END, tokens.PAD, tokens.VOCAB)
      == (tekens.VRAAG, tekens.ANTWOORD, tekens.EIND, tekens.VUL,
          tekens.OMVANG),
      "verschuiven die, dan wijst elke inbedding naar iets anders")

proeven = ["47 * 13", "Zet voort: 3, 6, 9, ?", "één röntgenfoto — ß≤ǿ",
           "a = 26\nb = 61\nprint(a - b)"]
toets("coderen is identiek op alles wat we haar voorleggen",
      all(tokens.encode(t) == tekens.codeer(t) for t in proeven))
toets("decoderen is identiek, ook met eigen tekens ertussen",
      all(tokens.decode([tekens.VRAAG] + tekens.codeer(t) + [tekens.EIND])
          == tekens.decodeer([tekens.VRAAG] + tekens.codeer(t) + [tekens.EIND])
          for t in proeven))

taak = taken.maak("rekenen", 3, 900)
r_nl, m_nl = tekens.taak_naar_reeks(taak)
r_en, m_en = tokens.task_to_sequence(taak)
toets("een taak wordt exact dezelfde reeks en hetzelfde masker",
      r_nl == r_en and m_nl == m_en)
toets("de vraagreeks en het teruglezen van een antwoord zijn gelijk",
      tekens.vraag_naar_reeks(taak) == tokens.question_to_sequence(taak)
      and tekens.antwoord_uit_reeks(r_nl) == tokens.answer_from_sequence(r_en))

b_nl = tekens.bundel([r_nl, r_nl[:9]], [m_nl, m_nl[:9]])
b_en = tokens.batch([r_en, r_en[:9]], [m_en, m_en[:9]])
toets("bundelen met opvulling is gelijk", b_nl == b_en)

# --- determinisme <-> determinism ------------------------------------------

print()
print("--- determinisme -> determinism ---")
toets("dezelfde zaad-afleiding, over een reeks stappen",
      all(determinisme.zaad_voor_stap(s, zaad=777)
          == determinism.seed_for_step(s, seed=777)
          for s in (0, 1, 2, 100, 170_000, 10**12)))

determinism.lock(1234)
toets("lock() zet en controleert dezelfde vlaggen",
      determinism.verify() and determinisme.controleer())
# De afleidingsbeschrijving is documentatie en heet in elke taal anders;
# het gedrág is hierboven al bewezen gelijk. Alleen het zaad moet kloppen.
toets("de stand meldt hetzelfde zaad",
      determinism.state()["seed"] == determinisme.stand()["zaad"])
toets("begin_step en begin_stap geven hetzelfde stapzaad",
      determinism.begin_step(41) == determinisme.begin_stap(41))

print()
print("=" * 70)
print(f"geslaagd: {geslaagd}    gefaald: {gefaald}")
print("=" * 70)
sys.exit(0 if gefaald == 0 else 1)
