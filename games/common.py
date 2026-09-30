from slowapi import Limiter
from slowapi.util import get_remote_address

# SlowAPI limiter for all games
limiter = Limiter(key_func=get_remote_address)