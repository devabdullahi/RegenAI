"""
Shared rate-limiter instance for RegenAI.

Defined here (not in main.py) so routers can import it without triggering
the circular import that would occur if they imported from app.main, which
itself imports all routers during module load.

Usage in a router:
    from app.rate_limit import limiter

    @router.post("/")
    @limiter.limit("30/hour")
    async def my_endpoint(request: Request, ...):
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
