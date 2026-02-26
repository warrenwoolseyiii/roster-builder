# Roster Builder

A Python CLI tool that generates per-game roster CSV files for a season. Given a player list, position list, number of games, and a sport configuration, it produces randomized rosters that respect sport-specific constraints.

## Features

- **Sport-agnostic**: Supports any sport via YAML configuration files
- **Position group rotation**: Prevents players from playing in the same position group (e.g., outfield) back-to-back games
- **Batting order / ordering constraints**: Ensures players alternate between top and bottom halves of the order
- **Game ball distribution**: Guarantees every player receives at least one game ball across the season
- **Fair sit-out rotation**: When there are more players than positions, sit-outs are distributed evenly
- **Reproducible**: Optional random seed for deterministic output

## Requirements

- Python 3.8+
- PyYAML (`pip install pyyaml`)

## Usage

```bash
python scripts/generate_rosters.py \
  --players=player-lists/collegiate_2026.csv \
  --positions=positions/collegiate_positions_2026.csv \
  --games=10 \
  --sport=baseball
```

### Arguments

| Argument       | Required | Description                                          |
|----------------|----------|------------------------------------------------------|
| `--players`    | Yes      | Path to player list CSV (`First Name,Last Name`)     |
| `--positions`  | Yes      | Path to positions CSV (`position`)                   |
| `--games`      | Yes      | Number of games in the season (integer)              |
| `--sport`      | Yes      | Sport name (maps to `sports/{sport}.yaml`)           |
| `--output`     | No       | Output directory (default: `rosters/`)               |
| `--seed`       | No       | Random seed for reproducible output                  |

### Output

Roster CSV files are written to the output directory with the naming convention:

```
{player_file_stem}_game_{N}_roster.csv
```

For example: `collegiate_2026_game_1_roster.csv`

Each roster CSV contains:

```csv
Position,Player,Batting Order,Game Ball
catcher,Weston Horton,1,
pitcher,Bixby Steil,2,Yes
...
Designated Hitter,,12,
```

## Input File Formats

### Player List CSV

```csv
First Name,Last Name
Weston,Horton
Bixby,Steil
```

### Positions CSV

```csv
position
catcher
pitcher
1st Base
```

## Sport Configuration

Sport-specific rules are defined in YAML files under `sports/`. See `sports/baseball.yaml` for a complete example.

### Configuration Schema

```yaml
sport: baseball

position_groups:
  outfield:                          # group name
    positions:                       # positions in this group
      - Left Field
      - Center Field
    constraints:
      - type: no_repeat_group        # constraint type
        cooldown: 1                  # games before player can return

special_slots:
  - name: Designated Hitter
    has_player: false                # true if a player fills this slot

ordering:
  name: Batting Order                # null to disable ordering
  total_slots: 12
  halves:
    top: [1, 6]
    bottom: [7, 12]
  constraints:
    - type: no_repeat_half
      cooldown: 1

game_ball:
  enabled: true
  min_per_game: 1
  rule: all_players_receive_at_least_one
```

### Adding a New Sport

Create a new YAML file in `sports/`, for example `sports/flag_football.yaml`:

```yaml
sport: flag_football

position_groups:
  receivers:
    positions: [Wide Receiver 1, Wide Receiver 2, Slot Receiver]
    constraints:
      - type: no_repeat_group
        cooldown: 1

special_slots: []

ordering:
  name: null          # no batting order in football

game_ball:
  enabled: true
  min_per_game: 1
  rule: all_players_receive_at_least_one
```

Then run:

```bash
python scripts/generate_rosters.py \
  --players=player-lists/my_team.csv \
  --positions=positions/flag_football_positions.csv \
  --games=8 \
  --sport=flag_football
```

## Constraint Rules

| Constraint            | Scope          | Description                                                              |
|-----------------------|----------------|--------------------------------------------------------------------------|
| `no_repeat_group`     | Position Group | Players in a position group cannot play in that group for N consecutive games |
| `no_repeat_half`      | Ordering       | Players in an ordering half cannot be in the same half next game         |
| Fair sit-out          | Roster-wide    | When players > positions, sit-outs are distributed evenly                |
| Game ball coverage    | Season-wide    | All players receive at least 1 game ball across the season               |

## Project Structure

```
roster-builder/
├── scripts/
│   ├── generate_rosters.py      # CLI entry point
│   └── validate_rosters.py      # Validation script for testing
├── roster_builder/
│   ├── __init__.py
│   ├── models.py                # Data models (Player, Position, Roster)
│   ├── config.py                # Sport config loader (YAML)
│   ├── constraints.py           # Constraint engine
│   ├── generator.py             # Roster generation algorithm
│   └── io.py                    # CSV read/write utilities
├── sports/
│   └── baseball.yaml            # Baseball sport config
├── player-lists/                # Input player CSVs
├── positions/                   # Input position CSVs
├── rosters/                     # Generated roster output
├── plans/                       # Architecture docs
└── README.md
```

## Validation

A validation script is included to verify generated rosters:

```bash
python scripts/validate_rosters.py
```

This checks all outfield rotation constraints and batting order half constraints across the generated season.
