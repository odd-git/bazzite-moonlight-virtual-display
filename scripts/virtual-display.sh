#!/bin/bash
# Turns a fake monitor on/off by forcing an EDID on a disconnected GPU connector. Runs as root.
# Usage: virtual-display.sh on|off
# Find your values with: sudo find /sys/kernel/debug/dri/ -maxdepth 2 -name edid_override
DRI=/sys/kernel/debug/dri/0000:c1:00.0   # on recent kernels the PCI address, not always dri/0
CONNECTOR=DP-2                            # a connector that reports "disconnected"
EDID=/usr/local/lib/firmware/virtual.bin   # both modes: edid/virtual.bin

C=$DRI/$CONNECTOR
case "$1" in
  on)  cat "$EDID" > "$C/edid_override"; echo on > "$C/force" ;;
  off) echo off > "$C/force" ;;
  *)   echo "usage: $0 on|off" >&2; exit 1 ;;
esac
echo 1 > "$C/trigger_hotplug"
