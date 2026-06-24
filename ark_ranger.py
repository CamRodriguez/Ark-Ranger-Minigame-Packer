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


BLOCKED = -2  # Sentinel for cells that are not part of the grid


def load_grid_layout(filepath: str) -> List[List[bool]]:
    """
    Load a grid layout from a text file.
    '#' or 'X' = valid cell, '.' or ' ' = blocked/missing cell.
    The file is read top-to-bottom, so the first line is the top row.
    Returns a 2D list [x][y] where True = valid cell.
    """
    with open(filepath, 'r') as f:
        lines = [line.rstrip('\n') for line in f.readlines()]

    # Remove empty lines
    lines = [line for line in lines if line.strip()]

    # Parse each line into cells (split by spaces or treat each char)
    rows = []
    for line in lines:
        # Support space-separated or character-by-character
        if ' ' in line.strip():
            cells = line.split()
        else:
            cells = list(line)
        rows.append(cells)

    # Determine grid dimensions
    height = len(rows)
    width = max(len(row) for row in rows)

    # Build layout[x][y] — file is top-to-bottom, so flip y
    layout = [[False] * height for _ in range(width)]
    for row_idx, row in enumerate(rows):
        y = height - 1 - row_idx  # flip: first line = top = highest y
        for x, cell in enumerate(row):
            if cell in ('#', 'X', 'x'):
                layout[x][y] = True

    return layout


class Grid:
    """A grid using math-style (x, y) coordinates with (0,0) at bottom-left.
    Supports custom layouts with blocked cells. Optimized with tracked empty cells."""

    def __init__(self, layout: Optional[List[List[bool]]] = None, size: int = 9):
        if layout:
            self.width = len(layout)
            self.height = len(layout[0])
            self.cells = [[0] * self.height for _ in range(self.width)]
            self._valid_cells = 0
            self._empty_cells = []  # sorted list of empty (x,y) for fast lookup
            for y in range(self.height):
                for x in range(self.width):
                    if not layout[x][y]:
                        self.cells[x][y] = BLOCKED
                    else:
                        self._valid_cells += 1
                        self._empty_cells.append((x, y))
        else:
            self.width = size
            self.height = size
            self.cells = [[0] * self.height for _ in range(self.width)]
            self._valid_cells = size * size
            self._empty_cells = [(x, y) for y in range(size) for x in range(size)]

        self.placements = []
        self.next_id = 1
        self._filled = 0
        self._shape_cells = {}
        self._empty_set = set(self._empty_cells)  # O(1) membership check

    @property
    def SIZE(self):
        return max(self.width, self.height)

    def can_place(self, shape: Shape, ox: int, oy: int) -> bool:
        """Check if a shape can be placed at origin (ox, oy)."""
        for dx, dy in shape:
            x, y = ox + dx, oy + dy
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
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
            self._empty_set.discard((x, y))
        self._shape_cells[shape_id] = coords
        self._filled += len(shape)
        self.placements.append((name, rot, ox, oy, shape_id))
        return shape_id

    def remove(self, shape_id: int):
        """Remove a placed shape by its ID using stored coordinates."""
        coords = self._shape_cells.pop(shape_id)
        for x, y in coords:
            self.cells[x][y] = 0
            self._empty_set.add((x, y))
        self._filled -= len(coords)
        self.placements.pop()

    def first_empty(self) -> Optional[Coord]:
        """Find the first empty cell (bottom-to-top, left-to-right)."""
        # Scan in order since set is unordered
        for y in range(self.height):
            for x in range(self.width):
                if self.cells[x][y] == 0:
                    return (x, y)
        return None

    def snapshot(self) -> Tuple:
        """Lightweight snapshot of grid state for best-solution tracking."""
        cells_copy = [row[:] for row in self.cells]
        placements_copy = list(self.placements)
        return (cells_copy, placements_copy, self._filled, dict(self._shape_cells))

    def restore_snapshot(self, snap: Tuple):
        """Restore grid from a snapshot."""
        cells_copy, placements_copy, filled, shape_cells = snap
        self.cells = [row[:] for row in cells_copy]
        self.placements = list(placements_copy)
        self._filled = filled
        self._shape_cells = {k: list(v) for k, v in shape_cells.items()}
        # Rebuild empty set
        self._empty_set = set()
        for y in range(self.height):
            for x in range(self.width):
                if self.cells[x][y] == 0:
                    self._empty_set.add((x, y))

    def cells_filled(self) -> int:
        """Count how many cells are occupied."""
        return self._filled

    def is_full(self) -> bool:
        return self._filled == self._valid_cells

    def display(self) -> str:
        """Return a visual string representation with (0,0) at bottom-left."""
        lines = []
        lines.append("    " + "  ".join(str(x) for x in range(self.width)) + "  x")
        lines.append("   " + "---" * self.width)
        # Print from top row down to bottom row
        for y in range(self.height - 1, -1, -1):
            row_str = f"{y} |"
            for x in range(self.width):
                val = self.cells[x][y]
                if val == BLOCKED:
                    row_str += "  X"
                elif val:
                    row_str += f" {val:2d}"
                else:
                    row_str += "  ."
            lines.append(row_str)
        lines.append("y")
        return "\n".join(lines)

    def display_pretty(self, colorblind: bool = False, highlight_cells: Optional[List[Coord]] = None) -> str:
        """Display with colored blocks. Each shape instance gets a unique color
        ensuring adjacent pieces are always visually distinct.
        highlight_cells: list of (x,y) coords to mark as expansion tiles."""
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
            # High-contrast matte palette — no similar greens/cyans adjacent
            # Ordered to maximize perceptual distance between consecutive entries
            COLORS = [
                "\033[48;5;124m",  # brick red
                "\033[48;5;25m",   # navy blue
                "\033[48;5;178m",  # mustard yellow
                "\033[48;5;97m",   # plum purple
                "\033[48;5;34m",   # kelly green
                "\033[48;5;172m",  # burnt orange
                "\033[48;5;55m",   # deep indigo
                "\033[48;5;143m",  # olive tan
                "\033[48;5;168m",  # rose pink
                "\033[48;5;24m",   # dark teal
                "\033[48;5;136m",  # dark gold
                "\033[48;5;90m",   # dark magenta
                "\033[48;5;64m",   # army green
                "\033[48;5;131m",  # sienna
                "\033[48;5;61m",   # slate purple
                "\033[48;5;130m",  # rust
                "\033[48;5;23m",   # midnight blue
                "\033[48;5;94m",   # chocolate
                "\033[48;5;126m",  # berry
                "\033[48;5;58m",   # dark olive
            ]
        RESET = "\033[0m"

        width = self.width
        height = self.height

        # Build adjacency between shape IDs
        neighbors = {}
        for x in range(width):
            for y in range(height):
                curr = self.cells[x][y]
                if curr <= 0:
                    continue
                if curr not in neighbors:
                    neighbors[curr] = set()
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
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

        highlight_set = set(highlight_cells) if highlight_cells else set()

        def colored_cell(shape_id, x, y):
            is_highlight = (x, y) in highlight_set
            if shape_id <= 0:
                if is_highlight:
                    # Empty expansion tile — bright white with "++" marker
                    return "\033[48;5;255m\033[30m++\033[0m"
                if shape_id == BLOCKED:
                    return "  "
                return "  "
            if is_highlight:
                # Filled expansion tile — colored with dots to mark it
                color_idx = id_to_color[shape_id]
                bg = COLORS[color_idx % len(COLORS)]
                return f"{bg}\033[97m░░{RESET}"
            color_idx = id_to_color[shape_id]
            bg = COLORS[color_idx % len(COLORS)]
            return f"{bg}  {RESET}"

        lines = []

        # X-axis label
        x_label = "   "
        for x in range(1, width + 1):
            x_label += f"{x} "
        lines.append(x_label)

        # Grid rows from top to bottom
        for y in range(height - 1, -1, -1):
            row_str = f"{y + 1}  "
            for x in range(width):
                row_str += colored_cell(self.cells[x][y], x, y)
            lines.append(row_str)

        lines.append("")

        # Legend — one entry per shape type using its base color
        lines.append("   Legend:")
        for name in name_to_base:
            color_idx = name_to_base[name]
            bg = COLORS[color_idx % len(COLORS)]
            lines.append(f"   {bg}  {RESET} = {name}")
        if highlight_cells:
            lines.append(f"   \033[48;5;255m\033[30m++\033[0m = new expansion tile (empty)")
            lines.append(f"   ░░ = new expansion tile (filled)")

        return "\n".join(lines)



def solve(grid: Grid, shapes_to_place: List[Tuple[str, List[Shape]]],
          best: List[int], best_grid: List[Optional['Grid']],
          calls: List[int] = None, max_attempts: int = 7_000_000,
          timeout: float = 30, start_time: float = None, quiet: bool = False) -> bool:
    """
    Backtracking solver with constraint propagation.
    
    Targets the first empty cell. For shapes that can cover it, requires
    they do so. If some shapes cannot reach it, allows skipping the cell
    so those shapes can be placed elsewhere.
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
            if not quiet:
                print(f"\r  Timeout ({timeout}s) reached after {calls[0]:,} attempts.                          ")
            return False
        if not quiet:
            print(f"\r  Searching... {calls[0]:,} attempts | best so far: {best[0]} cells | {elapsed:.0f}s elapsed", end="", flush=True)

    current_filled = grid.cells_filled()
    if current_filled > best[0]:
        best[0] = current_filled
        best_grid[0] = grid.snapshot()

    if not shapes_to_place:
        if not quiet:
            print(f"\r  Solution found after {calls[0]:,} attempts ({time.time() - start_time:.1f}s).                          ")
        return True

    # Find the first empty cell (bottom-to-top, left-to-right)
    target = grid.first_empty()

    if target is None:
        # No empty cells left — but check if all shapes are placed
        if not shapes_to_place:
            if not quiet:
                print(f"\r  Solution found after {calls[0]:,} attempts ({time.time() - start_time:.1f}s).                          ")
            return True
        return False

    tx, ty = target

    # Try each remaining shape that can cover the target cell
    tried_shapes = set()
    has_uncoverable = False
    any_shape_covered = False
    for i, (name, rotations) in enumerate(shapes_to_place):
        if name in tried_shapes:
            continue
        tried_shapes.add(name)

        remaining = shapes_to_place[:i] + shapes_to_place[i+1:]

        shape_can_cover = False
        for rot_shape in rotations:
            for dx, dy in rot_shape:
                ox, oy = tx - dx, ty - dy
                if grid.can_place(rot_shape, ox, oy):
                    shape_can_cover = True
                    any_shape_covered = True
                    shape_id = grid.place(rot_shape, ox, oy, name, 0)
                    if solve(grid, remaining, best, best_grid, calls, max_attempts, timeout, start_time, quiet):
                        return True
                    grid.remove(shape_id)
                    if calls[0] > max_attempts:
                        return False
                    if calls[0] % 1000 == 0 and time.time() - start_time >= timeout:
                        return False

        if not shape_can_cover:
            has_uncoverable = True

    # If NO shape could cover this cell at all, skip it so remaining shapes
    # can be placed in other valid positions (only on non-rectangular grids).
    if not any_shape_covered:
        if grid._valid_cells < grid.width * grid.height:
            old_val = grid.cells[tx][ty]
            grid.cells[tx][ty] = BLOCKED
            if solve(grid, shapes_to_place, best, best_grid, calls, max_attempts, timeout, start_time, quiet):
                grid.cells[tx][ty] = old_val
                return True
            grid.cells[tx][ty] = old_val

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
        for y in range(grid.height):
            for x in range(grid.width):
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


def pack_shapes(shape_list: List[str], strategy: str = "greedy", timeout: float = 30,
                layout: Optional[List[List[bool]]] = None, quiet: bool = False) -> Grid:
    """
    Main entry point. Takes a list of shape names and packs them into a grid.
    Each shape will be tried in all valid rotations.
    Jewels are placed last, backfilling any remaining empty cells.

    Args:
        shape_list: List of shape names (keys from SHAPES dict).
        strategy: "greedy" for fast heuristic, "backtrack" for optimal search.
        timeout: Max seconds for backtracking solver (default 30).
        layout: Optional custom grid layout. None = default 9x9 square.

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

    grid = Grid(layout=layout)

    if strategy == "backtrack":
        best = [0]
        best_grid = [None]
        calls = [0]
        # Sort largest first for better pruning
        shapes_to_place.sort(key=lambda x: len(x[1][0]), reverse=True)
        solved = solve(grid, shapes_to_place, best, best_grid, calls,
                       max_attempts=7_000_000, timeout=timeout, start_time=time.time(), quiet=quiet)
        if not solved:
            if calls[0] > 7_000_000:
                if not quiet:
                    print(f"\r  Max attempts (7,000,000) reached. Best: {best[0]} cells filled.                ")
            else:
                if not quiet:
                    print(f"\r  Exhausted search after {calls[0]:,} attempts. Best: {best[0]} cells filled.     ")
            if best_grid[0]:
                grid.restore_snapshot(best_grid[0])
    else:
        greedy_place(grid, shapes_to_place)

    # Backfill empty cells with jewels
    if jewels:
        jewel_shape = SHAPE_ROTATIONS["jewel"][0]
        for y in range(grid.height):
            for x in range(grid.width):
                if not jewels:
                    break
                if grid.cells[x][y] == 0:
                    grid.place(jewel_shape, x, y, "jewel", 0)
                    jewels.pop()

    return grid


# --- Expansion Logic ---

def get_expansion_candidates(layout: List[List[bool]], max_width: int = 9, max_height: int = 9) -> Set[Coord]:
    """Find all cells adjacent to the current grid that are within 9x9 bounds."""
    width = len(layout)
    height = len(layout[0])
    candidates = set()

    for x in range(width):
        for y in range(height):
            if layout[x][y]:
                # Check all 4 neighbors
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = x + dx, y + dy
                    # Within current bounds but not already valid
                    if 0 <= nx < width and 0 <= ny < height and not layout[nx][ny]:
                        candidates.add((nx, ny))
                    # Expanding beyond current bounds (within 9x9)
                    elif nx == width and width < max_width:
                        candidates.add((nx, ny))
                    elif nx == -1 and width < max_width:
                        candidates.add((nx, ny))
                    elif ny == height and height < max_height:
                        candidates.add((nx, ny))
                    elif ny == -1 and height < max_height:
                        candidates.add((nx, ny))

    # Filter to valid coordinate range after potential expansion
    valid = set()
    for x, y in candidates:
        # Remap: if negative, we'd shift the grid. For simplicity,
        # only allow expansion in positive direction and within bounds.
        if 0 <= x < max_width and 0 <= y < max_height:
            valid.add((x, y))

    return valid


def generate_connected_expansions(layout: List[List[bool]], num_tiles: int = 6,
                                   max_width: int = 9, max_height: int = 9) -> List[List[Coord]]:
    """
    Generate all valid groups of num_tiles cells that are each adjacent to the existing grid.
    Each tile just needs to touch the grid, not necessarily each other.
    """
    candidates = get_expansion_candidates(layout, max_width, max_height)
    if len(candidates) < num_tiles:
        return []

    # Generate all combinations of num_tiles from candidates
    from itertools import combinations
    return [list(combo) for combo in combinations(sorted(candidates), num_tiles)]


def largest_connected_empty(grid: Grid) -> int:
    """Find the size of the largest connected group of empty cells."""
    visited = set()
    largest = 0

    for x in range(grid.width):
        for y in range(grid.height):
            if grid.cells[x][y] == 0 and (x, y) not in visited:
                # BFS to find connected empty region
                size = 0
                queue = [(x, y)]
                visited.add((x, y))
                while queue:
                    cx, cy = queue.pop(0)
                    size += 1
                    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        nx, ny = cx + dx, cy + dy
                        if (0 <= nx < grid.width and 0 <= ny < grid.height
                                and grid.cells[nx][ny] == 0
                                and (nx, ny) not in visited):
                            visited.add((nx, ny))
                            queue.append((nx, ny))
                largest = max(largest, size)

    return largest


def expand_layout(layout: List[List[bool]], expansion: List[Coord]) -> List[List[bool]]:
    """Create a new layout with the expansion tiles added."""
    # Determine new bounds
    all_x = [x for x in range(len(layout))] + [x for x, y in expansion]
    all_y = [y for y in range(len(layout[0]))] + [y for x, y in expansion]
    new_width = max(all_x) + 1
    new_height = max(all_y) + 1

    # Build new layout
    new_layout = [[False] * new_height for _ in range(new_width)]

    # Copy existing
    for x in range(len(layout)):
        for y in range(len(layout[0])):
            if layout[x][y]:
                new_layout[x][y] = True

    # Add expansion
    for x, y in expansion:
        new_layout[x][y] = True

    return new_layout


def score_expansion(result: Grid, expand_targets: List[str]) -> Tuple[int, int]:
    """
    Score an expansion result.
    If expand_targets is provided: score = how many target weapons fit in remaining space.
    Tiebreaker = largest connected empty group after fitting targets.
    If no targets: score = largest connected empty group.
    Returns (primary_score, tiebreaker_score).
    """
    if not expand_targets:
        return (largest_connected_empty(result), 0)

    # Try to fit as many target weapons as possible in the remaining empty space
    # Build a mini grid from just the empty cells of result
    target_shapes = []
    for name in expand_targets:
        if name in SHAPES:
            target_shapes.append(name)

    # Greedy-fit targets into remaining space
    remaining_targets = list(target_shapes)
    test_grid = copy.deepcopy(result)

    placed_count = 0
    # Try placing each target weapon greedily
    for name in remaining_targets:
        rotations = SHAPE_ROTATIONS[name]
        placed = False
        for rot_shape in rotations:
            for y in range(test_grid.height):
                for x in range(test_grid.width):
                    if test_grid.can_place(rot_shape, x, y):
                        test_grid.place(rot_shape, x, y, name, 0)
                        placed_count += 1
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break

    # Tiebreaker: largest empty group after fitting targets
    tiebreaker = largest_connected_empty(test_grid)
    return (placed_count, tiebreaker)


def find_best_expansion(layout: List[List[bool]], shape_list: List[str],
                        timeout_per_solve: float = 5,
                        expand_targets: Optional[List[str]] = None) -> Optional[Tuple[List[Coord], Grid, int]]:
    """
    Find the best 6-tile expansion using a two-phase approach:
    Phase 1: Greedy-solve all expansions (fast screening)
    Phase 2: Backtrack-solve only the top candidates (accurate)

    Scoring:
    - If expand_targets provided: best = fits most target weapons in remaining space.
    - If no targets: best = largest connected empty group after packing.

    Returns: (expansion_cells, solved_grid, score) or None
    """
    if expand_targets is None:
        expand_targets = []

    print("  Generating possible expansions...")
    expansions = generate_connected_expansions(layout, num_tiles=6)

    # Pre-filter: skip expansions where total grid capacity < total shape cells
    total_shape_cells = sum(len(SHAPES[s]) for s in shape_list if s in SHAPES)
    current_valid = sum(1 for x in range(len(layout)) for y in range(len(layout[0])) if layout[x][y])
    filtered = []
    for exp in expansions:
        if current_valid + 6 >= total_shape_cells:
            filtered.append(exp)
    expansions = filtered if filtered else expansions

    if not expansions:
        width = len(layout)
        height = len(layout[0])
        valid_cells = sum(1 for x in range(width) for y in range(height) if layout[x][y])
        if width >= 9 and height >= 9 and valid_cells == 81:
            print("  🎉 MAX GRID ACHIEVED! Your 9x9 grid is fully unlocked.")
            print("  You've reached the final form. No more expanding — just pure packing power.")
            print("  Go fill that grid, Ranger. 💪")
        else:
            print("  No valid expansions found (no adjacent cells available within 9x9 bounds).")
        return None

    print(f"  Found {len(expansions)} valid expansions.")

    # --- Phase 1: Greedy screening (fast) ---
    print(f"  Phase 1: Greedy screening all {len(expansions)} expansions...")
    greedy_scores = []
    for i, expansion in enumerate(expansions):
        if (i + 1) % 100 == 0:
            print(f"\r    Screening {i + 1}/{len(expansions)}...", end="", flush=True)

        new_layout = expand_layout(layout, expansion)
        result = pack_shapes(shape_list, strategy="greedy", layout=new_layout, quiet=True)

        pieces_placed = len(result.placements)
        expected = len(shape_list)

        if pieces_placed == expected:
            primary, tiebreaker = score_expansion(result, expand_targets)
            greedy_scores.append((primary, tiebreaker, i, expansion))
        else:
            # Partial placement — lower priority
            greedy_scores.append((-1, pieces_placed, i, expansion))

    print(f"\r    Screened {len(expansions)} expansions.                    ")

    # Sort by score (best first)
    greedy_scores.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # --- Phase 2: Backtrack the top candidates ---
    TOP_N = 20
    top_candidates = greedy_scores[:TOP_N]
    print(f"  Phase 2: Backtracking top {len(top_candidates)} candidates...\n")

    # Determine max possible score for early termination
    max_possible_score = len(expand_targets) if expand_targets else None

    best_primary = -1
    best_tiebreaker = -1
    best_expansion = None
    best_grid = None

    for rank, (greedy_primary, greedy_tie, idx, expansion) in enumerate(top_candidates):
        if expand_targets:
            print(f"\r    Solving candidate {rank + 1}/{len(top_candidates)} | best: fits {best_primary} target weapon(s)", end="", flush=True)
        else:
            print(f"\r    Solving candidate {rank + 1}/{len(top_candidates)} | best: {best_primary} empty grouped", end="", flush=True)

        new_layout = expand_layout(layout, expansion)
        result = pack_shapes(shape_list, strategy="backtrack",
                            timeout=timeout_per_solve, layout=new_layout, quiet=True)

        expected_pieces = len(shape_list)
        if len(result.placements) == expected_pieces:
            primary, tiebreaker = score_expansion(result, expand_targets)
            if primary > best_primary or (primary == best_primary and tiebreaker > best_tiebreaker):
                best_primary = primary
                best_tiebreaker = tiebreaker
                best_expansion = expansion
                best_grid = result

            # Early termination
            if max_possible_score is not None and best_primary >= max_possible_score:
                print(f"\r    Found optimal expansion (fits all targets).                              ")
                break

    print(f"\r    Tested {len(top_candidates)} candidates.                                        ")

    if best_expansion:
        return (best_expansion, best_grid, best_primary)
    else:
        # Fallback: if backtracking failed on top candidates, try more from greedy list
        print("  No top candidate worked with backtracking. Trying more...")
        for greedy_primary, greedy_tie, idx, expansion in greedy_scores[TOP_N:TOP_N+50]:
            new_layout = expand_layout(layout, expansion)
            result = pack_shapes(shape_list, strategy="backtrack",
                                timeout=timeout_per_solve, layout=new_layout, quiet=True)
            if len(result.placements) == len(shape_list):
                primary, tiebreaker = score_expansion(result, expand_targets)
                return (expansion, result, primary)

        # Last resort: return best greedy result
        if greedy_scores and greedy_scores[0][0] >= 0:
            _, _, _, expansion = greedy_scores[0]
            new_layout = expand_layout(layout, expansion)
            result = pack_shapes(shape_list, strategy="greedy", layout=new_layout, quiet=True)
            primary, _ = score_expansion(result, expand_targets)
            return (expansion, result, primary)

        return None


def save_grid_layout(filepath: str, layout: List[List[bool]]):
    """
    Save a grid layout to a text file.
    '#' = valid cell, '.' = blocked cell.
    Written top-to-bottom (first line = highest y row).
    """
    width = len(layout)
    height = len(layout[0])

    lines = []
    for y in range(height - 1, -1, -1):  # top row first
        row = ""
        for x in range(width):
            row += "#" if layout[x][y] else "."
        lines.append(row)

    with open(filepath, 'w') as f:
        f.write("\n".join(lines) + "\n")


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

        # Parse --grid flag
        layout = None
        if "--grid" in args:
            idx = args.index("--grid")
            if idx + 1 < len(args):
                grid_file = args[idx + 1]
                args.pop(idx)  # remove --grid
                args.pop(idx)  # remove the filename
                try:
                    layout = load_grid_layout(grid_file)
                except FileNotFoundError:
                    print(f"Error: Grid file '{grid_file}' not found.")
                    sys.exit(1)
                except Exception as e:
                    print(f"Error reading grid file: {e}")
                    sys.exit(1)
            else:
                print("Error: --grid requires a filename")
                sys.exit(1)

        expand = False
        expand_targets = []
        if "--expand" in args:
            idx = args.index("--expand")
            args.pop(idx)  # remove --expand
            # Next arg (if present and not a flag) is a comma-separated list of target weapons
            if idx < len(args) and not args[idx].startswith("--") and ":" not in args[idx]:
                target_arg = args.pop(idx)
                for name in target_arg.split(","):
                    name = name.strip()
                    if name and name in SHAPES:
                        expand_targets.append(name)
                    elif name:
                        print(f"Error: Unknown expand target weapon '{name}'")
                        print(f"Available shapes: {', '.join(sorted(SHAPES.keys()))}")
                        sys.exit(1)
            expand = True
            if not layout:
                print("Error: --expand requires --grid to specify the current grid layout.")
                sys.exit(1)
            if not expand_targets:
                print("  (No target weapons specified, optimizing for largest empty group)\n")

        if "--help" in args or "-h" in args:
            print("Usage: python3 ark_ranger.py [--greedy] [--timeout SECONDS] [--colorblind] [--grid FILE] shape1[:qty] shape2[:qty] ...")
            print(f"\nAvailable shapes: {', '.join(sorted(SHAPES.keys()))}")
            print("\nExamples:")
            print("  python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4")
            print("  python3 ark_ranger.py --greedy blade:2 machine:3 fire corner:5")
            print("  python3 ark_ranger.py --timeout 30 blade:2 machine:3")
            print("  python3 ark_ranger.py --colorblind shotgun:3 square:4")
            print("  python3 ark_ranger.py --grid my_level.txt shotgun:3 blade:2")
            print("\nFlags:")
            print("  --greedy          Use fast greedy heuristic (may not find optimal solution)")
            print("                    Default is backtracking (thorough, finds valid arrangements)")
            print("  --timeout SECS    Max seconds for backtracking (default: 30)")
            print("  --colorblind      Use colorblind-friendly palette")
            print("  --grid FILE       Use a custom grid layout from a text file")
            print("                    '#' or 'X' = valid cell, '.' = blocked cell")
            print("                    Default is a 9x9 square grid")
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
        if layout:
            max_cells = sum(1 for col in layout for cell in col if cell)
        else:
            max_cells = 81
        if total_cells > max_cells:
            print(f"Error: Total cells ({total_cells}) exceed the grid capacity ({max_cells}).")
            print(f"Remove {total_cells - max_cells} cells worth of shapes to fit.")
            sys.exit(1)
        print(f"Packing {len(shape_list)} shapes ({total_cells} cells) using {strategy} strategy...\n")

        if expand:
            result_data = find_best_expansion(layout, shape_list, timeout_per_solve=5,
                                              expand_targets=expand_targets)
            if result_data:
                expansion, result, score = result_data
                print(f"\n  Best expansion adds tiles at: {[(x+1, y+1) for x, y in expansion]}")
                if expand_targets:
                    print(f"  Can fit {score} additional target weapon(s): {', '.join(expand_targets)}")
                else:
                    print(f"  Largest connected empty group: {score} cells")
                print()
                print(result.display_pretty(colorblind=colorblind, highlight_cells=expansion))
                print(f"\nCells filled: {result.cells_filled()} / {result._valid_cells}")
                print(f"Pieces placed: {len(result.placements)} / {len(shape_list)}")

                if len(result.placements) < len(shape_list):
                    placed_names = [p[0] for p in result.placements]
                    unplaced = list(shape_list)
                    for name in placed_names:
                        unplaced.remove(name)
                    print(f"\n⚠️  Could not fit all pieces! {len(unplaced)} shape(s) unplaced:")
                    for name in unplaced:
                        print(f"  - {name}")

                # Update the grid file with the expanded layout
                new_layout = expand_layout(layout, expansion)
                save_grid_layout(grid_file, new_layout)
                print(f"\n  ✓ Updated '{grid_file}' with the expanded grid.")
            else:
                print("  Could not find a valid expansion.")
        else:
            result = pack_shapes(shape_list, strategy=strategy, timeout=timeout, layout=layout)
            print(result.display_pretty(colorblind=colorblind))

            print(f"\nCells filled: {result.cells_filled()} / {result._valid_cells}")
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
