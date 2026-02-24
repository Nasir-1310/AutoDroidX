"""
LLMDroid UI Backend - FastAPI Server
Provides REST API and WebSocket for the frontend
"""
import os
import sys
import asyncio

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from process_manager import ProcessManager
from log_streamer import LogStreamer
from config_manager import ConfigManager
from file_manager import FileManager

# Initialize FastAPI
app = FastAPI(
    title="LLMDroid UI",
    description="Professional UI for LLMDroid Android Testing Framework",
    version="1.0.0"
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
process_manager = ProcessManager(BASE_DIR)
log_streamer = LogStreamer()
config_manager = ConfigManager(os.path.join(BASE_DIR, "config.json"))
file_manager = FileManager()


# ==================== Startup Event ====================

@app.on_event("startup")
async def startup_event():
    """Set up the event loop for log streaming"""
    loop = asyncio.get_running_loop()
    log_streamer.set_event_loop(loop)
    print("[Main] Event loop set for log streaming")


# ==================== Models ====================

class StartRequest(BaseModel):
    device: str = "emulator-5554"
    apk_path: str
    output_dir: str
    timeout: int = 3600
    policy: str = "dfs_greedy"
    interval: int = 3
    use_coverage: bool = True


class ConfigUpdate(BaseModel):
    app_name: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    total_method: Optional[int] = None
    tag: Optional[str] = None


# ==================== REST Endpoints ====================

@app.get("/api/status")
async def get_status():
    """Get current tool status"""
    return {
        "running": process_manager.is_running(),
        "pid": process_manager.get_pid(),
        "start_time": process_manager.get_start_time(),
        "runtime": process_manager.get_runtime()
    }


@app.post("/api/start")
async def start_tool(request: StartRequest):
    """Start the LLMDroid tool"""
    if process_manager.is_running():
        raise HTTPException(status_code=400, detail="Tool is already running")
    
    # Validate required fields
    if not request.apk_path or not request.apk_path.strip():
        raise HTTPException(status_code=400, detail="APK path is required")
    
    if not request.output_dir or not request.output_dir.strip():
        raise HTTPException(status_code=400, detail="Output directory is required")
    
    # Convert forward slashes to backslashes for Windows
    apk_path = request.apk_path.replace('/', '\\')
    output_dir = request.output_dir.replace('/', '\\')
    
    print(f"[API] Starting tool with APK: {apk_path}")
    print(f"[API] Output directory: {output_dir}")
    print(f"[API] Device: {request.device}")
    
    success = process_manager.start(
        device=request.device,
        apk_path=apk_path,
        output_dir=output_dir,
        timeout=request.timeout,
        policy=request.policy,
        interval=request.interval,
        use_coverage=request.use_coverage
    )
    
    if success:
        return {"status": "started", "pid": process_manager.get_pid()}
    else:
        raise HTTPException(status_code=500, detail="Failed to start tool")


@app.post("/api/stop")
async def stop_tool():
    """Stop the running tool"""
    if not process_manager.is_running():
        raise HTTPException(status_code=400, detail="Tool is not running")
    
    process_manager.stop()
    return {"status": "stopped"}


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return config_manager.get_config()


@app.put("/api/config")
async def update_config(update: ConfigUpdate):
    """Update configuration"""
    config_manager.update_config(update.dict(exclude_none=True))
    return {"status": "updated"}


@app.get("/api/coverage")
async def get_coverage():
    """Get current coverage data"""
    output_dir = process_manager.get_output_dir()
    if output_dir:
        return file_manager.get_coverage_data(output_dir)
    return {"percentage": 0, "covered": 0, "total": 0, "history": []}


@app.get("/api/files")
async def list_output_files():
    """List output files"""
    output_dir = process_manager.get_output_dir()
    if output_dir:
        return file_manager.list_files(output_dir)
    return {"files": []}


@app.get("/api/files/{filename:path}")
async def get_file_content(filename: str):
    """Get content of a specific file"""
    output_dir = process_manager.get_output_dir()
    if output_dir:
        return file_manager.get_file_content(output_dir, filename)
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/devices")
async def list_devices():
    """List connected Android devices"""
    return {"devices": process_manager.get_connected_devices()}


@app.post("/api/test-logs")
async def test_logs():
    """Test log streaming"""
    log_streamer.broadcast_log("Test log message from API", "INFO")
    return {"message": "Test log sent"}


# ==================== WebSocket for Real-time Logs ====================

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for streaming logs"""
    await websocket.accept()
    log_streamer.add_client(websocket)
    
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        log_streamer.remove_client(websocket)


# ==================== Serve Frontend ====================

# Serve standalone HTML (no build required)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML"""
    html_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"error": "Frontend not found", "path": html_path}


# ==================== Connect Process Manager to Log Streamer ====================

def setup_log_streaming():
    """Connect process output to WebSocket streaming"""
    def log_callback(line: str):
        log_streamer.parse_and_broadcast(line)
    
    process_manager.set_log_callback(log_callback)

setup_log_streaming()


# ==================== Main ====================

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the FastAPI server"""
    print(f"\n{'='*60}")
    print(f"  🤖 LLMDroid UI Server")
    print(f"  Open http://{host}:{port} in your browser")
    print(f"{'='*60}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
