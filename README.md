# Bazzite + Moonlight: on-demand virtual display at your phone's native resolution

Stream a Bazzite GNOME laptop to an Android phone with Sunshine/Moonlight in **true fullscreen**: no black bars, no scaling.

A virtual display at the phone's exact resolution **exists only while Moonlight is connected**:

- **Connect:** the virtual display is created, the laptop panel turns off, and Steam Big Picture or any game opens on the phone.
- **Quit:** everything goes back to the laptop screen.

Nothing is added at boot.

## Tested on

| | |
|---|---|
| OS | Bazzite GNOME (Fedora 44), Wayland |
| GPU | AMD Radeon 780M (amdgpu) |
| Host | Sunshine **flatpak** (`dev.lizardbyte.app.Sunshine` 2026.914) |
| Client | Moonlight on a Google Pixel 9 Pro, "Max" resolution: **2856×1280 @ 60 Hz** |

## How it works

1. A disconnected GPU connector (here `DP-2`) is turned into a fake monitor by forcing an EDID through debugfs (`scripts/virtual-display.sh`, run as root through a narrow sudo rule).
2. Sunshine's `global_prep_cmd` runs `scripts/moonlight-display`:
   - **`on`** runs when a client launches an app:
     1. load the portal token for the virtual display;
     2. create the display;
     3. use `gdctl` to leave **only** the virtual display active;
     4. start a watcher for the rest of the session. It gives the laptop back if the capture doesn't start within 20 s, or if the client disconnects **without Quit** and doesn't reconnect within `GRACE` (2 min).
   - **`off`** runs on Quit: load the laptop token and remove the virtual display. GNOME restores the laptop layout by itself.
3. A systemd drop-in runs `off` every time Sunshine starts, so a reboot mid-stream always starts clean.

Why the pieces are shaped this way is explained in [Pitfalls](#pitfalls-found-along-the-way).

## Setup

Replace `DP-2`, the PCI path, the resolution and `YOUR_USER` with your own values throughout.

### 1. Find a free connector and the debugfs path

```bash
for p in /sys/class/drm/*/status; do c=${p%/status}; echo "${c#*/card?-}: $(cat $p)"; done
sudo find /sys/kernel/debug/dri/ -maxdepth 2 -name edid_override
```

Pick a connector that shows `disconnected`. Note the directory that contains it. On recent kernels this is the PCI address, e.g. `/sys/kernel/debug/dri/0000:c1:00.0/DP-2`, **not** `dri/0`. Set `DRI` and `CONNECTOR` in `scripts/virtual-display.sh`, and the same `CONNECTOR` in `scripts/moonlight-display`.

### 2. EDID

For a Pixel 9 Pro at 2856×1280@60 you can use [`edid/2856x1280.bin`](edid/2856x1280.bin) directly. For another resolution, build one with [edid-generator](https://github.com/akatrevorjay/edid-generator) inside a distrobox (Bazzite is immutable):

```bash
distrobox enter ubuntu
sudo apt install -y zsh edid-decode automake dos2unix git build-essential
git clone https://github.com/akatrevorjay/edid-generator && cd edid-generator
./modeline2edid - <<< 'Modeline "2856x1280" 307.60  2856 3048 3360 3864  1280 1283 1293 1328 -hsync +vsync ratio=16:9'
make    # produces 2856x1280.bin
```

- The argument of `modeline2edid` is the **input** (`-` = stdin). The output file name comes from the modeline's name. Redirecting stdout mixes log lines into the `.S` file.
- `ratio=16:9` is required for phone aspect ratios. The tool only knows 16:10, 16:9, 4:3 and 5:4, and silently writes nothing otherwise. The value only affects a cosmetic byte; the real mode comes from the detailed timing.
- A warning like `value 0x146 truncated` is harmless. The legacy "standard timing" field can't hold widths above 2288 px, so it only adds an odd extra mode (e.g. `808x454`).

Get the modeline from any CVT calculator (`cvt 2856 1280 60`). Install the result:

```bash
sudo mkdir -p /usr/local/lib/firmware
sudo cp 2856x1280.bin /usr/local/lib/firmware/
```

### 3. Scripts, sudo rule, systemd drop-in

```bash
sudo install -o root -g root -m 0755 scripts/virtual-display.sh /usr/local/sbin/virtual-display.sh
install -m 0755 scripts/moonlight-display ~/.local/bin/moonlight-display

sed "s/YOUR_USER/$USER/" config/virtual-display.sudoers > /tmp/virtual-display
sudo visudo -cf /tmp/virtual-display && sudo install -o root -g root -m 0440 /tmp/virtual-display /etc/sudoers.d/virtual-display

mkdir -p ~/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d
cp config/moonlight-display.conf ~/.config/systemd/user/app-dev.lizardbyte.app.Sunshine.service.d/
systemctl --user daemon-reload
```

Test: `sudo -n /usr/local/sbin/virtual-display.sh on` must work **without a password**. `gnome-control-center display` should show the new monitor at the right resolution. Turn it off again with `... off`.

### 4. Sunshine config

In `~/.var/app/dev.lizardbyte.app.Sunshine/config/sunshine/`:

- `sunshine.conf`: see [`config/sunshine.conf.example`](config/sunshine.conf.example). Use the absolute path, and **do not set `output_name`**.
- `apps.json`: add the "Steam Big Picture" entry from [`config/apps.json.example`](config/apps.json.example).

### 5. One-time portal permissions (two tokens)

The flatpak captures the screen through the GNOME portal. The portal remembers **which monitors** you allowed, so two tokens are needed. Both dialogs must be accepted **on the laptop screen**, where you can see them.

```bash
S=~/.var/app/dev.lizardbyte.app.Sunshine/config/sunshine

# a) laptop only
sudo -n /usr/local/sbin/virtual-display.sh off
rm -f $S/portal_token; systemctl --user restart sunshine
#    -> accept the GNOME dialog ("Built-in display"), then:
cp $S/portal_token $S/portal_token.edp

# b) virtual display (keep the laptop on so the dialog is visible)
sudo -n /usr/local/sbin/virtual-display.sh on
rm -f $S/portal_token; systemctl --user restart sunshine
#    -> accept the GNOME dialog, then:
cp $S/portal_token $S/portal_token.dp2
sudo -n /usr/local/sbin/virtual-display.sh off
systemctl --user restart sunshine    # the drop-in loads the laptop token
```

### 6. Moonlight

1. Settings → Resolution: add a custom **2856×1280** at **60 FPS**.
2. Launch **Steam Big Picture**.
3. Use **Quit** to end the session and bring the laptop back right away. Quit is in the in-stream menu, or long-press the app → Quit session.
4. A plain disconnect (back button, Wi-Fi drop) leaves the app running, so it can be resumed. The laptop comes back after `GRACE` (2 minutes).
5. If you reconnect **after** that, Sunshine resumes the app without running `do`. You get the laptop panel with black bars: Quit and launch again.

## Pitfalls found along the way

- **Sunshine probes the encoder before running `prep-cmd`.** At launch it checks that it can capture a display, and only then runs `do`. So the probe always happens on the laptop panel. The virtual display is only captured when the stream starts.
- **Sunshine splits commands understanding only double quotes.** `sh -c '...'` in `prep-cmd` fails with exit code 2. Keeping all the logic in a script avoids quoting entirely.
- **GNOME portal tokens are tied to specific monitors:**
  - A token restores only while its monitors exist.
  - A missing or revoked token makes GNOME open a permission dialog, and Sunshine waits on it indefinitely.
  - If that dialog opens on a monitor nobody sees (the laptop is off during the stream), the machine looks frozen.
  - Hence the two tokens, the refusal to run `on` without `.dp2`, and the 20-second check in the watcher.
- **Disconnect is not Quit.** Sunshine runs `undo` only when the app is terminated. On a disconnect it keeps the app alive for resuming, so with the laptop panel turned off the screen stayed black until a forced reboot. The watcher follows `CLIENT DISCONNECTED` / `CLIENT CONNECTED` in `sunshine.log` and runs `off` after `GRACE`.
- **`output_name` caused the laptop token to be revoked.** With `output_name = DP-2`, every probe on the laptop logged `no matching stream was found for: 'DP-2'`, and the laptop token kept getting revoked after a restart or two. Removing `output_name` stopped it. This is observed behavior, not proven from source.
- **With the laptop panel left on during the stream, game windows split across both screens.** This happens with XWayland/Proton titles and mixed scaling. Keeping only the virtual display active fixes it, and Steam then has only one screen to open on.
- **`gdctl set` without `-P` is temporary.** When the virtual display disappears, GNOME re-applies the saved laptop-only layout, top bar included.

## Recovery

If the screen stays black:

- press `Super+P` to cycle display modes;
- or run `~/.local/bin/moonlight-display off`, e.g. over SSH.

If Moonlight fails with a generic "check your firewall" error after a reboot, check `sunshine.log` for `response code: 1` or `Fatal`. A portal dialog was probably dismissed. Accept it (step 5a) and copy the new token to `portal_token.edp`. The script also picks up a renewed laptop token by itself on the next `on`/`off`.

## Credits

- Original guide this setup started from: <https://feddit.org/post/12000513>
- [akatrevorjay/edid-generator](https://github.com/akatrevorjay/edid-generator)
- [Sunshine](https://github.com/LizardByte/Sunshine) by LizardByte
- [Moonlight](https://moonlight-stream.org/)
- [Bazzite](https://bazzite.gg/) / Universal Blue

## License

MIT
