#!/usr/bin/env bash
# Eenmalige inrichting van de Z490 als Amber-trainer (12 aug 2026).
# Draaien als gebruiker arch met sudo-rechten. Recept: x399-recept.txt.
set -e

echo "== 1. systeem en gereedschap =="
sudo pacman -Syu --noconfirm \
  nvidia-open nvidia-utils \
  lm_sensors fastfetch htop \
  base-devel git go \
  python python-pip \
  openssh sshpass rsync
sudo systemctl enable --now sshd

echo "== 2. sensoren aanleren =="
sudo sensors-detect --auto || true

echo "== 3. torch (het recept van de X399: 2.12.1+cu130) =="
python3 -m pip install --break-system-packages \
  torch==2.12.1 --index-url https://download.pytorch.org/whl/cu130

echo "== 4. Claude Code (native installer, werkt zichzelf bij) =="
curl -fsSL https://claude.ai/install.sh | bash

echo "== 5. OpenLinkHub voor de Corsair iCUE Link-fans (AUR) =="
T=$(mktemp -d)
git clone https://aur.archlinux.org/openlinkhub.git "$T/openlinkhub" \
  && cd "$T/openlinkhub" && makepkg -si --noconfirm \
  && sudo systemctl enable --now openlinkhub \
  && echo "OpenLinkHub draait — webpaneel op poort 27003" \
  || echo "LET OP: AUR-bouw mislukt; Claude pakt dit straks handmatig op"
cd ~

echo "== 6. mappen voor Amber =="
mkdir -p ~/amber-werk/fase1/leven

echo
echo "KLAAR — herstart nu één keer voor de NVIDIA-driver:  sudo reboot"
