# LLMDroid UI

Professional dashboard interface for the LLMDroid Android Testing Framework.

## Features

- **Start/Stop Control**: Launch and terminate testing with a single click
- **Real-time Terminal**: Live streaming of tool output via WebSocket
- **Coverage Visualization**: Interactive chart showing code coverage progress
- **File Explorer**: Browse generated output files and screenshots
- **Configuration Panel**: Adjust settings without editing config.json
- **Modern Design**: Professional look suitable for research demos

## Quick Start

### Option 1: Double-click (Windows)
```
Double-click: start_ui.bat
```

### Option 2: PowerShell
```powershell
cd LLMDroid-Droidbot/ui
.\start_ui.ps1
```

### Option 3: Python
```bash
cd LLMDroid-Droidbot/ui
pip install -r requirements.txt
python run_ui.py
```

The UI will automatically open at **http://127.0.0.1:8000**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (React UI)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Config  │  │  Start/  │  │ Terminal │  │  Output  │    │
│  │  Panel   │  │  Stop    │  │   Logs   │  │  Viewer  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │ REST API    │ REST API    │ WebSocket   │ REST API
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  process_manager.py  │  log_streamer.py  │  file_manager.py │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Existing LLMDroid (start.py)                    │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get tool running status |
| `/api/start` | POST | Start the testing tool |
| `/api/stop` | POST | Stop the running tool |
| `/api/config` | GET/PUT | Read/update configuration |
| `/api/coverage` | GET | Get current coverage data |
| `/api/files` | GET | List output files |
| `/api/devices` | GET | List connected Android devices |
| `/ws/logs` | WebSocket | Real-time log streaming |

## Dependencies

- **Backend**: FastAPI, Uvicorn, WebSockets
- **Frontend**: React (via CDN), Tailwind CSS, Chart.js

No npm/node required - the frontend runs directly in the browser!

## File Structure

```
ui/
├── backend/
│   ├── main.py              # FastAPI server
│   ├── process_manager.py   # Start/stop tool control
│   ├── log_streamer.py      # WebSocket log streaming
│   ├── config_manager.py    # Configuration management
│   └── file_manager.py      # Output file handling
│
├── frontend/
│   └── index.html           # Standalone React dashboard
│
├── requirements.txt         # Python dependencies
├── run_ui.py               # Entry point
├── start_ui.bat            # Windows launcher
└── start_ui.ps1            # PowerShell launcher
```

## Customization

### Change Port
```bash
python run_ui.py --port 3000
```

### Development Mode (auto-reload)
```bash
python run_ui.py --dev
```

### Don't Open Browser
```bash
python run_ui.py --no-browser
```

## Troubleshooting

### "Backend offline" in UI
- Make sure adb is in PATH
- Check if port 8000 is available
- Try running `python run_ui.py` directly to see errors

### Logs not streaming
- Refresh the browser
- Check WebSocket connection in browser DevTools

### Coverage chart not updating
- Ensure `-cv` flag is used when testing
- Check `codecoverage.txt` is being generated
