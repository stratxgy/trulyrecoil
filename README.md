# Truly
> [!CAUTION]
> This program does not automatically account for your dpi, sens, windows sens or any other sensitivities. If you do not want to match my settings, then you will have to manually tweak the values. The current sens for r6 is 4-4 800 dpi 60 holo 67 acog advanced zoom

> [!IMPORTANT]
> The MAKXD (the new makcu) will have built-in advanced RCS, effectively making this tool obsolete. It is not clear whether it will work on the old Makcu, but either way this will stop being maintained eventually due to that issue. Also, if the recoil is slightly off make sure your windows mouse sensitivity is set to the default.

> [!NOTE]  
> To do: add option to only pull when LMB and RMB are held.
> Add the option for no toggle button

A recoil control script with a web UI, powered by a makcu.

I've not tried it, but people say it works on 1pc.

The default config has R6 and Rust guns but you can use it for any game.
(featured in a Camomo video when??)

## Preview

### The GOAT 👑 (idk who this is)
<img src="https://github.com/stratxgy/stratxgy.github.io/blob/main/trulyimages/trulyr6.jpg" width="850"/>


### Web UI
<img src="https://raw.githubusercontent.com/stratxgy/stratxgy.github.io/main/trulyimages/ui.png" width="250"/>

### Demo
[![Truly Demo](https://img.youtube.com/vi/ysIKCjLv5eo/maxresdefault.jpg)](https://www.youtube.com/watch?v=ysIKCjLv5eo)

## Requirements
- Python 3.10+
- A makcu
  
> [!NOTE]
> By default, the recoil is set to work with the flash hider + vertical grip on ALL guns.
## Setup
Download the release, then run (terminal)
```bash
pip install -r requirements.txt
```
If you don't have port 8000 allowed it won't work (powershell)
```powershell
New-NetFirewallRule -DisplayName "Open Port 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000
```
## Usage
```bash
python truly.py
```
The console will print the URL to open:
```
  Open on this PC:      http://localhost:8000
  Open on another PC:   http://192.168.x.x:8000
```
Open that URL in any browser (works from your phone too).
## Controls
- **Vertical (Pull-down)** -- how much the mouse pulls down while holding LMB
- **Horizontal (Side-to-side)** -- left/right compensation (negative = left, positive = right)
- **Horizontal Delay** -- how long LMB must be held before horizontal kicks in (ms)
- **Horizontal Duration** -- how long horizontal lasts after the delay (0 = forever)
- **Toggle key** -- choose which mouse button (M4, M5, or Middle Mouse) toggles recoil on/off
## Gun Configs
Save and load per-gun settings from the web UI. Configs are stored in `configs/(yourgame)` (created automatically).
## Accessing from another device
Both devices must be on the same network (same Wi-Fi/LAN). Use the IP address shown in the console on port 8000.
