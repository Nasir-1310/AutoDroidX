#!/usr/bin/env python3
"""
LLMDroid UI - Single Entry Point
Run this script to start the UI server
"""
import os
import sys
import argparse
import webbrowser
import threading
import time

# Add directories to path for imports
UI_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(UI_DIR))  # Parent (LLMDroid-Droidbot)
sys.path.insert(0, os.path.join(UI_DIR, 'backend'))  # Backend module


def check_dependencies():
    """Check if required packages are installed"""
    missing = []
    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")
    
    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn[standard]")
    
    try:
        import websockets
    except ImportError:
        missing.append("websockets")
    
    if missing:
        print("Missing dependencies. Installing...")
        import subprocess
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", *missing
        ])
        print("Dependencies installed successfully!")


def open_browser(url: str, delay: float = 1.5):
    """Open browser after a delay"""
    def _open():
        time.sleep(delay)
        webbrowser.open(url)
    
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def find_free_port(start_port: int, max_tries: int = 10) -> int:
    """Find an available port starting from start_port"""
    import socket
    for port in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return start_port  # Fall back to original


def main():
    parser = argparse.ArgumentParser(description="LLMDroid UI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    parser.add_argument("--dev", action="store_true", help="Development mode with reload")
    
    args = parser.parse_args()
    
    # Check dependencies
    check_dependencies()
    
    # Import after checking dependencies
    import uvicorn
    
    # Change to UI directory for module resolution
    os.chdir(UI_DIR)
    
    # Find available port
    port = find_free_port(args.port)
    if port != args.port:
        print(f"Port {args.port} is busy, using port {port} instead")
    
    url = f"http://{args.host}:{port}"
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🤖 LLMDroid UI - Android Testing Framework                 ║
║                                                              ║
║   Server running at: {url:<38} ║
║                                                              ║
║   Press Ctrl+C to stop                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Open browser
    if not args.no_browser:
        open_browser(url)
    
    # Run server
    if args.dev:
        uvicorn.run(
            "backend.main:app",
            host=args.host,
            port=port,
            reload=True,
            log_level="warning"  # Reduce log verbosity
        )
    else:
        uvicorn.run(
            "backend.main:app",
            host=args.host,
            port=port,
            log_level="warning"  # Reduce log verbosity
        )


if __name__ == "__main__":
    main()
