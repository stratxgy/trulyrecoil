# Truly
> [!CAUTION]
> I forgot to account for different DPI's and sensitivities (😭) I'll fix it in the next update but right now its 4-4 800 dpi 60 holo 67 acog advanced zoom settings

A recoil control script with a web UI, powered by a makcu.

The default config has R6 guns but you can use it for any game.

## Preview

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
```bash
pip install -r requirements.txt
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
Save and load per-gun settings from the web UI. Configs are stored in `configs.json` (created automatically).
## Accessing from another device
Both devices must be on the same network (same Wi-Fi/LAN). Use the IP address shown in the console on port 8000.
