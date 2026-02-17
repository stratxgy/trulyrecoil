import threading
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import json
import os
import socket
import time



from mouse.makcu import makcu_controller

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'configs.json')

class GunConfig(BaseModel):
    gun_name: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_\- ]+$')
    pull_down_value: float = Field(..., ge=0, le=300)
    horizontal_value: float = Field(default=0, ge=-300, le=300)
    horizontal_delay_ms: int = Field(default=500, ge=0, le=5000)
    horizontal_duration_ms: int = Field(default=2000, ge=0, le=10000)

def read_configs():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[CONFIG] Error reading configs: {e}")
        return {}

def write_configs(configs):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=4)
    except OSError as e:
        print(f"[CONFIG] Error writing configs: {e}")

VALID_TOGGLE_BUTTONS = ["MMB", "M4", "M5"]

class AppState:
    def __init__(self):
        self.active_pull_down_value = 1.0
        self.active_horizontal_value = 0.0
        self.horizontal_delay_ms = 500
        self.horizontal_duration_ms = 2000
        self.is_enabled = False
        self.toggle_button = "M5"
        self.lock = threading.Lock()

    def set_active_value(self, value):
        with self.lock:
            self.active_pull_down_value = value

    def get_active_value(self):
        with self.lock:
            return self.active_pull_down_value

    def set_horizontal_value(self, value):
        with self.lock:
            self.active_horizontal_value = value

    def get_horizontal_value(self):
        with self.lock:
            return self.active_horizontal_value

    def set_horizontal_delay(self, ms):
        with self.lock:
            self.horizontal_delay_ms = max(0, min(5000, ms))

    def get_horizontal_delay(self):
        with self.lock:
            return self.horizontal_delay_ms

    def set_horizontal_duration(self, ms):
        with self.lock:
            self.horizontal_duration_ms = max(0, min(10000, ms))

    def get_horizontal_duration(self):
        with self.lock:
            return self.horizontal_duration_ms

    def get_enabled(self):
        with self.lock:
            return self.is_enabled

    def toggle_enabled(self):
        with self.lock:
            self.is_enabled = not self.is_enabled
            return self.is_enabled

    def set_toggle_button(self, button):
        with self.lock:
            if button in VALID_TOGGLE_BUTTONS:
                self.toggle_button = button
                return self.toggle_button
            return None

    def get_toggle_button(self):
        with self.lock:
            return self.toggle_button

    def get_status(self):
        with self.lock:
            return {
                "is_enabled": self.is_enabled,
                "toggle_button": self.toggle_button,
                "pull_down": self.active_pull_down_value,
                "horizontal": self.active_horizontal_value,
                "horizontal_delay_ms": self.horizontal_delay_ms,
                "horizontal_duration_ms": self.horizontal_duration_ms,
            }

app_state = AppState()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    thread = threading.Thread(target=mouse_control_loop, daemon=True)
    thread.start()
    yield

app = FastAPI(lifespan=lifespan)

def mouse_control_loop():
    makcu_controller.StartButtonListener()
    toggle_was_pressed = False
    lmb_hold_start = None
    while True:
        if not makcu_controller.is_connected():
            time.sleep(0.5)
            makcu_controller.connect()
            continue

        btn = app_state.get_toggle_button()
        toggle_pressed = makcu_controller.get_button_state(btn)
        if toggle_pressed and not toggle_was_pressed:
            app_state.toggle_enabled()
        toggle_was_pressed = toggle_pressed

        lmb_down = makcu_controller.get_button_state("LMB")

        if app_state.get_enabled() and lmb_down:
            now = time.time()
            if lmb_hold_start is None:
                lmb_hold_start = now

            pull_value = app_state.get_active_value()
            y_move = round(pull_value / 5) if pull_value > 0 else 0

            x_move = 0
            hold_ms = (now - lmb_hold_start) * 1000
            delay = app_state.get_horizontal_delay()
            duration = app_state.get_horizontal_duration()
            if hold_ms >= delay and (duration == 0 or hold_ms <= delay + duration):
                h_value = app_state.get_horizontal_value()
                x_move = round(h_value / 5)

            if y_move != 0 or x_move != 0:
                makcu_controller.simple_move_mouse(x_move, y_move)
        else:
            lmb_hold_start = None

        time.sleep(0.01)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if "pull_down" in msg:
                    app_state.set_active_value(float(msg["pull_down"]))
                if "horizontal" in msg:
                    app_state.set_horizontal_value(float(msg["horizontal"]))
                if "horizontal_delay_ms" in msg:
                    app_state.set_horizontal_delay(int(msg["horizontal_delay_ms"]))
                if "horizontal_duration_ms" in msg:
                    app_state.set_horizontal_duration(int(msg["horizontal_duration_ms"]))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
    except WebSocketDisconnect:
        pass

@app.get("/status", response_class=JSONResponse)
async def get_status():
    return app_state.get_status()

@app.post("/toggle", response_class=JSONResponse)
async def toggle_status():
    is_enabled = app_state.toggle_enabled()
    return {"is_enabled": is_enabled}

class ToggleButtonConfig(BaseModel):
    button: str

@app.post("/toggle-button", response_class=JSONResponse)
async def set_toggle_button(config: ToggleButtonConfig):
    result = app_state.set_toggle_button(config.button)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Invalid button. Must be one of: {VALID_TOGGLE_BUTTONS}")
    return {"toggle_button": result}

@app.get("/configs", response_class=JSONResponse)
async def get_configs():
    return read_configs()

@app.post("/configs", response_class=JSONResponse)
async def create_config(config: GunConfig):
    configs = read_configs()
    configs[config.gun_name] = {
        "pull_down": config.pull_down_value,
        "horizontal": config.horizontal_value,
        "horizontal_delay_ms": config.horizontal_delay_ms,
        "horizontal_duration_ms": config.horizontal_duration_ms,
    }
    write_configs(configs)
    return {"message": "Config saved successfully."}

@app.delete("/configs/{gun_name}", response_class=JSONResponse)
async def delete_config(gun_name: str):
    configs = read_configs()
    if gun_name not in configs:
        raise HTTPException(status_code=404, detail="Config not found.")
    del configs[gun_name]
    write_configs(configs)
    return {"message": "Config deleted successfully."}
    
@app.get("/", response_class=HTMLResponse)
async def get():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Truly</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            * { margin: 0; padding: 0; box-sizing: border-box; }

            body {
                font-family: 'Inter', sans-serif;
                background: #0f0f0f;
                color: #e0e0e0;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                padding: 40px 16px;
            }

            .container {
                max-width: 440px;
                width: 100%;
                animation: fadeInUp 0.5s ease-out;
            }

            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @keyframes pulse {
                0%, 100% { box-shadow: 0 0 0 0 rgba(99, 255, 150, 0.4); }
                50% { box-shadow: 0 0 20px 4px rgba(99, 255, 150, 0.15); }
            }

            @keyframes pulseOff {
                0%, 100% { box-shadow: 0 0 0 0 rgba(255, 80, 80, 0.3); }
                50% { box-shadow: 0 0 20px 4px rgba(255, 80, 80, 0.1); }
            }

            h1 {
                font-size: 2.4em;
                font-weight: 700;
                letter-spacing: -1px;
                color: #fff;
                margin-bottom: 32px;
                text-align: center;
            }

            .card {
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 12px;
                transition: border-color 0.3s ease, transform 0.2s ease;
            }

            .card:hover {
                border-color: #3a3a3a;
                transform: translateY(-1px);
            }

            .card-label {
                font-size: 0.75em;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #666;
                margin-bottom: 12px;
            }

            #toggle-btn {
                width: 100%;
                padding: 16px;
                border: 2px solid #2a2a2a;
                border-radius: 10px;
                font-size: 1.1em;
                font-weight: 600;
                font-family: 'Inter', sans-serif;
                cursor: pointer;
                transition: all 0.3s ease;
                background: #1a1a1a;
                color: #888;
                letter-spacing: 0.5px;
            }

            #toggle-btn.enabled {
                background: linear-gradient(135deg, #0a2a12, #0f3318);
                border-color: #2d6b3f;
                color: #63ff96;
                animation: pulse 2s infinite;
            }

            #toggle-btn.disabled {
                background: linear-gradient(135deg, #2a0f0f, #331414);
                border-color: #6b2d2d;
                color: #ff5050;
                animation: pulseOff 2s infinite;
            }

            #toggle-btn:active { transform: scale(0.98); }

            .toggle-row {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                margin-top: 12px;
                font-size: 0.8em;
                color: #555;
            }

            select, input[type="text"] {
                background: #111;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 10px 12px;
                font-size: 0.9em;
                font-family: 'Inter', sans-serif;
                outline: none;
                transition: border-color 0.2s ease;
            }

            select:focus, input[type="text"]:focus {
                border-color: #555;
            }

            select { cursor: pointer; }

            #toggle-button-select {
                background: #111;
                border: 1px solid #2a2a2a;
                border-radius: 6px;
                color: #999;
                padding: 4px 8px;
                font-size: 1em;
                font-family: 'Inter', sans-serif;
            }

            #configs-dropdown { width: 100%; }

            .slider-hint {
                font-size: 0.75em;
                color: #555;
                margin-top: 8px;
            }

            .delay-unit {
                font-size: 0.45em;
                color: #666;
                font-weight: 400;
                margin-left: 2px;
            }

            .number-input {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: #fff;
                font-size: 2em;
                font-weight: 700;
                font-family: 'Inter', sans-serif;
                width: 100%;
                text-align: left;
                padding: 0 4px;
                margin-bottom: 8px;
                outline: none;
                -moz-appearance: textfield;
                transition: border-color 0.2s ease, background 0.2s ease;
            }

            .number-input::-webkit-outer-spin-button,
            .number-input::-webkit-inner-spin-button {
                -webkit-appearance: none;
                margin: 0;
            }

            .number-input:hover { border-color: #333; }
            .number-input:focus { border-color: #555; background: #111; }

            .number-row {
                display: flex;
                align-items: baseline;
                gap: 4px;
            }

            .number-row .number-input { width: auto; flex: 0 0 auto; }

            input[type="range"] {
                -webkit-appearance: none;
                appearance: none;
                width: 100%;
                height: 6px;
                border-radius: 3px;
                background: #2a2a2a;
                outline: none;
                transition: background 0.2s;
            }

            input[type="range"]::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #fff;
                cursor: pointer;
                box-shadow: 0 0 8px rgba(255,255,255,0.2);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }

            input[type="range"]::-webkit-slider-thumb:hover {
                transform: scale(1.2);
                box-shadow: 0 0 12px rgba(255,255,255,0.35);
            }

            input[type="range"]::-moz-range-thumb {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #fff;
                cursor: pointer;
                border: none;
            }

            .btn {
                padding: 10px 18px;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                font-size: 0.85em;
                font-weight: 500;
                font-family: 'Inter', sans-serif;
                cursor: pointer;
                transition: all 0.2s ease;
                background: #1a1a1a;
                color: #ccc;
            }

            .btn:hover {
                background: #222;
                border-color: #444;
                transform: translateY(-1px);
            }

            .btn:active { transform: translateY(0) scale(0.98); }

            .btn-save {
                background: #1a1a2e;
                border-color: #2d2d6b;
                color: #8888ff;
            }
            .btn-save:hover { background: #22224a; border-color: #4444aa; }

            .btn-delete {
                background: #2a1010;
                border-color: #5a2020;
                color: #ff6666;
            }
            .btn-delete:hover { background: #3a1515; border-color: #7a3030; }

            .info-wrap {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .info-icon {
                position: relative;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                border: 1px solid #444;
                color: #666;
                font-size: 0.7em;
                font-weight: 700;
                cursor: help;
                flex-shrink: 0;
            }

            .info-icon .tooltip {
                display: none;
                position: absolute;
                bottom: calc(100% + 8px);
                left: 50%;
                transform: translateX(-50%);
                background: #222;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 1.1em;
                font-weight: 400;
                color: #bbb;
                white-space: nowrap;
                z-index: 10;
            }

            .info-icon:hover .tooltip { display: block; }

            .save-row {
                display: flex;
                gap: 8px;
            }

            .save-row input[type="text"] { flex: 1; }

            .btn-overwrite {
                background: #1a1e2a;
                border-color: #2d3d6b;
                color: #88aaff;
            }
            .btn-overwrite:hover { background: #222a4a; border-color: #4466aa; }

            .card:nth-child(2) { animation: fadeInUp 0.5s ease-out 0.05s both; }
            .card:nth-child(3) { animation: fadeInUp 0.5s ease-out 0.1s both; }
            .card:nth-child(4) { animation: fadeInUp 0.5s ease-out 0.15s both; }
            .card:nth-child(5) { animation: fadeInUp 0.5s ease-out 0.2s both; }
            .card:nth-child(6) { animation: fadeInUp 0.5s ease-out 0.25s both; }
            .card:nth-child(7) { animation: fadeInUp 0.5s ease-out 0.3s both; }
            .card:nth-child(8) { animation: fadeInUp 0.5s ease-out 0.35s both; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="info-wrap" style="justify-content:center;margin-bottom:32px;">
                <h1 style="margin-bottom:0;">truly</h1>
                <span class="info-icon">i<span class="tooltip">All values are for flash hider + vertical grip</span></span>
            </div>

            <div class="card">
                <div class="card-label">Status</div>
                <button id="toggle-btn">LOADING</button>
                <div class="toggle-row">
                    <span>Toggle key</span>
                    <select id="toggle-button-select">
                        <option value="MMB">Middle Mouse</option>
                        <option value="M4">M4 (Side Back)</option>
                        <option value="M5" selected>M5 (Side Forward)</option>
                    </select>
                </div>
            </div>

            <div class="card">
                <div class="card-label">Gun Config</div>
                <input type="text" id="config-search" placeholder="Search guns..." style="width:100%;margin-bottom:8px;">
                <select id="configs-dropdown"></select>
            </div>

            <div class="card">
                <div class="card-label">Vertical (Pull-down)</div>
                <input type="number" class="number-input" id="slider-value" value="1" min="0" max="300" step="0.001">
                <input type="range" min="0" max="300" value="1" id="recoil-slider">
            </div>

            <div class="card">
                <div class="card-label">Horizontal (Side-to-side)</div>
                <input type="number" class="number-input" id="horizontal-value" value="0" min="-300" max="300" step="0.001">
                <input type="range" min="-300" max="300" value="0" id="horizontal-slider">
                <div class="slider-hint">Negative = left, Positive = right, 0 = off</div>
            </div>

            <div class="card">
                <div class="card-label">Horizontal Delay</div>
                <div class="number-row"><input type="number" class="number-input" id="delay-value" value="500" min="0" max="5000"><span class="delay-unit">ms</span></div>
                <input type="range" min="0" max="5000" step="1" value="500" id="delay-slider">
                <div class="slider-hint">How long LMB is held before horizontal kicks in</div>
            </div>

            <div class="card">
                <div class="card-label">Horizontal Duration</div>
                <div class="number-row"><input type="number" class="number-input" id="duration-value" value="2000" min="0" max="10000"><span class="delay-unit">ms</span></div>
                <input type="range" min="0" max="10000" step="1" value="2000" id="duration-slider">
                <div class="slider-hint">How long horizontal lasts (0 = forever)</div>
            </div>

            <div class="card">
                <div class="card-label">Save Config</div>
                <div class="save-row">
                    <input type="text" id="gun-name" placeholder="Gun name...">
                    <button class="btn btn-save" id="save-btn">Save</button>
                </div>
            </div>

            <div class="card" style="text-align:center;display:flex;gap:8px;justify-content:center;">
                <button class="btn btn-overwrite" id="overwrite-btn">Overwrite Selected</button>
                <button class="btn btn-delete" id="delete-btn">Delete Selected</button>
            </div>
        </div>

        <script>
            document.addEventListener('DOMContentLoaded', function() {
                const slider = document.getElementById("recoil-slider");
                const sliderValue = document.getElementById("slider-value");
                const hSlider = document.getElementById("horizontal-slider");
                const hValue = document.getElementById("horizontal-value");
                const delaySlider = document.getElementById("delay-slider");
                const delayValue = document.getElementById("delay-value");
                const durationSlider = document.getElementById("duration-slider");
                const durationValue = document.getElementById("duration-value");
                const gunNameInput = document.getElementById("gun-name");
                const saveBtn = document.getElementById("save-btn");
                const deleteBtn = document.getElementById("delete-btn");
                const overwriteBtn = document.getElementById("overwrite-btn");
                const configsDropdown = document.getElementById("configs-dropdown");
                const configSearch = document.getElementById("config-search");
                const toggleBtn = document.getElementById("toggle-btn");
                const toggleButtonSelect = document.getElementById("toggle-button-select");

                let ws;
                function connectWs() {
                    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
                    ws = new WebSocket(proto + '//' + location.host + '/ws');
                    ws.onopen = () => sendAll();
                    ws.onclose = () => setTimeout(connectWs, 2000);
                }
                connectWs();

                function sendAll() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({
                            pull_down: parseFloat(sliderValue.value) || 0,
                            horizontal: parseFloat(hValue.value) || 0,
                            horizontal_delay_ms: parseInt(delayValue.value) || 0,
                            horizontal_duration_ms: parseInt(durationValue.value) || 0
                        }));
                    }
                }

                function syncPair(sliderEl, inputEl) {
                    sliderEl.oninput = () => { inputEl.value = sliderEl.value; sendAll(); };
                    inputEl.oninput = () => { sliderEl.value = inputEl.value; sendAll(); };
                }
                syncPair(slider, sliderValue);
                syncPair(hSlider, hValue);
                syncPair(delaySlider, delayValue);
                syncPair(durationSlider, durationValue);
                toggleBtn.onclick = toggleStatus;
                saveBtn.onclick = saveConfig;
                deleteBtn.onclick = deleteConfig;
                overwriteBtn.onclick = overwriteConfig;
                configsDropdown.onchange = activateConfig;
                toggleButtonSelect.onchange = changeToggleButton;

                function updateToggleButton(isEnabled) {
                    toggleBtn.textContent = isEnabled ? 'ON' : 'OFF';
                    toggleBtn.className = isEnabled ? 'enabled' : 'disabled';
                }

                function getStatus() {
                    fetch('/status').then(r => r.json()).then(data => {
                        updateToggleButton(data.is_enabled);
                        if (data.toggle_button) toggleButtonSelect.value = data.toggle_button;
                    }).catch(() => {});
                }

                function changeToggleButton() {
                    fetch('/toggle-button', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ button: toggleButtonSelect.value })
                    }).catch(() => {});
                }

                function toggleStatus() {
                    fetch('/toggle', { method: 'POST' }).then(r => r.json()).then(data => updateToggleButton(data.is_enabled)).catch(() => {});
                }

                let allGuns = [];

                function fetchConfigs() {
                    fetch('/configs').then(r => r.json()).then(data => {
                        allGuns = Object.keys(data);
                        filterConfigs();
                    }).catch(() => {});
                }

                function filterConfigs() {
                    const q = configSearch.value.toLowerCase();
                    const prev = configsDropdown.value;
                    configsDropdown.innerHTML = '<option value="">-- Select a Gun --</option>';
                    for (const gun of allGuns) {
                        if (!q || gun.toLowerCase().includes(q)) {
                            const option = document.createElement('option');
                            option.value = gun;
                            option.textContent = gun;
                            configsDropdown.appendChild(option);
                        }
                    }
                    configsDropdown.value = prev;
                }

                configSearch.oninput = filterConfigs;

                function saveConfig() {
                    const gunName = gunNameInput.value.trim();
                    if (!gunName) return alert('Please enter a gun name.');
                    fetch('/configs', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            gun_name: gunName,
                            pull_down_value: parseFloat(sliderValue.value) || 0,
                            horizontal_value: parseFloat(hValue.value) || 0,
                            horizontal_delay_ms: parseInt(delayValue.value) || 0,
                            horizontal_duration_ms: parseInt(durationValue.value) || 0
                        })
                    }).then(r => r.json()).then(data => {
                        alert(data.message || data.detail);
                        fetchConfigs();
                        gunNameInput.value = '';
                    }).catch(() => alert('Failed to save config.'));
                }

                function deleteConfig() {
                    const selectedGun = configsDropdown.value;
                    if (!selectedGun) return alert('Please select a config to delete.');
                    if (confirm('Delete config for ' + selectedGun + '?')) {
                        fetch('/configs/' + encodeURIComponent(selectedGun), { method: 'DELETE' }).then(r => r.json()).then(data => {
                            alert(data.message || data.detail);
                            fetchConfigs();
                        }).catch(() => alert('Failed to delete config.'));
                    }
                }

                function overwriteConfig() {
                    const selectedGun = configsDropdown.value;
                    if (!selectedGun) return alert('Please select a config to overwrite.');
                    if (confirm('Overwrite config for ' + selectedGun + ' with current values?')) {
                        fetch('/configs', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                gun_name: selectedGun,
                                pull_down_value: parseFloat(sliderValue.value) || 0,
                                horizontal_value: parseFloat(hValue.value) || 0,
                                horizontal_delay_ms: parseInt(delayValue.value) || 0,
                                horizontal_duration_ms: parseInt(durationValue.value) || 0
                            })
                        }).then(r => r.json()).then(data => {
                            alert(data.message || data.detail);
                        }).catch(() => alert('Failed to overwrite config.'));
                    }
                }

                function activateConfig() {
                    const selectedGun = configsDropdown.value;
                    if (!selectedGun) return;
                    fetch('/configs').then(r => r.json()).then(data => {
                        const cfg = data[selectedGun];
                        let pd, hz, dl, du;
                        if (typeof cfg === 'object') {
                            pd = cfg.pull_down ?? 0;
                            hz = cfg.horizontal ?? 0;
                            dl = cfg.horizontal_delay_ms ?? 500;
                            du = cfg.horizontal_duration_ms ?? 2000;
                        } else {
                            pd = cfg ?? 0;
                            hz = 0;
                            dl = 500;
                            du = 2000;
                        }
                        sliderValue.value = pd;
                        hValue.value = hz;
                        delayValue.value = dl;
                        durationValue.value = du;
                        slider.value = Math.round(pd);
                        hSlider.value = Math.round(hz);
                        delaySlider.value = dl;
                        durationSlider.value = du;
                        sendAll();
                    }).catch(() => {});
                }

                getStatus();
                fetchConfigs();
                setInterval(getStatus, 500);
            });
        </script>
    </body>
    </html>
    """
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"\n  Open on this PC:      http://localhost:8000")
    print(f"  Open on another PC:   http://{local_ip}:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
