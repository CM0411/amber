#!/bin/bash
# Start Remote Control voor de mobiele app (Z490).
# De "y" beantwoordt de vraag "Enable Remote Control? (y/n)" —
# onder systemd is er niemand die op y drukt (gevonden 13 aug 2026).
echo y | /home/arch/.local/bin/claude remote-control --name "Amber Z490"
