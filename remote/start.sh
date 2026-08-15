#!/bin/bash
# Start Remote Control voor de mobiele app.
# De "y" beantwoordt de vraag "Enable Remote Control? (y/n)" —
# onder systemd is er niemand die op y drukt (gevonden 13 aug 2026).
# --effort bestaat niet op het remote-control-subcommando (13 aug 2026,
# crashlus): de effort staat daarom in ~/.claude/settings.json.
echo y | /home/arch/.local/bin/claude remote-control --name "Amber DL380"
