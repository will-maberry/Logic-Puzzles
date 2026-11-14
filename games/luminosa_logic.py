import random


# Yield orthogonally adjacent corrds within size of grid
def neighbors(row, col, size):
    # Loop through directions
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r, c = row + dr, col + dc
        if 0 <= r < size and 0 <= c < size:
            yield r, c


# Yield orthogonally adjacent corrds within size of grid
    # -2: open white square
    # -1: unnumbered black wall
    # 0..4: numbered black wall clue
def visible(cells, row, col):
    yield row, col

    # Loop through directions
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r, c = row + dr, col + dc
        # Cast ray until hitting a wall or board edge
        while 0 <= r < len(cells) and 0 <= c < len(cells) and cells[r][c] == -2:
            yield r, c
            r, c = r + dr, c + dc


# Validate a player's bulb placement grid against Akari rules
    # Win: no confilicts exist, all clues match, and all open cells are lit
    # Conflicts: sorted list of coordinates involved in rule violations
    # Lit: sorted list of illuminated coordinates
def check_board(cells, board):
    size = len(cells)
    bulbs = {(r, c) for r in range(size) for c in range(size) if board[r][c]}
    lit, conflicts = set(), set()

    # Check bulb legality, compute illumination, and detect line-of-sight bulb clashes
    for bulb in bulbs:
        r, c = bulb

        if cells[r][c] != -2:
            # Bulb placed illegally on a wall
            conflicts.add(bulb)
            continue

        sight = set(visible(cells, r, c))
        lit.update(sight)

        # If another bulb is visible from this bulb, mark all visible bulbs as conflicts
        if (sight & bulbs) - {bulb}:
            conflicts.update(sight & bulbs)

    # Check numbered wall clues against orthogonally adjacent bulbs
    clues_match = True
    for r in range(size):
        for c in range(size):
            if cells[r][c] >= 0:
                adjacent = set(neighbors(r, c, size)) & bulbs

                if len(adjacent) != cells[r][c]:
                    clues_match = False
                
                # Exceeding a clue is an active conflict (under-filling is merely incomplete)
                if len(adjacent) > cells[r][c]:
                    conflicts.add((r, c))
                    conflicts.update(adjacent)

    opens = {(r, c) for r in range(size) for c in range(size) if cells[r][c] == -2}

    return {
        "win": not conflicts and clues_match and opens <= lit,
        "conflicts": sorted(conflicts),
        "lit": sorted(lit),
    }


# Detect all valid bulb placements for a given puzzle using backtracking search with constraint propagation
def find_solutions(cells, limit=2, node_limit=10000):
    size = len(cells)
    opens = [(r, c) for r in range(size) for c in range(size) if cells[r][c] == -2]

    # Map each open cell to a single bit position in Python integer
    bits = {cell: 1 << i for i, cell in enumerate(opens)}

    # Each constraint is (bitmask, min_bulbs, max_bulbs)
    constraints = set()
    for r, c in opens:
        sight = list(visible(cells, r, c))

        # Rule 1: Every open cell must be lit by at least 1 bulb in its line of sight
        constraints.add((sum(bits[cell] for cell in sight), 1, len(sight)))

        # Rule 2: Each contiguous horizontal and vertical corridor can contain at most 1 bulb
        for axis in (0, 1):
            segment = [cell for cell in sight if cell[axis] == (r, c)[axis]]
            constraints.add((sum(bits[cell] for cell in segment), 0, 1))

    # Rule 3: Numbered walls must have an exact count of orthogonally adjacent bulbs
    for r in range(size):
        for c in range(size):
            if cells[r][c] >= 0:
                mask = sum(bits.get(cell, 0) for cell in neighbors(r, c, size))
                constraints.add((mask, cells[r][c], cells[r][c]))

    constraints = sorted(constraints)
    solutions, nodes = [], 0
    all_bits = (1 << len(opens)) - 1

    # Backtracking search with unit propagation
        # On: bitmask of cells confirmed to have bulbs
        # Off: bitmask of cells confirmed to be empty
    def search(on, off):
        nonlocal nodes
        nodes += 1

        # Bounded search: stop if the number of nodes explored exceeds the limit
        if nodes > node_limit:
            raise RuntimeError("Solver search budget exceeded")

        # Unit propagation loop: deduce forced bulbs/blanks until no new deductions occur
        while True:
            previous = on, off
            for mask, low, high in constraints:
                count = (mask & on).bit_count()
                unknown = mask & ~(on | off)
                remaining = unknown.bit_count()

                # Contradiction: too many bulbs placed, or too few cells left to meet minimum
                if count > high or count + remaining < low:
                    return
                
                # Max bulbs reached: all remaining cells in this mask must be empty
                if count == high:
                    off |= unknown
                
                # All remaining cells are needed to hit minimum: all must be bulbs
                elif count + remaining == low:
                    on |= unknown

            # If no new deductions were made, exit the unit propagation loop
            if previous == (on, off):
                break

        unknown = all_bits & ~(on | off)

        # Base case: every open cell has been resolved
        if not unknown:
            solutions.append([cell for cell in opens if bits[cell] & on])
            return

        # MRV heuristic: branch on the unsatisfied constraint with the fewest unknown cells
        candidates = [
            mask & unknown
            for mask, low, high in constraints
            if mask & unknown and (mask & on).bit_count() < low
        ]

        branch = min(candidates, key=int.bit_count) if candidates else unknown

        # Isolate the lowest set bit in the branch to create two branches
            # One with a bulb and one without
        bit = branch & -branch

        # Try placing a bulb first, then try leaving it empty
        search(on | bit, off)
        if len(solutions) < limit:
            search(on, off | bit)

    search(0, 0)
    return solutions


# Generate a `size x size` Akari puzzle with a verified unique solution
def generate_puzzle(size):
    # Attempt to generate a unique solution puzzle up to 100 times
    for attempt in range(100):
        # Populate grid with ~30% walls (-1) and ~70% open cells (-2)
        cells = [[-1 if random.random() < 0.30 else -2 for _ in range(size)] for _ in range(size)]
        opens = [(r, c) for r in range(size) for c in range(size) if cells[r][c] == -2]
        
        if len(opens) < size * size // 2:
            continue

        # Greedily place conflict-free bulbs on unlit cells until the whole board is lit
        random.shuffle(opens)
        lit, bulbs = set(), set()
        for r, c in opens:
            if (r, c) not in lit:
                bulbs.add((r, c))
                lit.update(visible(cells, r, c))

        # Convert walls into numbered clues matching the generated bulb placement
        for r in range(size):
            for c in range(size):
                if cells[r][c] == -1:
                    cells[r][c] = sum(cell in bulbs for cell in neighbors(r, c, size))

        # Accept the puzzle only if the solver proves the solution is unique
        try:
            if len(find_solutions(cells)) == 1:
                return {"size": size, "cells": cells, "solution": sorted(bulbs)}
        except RuntimeError:
            continue

    # Bounded fallback: checkerboard of walls and isolated single open cells (trivially unique)
    cells = [[-2 if (r + c) % 2 == 0 else -1 for c in range(size)] for r in range(size)]
    return {
        "size": size,
        "cells": cells,
        "solution": [(r, c) for r in range(size) for c in range(size) if cells[r][c] == -2],
    }