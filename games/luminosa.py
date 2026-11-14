from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import limiter
from .luminosa_logic import check_board, generate_puzzle, neighbors

'''
Luminosa game specific API
'''

router = APIRouter(prefix="/api/luminosa", tags=["luminosa"])

# Strict field types prevent automatic type coercion (e.g., rejecting "5" or True for an int)
Size = Annotated[int, Field(strict=True, ge=4, le=10)]  # Grid dimension: 4x4 up to 10x10
Cell = Annotated[int, Field(strict=True, ge=0, le=1)]   # Player board state: 0 = empty, 1 = bulb
Clue = Annotated[int, Field(strict=True, ge=-2, le=4)]  # Puzzle cell: -2 = open, -1 = wall, 0..4 = clue


class GenerateRequest(BaseModel):
    # Reject payloads containing unexpected JSON keys (returns HTTP 422)
    model_config = ConfigDict(extra="forbid")
    size: Size


class CheckRequest(GenerateRequest):
    board: list[list[Cell]]
    cells: list[list[Clue]]

    @model_validator(mode="after")
    # Ensure matrices match `size` and represent a structurally valid puzzle
    def validate_matrices(self):
        # Verify both matrices are exact size x size squares
        for matrix in (self.board, self.cells):
            if len(matrix) != self.size or any(len(row) != self.size for row in matrix):
                raise ValueError("matrix dimensions do not match size")

        # Reject boards with zero playable open spaces
        if not any(-2 in row for row in self.cells):
            raise ValueError("puzzle must contain open cells")

        # Ensure no numbered wall demands more bulbs than it has adjacent open cells
        for r in range(self.size):
            for c in range(self.size):
                if self.cells[r][c] >= 0 and self.cells[r][c] > sum(
                    self.cells[a][b] == -2 for a, b in neighbors(r, c, self.size)
                ):
                    raise ValueError("clue exceeds adjacent open cells")
        return self


@router.post("/generate")
@limiter.limit("20/minute")
# Generate a new Luminosa puzzle with a unique solution
def generate(request: Request, payload: GenerateRequest):
    return generate_puzzle(payload.size)


@router.post("/check")
@limiter.limit("150/minute")
# Validate the player's current bulb placements against the puzzle rules
def check(request: Request, payload: CheckRequest):
    return check_board(payload.cells, payload.board)