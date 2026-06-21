#!/usr/bin/env python3
"""
Tetris-style shape packer for a 9x9 grid.

Coordinates use math-style (x, y):
  - x = column (increases rightward)
  - y = row (increases upward)
  - (0, 0) = bottom-left corner

Defines shapes as relative (x, y) offset sets, supports rotation (0/90/180/270),
and uses backtracking or greedy heuristics to optimally arrange them.
"""

import copy
import time
from typing import List, Tuple, Set, Optional

# Type aliases
Coord = Tuple[int, int]  # (x, y) where x=col, y=row from bottom-left
Shape = List[Coord]

# --- Shape Definitions ---
# Each shape is a list of (x, y) offsets relative to a reference point.
# x increases rightward, y increases upward.
# Only one orientation is needed per shape — rotations are generated automatically.

SHAPES = {
    # Single
    "jewel": [(0, 0)],

    # Lines (horizontal)
    "buffs": [(0, 0), (1, 0), (2, 0)],

    # Squares
    "square": [(0, 0), (1, 0), (0, 1), (1, 1)],

    # L-shape (other orientations come from rotation)
    "shotgun": [(0, 0), (0, 1), (0, 2), (1, 0)],

    # T-shape
    "dual_pistols": [(0, 0), (1, 0), (2, 0), (1, 1)],

    # S/Z shapes
    "launcher": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "photon": [(0, 1), (1, 0), (1, 1), (2, 0)],

    # Corner (2x2 missing one)
    "corner": [(0, 0), (1, 0), (0, 1)],

    # Plus/cross
    "blade": [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],

    # Data chip (horizontal domino)
    "data_chip": [(0, 0), (1, 0)],

    # 5-cell shapes
    "machine": [(0, 1), (1, 1), (1, 0), (2, 1), (3, 1)],
    "fire": [(0, 1), (1, 1), (2, 1), (2, 0), (3, 1)],
    "rifle_laser": [(0, 0), (0, 1), (1, 1), (2, 1), (3, 1)],
    "bowgun": [(0, 0), (1, 0), (2, 0), (1, 1), (1, 2)],
}


# --- Rotation Utilities ---

def normalize(shape: Shape) -> Shape:
    """
    Normalize a shape so its bottom-left bounding corner is at (0, 0).
    Returns sorted coordinates for consistent comparison.
    """
    min_x = min(x for x, y in shape)
    min_y = min(y for x, y in shape)
    normalized = sorted((x - min_x, y - min_y) for x, y in shape)
    return normalized


def rotate_90(shape: Shape) -> Shape:
    """Rotate shape 90 degrees counter-clockwise: (x, y) -> (-y, x)."""
    return [(-y, x) for x, y in shape]


def get_rotations(shape: Shape) -> List[Shape]:
    """
    Generate all unique rotations (0°, 90°, 180°, 270°) of a shape.
    Deduplicates symmetric shapes (e.g., square only has 1 unique rotation).
    """
    seen = set()
    rotations = []
    current = shape

    for _ in range(4):
        normed = normalize(current)
        key = tuple(normed)
        if key not in seen:
            seen.add(key)
            rotations.append(normed)
        current = rotate_90(current)

    return rotations


# Pre-compute all rotations for each shape
SHAPE_ROTATIONS = {name: get_rotations(coords) for name, coords in SHAPES.items()}


class Grid:
    """A 9x9 grid using math-style (x, y) coordinates with (0,0) at bottom-left."""

    SIZE = 9

    def __init__(self):
        # cells[x][y]: 0 = empty, positive int = shape ID
        self.cells = [[0] * self.SIZE for _ in range(self.SIZE)]
        self.placements = []  # list of (shape_name, rotation_idx, x, y, shape_id)
        self.next_id = 1

    def can_place(self, shape: Shape, ox: int, oy: int) -> bool:
        """Check if a shape can be placed at origin (ox, oy)."""
        for dx, dy in shape:
            x, y = ox + dx, oy + dy
            if x < 0 or x >= self.SIZE or y < 0 or y >= self.SIZE:
                return False
            if self.cells[x][y] != 0:
                return False
        return True

    def place(self, shape: Shape, ox: int, oy: int, name: str = "", rot: int = 0) -> int:
        """Place a shape at origin (ox, oy) and return its ID."""
        shape_id = self.next_id
        self.next_id += 1
        for dx, dy in shape:
            self.cells[ox + dx][oy + dy] = shape_id
        self.placements.append((name, rot, ox, oy, shape_id))
        return shape_id

    def remove(self, shape_id: int):
        """Remove a placed shape by its ID."""
        for x in range(self.SIZE):
            for y in range(self.SIZE):
                if self.cells[x][y] == shape_id:
                    self.cells[x][y] = 0
        self.placements = [p for p in self.placements if p[4] != shape_id]

    def cells_filled(self) -> int:
        """Count how many cells are occupied."""
        return sum(1 for x in range(self.SIZE) for y in range(self.SIZE) if self.cells[x][y] != 0)

    def is_full(self) -> bool:
        return self.cells_filled() == self.SIZE * self.SIZE

    def display(self) -> str:
        """Return a visual string representation with (0,0) at bottom-left."""
        lines = []
        lines.append("    " + "  ".join(str(x) for x in range(self.SIZE)) + "  x")
        lines.append("   " + "---" * self.SIZE)
        # Print from top row (y=8) down to bottom row (y=0)
        for y in range(self.SIZE - 1, -1, -1):
            row_str = f"{y} |"
            for x in range(self.SIZE):
                val = self.cells[x][y]
                if val:
                    row_str += f" {val:2d}"
                else:
                    row_str += "  ."
            lines.append(row_str)
        lines.append("y")
        return "\n".join(lines)

    def display_pretty(self) -> str:
        """Display with box-drawing borders between different shapes. (0,0) at bottom-left."""
        # Box-drawing characters
        H = "─"  # horizontal
        V = "│"  # vertical
        TL = "┌"  # top-left
        TR = "┐"  # top-right
        BL = "└"  # bottom-left
        BR = "┘"  # bottom-right
        T = "┬"   # top tee
        B = "┴"   # bottom tee
        L = "├"   # left tee
        R = "┤"   # right tee
        X = "┼"   # cross

        size = self.SIZE

        def get_id(x, y):
            """Get shape ID at (x, y), or 0 if out of bounds or empty."""
            if 0 <= x < size and 0 <= y < size:
                return self.cells[x][y]
            return 0

        # Build the grid string with borders
        # Each cell is 3 chars wide, 1 char tall
        # We need (size+1) horizontal lines and (size+1) vertical lines
        lines = []

        # X-axis label
        x_label = "    "
        for x in range(size):
            x_label += f" {x}  "
        lines.append(x_label + " x")

        # Build row by row from top (y=8) to bottom (y=0)
        for y in range(size - 1, -1, -1):
            # Top border of this row
            border = ""
            for x in range(size):
                above = get_id(x, y + 1)
                curr = get_id(x, y)
                # Determine left corner
                left_above = get_id(x - 1, y + 1)
                left_curr = get_id(x - 1, y)

                # Choose corner character
                if x == 0:
                    if y == size - 1:
                        corner = TL
                    else:
                        # Left edge: is there a border above or below?
                        h_border = (above != curr)
                        v_border_below = (left_curr != curr)  # always true at edge
                        corner = L if h_border else V if v_border_below else " "
                        corner = L
                else:
                    h_left = (left_above != left_curr)
                    h_right = (above != curr)
                    v_top = (left_above != above)
                    v_bottom = (left_curr != curr)

                    if y == size - 1:
                        # Top edge
                        if v_bottom:
                            corner = T
                        else:
                            corner = H if h_right else H
                            corner = T if v_bottom else H
                    else:
                        # Interior
                        has_h = h_left or h_right
                        has_v = v_top or v_bottom
                        if has_h and has_v:
                            corner = X
                        elif has_h:
                            if v_bottom:
                                corner = T
                            elif v_top:
                                corner = B
                            else:
                                corner = H
                        elif has_v:
                            if h_right:
                                corner = L
                            elif h_left:
                                corner = R
                            else:
                                corner = V
                        else:
                            corner = " "

                # Horizontal segment
                if above != curr:
                    seg = H * 3
                else:
                    seg = "   "

                border += corner + seg

            # Right edge corner
            if y == size - 1:
                border += TR
            else:
                above_r = get_id(size - 1, y + 1)
                curr_r = get_id(size - 1, y)
                if above_r != curr_r:
                    border += R
                else:
                    border += V

            lines.append("   " + border)

            # Cell content row
            row_str = f"{y}  {V}"
            for x in range(size):
                curr = get_id(x, y)
                right = get_id(x + 1, y)

                # Cell content
                if curr == 0:
                    cell = " . "
                else:
                    # Map to label
                    idx = next((i for i, p in enumerate(self.placements) if p[4] == curr), -1)
                    if idx >= 0 and idx < 26:
                        cell = f" {chr(65 + idx)} "
                    elif idx >= 0:
                        cell = f" {chr(97 + idx - 26)} "
                    else:
                        cell = " ? "

                # Right border
                if x == size - 1:
                    row_str += cell + V
                elif curr != right:
                    row_str += cell + V
                else:
                    row_str += cell + " "

            lines.append(row_str)

        # Bottom border
        border = ""
        for x in range(size):
            curr = get_id(x, 0)
            left = get_id(x - 1, 0)
            if x == 0:
                corner = BL
            else:
                if left != curr:
                    corner = B
                else:
                    corner = H
            border += corner + H * 3
        border += BR
        lines.append("   " + border)
        lines.append("y")

        return "\n".join(lines)


def find_first_empty(grid: Grid) -> Optional[Coord]:
    """Find the first empty cell scanning bottom-to-top, left-to-right."""
    for y in range(Grid.SIZE):
        for x in range(Grid.SIZE):
            if grid.cells[x][y] == 0:
                return (x, y)
    return None


def solve(grid: Grid, shapes_to_place: List[Tuple[str, List[Shape]]],
          best: List[int], best_grid: List[Optional[Grid]],
          calls: List[int] = None, max_attempts: int = 5_000_000,
          timeout: float = 120, start_time: float = None) -> bool:
    """
    Backtracking solver that tries to place all shapes.
    Tries all rotations for each shape at each position.

    Returns True if all shapes are placed.
    Tracks the best solution found (most cells filled).
    Stops if max_attempts or timeout is reached.
    """
    if calls is None:
        calls = [0]
    if start_time is None:
        start_time = time.time()

    calls[0] += 1

    # Check limits
    if calls[0] > max_attempts:
        return False

    if calls[0] % 1000 == 0:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            print(f"\r  Timeout ({timeout}s) reached after {calls[0]:,} attempts.                          ")
            return False
        print(f"\r  Searching... {calls[0]:,} attempts | best so far: {best[0]} cells | {elapsed:.0f}s elapsed", end="", flush=True)

    current_filled = grid.cells_filled()
    if current_filled > best[0]:
        best[0] = current_filled
        best_grid[0] = copy.deepcopy(grid)

    if not shapes_to_place:
        print(f"\r  Solution found after {calls[0]:,} attempts ({time.time() - start_time:.1f}s).                          ")
        return True

    # Try each remaining shape at every valid position on the grid
    for i, (name, rotations) in enumerate(shapes_to_place):
        remaining = shapes_to_place[:i] + shapes_to_place[i+1:]

        for rot_idx, rot_shape in enumerate(rotations):
            for ox in range(Grid.SIZE):
                for oy in range(Grid.SIZE):
                    if grid.can_place(rot_shape, ox, oy):
                        shape_id = grid.place(rot_shape, ox, oy, name, rot_idx)
                        if solve(grid, remaining, best, best_grid, calls, max_attempts, timeout, start_time):
                            return True
                        grid.remove(shape_id)
                        # Early exit if limits hit
                        if calls[0] > max_attempts:
                            return False
                        if calls[0] % 1000 == 0 and time.time() - start_time >= timeout:
                            return False

    return False


def greedy_place(grid: Grid, shapes_to_place: List[Tuple[str, List[Shape]]]) -> Grid:
    """
    Greedy heuristic: for each empty cell (bottom-left first), try to place
    the largest fitting shape in any rotation. Fast but not optimal.
    If no shape can cover a given empty cell, skip it and try the next one.
    """
    remaining = list(shapes_to_place)
    # Sort by size descending so we try big pieces first
    remaining.sort(key=lambda x: len(x[1][0]), reverse=True)

    changed = True
    while changed and remaining:
        changed = False
        # Scan all empty cells
        for y in range(Grid.SIZE):
            for x in range(Grid.SIZE):
                if grid.cells[x][y] != 0:
                    continue
                # Try to place a shape covering this cell
                for i, (name, rotations) in enumerate(remaining):
                    placed = False
                    for rot_idx, rot_shape in enumerate(rotations):
                        for dx, dy in rot_shape:
                            ox, oy = x - dx, y - dy
                            if grid.can_place(rot_shape, ox, oy):
                                grid.place(rot_shape, ox, oy, name, rot_idx)
                                remaining.pop(i)
                                placed = True
                                changed = True
                                break
                        if placed:
                            break
                    if placed:
                        break
                if changed:
                    break
            if changed:
                break

    return grid


def pack_shapes(shape_list: List[str], strategy: str = "greedy", timeout: float = 120) -> Grid:
    """
    Main entry point. Takes a list of shape names and packs them into a 9x9 grid.
    Each shape will be tried in all valid rotations.

    Args:
        shape_list: List of shape names (keys from SHAPES dict).
        strategy: "greedy" for fast heuristic, "backtrack" for optimal search.
        timeout: Max seconds for backtracking solver (default 120).

    Returns:
        The resulting Grid with shapes placed.
    """
    shapes_to_place = []
    for name in shape_list:
        if name not in SHAPES:
            raise ValueError(f"Unknown shape: '{name}'. Available: {sorted(SHAPES.keys())}")
        shapes_to_place.append((name, SHAPE_ROTATIONS[name]))

    grid = Grid()

    if strategy == "backtrack":
        best = [0]
        best_grid = [None]
        calls = [0]
        # Sort largest first for better pruning
        shapes_to_place.sort(key=lambda x: len(x[1][0]), reverse=True)
        solved = solve(grid, shapes_to_place, best, best_grid, calls,
                       max_attempts=5_000_000, timeout=timeout, start_time=time.time())
        if solved:
            return grid
        # Return best partial solution found
        if calls[0] > 5_000_000:
            print(f"\r  Max attempts (5,000,000) reached. Best: {best[0]} cells filled.                ")
        elif not solved and calls[0] <= 5_000_000:
            elapsed = time.time()
            print(f"\r  Exhausted search after {calls[0]:,} attempts. Best: {best[0]} cells filled.     ")
        return best_grid[0] if best_grid[0] else grid
    else:
        return greedy_place(grid, shapes_to_place)


# --- CLI ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Parse command-line arguments as shape names with optional quantities
        # Usage: python3 tetris_grid.py shotgun:3 dual_pistols:2 buffs grenade:4
        # A shape without a quantity defaults to 1
        # Use --backtrack flag for optimal solver (default is greedy)
        args = sys.argv[1:]
        strategy = "greedy"
        timeout = 120  # default 2 minutes

        if "--backtrack" in args:
            args.remove("--backtrack")
            strategy = "backtrack"

        # Parse --timeout flag
        if "--timeout" in args:
            idx = args.index("--timeout")
            if idx + 1 < len(args):
                try:
                    timeout = int(args[idx + 1])
                except ValueError:
                    print(f"Error: --timeout requires a number (seconds). Got '{args[idx + 1]}'")
                    sys.exit(1)
                args.pop(idx)  # remove --timeout
                args.pop(idx)  # remove the value
            else:
                print("Error: --timeout requires a value (seconds)")
                sys.exit(1)

        if "--help" in args or "-h" in args:
            print("Usage: python3 ark_ranger.py [--backtrack] [--timeout SECONDS] shape1[:qty] shape2[:qty] ...")
            print(f"\nAvailable shapes: {', '.join(sorted(SHAPES.keys()))}")
            print("\nExamples:")
            print("  python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4")
            print("  python3 ark_ranger.py --backtrack blade:2 machine:3 fire corner:5")
            print("  python3 ark_ranger.py --backtrack --timeout 60 blade:2 machine:3")
            print("\nFlags:")
            print("  --backtrack       Use exhaustive backtracking solver (slower, optimal)")
            print("                    Default is greedy (fast, may not be optimal)")
            print("  --timeout SECS    Max seconds for backtracking (default: 120)")
            sys.exit(0)

        # Validate shape names
        for name in args:
            if ":" in name:
                name = name.rsplit(":", 1)[0]
            if name not in SHAPES:
                print(f"Error: Unknown shape '{name}'")
                print(f"Available shapes: {', '.join(sorted(SHAPES.keys()))}")
                sys.exit(1)

        # Parse shape:quantity pairs
        shape_list = []
        for arg in args:
            if ":" in arg:
                name, qty_str = arg.rsplit(":", 1)
                try:
                    qty = int(qty_str)
                except ValueError:
                    print(f"Error: Invalid quantity in '{arg}'. Use format shape:number")
                    sys.exit(1)
            else:
                name = arg
                qty = 1

            if name not in SHAPES:
                print(f"Error: Unknown shape '{name}'")
                print(f"Available shapes: {', '.join(sorted(SHAPES.keys()))}")
                sys.exit(1)

            shape_list.extend([name] * qty)

        total_cells = sum(len(SHAPES[s]) for s in shape_list)

        # Check if pieces exceed grid capacity
        if total_cells > 81:
            print(f"Error: Total cells ({total_cells}) exceed the 9x9 grid capacity (81).")
            print(f"Remove {total_cells - 81} cells worth of shapes to fit.")
            sys.exit(1)
        print(f"Packing {len(shape_list)} shapes ({total_cells} cells) using {strategy} strategy...\n")

        result = pack_shapes(shape_list, strategy=strategy, timeout=timeout)
        print(result.display_pretty())
        print(f"\nCells filled: {result.cells_filled()} / 81")
        print(f"Pieces placed: {len(result.placements)} / {len(shape_list)}")

        if len(result.placements) < len(shape_list):
            placed_names = [p[0] for p in result.placements]
            unplaced = list(shape_list)
            for name in placed_names:
                unplaced.remove(name)
            print(f"\n⚠️  Could not fit all pieces! {len(unplaced)} shape(s) unplaced:")
            for name in unplaced:
                print(f"  - {name}")

        if result.placements:
            print("\nPlacement details:")
            for name, rot, x, y, sid in result.placements:
                print(f"  {name} (rotation {rot}) at x={x}, y={y}")
    else:
        print("Usage: python3 tetris_grid.py [--backtrack] shape1[:qty] shape2[:qty] ...")
        print(f"\nAvailable shapes: {', '.join(sorted(SHAPES.keys()))}")
        print("\nExamples:")
        print("  python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4")
        print("  python3 ark_ranger.py --backtrack blade:2 machine:3 fire corner:5")
