from settings import Settings
from quart import request, websocket
import functools


def black_list_ip():
    """Decorator to blacklist specific IPs for both HTTP routes and WebSocket routes"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):

            try:

                client_ip = websocket.remote_addr
            except RuntimeError:
                try:

                    client_ip = request.remote_addr
                except RuntimeError:
                    return "Access Denied: No context available", 403

            if client_ip in Settings.allowed_ips:
                return await func(*args, **kwargs)
            else:
                if (
                    "websocket" in func.__name__
                ):  # we gotta handle web sockets dif for fun

                    return "Access Denied", 403
                else:

                    return "Access Denied", 403

        return wrapper

    return decorator
