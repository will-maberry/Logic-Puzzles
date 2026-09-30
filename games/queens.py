from typing import Annotated, List

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import limiter

from .queens_logic import (
    carve_regions,
    find_queen_solutions,
    generate_queen_solution,
    generate_regions,
    queens_attack,
)

'''
Queens game specific API
'''

router = APIRouter(prefix="/api/queens", tags=["queens"])

# Board size is 4x4 through 10x10, board cells are binary, and region IDs use one integer per region
Size = Annotated[int, Field(strict=True, ge=4, le=10)]
Cell = Annotated[int, Field(strict=True, ge=0, le=1)]
Region = Annotated[int, Field(strict=True, ge=0, le=9)]


# Base model for API input with unexpected fields rejected
class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

# Requested board size for a new puzzle
class GenerateRequest(InputModel):
    size: Size

# Generated puzzle with unique solution and region map attached
class GenerateResponse(BaseModel):
    size: int
    solution: List[int]
    regions: List[List[int]]

# Current board state submitted for conflicts and win checking
class CheckRequest(InputModel):
    size: Size
    board: List[List[Cell]]
    regions: List[List[Region]]

    # Validate matrix dimensions and complete set of region IDs
    @model_validator(mode="after")
    def validate_matrices(self):
        size = self.size

        # Matrices much match board side passed to API
        for name in ("board", "regions"):
            matrix = getattr(self, name)

            if len(matrix) != size or any(
                len(row) != size for row in matrix
            ):
                raise ValueError(
                    f"{name} must be a {size} x {size} matrix"
                )

        # Size n puzzle must have n regions
        region_ids = {
            cell
            for row in self.regions
            for cell in row
        }

        if region_ids != set(range(size)):
            raise ValueError(
                "regions must contain every ID from 0 through size - 1"
            )

        return self

# Result of checking player's current queen placement
class CheckResponse(BaseModel):
    win: bool
    conflicts: List[List[int]]


'''
Puzzle generation
'''

# Generate a queens puzzle with one solution
@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("20/minute")
def generate(request: Request, payload: GenerateRequest):
    size = payload.size

    # Loop until there's only one solution before returning
    while True:
        # Create valid placement for queens
        solution = generate_queen_solution(size)

        # Generate and carve colored regions
        regions = carve_regions(solution, generate_regions(solution, size))
        if len(find_queen_solutions(regions)) == 1:
            return {"size": size, "solution": solution, "regions": regions}

'''
Board validation
'''

# Check current board for region and queen conflicts
@router.post("/check", response_model=CheckResponse)
@limiter.limit("150/minute")
def check(request: Request, payload: CheckRequest):
    # Convert board matrix into queen coordinates
    positions = [
        (row, col)
        for row in range(payload.size)
        for col in range(payload.size)
        if payload.board[row][col] == 1
    ]
    conflicts = set()
    seen_regions = {}

    # #A region can only contain a single queen so track queens seen in each region
    for row, col in positions:
        region = payload.regions[row][col]

        # Region conflict
            # Should never happen because queens overwritten when clicked in same region
        if region in seen_regions:
            conflicts.update(((row, col), seen_regions[region]))
        
        # Add region to seen list
        else:
            seen_regions[region] = (row, col)

    # Compare every pair of placed queens for attacks
    for index, (row, col) in enumerate(positions):
        for other_row, other_col in positions[index + 1:]:
            if queens_attack(row, col, other_row, other_col):
                conflicts.update(((row, col), (other_row, other_col)))
    
    # Solved board contains one queen per region and no attacking pair
    return {
        "win": len(positions) == payload.size and len(seen_regions) == payload.size and not conflicts,
        # Sort conflicts for determinism
        "conflicts": [list(position) for position in sorted(conflicts)],
    }