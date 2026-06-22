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
        self._filled = 0
        self._shape_cells = {}  # shape_id -> list of (x, y) for fast removal

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
        coords = []
        for dx, dy in shape:
            x, y = ox + dx, oy + dy
            self.cells[x][y] = shape_id
            coords.append((x, y))
        self._shape_cells[shape_id] = coords
        self._filled += len(shape)
        self.placements.append((name, rot, ox, oy, shape_id))
        return shape_id

    def remove(self, shape_id: int):
        """Remove a placed shape by its ID using stored coordinates."""
        coords = self._shape_cells.pop(shape_id)
        for x, y in coords:
            self.cells[x][y] = 0
        self._filled -= len(coords)
        self.placements.pop()  # backtracking always removes the last placed

    def cells_filled(self) -> int:
        """Count how many cells are occupied."""
        return self._filled

    def is_full(self) -> bool:
        return self._filled == self.SIZE * self.SIZE

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

    def display_pretty(self, colorblind: bool = False) -> str:
        """Display with colored blocks. Each shape instance gets a unique color
        ensuring adjacent pieces are always visually distinct."""
        if colorblind:
            COLORS = [
                "\033[48;5;24m",   # dark blue
                "\033[48;5;166m",  # orange
                "\033[48;5;72m",   # teal
                "\033[48;5;132m",  # purple
                "\033[48;5;136m",  # gold
                "\033[48;5;30m",   # dark cyan
                "\033[48;5;174m",  # pink
                "\033[48;5;67m",   # steel
                "\033[48;5;107m",  # olive
                "\033[48;5;95m",   # dusty rose
                "\033[48;5;37m",   # cyan
                "\033[48;5;180m",  # tan
                "\033[48;5;60m",   # slate
                "\033[48;5;203m",  # coral
                "\033[48;5;109m",  # light slate
                "\033[48;5;173m",  # peach
            ]
        else:
            # Muted matte palette — ordered to maximize contrast between adjacent indices
            # Alternates: dark/light, warm/cool so any two neighbors are distinct
            COLORS = [
                "\033[48;5;124m",  # muted red (dark warm)
                "\033[48;5;37m",   # muted cyan (light cool)
                "\033[48;5;136m",  # muted gold (light warm)
                "\033[48;5;24m",   # muted dark blue (dark cool)
                "\033[48;5;34m",   # muted green (medium cool)
                "\033[48;5;168m",  # muted pink (light warm)
                "\033[48;5;22m",   # muted dark green (dark cool)
                "\033[48;5;172m",  # muted orange (light warm)
                "\033[48;5;55m",   # muted indigo (dark cool)
                "\033[48;5;178m",  # muted yellow (light warm)
                "\033[48;5;97m",   # muted purple (dark warm)
                "\033[48;5;36m",   # muted sea green (light cool)
                "\033[48;5;88m",   # muted dark red (dark warm)
                "\033[48;5;143m",  # muted khaki (light warm)
                "\033[48;5;25m",   # muted blue (dark cool)
                "\033[48;5;133m",  # muted magenta (medium warm)
                "\033[48;5;28m",   # muted forest green (dark cool)
                "\033[48;5;94m",   # muted brown (medium warm)
                "\033[48;5;67m",   # muted sky blue (medium cool)
                "\033[48;5;125m",  # muted deep pink (dark warm)
            ]
        RESET = "\033[0m"

        size = self.SIZE

        # Build adjacency between shape IDs
        neighbors = {}
        for x in range(size):
            for y in range(size):
                curr = self.cells[x][y]
                if curr <= 0:
                    continue
                if curr not in neighbors:
                    neighbors[curr] = set()
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < size and 0 <= ny < size:
                        adj = self.cells[nx][ny]
                        if adj > 0 and adj != curr:
                            neighbors[curr].add(adj)

        # Assign a fixed base color per shape TYPE (for the legend)
        name_to_base = {}
        base_idx = 0
        for name, _, _, _, _ in self.placements:
            if name not in name_to_base:
                name_to_base[name] = base_idx
                base_idx += 1

        # Graph coloring: assign colors to each piece, preferring its type's base color
        # but picking the most distant available color if there's a conflict
        id_to_color = {}
        id_to_name = {}
        for name, _, _, _, shape_id in self.placements:
            id_to_name[shape_id] = name
            if shape_id not in neighbors:
                neighbors[shape_id] = set()
            used_colors = {id_to_color[n] for n in neighbors[shape_id] if n in id_to_color}

            # Try the base color for this type first
            preferred = name_to_base[name]
            if preferred not in used_colors:
                id_to_color[shape_id] = preferred
            else:
                # Pick the color with maximum distance from all used neighbor colors
                num_colors = len(COLORS)
                best_candidate = None
                best_min_dist = -1
                for candidate in range(num_colors):
                    if candidate in used_colors:
                        continue
                    # Distance = minimum gap to any used color (wrapping around)
                    min_dist = min(
                        min(abs(candidate - uc), num_colors - abs(candidate - uc))
                        for uc in used_colors
                    ) if used_colors else num_colors
                    if min_dist > best_min_dist:
                        best_min_dist = min_dist
                        best_candidate = candidate
                if best_candidate is not None:
                    id_to_color[shape_id] = best_candidate
                else:
                    id_to_color[shape_id] = preferred  # fallback

        def colored_cell(shape_id):
            if shape_id <= 0:
                return "  "
            color_idx = id_to_color[shape_id]
            bg = COLORS[color_idx % len(COLORS)]
            return f"{bg}  {RESET}"

        lines = []

        # X-axis label
        x_label = "   "
        for x in range(1, size + 1):
            x_label += f"{x} "
        lines.append(x_label)

        # Grid rows from top to bottom
        for y in range(size - 1, -1, -1):
            row_str = f"{y + 1}  "
            for x in range(size):
                row_str += colored_cell(self.cells[x][y])
            lines.append(row_str)

        lines.append("")

        # Legend — one entry per shape type using its base color
        lines.append("   Legend:")
        for name in name_to_base:
            color_idx = name_to_base[name]
            bg = COLORS[color_idx % len(COLORS)]
            lines.append(f"   {bg}  {RESET} = {name}")

        return "\n".join(lines)


def find_first_empty(grid: Grid) -> Optional[Coord]:
    """Find the first empty cell scanning bottom-to-top, left-to-right."""
    for y in range(Grid.SIZE):
        for x in range(Grid.SIZE):
            if grid.cells[x][y] == 0:
                return (x, y)
    return None


def solve(grid: Grid, shapes_to_place: List[Tuple[str, List[Shape]]],
          best: List[int], best_grid: List[Optional['Grid']],
          calls: List[int] = None, max_attempts: int = 7_000_000,
          timeout: float = 30, start_time: float = None) -> bool:
    """
    Backtracking solver with constraint propagation.
    
    Targets the first empty cell — tries all shapes that can cover it.
    If no shape can cover it, marks it as a dead cell and continues
    placing remaining shapes elsewhere (maximizes cells filled).
    Deduplicates identical shapes to avoid redundant work.
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

    # Find the first empty cell (bottom-to-top, left-to-right)
    target = None
    for y in range(Grid.SIZE):
        for x in range(Grid.SIZE):
            if grid.cells[x][y] == 0:
                target = (x, y)
                break
        if target:
            break

    if target is None:
        print(f"\r  Solution found after {calls[0]:,} attempts ({time.time() - start_time:.1f}s).                          ")
        return True

    tx, ty = target

    # Try each remaining shape, skipping duplicates
    tried_shapes = set()
    any_placed = False
    for i, (name, rotations) in enumerate(shapes_to_place):
        if name in tried_shapes:
            continue
        tried_shapes.add(name)

        remaining = shapes_to_place[:i] + shapes_to_place[i+1:]

        for rot_shape in rotations:
            # Only try placements that cover the target empty cell
            for dx, dy in rot_shape:
                ox, oy = tx - dx, ty - dy
                if grid.can_place(rot_shape, ox, oy):
                    any_placed = True
                    shape_id = grid.place(rot_shape, ox, oy, name, 0)
                    if solve(grid, remaining, best, best_grid, calls, max_attempts, timeout, start_time):
                        return True
                    grid.remove(shape_id)
                    # Early exit if limits hit
                    if calls[0] > max_attempts:
                        return False
                    if calls[0] % 1000 == 0 and time.time() - start_time >= timeout:
                        return False

    # If no shape could cover this cell, this branch is a dead end.
    # The best partial solution is already tracked via best_grid.
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


def pack_shapes(shape_list: List[str], strategy: str = "greedy", timeout: float = 30) -> Grid:
    """
    Main entry point. Takes a list of shape names and packs them into a 9x9 grid.
    Each shape will be tried in all valid rotations.
    Jewels are placed last, backfilling any remaining empty cells.

    Args:
        shape_list: List of shape names (keys from SHAPES dict).
        strategy: "greedy" for fast heuristic, "backtrack" for optimal search.
        timeout: Max seconds for backtracking solver (default 30).

    Returns:
        The resulting Grid with shapes placed.
    """
    # Separate jewels from other shapes
    jewels = [name for name in shape_list if name == "jewel"]
    other_shapes = [name for name in shape_list if name != "jewel"]

    shapes_to_place = []
    for name in other_shapes:
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
                       max_attempts=7_000_000, timeout=timeout, start_time=time.time())
        if not solved:
            if calls[0] > 7_000_000:
                print(f"\r  Max attempts (7,000,000) reached. Best: {best[0]} cells filled.                ")
            else:
                print(f"\r  Exhausted search after {calls[0]:,} attempts. Best: {best[0]} cells filled.     ")
            grid = best_grid[0] if best_grid[0] else grid
    else:
        greedy_place(grid, shapes_to_place)

    # Backfill empty cells with jewels
    if jewels:
        jewel_shape = SHAPE_ROTATIONS["jewel"][0]
        for y in range(Grid.SIZE):
            for x in range(Grid.SIZE):
                if not jewels:
                    break
                if grid.cells[x][y] == 0:
                    grid.place(jewel_shape, x, y, "jewel", 0)
                    jewels.pop()

    return grid


# --- CLI ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Parse command-line arguments as shape names with optional quantities
        # Usage: python3 tetris_grid.py shotgun:3 dual_pistols:2 buffs grenade:4
        # A shape without a quantity defaults to 1
        # Use --backtrack flag for optimal solver (default is greedy)
        args = sys.argv[1:]
        strategy = "backtrack"
        timeout = 30  # default 30 seconds

        if "--greedy" in args:
            args.remove("--greedy")
            strategy = "greedy"

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

        colorblind = False
        if "--colorblind" in args:
            args.remove("--colorblind")
            colorblind = True

        if "--help" in args or "-h" in args:
            print("Usage: python3 ark_ranger.py [--greedy] [--timeout SECONDS] [--colorblind] shape1[:qty] shape2[:qty] ...")
            print(f"\nAvailable shapes: {', '.join(sorted(SHAPES.keys()))}")
            print("\nExamples:")
            print("  python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4")
            print("  python3 ark_ranger.py --greedy blade:2 machine:3 fire corner:5")
            print("  python3 ark_ranger.py --timeout 30 blade:2 machine:3")
            print("  python3 ark_ranger.py --colorblind shotgun:3 square:4")
            print("\nFlags:")
            print("  --greedy          Use fast greedy heuristic (may not find optimal solution)")
            print("                    Default is backtracking (thorough, finds valid arrangements)")
            print("  --timeout SECS    Max seconds for backtracking (default: 30)")
            print("  --colorblind      Use colorblind-friendly palette")
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
        print(result.display_pretty(colorblind=colorblind))
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
    else:
        print("Usage: python3 ark_ranger.py [--greedy] [--timeout SECONDS] [--colorblind] shape1[:qty] shape2[:qty] ...")
        print(f"\nAvailable shapes: {', '.join(sorted(SHAPES.keys()))}")
        print("\nExamples:")
        print("  python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4")
        print("  python3 ark_ranger.py --greedy blade:2 machine:3 fire corner:5")
