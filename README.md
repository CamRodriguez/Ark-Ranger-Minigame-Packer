# Ark Ranger Minigame Packer

A script that optimally arranges Tetris-style shapes into a 9x9 grid. Designed for the Ark Ranger minigame puzzle.

## Usage

```bash
python3 ark_ranger.py [--backtrack] [--timeout SECONDS] [--colorblind] shape1[:qty] shape2[:qty] ...
```

### Examples

```bash
# Pack 3 shotguns, 2 dual_pistols, 1 buffs, and 4 squares
python3 ark_ranger.py shotgun:3 dual_pistols:2 buffs square:4

# Use the backtracking solver for an optimal solution
python3 ark_ranger.py --backtrack blade:2 machine:3 fire corner:5

# Backtrack with a custom timeout of 30 seconds
python3 ark_ranger.py --backtrack --timeout 30 blade:2 machine:3

# Colorblind-friendly mode
python3 ark_ranger.py --colorblind --backtrack shotgun:3 square:4

# Single shape (quantity defaults to 1)
python3 ark_ranger.py blade shotgun corner
```

### Flags

- `--backtrack` — Use exhaustive backtracking solver. Slower but finds valid arrangements that greedy might miss.
- `--timeout SECONDS` — Max time for backtracking solver (default: 30 seconds). Also stops after 2,000,000 attempts.
- `--colorblind` — Use a colorblind-friendly palette.
- Default (no flag) — Uses a greedy heuristic. Fast but may not find a solution even if one exists.

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
- When two of the same weapon type are placed next to each other, one uses a lighter shade so you can tell them apart.
- A legend below the grid maps colors to shape names.
- Empty cells are left blank.
- Jewels are always placed last, backfilling any gaps after all other shapes are arranged.

## Notes

- Shapes are automatically rotated (0°, 90°, 180°, 270°) to find the best fit.
- The grid is 9x9 (81 cells max). The script will error if your shapes exceed this.
- If not all pieces fit, the output shows which shapes were unplaced.
- The backtracking solver shows live progress (attempts, time elapsed, best solution so far).
- Backtracking stops after 30 seconds or 2,000,000 attempts (whichever comes first) and returns the best solution found.
