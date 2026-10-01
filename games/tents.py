from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import limiter
from .tents_logic import MIN_TENTS, can_pair_tents, generate_puzzle, neighbors, touching

'''
Tents Game Specific API
'''

router = APIRouter(prefix="/api/tents", tags=["tents"])

# Bard size is 4x4 through 15x15, board cells are binary, and clues tell you how many tents in each row/column
Size = Annotated[int, Field(strict=True, ge=4, le=15)]
Cell = Annotated[int, Field(strict=True, ge=0, le=1)]
Clue = Annotated[int, Field(strict=True, ge=0, le=8)]

# Coordinates show all locations on board
Coordinate = tuple[Annotated[int, Field(strict=True, ge=0, le=14)],
                   Annotated[int, Field(strict=True, ge=0, le=14)]]


# Base model for API input with unexpected fields rejected
class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

# Requested board size for a new puzzle

class GenerateRequest(InputModel):
    size: Size

# Generated puzzle with unique solution and region map attached
class CheckRequest(InputModel):
    size: Size
    board: list[list[Cell]]
    trees: list[Coordinate]
    row_clues: list[Clue]
    col_clues: list[Clue]

    # Validate matrix dimensions and all game inputs
    @model_validator(mode="after")
    def validate_puzzle(self):
        size = self.size
        if len(self.board) != size or any(len(row) != size for row in self.board):
            raise ValueError("board dimensions do not match size")
        if len(self.row_clues) != size or len(self.col_clues) != size:
            raise ValueError("clue dimensions do not match size")
        if any(clue > (size + 1) // 2 for clue in self.row_clues + self.col_clues):
            raise ValueError("clue exceeds row or column capacity")
        if len(self.trees) < MIN_TENTS[size] or len(self.trees) > size * size // 2:
            raise ValueError("invalid tree count")
        if len(set(self.trees)) != len(self.trees) or any(
            row >= size or col >= size for row, col in self.trees
        ):
            raise ValueError("invalid tree coordinates")
        if sum(self.row_clues) != len(self.trees) or sum(self.col_clues) != len(self.trees):
            raise ValueError("clues must total tree count")

        # All parts of input passed
        return self


'''
Puzzle Generation
'''

# Generate a tents puzzle with one solution
@router.post("/generate")
@limiter.limit("20/minute")
def generate(request: Request, payload: GenerateRequest):
    return generate_puzzle(payload.size)


'''
Board validation
'''

# Check current board for tent conflicts
@router.post("/check")
@limiter.limit("150/minute")
def check(request: Request, payload: CheckRequest):
    size = payload.size
    trees = set(payload.trees)
    # Convert tents into list to be looped through
    tents = [(row, col) for row in range(size) for col in range(size)
             if payload.board[row][col]]
    conflicts = set()

    # Loop through list of tent tuples to check
    for tent in tents:
        row, col = tent

        # Tent on tree or not adjacent to a tree
        if tent in trees or not any(tree in trees for tree in neighbors(row, col, size)):
            conflicts.add(tent)

        # Tents can't touch
        for other in tents:
            if tent != other and touching(tent, other):
                conflicts.update((tent, other))

    # Tent row and column counts can't exceed clues
    for row in range(size):
        if sum(payload.board[row]) > payload.row_clues[row]:
            conflicts.update(tent for tent in tents if tent[0] == row)
    for col in range(size):
        if sum(payload.board[row][col] for row in range(size)) > payload.col_clues[col]:
            conflicts.update(tent for tent in tents if tent[1] == col)
    
    # See if all rows and columns complete
    counts_match = all(sum(payload.board[row]) == payload.row_clues[row] for row in range(size)) and all(
        sum(payload.board[row][col] for row in range(size)) == payload.col_clues[col]
        for col in range(size))

    # Only one tent per tree
    paired = counts_match and not conflicts and can_pair_tents(payload.trees, tents, size)

    # Return info and sort for determinism
    return {"win": counts_match and not conflicts and paired,
            "conflicts": [list(cell) for cell in sorted(conflicts)]}