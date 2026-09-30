import random

'''
Generate one N-Queens solution
board_size: size of the board (square)
output: list where index = row and value = column of each queen in the solution
'''
def generate_queen_solution(board_size: int) -> list[int]:
    # Store queen placement
    sol = [-1] * board_size

    # Used columns, L -> R diag, and R -> L diag
    used_cols = set()
    used_diagLR = set()
    used_diagRL = set()

    # Recursive helper to place queens onto board
    def backtrack(row):
        # Return copy of solution
            # Further mutations don't alter returned solution!
        if row == board_size:
            return sol.copy()
        
        # Shuffle all columns to get random solutions
            # Look through each column in the list
        for col in random.sample(range(board_size), board_size):

            # Skip placement because column already used or is under attack
            if col in used_cols or (row + col) in used_diagLR or (row - col) in used_diagRL:
                continue

            # Put queen in that location
            sol[row] = col

            # Mark column and diagonals as "occupied"
            used_cols.add(col)
            used_diagLR.add(row + col)
            used_diagRL.add(row - col)

            # Try placing a queen in the next row
            res = backtrack(row + 1)

            # If a non-None list is returned, we've found a complete solution (bubbles up out of recursion)
            if res:
                return res
            
            #print(f"undoing placement at ({row}, {col})")
            
            # Deeper recursion failed, so remove the queen and try the next column instead
            used_cols.remove(col)
            used_diagLR.remove(row + col)
            used_diagRL.remove(row - col)
        
        # Every column in row fails, so return None
            # Never occur because smallest board is 4 * 4
        return None

    # Call function starting at row 0
    solution = backtrack(0)
    #print(f"generate_queen_solution({board_size}) -> {solution}")
    return solution

'''
Return true if queens can attack one another and false if not
row1, col1: position of the first queen
row2, col2: position of the second queen
output: True if they are in the same row, column, or diagonal; otherwise False
'''
def queens_attack(row1: int, col1: int, row2: int, col2: int) -> bool:
    # Row, column, and diagonals
    return row1 == row2 or col1 == col2 or abs(row1 - row2) == abs(col1 - col2)

'''
Sees if a given region of the board remains connected after removing a cell
region_board: 2D grid where each cell is a region ID
region_id: the ID of the region to check
cell_to_remove: (row, col) of the cell to remove from the region
output: True if all remaining cells in the region are still 4-connected; otherwise False
'''
def is_region_connected(region_board: list[list[int]], region_id: int, cell_to_remove: tuple[int, int]) -> bool:
    n = len(region_board)

    # Get all cells in region except one being removed
    cells = [(i, j)
             for i in range(n)
             for j in range(n)
             if region_board[i][j] == region_id and (i, j) != cell_to_remove
            ]
    
    # No cells left in region (can't remove)
    if not cells:
        return False
    
    # Track which cells we've visited
    visited = set()
    # Start stack with first cell in list
    stack = [cells[0]]

    # DFS traversal to all cells in list
    while stack:
        # Get current cell in stack
        row, col = stack.pop()

        # Skip visited cells
        if (row, col) in visited:
            continue

        # Add new cells to set
        visited.add((row, col))

        # Compute neighbor for up, down, left, and right
        for d_row, d_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_row = row + d_row
            neighbor_col = col + d_col
        
            # Ensure neighbor cell inside board
            if (0 <= neighbor_row < n) and (0 <= neighbor_col < n):
                neighbor = (neighbor_row, neighbor_col)

                # Add to stack if it's in same region and not removed cell and not visited yet
                if (region_board[neighbor_row][neighbor_col] == region_id and
                    neighbor != cell_to_remove and
                    neighbor not in visited):
                        stack.append(neighbor)

    # Region connected if we visited every cell
    return len(visited) == len(cells)

'''
Create regions of colors seeded from queen's solution placement
solution: list where index = row and value = column of each queen
board_size: size of the square board (N x N)
output: 2D list where each cell contains a region ID associated with a queen
'''
def generate_regions(solution: list[int], board_size: int) -> list[list[int]]:
    # Create an empty board of correct size
    board = [[None for _ in range(board_size)] for _ in range(board_size)]
    # List of cells to fill next (row, col, region_id)
    fringe = []

    # Place each queen's location as seed of region
    for region_id in range(board_size):
        row = region_id
        # Queen at (row, col) in solution
        col = solution[region_id]

        # Mark cell with its region
        board[row][col] = region_id
        #print(f"Seeded region {region_id} at cell ({row}, {col})")

        # Compute neighbor for up, down, left, and right
        for d_row, d_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_row = row + d_row
            neighbor_col = col + d_col

            # Ensure neighbor cell inside board
            if 0 <= neighbor_row < board_size and 0 <= neighbor_col < board_size:
                # Add cell to fringe
                    # Next spots we could claim for this region
                fringe.append((neighbor_row, neighbor_col, region_id))

    # Randomized flood fill
        # Helps keep layouts irregular
    while fringe:
        # Pick a random cell in fringe and remove from fringe
        index = random.randrange(len(fringe))
        row, col, region_id = fringe.pop(index)

        # Skip cells already assigned
        if board[row][col] is not None:
            continue

        # Assign cell it's associated region ID
        board[row][col] = region_id
        #print(f"Filled cell ({row}, {col}) with region {region_id}")

        # Compute neighbor for up, down, left, and right
        for d_row, d_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor_row = row + d_row
            neighbor_col = col + d_col

            # Ensure neighbor cell inside board and not already assigned
            if (0 <= neighbor_row < board_size and 0 <= neighbor_col < board_size and
                board[neighbor_row][neighbor_col] is None):
                # Add cell to fringe
                    # Next spots we could claim for this region
                fringe.append((neighbor_row, neighbor_col, region_id))
    
    # Final board output
    #print("\nFinal region board:\n")
    #for row in board:
    #    print(" ".join(str(cell) if cell is not None else '.' for cell in row))
    
    # 2D grid where each cell's value is the ID of the queen-region it belongs to
    return board

'''
Sees if found region placement has a unique solution or needs to be carved
region_board: 2D list of integers where region_board[row][col] = region_id
output: A list of solutions, where each solution maps (row, column): solution[row] = column
'''
def find_queen_solutions(region_board: list[list[int]]) -> list[list[int]]:
    n = len(region_board)

    # Dictionary mapping region ID to a list of board cells (row, col) in that region
        # Prepares empty list for each region ID (fill with (row, col) coordinates belonging to that region)
    region_cells = {region_id: [] for region_id in range(n)}

    # Populate region's list with all cells in it
    for row in range(n):
        for col in range(n):
            # Read the region ID of a cell
            region = region_board[row][col]
            # Add the cell to its respective list at region position in dictionary
            region_cells[region].append((row, col))

    # Sort regions by size of cell lists (ascending)
        # Small cells sorted first (MRV heuristic)
        # Try most constrained regions first to prune faster
    region_order = sorted(region_cells, key = lambda r: len(region_cells[r]))

    # Track which constraints are already used
        # Avoid row, column, and diagonal conflicts
    used_rows = set()
    used_cols = set()
    used_diagLR = set()
    used_diagRL = set()
    # Hold cells for each region as partial assignements built
        # Maps region_id to (row, col)
    queen_in_region = {}
    # keep track of solutions found (up to 2 solutions)
    solutions = []

    # Recursive constraint satisfaction problem (CSP) solver
        # region_index: which region in region_order we're assigning next
    def backtrack(region_index):
        # Only care if there's > 1 solution
            # Saves work to leave early
        if len(solutions) >= 2:
            return
        
        # All regions assigned one queen
        if region_index == n:
            # Build row -> col list
            board_row_to_col = [-1] * n

            # Loop through region ids
            for region_id, (row, col) in queen_in_region.items():
                # Store column of queen placement in row position of list
                board_row_to_col[row] = col

            # Add to solutions
            solutions.append(board_row_to_col)
            #print(f"Found Solution: {board_row_to_col}")
            return
        
        # Next region ID to place
        current_region = region_order[region_index]
        #print(f"Trying to place queen for region {current_region} (index {region_index})")

        # Loop through all possible cell (row, col) slots
        for (row, col) in region_cells[current_region]:
            # Placement invalid (conflict with another queen) so skip
            if (row in used_rows or col in used_cols or
                (row + col) in used_diagLR or (row - col) in used_diagRL):
                continue

            # Add queen to that position
                # Mark all constraints used and record placement
            used_rows.add(row)
            used_cols.add(col)
            used_diagLR.add(row + col)
            used_diagRL.add(row - col)
            queen_in_region[current_region] = (row, col)

            # Recurse to fill next region
            backtrack(region_index + 1)

            # Backtrack (undo) the move
            used_rows.remove(row)
            used_cols.remove(col)
            used_diagLR.remove(row + col)
            used_diagRL.remove(row - col)
            del queen_in_region[current_region]

            # Early stopping (2 solutions found)
            if len(solutions) >= 2:
                return

    # Call backtrack starting at row 0
    backtrack(0)
    #print(f"find_queen_solutions: returning {len(solutions)} solution(s)")
    return solutions

'''
Modify regions to try and ensure only 1 valid solution
target_solution: the desired unique N-Queens solution (list of column positions)
region_board: Current 2D grid where each cell has a region ID
max_attempts: number of modification attempts before giving up
output: modified region_board with at most one valid N-Queens solution
'''
def carve_regions(target_solution: list[int], region_board: list[list[int]], max_attempts: int = 200) -> list[list[int]]:
    n = len(region_board)
    attempt = 0

    # Cap attempts to carving
    while attempt < max_attempts:
        attempt += 1

        # Returns up to 2 solutions
        solutions = find_queen_solutions(region_board)

        # Return solution if uniqueness met
        if len(solutions) < 2:
            print(f"Uniqueness achieved after {attempt} attempt(s).")
            return region_board
        
        # Alternate solution that we want to get rid of
        alternate_solution = solutions[1]
        # See if we've made a change
        made_change = False

        # Loop through all rows in board
            # As long as we change one row, the whole solution is invalid
        for row in range(n):
            # First row where queen put in alternate column
                # Try to make this placement invalid
            if alternate_solution[row] != target_solution[row]:
                wrong_col = alternate_solution[row]
                region_to_remove_from = region_board[row][wrong_col]

                # Try to remove cell from region by merging into a neighbor's region
                for d_row, d_col in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    neighbor_row = row + d_row
                    neighbor_col = wrong_col + d_col

                    # Ensure neighbor cell inside board
                    if (0 <= neighbor_row < n and 0 <= neighbor_col < n):
                        neighbor_region = region_board[neighbor_row][neighbor_col]

                        # See if regions are different and ensure region connectivity isn't broken
                        if (neighbor_region != region_to_remove_from and
                            is_region_connected(region_board, region_to_remove_from, (row, wrong_col))):
                            # Reassign to neighbor region
                            region_board[row][wrong_col] = neighbor_region
                            made_change = True
                            # Stop after successful change
                            break

                # Stop after successful change
                if made_change:
                    break
        
        # No neighbor merge possible
        if not made_change:
            print(f"Gave up after {attempt} attempt(s): can't modify further.")
            return region_board

    # Max attempts reached
    print(f"Maximum attempts ({max_attempts}) reached without enforcing uniqueness.")
    return region_board