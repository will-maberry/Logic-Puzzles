'''
Fast API interface for logic game website

Configures shared web application, serves static front-end, registers game API routers, and applies API input checks for all game-specific APIs

uvicorn main:app --reload

http://127.0.0.1:8000/
'''

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from games.common import limiter
from games.queens import router as queens_router
from games.tents import router as tents_router


# Static assets relative to this file
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Cap amount of input data sent to API
MAX_API_BODY_BYTES = 16 * 1024


'''
Reject oversized API POST requests before parsing
'''
class APIBodyLimit:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Limit applies onlly to POST requests sent to game APIs
        if scope["type"] != "http" or not scope["path"].startswith("/api/") or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        # Incrementally read requests so oversized ones can be dropped before reading the whole thing
        chunks = []
        total = 0

        while True:
            message = await receive()

            # Stop processing if client disconnects
            if message["type"] == "http.disconnect":
                return
            
            chunk = message.get("body", b"")
            total += len(chunk)

            if total > MAX_API_BODY_BYTES:
                await PlainTextResponse("API request body is too large", status_code=413)(scope, receive, send)
                return
            
            chunks.append(chunk)

            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        # Middleware consumed original request for size-checking
            # Replay accepted request for FastAPI to receive as if it was new
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

'''
Application setup
'''

app = FastAPI(title="Will's Logic Games")

# Apply shared API protections before game-specific routes
app.add_middleware(APIBodyLimit)

# SlowAPI stores limiter on application state and converts exceeded limits to HTTP 429
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# Each game uses its own API endpoints and logic
app.include_router(queens_router)
app.include_router(tents_router)

# Shared front-end assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/css", StaticFiles(directory=STATIC_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")

# Page routes that serve front-end
@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def home():
    # Serves homepage
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/queens", include_in_schema=False)
@app.get("/queens/index.html", include_in_schema=False)
def queens():
    # Serves Queens game
    return FileResponse(STATIC_DIR / "queens" / "index.html")


@app.get("/tents", include_in_schema=False)
@app.get("/tents/index.html", include_in_schema=False)
def tents():
    # Serves Tents game
    return FileResponse(STATIC_DIR / "tents" / "index.html")


@app.get("/privacy", include_in_schema=False)
@app.get("/privacy.html", include_in_schema=False)
def privacy():
    # Serves data and privacy information
    return FileResponse(STATIC_DIR / "privacy.html")
