# Het oog — kopie voor de back-up

De levende versie staat in `/home/arch/oog/` (dienst `amber-oog`); dit is
de kopie die meegaat in de back-up, zoals `fase2/stem/` dat voor de
spraak is.

Herbouwen op een kale machine:

    ~/.pyenv/versions/3.11.9/bin/python3.11 -m venv ~/oog/oog-venv
    echo "/home/arch/amber-werk/venv/lib/python3.11/site-packages" \
      > ~/oog/oog-venv/lib/python3.11/site-packages/amber-torch.pth
    ~/oog/oog-venv/bin/pip install "transformers==4.51.3" \
      "qwen-vl-utils==0.0.8" pillow
    ~/oog/oog-venv/bin/pip install --no-deps torchvision==0.19.1 \
      --index-url https://download.pytorch.org/whl/cu121

De `.pth`-brug leent torch 2.4.1+cu121 uit de amber-venv (Pascal!), en
torchvision moet met `--no-deps` zodat pip geen nieuwe torch meetrekt.
Het model (Qwen/Qwen2.5-VL-3B-Instruct, ~7 GB) haalt zichzelf bij de
eerste start naar ~/.cache/huggingface.
