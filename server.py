import json
import psutil
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Context

# Initialize the server
mcp = FastMCP("Me-Server")

# Persistence
STATE_FILE = Path("state.json")

@dataclass
class Status:
    text: str
    last_updated: str
    until: Optional[str] = None

def load_status() -> Status:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return Status(**data)
        except Exception:
            pass
    return Status(text="Unknown", last_updated=datetime.now().isoformat())

def save_status(status: Status):
    STATE_FILE.write_text(json.dumps(asdict(status), indent=2))

# --- Resources ---

@mcp.resource("me://status")
def get_status() -> str:
    """Returns the user's current status."""
    status = load_status()
    return json.dumps(asdict(status), indent=2)

# --- Tools ---

@mcp.tool()
def update_status(status: str, until: str = None, ctx: Context = None) -> str:
    """
    Update the user's current status.
    
    Args:
        status: The new status (e.g., "Deep Work", "Meeting", "Free").
        until: Optional time when this status expires or changes.
    """
    new_status = Status(
        text=status,
        last_updated=datetime.now().isoformat(),
        until=until
    )
    save_status(new_status)
    
    if ctx:
        ctx.info(f"Updated status to: {status}")
        
    return f"Status updated to: {status}"

@mcp.tool()
def get_system_stats() -> str:
    """Get the current system statistics (CPU / RAM)."""
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    stats = {
        "cpu_percent": cpu,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "memory_total_gb": round(memory.total / (1024**3), 2)
    }
    return json.dumps(stats, indent=2)

if __name__ == "__main__":
    mcp.run()
