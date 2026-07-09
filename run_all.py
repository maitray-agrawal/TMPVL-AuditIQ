#!/usr/bin/env python3
"""
TMPVL Billing Audit & Fraud Detection System — Cross-Platform Service Orchestrator.

Starts the FastAPI backend service and Vite/React frontend dev server simultaneously,
opens the browser to the application page, and manages clean termination on exit.
"""
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

# Resolve absolute paths
ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"

print("=======================================================================")
print("        TMPVL BILLING AUDIT & FRAUD DETECTION SYSTEM RUNNER")
print("=======================================================================")
print()

# 1. Start FastAPI Backend
print("[1/3] Starting FastAPI backend...")
python_bin = sys.executable

# Inject project root into PYTHONPATH env variable
backend_env = {**subprocess.os.environ, "PYTHONPATH": str(ROOT_DIR)}
backend_process = subprocess.Popen(
    [python_bin, "-m", "backend.main"],
    cwd=ROOT_DIR,
    env=backend_env
)

# 2. Start Vite/React Frontend
print("[2/3] Starting React frontend dev server...")
# On Windows, shell=True is needed to run command batch scripts like npm.cmd
use_shell = (sys.platform == "win32")
frontend_process = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=FRONTEND_DIR,
    shell=use_shell
)

# 3. Launch Web Browser
print("[3/3] Launching web browser...")
time.sleep(3.0)
webbrowser.open("http://localhost:5173/")

print()
print("=======================================================================")
print("  System is running. Press Ctrl+C in this terminal to stop both services.")
print("=======================================================================")
print()

try:
    while True:
        # Check if backend died
        if backend_process.poll() is not None:
            print("Backend process terminated unexpectedly.")
            break
        # Check if frontend died
        if frontend_process.poll() is not None:
            print("Frontend process terminated unexpectedly.")
            break
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down services...")
finally:
    # Gracefully terminate processes
    backend_process.terminate()
    frontend_process.terminate()
    try:
        backend_process.wait(timeout=3)
        frontend_process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        backend_process.kill()
        frontend_process.kill()
    print("Services stopped.")
