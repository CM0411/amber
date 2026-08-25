#!/bin/zsh
# foto.sh <tag> <breedte> <hoogte> <budget-ms> <uit.png|dom> <url>  -- headless Chrome met een waakhond van 45 s
tag=$1; b=$2; h=$3; budget=$4; uit=$5; url=$6
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
rm -rf "/tmp/chr-$tag"; 
if [ "$uit" = "dom" ]; then
  "$CH" --headless=new --disable-gpu --hide-scrollbars --window-size=$b,$h --user-data-dir=/tmp/chr-$tag --virtual-time-budget=$budget --dump-dom "$url" > "dom-$tag.html" 2>/dev/null &
else
  "$CH" --headless=new --disable-gpu --hide-scrollbars --window-size=$b,$h --user-data-dir=/tmp/chr-$tag --virtual-time-budget=$budget --screenshot="$uit" "$url" >/dev/null 2>&1 &
fi
pid=$!
for i in {1..45}; do sleep 1; kill -0 $pid 2>/dev/null || break; done
if kill -0 $pid 2>/dev/null; then kill -9 $pid 2>/dev/null; pkill -9 -f "chr-$tag" 2>/dev/null; echo "$tag: afgebroken na 45 s"; else echo "$tag: klaar na $i s"; fi
