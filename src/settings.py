from dataclasses import dataclass
from typing import List, ClassVar


@dataclass
class Settings:
    host_url: str = "https://127.0.0.1"
    host_port: int = 40175

    rate_limit: int = 8  # 8 requests per minute max (updated from 5)
    allowed_ips: ClassVar[List[str]] = [
        "127.0.0.1"
    ]  # this is the list of allowed IPs for rate limiting

    debug: bool = False
