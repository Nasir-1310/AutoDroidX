"""
Process Manager - Start/Stop LLMDroid tool
"""
import os
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional, List
import re


class ProcessManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.start_time: Optional[datetime] = None
        self.output_dir: Optional[str] = None
        self._log_callback = None
        self._output_thread: Optional[threading.Thread] = None
        
    def set_log_callback(self, callback):
        """Set callback for log streaming"""
        self._log_callback = callback
        
    def is_running(self) -> bool:
        """Check if the tool is currently running"""
        if self.process is None:
            return False
        return self.process.poll() is None
    
    def get_pid(self) -> Optional[int]:
        """Get process ID"""
        return self.pid if self.is_running() else None
    
    def get_start_time(self) -> Optional[str]:
        """Get start time as ISO string"""
        return self.start_time.isoformat() if self.start_time else None
    
    def get_runtime(self) -> Optional[float]:
        """Get runtime in seconds"""
        if self.start_time and self.is_running():
            return (datetime.now() - self.start_time).total_seconds()
        return None
    
    def get_output_dir(self) -> Optional[str]:
        """Get current output directory"""
        return self.output_dir
    
    def get_connected_devices(self) -> List[str]:
        """Get list of connected Android devices"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip() and 'device' in line:
                    device_id = line.split()[0]
                    devices.append(device_id)
            return devices
        except Exception as e:
            print(f"Error getting devices: {e}")
            return []
    
    def start(self, device: str, apk_path: str, output_dir: str,
              timeout: int = 3600, policy: str = "dfs_greedy",
              interval: int = 3, use_coverage: bool = True) -> bool:
        """Start the LLMDroid tool"""
        if self.is_running():
            return False
        
        self.output_dir = output_dir
        
        # Build command
        cmd = [
            "python", "start.py",
            "-d", device,
            "-a", apk_path,
            "-o", output_dir,
            "-timeout", str(timeout),
            "-interval", str(interval),
            "-count", "1000000",
            "-keep_app",
            "-keep_env",
            "-policy", policy,
            "-grant_perm"
        ]
        
        if use_coverage:
            cmd.append("-cv")
        
        # Debug: Print command being executed
        print(f"[ProcessManager] Starting command: {' '.join(cmd)}")
        print(f"[ProcessManager] Working directory: {self.base_dir}")
        
        try:
            # Start process
            self.process = subprocess.Popen(
                cmd,
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self.pid = self.process.pid
            self.start_time = datetime.now()
            
            # Start output reader thread
            self._output_thread = threading.Thread(target=self._read_output, daemon=True)
            self._output_thread.start()
            
            return True
        except Exception as e:
            print(f"Error starting tool: {e}")
            return False
    
    def _read_output(self):
        """Read process output and send to callback"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    line = line.rstrip()
                    print(f"[TOOL] {line}")  # Always print to server console
                    if self._log_callback:
                        try:
                            self._log_callback(line)
                        except Exception as cb_error:
                            # Don't let callback errors stop reading
                            print(f"[TOOL] Callback error (ignored): {cb_error}")
            
            # Read any remaining output after process ends
            if self.process:
                remaining = self.process.stdout.read()
                if remaining:
                    for line in remaining.strip().split('\n'):
                        print(f"[TOOL] {line}")
                        if self._log_callback:
                            try:
                                self._log_callback(line)
                            except Exception:
                                pass
                                
        except Exception as e:
            print(f"[TOOL] Error reading output: {e}")
            if self._log_callback:
                try:
                    self._log_callback(f"Error reading output: {e}")
                except Exception:
                    pass
    
    def stop(self) -> bool:
        """Stop the running tool"""
        if not self.is_running():
            return False
        
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        
        self.process = None
        self.pid = None
        return True
