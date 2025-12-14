import json
import psutil
import re
from datetime import datetime, timedelta
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
            status = Status(**data)
            
            # Smart Status Check: Has it expired?
            if status.until:
                try:
                    until_dt = datetime.fromisoformat(status.until)
                    if datetime.now() > until_dt:
                        # Expired, return default "Free"
                        return Status(text="Free", last_updated=datetime.now().isoformat())
                except ValueError:
                    pass # Invalid date format, ignore
            
            return status
        except Exception:
            pass
    return Status(text="Unknown", last_updated=datetime.now().isoformat())

def save_status(status: Status):
    STATE_FILE.write_text(json.dumps(asdict(status), indent=2))

def parse_expiry(until_str: str) -> Optional[str]:
    """Parses a time string (30m, 1h, 16:00) into an absolute ISO timestamp."""
    if not until_str:
        return None
    
    now = datetime.now()
    
    # Format: "30m", "1h" (Delta)
    if match := re.match(r"^(\d+)([hm])$", until_str):
        value = int(match.group(1))
        unit = match.group(2)
        delta = timedelta(minutes=value) if unit == "m" else timedelta(hours=value)
        return (now + delta).isoformat()
    
    # Format: "16:00" (Absolute Time today)
    if re.match(r"^\d{1,2}:\d{2}$", until_str):
        try:
            target_time = datetime.strptime(until_str, "%H:%M").time()
            target_dt = datetime.combine(now.date(), target_time)
            # If time passed, assume tomorrow? (Optional: for now assume today)
            if target_dt < now:
                target_dt += timedelta(days=1)
            return target_dt.isoformat()
        except ValueError:
            pass

    return None

# --- Resources ---

@mcp.resource("me://status")
def get_status() -> str:
    """Returns the user's current status. Auto-reverts to 'Free' if expired."""
    status = load_status()
    return json.dumps(asdict(status), indent=2)

# --- Tools ---

@mcp.tool()
def update_status(status: str, until: str = None, ctx: Context = None) -> str:
    """
    Update the user's current status.
    
    Args:
        status: The new status (e.g., "Deep Work", "Meeting", "Free").
        until: Optional duration ("30m", "2h") or time ("17:00") when this status expires.
    """
    expiry_iso = parse_expiry(until)
    
    new_status = Status(
        text=status,
        last_updated=datetime.now().isoformat(),
        until=expiry_iso
    )
    save_status(new_status)
    
    msg = f"Status updated to: {status}"
    if expiry_iso:
        msg += f" (until {expiry_iso})"
    
    if ctx:
        ctx.info(msg)
        
    return msg

@mcp.tool()
def get_system_stats() -> str:
    """Get system stats: CPU, RAM, Disk, and Battery."""
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    battery = psutil.sensors_battery()
    
    stats = {
        "cpu_percent": cpu,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
    }
    
    if battery:
        stats["battery_percent"] = round(battery.percent, 1)
        stats["battery_plugged"] = battery.power_plugged
        # psutil returns mins or -1/None
        if battery.secsleft and battery.secsleft > 0: 
             stats["battery_time_left_min"] = int(battery.secsleft / 60)
    
    return json.dumps(stats, indent=2)

if __name__ == "__main__":
    mcp.run()
