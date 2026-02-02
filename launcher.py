#!/usr/bin/env python3
"""Clawgotchi launcher — auto-start setup for Mac Mini + USB display."""

import os
import subprocess
import sys
from pathlib import Path

PLIST_NAME = "com.clawgotchi.display"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_NAME}.plist"
CLAWGOTCHI_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable


def generate_plist() -> str:
    """Generate a launchd plist that auto-starts Clawgotchi."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>Terminal</string>
        <string>{CLAWGOTCHI_DIR / 'start.sh'}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>/tmp/clawgotchi.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/clawgotchi.err</string>
</dict>
</plist>"""


def generate_start_script() -> str:
    """Generate the shell script that Terminal.app will run."""
    return f"""#!/bin/bash
# Clawgotchi start script — runs in Terminal.app

# Prevent display sleep
caffeinate -d &
CAFFEINATE_PID=$!

# Trap exit to clean up caffeinate
trap "kill $CAFFEINATE_PID 2>/dev/null" EXIT

cd "{CLAWGOTCHI_DIR}"
{PYTHON} clawgotchi.py
"""


def install():
    """Install the launchd agent and start script."""
    # Write start.sh
    start_sh = CLAWGOTCHI_DIR / "start.sh"
    start_sh.write_text(generate_start_script())
    start_sh.chmod(0o755)
    print(f"Created {start_sh}")

    # Write plist
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(generate_plist())
    print(f"Created {PLIST_PATH}")

    # Load the agent
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)
    print(f"Loaded {PLIST_NAME}")

    print()
    print("Clawgotchi will now start automatically on login.")
    print(f"To start now:  bash {start_sh}")
    print(f"To uninstall:  python3 {__file__} --uninstall")


def uninstall():
    """Remove the launchd agent."""
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        PLIST_PATH.unlink()
        print(f"Removed {PLIST_PATH}")
    else:
        print("Plist not found, nothing to uninstall.")

    start_sh = CLAWGOTCHI_DIR / "start.sh"
    if start_sh.exists():
        start_sh.unlink()
        print(f"Removed {start_sh}")


def status():
    """Check if the agent is loaded."""
    result = subprocess.run(
        ["launchctl", "list"],
        capture_output=True, text=True,
    )
    if PLIST_NAME in result.stdout:
        print(f"{PLIST_NAME}: LOADED")
    else:
        print(f"{PLIST_NAME}: NOT LOADED")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        uninstall()
    elif len(sys.argv) > 1 and sys.argv[1] == "--status":
        status()
    else:
        install()
