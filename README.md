# Truly

A recoil control script with a web UI, powered by a makcu.
The default config has R6 guns but you can use it for any game.

## Requirements

- Python 3.10+
- A makcu

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
