#!/usr/bin/env bash
# De brug — de postbode tussen de Z490 (venster, altijd aan) en de DL380
# (gesprek, oren, mond, oog — als hij aanstaat). Sinds 14 aug 2026; de
# kijker woont sinds 16 aug 2026 op de Z490 zelf.
#
# Het venster op de Z490 schrijft wat Cley doet in lokale mappen; deze lus
# haalt dat hierheen (verplaatsen, niet kopiëren) en duwt terug wat de
# GPU-diensten maken. Alles is bestandsgebaseerd en atomair (.deel of een
# hernoeming binnen dezelfde schijf), dus een halve overdracht bestaat niet.
#
# Draait als dienst (amber-brug) zolang de DL380 aan is. Valt de Z490 even
# weg, dan wacht de lus rustig — er verdampt niets, alles blijft liggen.

set -u

Z=arch@192.168.1.239
BREIN=/home/arch/amber-werk/brein
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=5)
RS=(rsync -a --timeout=30 -e "ssh -o BatchMode=yes -o ConnectTimeout=5")

# De foto-soorten van beelden.py: die blijven op de Z490 (daar draait de
# opvang) en gaan apart als kopie naar het oog — niet via de inbox-route.
FOTO_WEG=()
for e in jpg jpeg png heic heif webp gif JPG JPEG PNG HEIC HEIF WEBP GIF; do
    FOTO_WEG+=(--exclude "*.$e")
done

mkdir -p /home/arch/inbox /home/arch/spraak/zeg-wachtrij \
         /home/arch/spraak-uit-staging \
         "$BREIN/vraag-wachtrij" "$BREIN/gesprek-inbox"

ronde() {
    # ophalen (verplaatsen): wat Cley via het venster instuurde
    "${RS[@]}" --remove-source-files --exclude '*.deel' "${FOTO_WEG[@]}" \
        "$Z:inbox/" /home/arch/inbox/ 2>/dev/null
    "${RS[@]}" --remove-source-files --exclude '*.deel' \
        "$Z:amber-werk/brein/gesprek-inbox/" "$BREIN/gesprek-inbox/" 2>/dev/null
    # de vraag-wachtrij blijft sinds 16 aug 2026 op de Z490: de kijker die
    # de vragen beantwoordt woont daar nu zelf (amber-kijker op de Z490, CPU)

    # spraakverzoeken: eerst naar een tussenmap, dan pas de zeg-wachtrij in —
    # de mond pakt elk bestand dat hij daar ziet, ook een half geschreven
    "${RS[@]}" --remove-source-files --exclude '*.deel' \
        "$Z:spraak-uit/" /home/arch/spraak-uit-staging/ 2>/dev/null
    for f in /home/arch/spraak-uit-staging/*.txt; do
        [[ -e $f ]] && mv "$f" /home/arch/spraak/zeg-wachtrij/
    done

    # foto's voor het oog: kopie hierheen (het archief blijft op de Z490)
    "${RS[@]}" "$Z:amber-werk/fase2/beelden/" \
        /home/arch/amber-werk/fase2/beelden/ 2>/dev/null

    # terugduwen: wat de GPU-diensten maakten, voor de pagina's
    # stand.json, vraag-antwoord.json en herinneringen.json komen sinds
    # 16 aug 2026 van de kijker op de Z490 zelf — hier niet meer terugduwen,
    # anders overschrijft een oude kopie van hier de verse daar
    "${RS[@]}" "$BREIN/gesprek.json" "$BREIN/gesprek-verwerkt.json" \
        "$Z:amber-werk/brein/" 2>/dev/null
    "${RS[@]}" --include '*.wav' --include 'gehoord.json' \
        --include 'gesprek.json' --include 'gezien.json' --exclude '*' \
        /home/arch/rapport/ "$Z:rapport/" 2>/dev/null
    "${RS[@]}" /home/arch/amber-werk/wachter/stand.json \
        "$Z:amber-werk/wachter/" 2>/dev/null
    [[ -f /home/arch/amber/uren-live.json ]] && \
        "${RS[@]}" /home/arch/amber/uren-live.json "$Z:amber/" 2>/dev/null

    # de brievenbus: regels die hier geschreven zijn (oren, gesprek, oog)
    # aanhangen bij de échte brievenbus op de Z490. Eerst wegdraaien, dan
    # verzenden — een schrijver die er middenin aanhangt raakt niets kwijt.
    local bb=/home/arch/amber-werk/fase1/brievenbus.jsonl
    if [[ -s $bb.verzend ]] || { [[ -s $bb ]] && mv "$bb" "$bb.verzend"; }; then
        # onder het gedeelde slot aanhangen: de bezorging op de Z490 wisselt
        # het bestand om bij het afvinken, en zonder slot kan dit aanhangsel
        # dan stil verdwijnen
        if ssh "${SSH_OPTS[@]}" "$Z" \
                "flock ~/amber-werk/fase1/brievenbus.jsonl.slot -c \
                 'cat >> ~/amber-werk/fase1/brievenbus.jsonl'" \
                < "$bb.verzend"; then
            rm -f "$bb.verzend"
        fi
    fi
}

echo "brug wakker" >&2
while true; do
    if ssh "${SSH_OPTS[@]}" "$Z" true 2>/dev/null; then
        ronde
        sleep 3
    else
        sleep 20
    fi
done
