import random

'''
Generate Tents solution
'''

# Minimum tent counts by grid size
MIN_TENTS = {
    4: 4, 5: 7, 6: 9, 7: 12, 8: 15, 9: 20, 10: 22,
    11: 27, 12: 31, 13: 36, 14: 42, 15: 48,
}

# Return orthogonal neighbors of a cell on the board
def neighbors(row, col, size):
    return [
        (r, c)
        for r, c in (
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        )
        if 0 <= r < size and 0 <= c < size
    ]


# Chekc if two cells are touching horizonatlly, vertically, or diagonally
def touching(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1


# Find up to the limit of distinct valid tent arrangements
def find_solutions(trees, row_clues, col_clues, limit=2):
    size = len(row_clues)

    # Normalize tree coordinates
    trees = [tuple(tree) for tree in trees]
    tree_set = set(trees)

    # Every possible tent location for each tree
        # Cells containing other trees can't be used as tent positions
    options = [tuple(row * size + col for row, col in neighbors(*tree, size)
                     if (row, col) not in tree_set) for tree in trees]
    
    # Represent board cells as bits and make mask of all surrounding cells
        # Halo ensures no two tents touched
    halos = []
    for row in range(size):
        for col in range(size):
            halos.append(sum(1 << (r * size + c)
                             for r in range(max(0, row - 1), min(size, row + 2))
                             for c in range(max(0, col - 1), min(size, col + 2))))
    
    # Track how many tents currently assigned to each row and column
    row_used, col_used = [0] * size, [0] * size

    # Solutions stored as bitmasks so duplicate tent arrangements collapse to one solution
    found = set()

    # Recursively assign tents to remaining trees
    def search(remaining, blocked, placed):

        # Generate only cares if puzzle has 0, 1, or 2 solutions
        if len(found) >= limit:
            return

        # Once all trees assigned, arrangement valid if all row and column clues are satisfied
        if not remaining:
            if row_used == row_clues and col_used == col_clues:
                found.add(placed)
            return

        
        possible_rows, possible_cols = [0] * size, [0] * size

        best_tree, best_choices = None, None

        # Loop through remaining trees and determine tent locations that are still elgal
        for tree_index in remaining:
            choices = [cell for cell in options[tree_index]
                       if not blocked & (1 << cell)
                       and row_used[cell // size] < row_clues[cell // size]
                       and col_used[cell % size] < col_clues[cell % size]]

            # Tree with no remaining tent position makes this branch of solution invalid
            if not choices:
                return

            # Record rows and columns that could still receive tents
                # Used to prune branches that can't reach required clues
            for row in {cell // size for cell in choices}:
                possible_rows[row] += 1
            for col in {cell % size for cell in choices}:
                possible_cols[col] += 1

            # Search most constrained tree first to avoid needless branching
            if best_choices is None or len(choices) < len(best_choices):
                best_tree, best_choices = tree_index, choices

        # If remaining trees can't supply enough tents for clues, abandon branch
        if any(row_used[row] + possible_rows[row] < row_clues[row]
               for row in range(size)) or any(
                   col_used[col] + possible_cols[col] < col_clues[col]
                   for col in range(size)):
            return

        # Remove selected tree from recursion
        next_remaining = tuple(index for index in remaining if index != best_tree)

        # Try each currently valid tent location for selected tree
        for cell in best_choices:
            row, col = divmod(cell, size)
            row_used[row] += 1
            col_used[col] += 1

            # Add tent's halo to blocked mask and cell to placed-tent mask
            search(next_remaining, blocked | halos[cell], placed | (1 << cell))

            # Backtrack so next candidate starts from last valid state
            row_used[row] -= 1
            col_used[col] -= 1

    # Inital call with all trees unassigned and no cells blocked
    search(tuple(range(len(trees))), 0, 0)

    # Conver solution bitmasks back to (row, column) coordinates
    return [[(cell // size, cell % size) for cell in range(size * size)
             if solution & (1 << cell)] for solution in found]


'''
Check if every tree can be paired with distinct adjacent tent
'''
def can_pair_tents(trees, tents, size):
    tent_set = set(tents)

    # Build set of player-placed tents available to each tree
    options = [tuple(cell for cell in neighbors(*tree, size) if cell in tent_set)
               for tree in trees]

    # Every tree must have at least on adjacent tent candidate
    if any(not choices for choices in options):
        return False

    # Map each tent to tree currently assigned to it
    assigned = {}

    # Try to assign distinct tent to one tree
    def assign(tree_index, seen):
        for tent in options[tree_index]:
            if tent in seen:
                continue

            seen.add(tent)
            
            if tent not in assigned or assign(assigned[tent], seen):
                assigned[tent] = tree_index
                return True
        
        return False
    
    # Valid board requires successful distinct assignment for every tree
    return all(assign(index, set()) for index in range(len(trees)))


'''
Generate tents puzzle with one tent arrangement
'''
def generate_puzzle(size):
    cells = [(row, col) for row in range(size) for col in range(size)]

    # Minimum number of tents required for puzzle size
    minimum = MIN_TENTS[size]

    # Randomize generation
    for _ in range(600):
        # Every candidate is a possible tent cell paired with a tree in adjacent cell
        candidates = [(tent, tree) for tent in cells
                      for tree in neighbors(*tent, size)]
        
        random.shuffle(candidates)

        tents, trees = [], []
        occupied = set()

        # Build valid collection of tree and tent pairs
        for tent, tree in candidates:
            # Trees and tents occupy distinct cells
            if tent in occupied or tree in occupied:
                continue

            # Tents can't touch any adjacent ones
            if any(touching(tent, other) for other in tents):
                continue


            tents.append(tent)
            trees.append(tree)

            # Neither cell can be in another generated pair
            occupied.update((tent, tree))

        # Reject boards with too few tents
        if len(tents) < minimum:
            continue

        # Use dense subset of generated pairs
            # Final count can be a bit random for variety
        count = random.randint(minimum, min(len(tents), minimum + 2))

        tents, trees = tents[:count], trees[:count]

        # Visible clues generated from solution
        row_clues = [sum(row == r for row, _ in tents) for r in range(size)]
        col_clues = [sum(col == c for _, col in tents) for c in range(size)]

        # Only return puzzles with exactly one solution
        if len(find_solutions(trees, row_clues, col_clues)) == 1:
            return {
                "size": size, "trees": [list(tree) for tree in trees],
                "row_clues": row_clues, "col_clues": col_clues,
                "solution": [list(tent) for tent in sorted(tents)],
            }
    
    # Every attempt to generate a puzzle failed
    raise RuntimeError(f"Could not generate a unique {size}x{size} Tents puzzle")