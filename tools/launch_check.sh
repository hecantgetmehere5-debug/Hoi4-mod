#!/bin/bash
# Launch HOI4 with the mod enabled and report whether it gets through map loading.
# Prints OK when the game reaches the main menu stage, CRASH if it exits first.
# Usage: tools/launch_check.sh [seconds_to_keep_running_after_ok]
# Set HANDS_OFF=1 to start a game automatically (as NDefines.NGame.HANDS_OFF_START_TAG) and wait for days to pass.
# Set DEBUG=1 to launch with -debug: the game then logs map validation errors to error.log instead of stopping.
D="$HOME/Documents/Paradox Interactive/Hearts of Iron IV"
G="$HOME/Library/Application Support/Steam/steamapps/common/Hearts of Iron IV"
KEEP="${1:-0}"
echo '{"enabled_mods":["mod/norway_civil_war.mod"],"disabled_dlcs":[]}' > "$D/dlc_load.json"
pkill -x hoi4 2>/dev/null
sleep 1
(cd "$G" && nohup ./hoi4.app/Contents/MacOS/hoi4 --skiplauncher ${DEBUG:+-debug} ${HANDS_OFF:+-hands_off} > /tmp/hoi4_launch_check.txt 2>&1 &)
sleep 3
for _ in $(seq 1 90); do
  sleep 2
  if [ -n "$HANDS_OFF" ] && grep -q "Launching SINGLEPLAYER-game" "$D/logs/game.log" 2>/dev/null; then
    for _ in $(seq 1 30); do sleep 2; pgrep -xq hoi4 || { echo CRASH; exit 1; }; done
    echo "OK (game still running 60 s after it started)"; pkill -x hoi4; exit 0
  fi
  if [ -z "$HANDS_OFF" ] && grep -q "Startup time" "$D/logs/game.log" 2>/dev/null; then
    echo OK
    sleep "$KEEP"
    [ "$KEEP" = 0 ] && pkill -x hoi4
    exit 0
  fi
  pgrep -xq hoi4 || { echo CRASH; tail -3 "$D/logs/game.log"; tail -2 "$D/logs/setup.log"; exit 1; }
done
echo TIMEOUT
pkill -x hoi4
exit 2
