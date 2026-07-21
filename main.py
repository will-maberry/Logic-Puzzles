'''
Postman Collection: https://will-3662739.postman.co/workspace/Will's-Workspace~c8383f4b-a7a4-4747-87f0-642d41c8cc2c/run/43792533-5213bd54-3679-4d5f-9cf8-bef3478bc134

docker build -t queen-game .
docker run -p 8000:8000 queen-game
http://localhost:8000/

uvicorn main:app --host 0.0.0.0 --port 8000
'''
# Web framework
from fastapi import FastAPI, Path, HTTPException, Request
# Serve files from a static folder
from fastapi.staticfiles import StaticFiles
# Return file responses and JSON responses
from fastapi.responses import FileResponse, JSONResponse
# Used for input validation
from pydantic import BaseModel, Field, validator, root_validator
from typing import List
# Game logic imports
from logic import generate_queen_solution, generate_regions, carve_regions, find_queen_solutions, queens_attack
# Puzzle size
import random
# Rate limit to protect API
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create limiter
limiter = Limiter(key_func = get_remote_address)

# Create API app and serve files from static directory
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory = "static"), name = "static")

# No saved state and default to easy difficulty
rand_one = 4
rand_two = 6

''' Pydantic Validation '''

class GenerateResponse(BaseModel):
    size: int = Field(..., ge=4, le=12)
    solution: List[int]
    regions: List[List[int]]

    @validator("solution", each_item=True)
    def validate_solution_values(cls, v):
        if v < 0:
            raise ValueError("solution values must be >= 0")
        return v

    @root_validator
    def validate_regions_matrix(cls, values):
        size = values.get("size")
        regions = values.get("regions")

        if not isinstance(regions, list) or not all(isinstance(row, list) for row in regions):
            raise ValueError("regions must be a 2D list")

        if len(regions) != size or any(len(row) != size for row in regions):
            raise ValueError(f"regions must be a {size} x {size} matrix")

        for row in regions:
            for val in row:
                if val < 0:
                    raise ValueError("region values must be >= 0")

        return values

# Used when front-end sends board to be checked
class CheckRequest(BaseModel):
    size: int = Field(..., ge=4, le=12)
    # Board is a 2D list
        # Each cell is either empty (0) or has a queen (1)
    board: List[List[int]]
    # Matrix for each cell's region
    regions: List[List[int]]

    # Validate model after all data available
    @root_validator
    def validate_matrices(cls, values):
        size = values.get("size")
        for name in ["board", "regions"]:
            matrix = values.get(name)
            if matrix is not None:
                if len(matrix) != size or any(len(r) != size for r in matrix):
                    raise ValueError(f"{name} must be a {size} x {size} matrix")
        return values

# Used when user submits board for validation
class CheckResponse(BaseModel):
    # Boolean value for win and list of lists of conflict positions
    win: bool
    conflicts: List[List[int]]

# Used when a save is created
class SaveRequest(BaseModel):
    size: int = Field(..., ge=4, le=12)
    board: List[List[int]]
    notes: List[List[int]]
    regions: List[List[int]]

    # Validate model after all data available
    @root_validator
    def ensure_matrices_square(cls, values):
        size = values.get("size")
        for name in ["board", "notes", "regions"]:
            matrix = values.get(name)
            if matrix is not None:
                if len(matrix) != size or any(len(row) != size for row in matrix):
                    raise ValueError(f"{name} must be a {size} x {size} matrix")
        return values

'''API Endpoints'''

# Serve the webpage
@app.get("/", include_in_schema = False)
def root():
    return FileResponse("static/index.html")

# Generate a puzzle
@app.get("/generate", response_model = GenerateResponse)
# Limit to 20 generations a minute
@limiter.limit("20/minute")
def generate(request: Request):
    difficulty = request.cookies.get("difficulty", "easy")

    # Map difficulty to range
    difficulty_map = {
        "easy": (4, 6),
        "medium": (7, 8),
        "hard": (9, 10)
    }

    rand_one, rand_two = difficulty_map.get(difficulty, (4, 6))

    # Loop until a valid puzzle is found
    while True:
        # Size of puzzle
        size = random.randint(rand_one, rand_two)
        # Generate queens solution
        solution = generate_queen_solution(size)
        # Flood-fill region colors (seeding is queen solution)
        regions = generate_regions(solution, size)
        # Carve regions to ensure unique solution
        carved = carve_regions(solution, regions)

        # Only return if unique solution is found
        if len(find_queen_solutions(carved)) < 2:
            return {"size": size, "solution": solution, "regions": carved}

# See if board matches solution or has conflicts
@app.post("/check", response_model = CheckResponse)
# Limit to 150 checks a minute
@limiter.limit("150/minute")
async def check(request: Request, payload: CheckRequest):
    board, regions, size = payload.board, payload.regions, payload.size

    # See if there are duplicate queens in the same region
        # Should never happen as queens are moved via region
    region_seen = set()
    # Stores placed queens
    positions = []
    # Stores all conflicts
    conflicts = []

    # Loop through the board one square at a time
    for row in range(size):
        for col in range(size):
            # Queen placed at square
            if board[row][col] == 1:
                reg = regions[row][col]
                # Append to conflicts is that region already seen
                if reg in region_seen:
                    conflicts.append((row, col))
                # Add to regions seen and queen positions
                region_seen.add(reg)
                positions.append((row, col))

    # Look through all queen positions
    for idx, (r, c) in enumerate(positions):
        for r2, c2 in positions[idx + 1:]:
            # Add to conflicts and any queens are attacking one another
            if queens_attack(r, c, r2, c2):
                conflicts.extend([(r, c), (r2, c2)])

    return {
        # No conflicts and all queens place
        "win": len(region_seen) == size and len(conflicts) == 0,
        # Conflicts present
        "conflicts": [list(pos) for pos in set(conflicts)]
    }

# Change difficulty of the game
# Limit to 5 difficulty changes a minute
@app.get(
    "/difficulty/{level}",
    summary = "Set puzzle difficulty"
)
@limiter.limit("5/minute")
def set_difficulty(request: Request, level: str = Path(..., regex="^(easy|medium|hard)$", description="easy, medium, or hard")):
    # Map difficulty to range
    difficulty_map = {
        "easy": (4, 6),
        "medium": (7, 8),
        "hard": (9, 10)
    }

    if level not in difficulty_map:
        raise HTTPException(status_code = 400, detail = "Invalid difficulty")

    rand_one, rand_two = difficulty_map[level]
    
    # Set difficulty in a cookie
    response = JSONResponse(content = {"status": "difficulty set", "range": [rand_one, rand_two]})
    response.set_cookie(key = "difficulty", value = level, httponly = True, max_age = 3600*24)  # expires in 1 day
    return response