import functools
from datetime import timedelta
from quart import request
from quart_rate_limiter import rate_limit
from settings import Settings


def api_rate_limit():
    """
    Decorator to apply rate limiting to API endpoints.
    Uses the rate limit defined in Settings.
    Only applies rate limiting to IPs not in the allowed_ips list.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if client IP is in allowed IPs list
            client_ip = request.remote_addr

            # If client is in the allowed list, no rate limiting
            if client_ip in Settings.allowed_ips:
                return await func(*args, **kwargs)

            # For other IPs, apply rate limiting
            rate_limited_func = rate_limit(Settings.rate_limit, timedelta(seconds=60))(
                func
            )
            return await rate_limited_func(*args, **kwargs)

        return wrapper

    return decorator
