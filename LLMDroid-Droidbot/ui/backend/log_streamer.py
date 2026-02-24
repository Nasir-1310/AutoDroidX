"""
Log Streamer - WebSocket-based real-time log streaming
"""
import asyncio
import threading
from typing import List, Set, Optional
from fastapi import WebSocket
import json
from datetime import datetime
from queue import Queue


class LogStreamer:
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._log_buffer: List[dict] = []
        self._max_buffer_size = 1000
        self._log_queue: Queue = Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop for async operations"""
        self._loop = loop
        
    def add_client(self, websocket: WebSocket):
        """Add a new WebSocket client"""
        self._clients.add(websocket)
        # Send buffered logs to new client
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send_buffer(websocket), self._loop)
        
    def remove_client(self, websocket: WebSocket):
        """Remove a WebSocket client"""
        self._clients.discard(websocket)
        
    async def _send_buffer(self, websocket: WebSocket):
        """Send buffered logs to a client"""
        try:
            for log_entry in self._log_buffer[-100:]:  # Send last 100 logs
                await websocket.send_json(log_entry)
        except Exception:
            pass
    
    def broadcast_log(self, message: str, level: str = "INFO"):
        """Broadcast a log message to all connected clients (thread-safe)"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        
        # Add to buffer (thread-safe)
        self._log_buffer.append(log_entry)
        if len(self._log_buffer) > self._max_buffer_size:
            self._log_buffer.pop(0)
        
        # Broadcast to all clients using thread-safe method
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(log_entry), self._loop)
        else:
            # Fallback: just store in buffer
            pass
    
    async def _broadcast(self, log_entry: dict):
        """Send log to all connected clients"""
        disconnected = set()
        for client in self._clients.copy():  # Use copy to avoid modification during iteration
            try:
                await client.send_json(log_entry)
            except Exception:
                disconnected.add(client)
        
        # Remove disconnected clients
        self._clients -= disconnected
    
    def parse_and_broadcast(self, line: str):
        """Parse a log line and broadcast with appropriate level"""
        level = "INFO"
        
        # Debug print to console
        print(f"[LOG STREAM] {line}")
        
        # Detect log level from line content
        if "[ERROR]" in line or "Error" in line or "error" in line:
            level = "ERROR"
        elif "[WARNING]" in line or "Warning" in line:
            level = "WARNING"
        elif "[DEBUG]" in line:
            level = "DEBUG"
        elif "-->" in line:  # Coverage output
            level = "COVERAGE"
        elif "[INFO]" in line:
            level = "INFO"
        
        self.broadcast_log(line, level)
    
    def get_recent_logs(self, count: int = 100) -> List[dict]:
        """Get recent logs from buffer"""
        return self._log_buffer[-count:]
    
    def clear_buffer(self):
        """Clear the log buffer"""
        self._log_buffer.clear()
