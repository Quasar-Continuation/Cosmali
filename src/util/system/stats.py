import time
import psutil
import datetime

APP_START_TIME = time.time()


def get_system_stats():
    """Get current system statistics"""

    uptime_seconds = time.time() - APP_START_TIME
    uptime = str(datetime.timedelta(seconds=int(uptime_seconds)))

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    memory_percent = memory.percent

    disk = psutil.disk_usage("/")
    disk_percent = disk.percent

    return {
        "uptime": uptime,
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "disk_percent": disk_percent,
    }
