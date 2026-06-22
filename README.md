# Ark Ranger Minigame Packer

A script that optimally arranges Tetris-style shapes into a grid. Designed for the Ark Ranger minigame puzzle.

## Usage

```bash
python3 ark_ranger.py [--greedy] [--timeout SECONDS] [--colorblind] [--grid FILE] [--expand [TARGETS]] shape1[:qty] shape2[:qty] ...
```

### Examples

```bash
# Pack 3 shotguns, 2 dual_pistols, 1 buffs, and 4 squares (default 9x9 grid)
python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4

# Use a custom grid layout
python3 ark_ranger.py --grid my_level.txt shotgun:3 blade:2

# Find the best 6-tile expansion (largest empty group)
python3 ark_ranger.py --grid my_level.txt --expand shotgun:2 square:3 launcher:2

# Find the best expansion prioritizing space for more blades
python3 ark_ranger.py --grid my_level.txt --expand blade shotgun:2 square:3

# Prioritize expansion for multiple weapons (comma-separated)
python3 ark_ranger.py --grid my_level.txt --expand blade,machine shotgun:2 square:3

# Use greedy solver (fast but may miss solutions)
python3 ark_ranger.py --greedy blade:2 machine:3 fire corner:5

# Custom timeout
python3 ark_ranger.py --timeout 15 blade:2 machine:3

# Colorblind-friendly mode
python3 ark_ranger.py --colorblind shotgun:3 square:4
```

### Flags

| Flag | Description |
|------|-------------|
| `--greedy` | Use fast greedy heuristic (may not find a solution even if one exists) |
| `--timeout SECS` | Max seconds for backtracking (default: 30) |
| `--colorblind` | Use a colorblind-friendly color palette |
| `--grid FILE` | Use a custom grid layout from a text file (default: 9x9 square) |
| `--expand [TARGETS]` | Find optimal 6-tile grid expansion. Optionally specify comma-separated target weapons to prioritize |

Default solver is backtracking (thorough, finds valid arrangements).

## Custom Grid Layouts

Create a text file where each character represents a cell:
- `#` or `X` = valid cell (shapes can go here)
- `.` = blocked/missing cell

The first line is the top row of the grid. Example:

```
.####.
######
######
######
.####.
```

Save as a `.txt` file and pass with `--grid`:

```bash
python3 ark_ranger.py --grid my_level.txt shotgun:3 blade:2
```

The grid can be any shape — L-shaped, with holes, extensions off the side — up to 9x9 max.

## Grid Expansion

The `--expand` flag finds the best way to add 6 tiles to your current grid:

- New tiles will be connected to each other
- New tiles must attach to the existing grid
- Grid cannot exceed 9x9 in any direction

**Without targets** — optimizes for the largest connected empty group (most room for future weapons):
```bash
python3 ark_ranger.py --grid my_level.txt --expand shotgun:2 square:3
```

**With targets** — optimizes for fitting specific future weapons in the remaining space:
```bash
python3 ark_ranger.py --grid my_level.txt --expand blade shotgun:2 square:3
```

The output shows exactly where to add tiles with `++` markers on the grid and a `░░` pattern for expansion tiles that have weapons placed on them.

## Available Shapes

| Name | Cells |
|------|-------|
| jewel | 1 |
| data_chip | 2 |
| buffs | 3 |
| corner | 3 |
| square | 4 |
| dual_pistols | 4 |
| launcher | 4 |
| photon | 4 |
| shotgun | 4 |
| blade | 5 |
| bowgun | 5 |
| fire | 5 |
| machine | 5 |
| rifle_laser | 5 |

## Output

- The grid displays with colored blocks. Each weapon type has its own unique color.
- When two of the same weapon are adjacent, the graph coloring ensures they get different colors.
- A legend below the grid maps colors to shape names.
- Empty cells are left blank. Blocked cells don't render.
- Jewels are always placed last, backfilling any gaps after all other shapes are arranged.

## Notes

- Shapes are automatically rotated (0°, 90°, 180°, 270°) to find the best fit.
- The script errors if total shape cells exceed the grid capacity.
- If not all pieces fit, the output shows which shapes were unplaced.
- The backtracking solver shows live progress (attempts, time elapsed, best solution so far).
- Backtracking stops after 30 seconds or 7,000,000 attempts (whichever comes first) and returns the best solution found.
