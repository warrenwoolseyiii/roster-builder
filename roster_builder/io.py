"""CSV I/O utilities for reading player/position files and writing rosters."""

import csv
import os
from pathlib import Path
from typing import List

from roster_builder.config import SportConfig
from roster_builder.models import GameRoster, Player, Position


def read_players(filepath: str) -> List[Player]:
    """Read a player list from a CSV file.

    Expected CSV format:
        First Name,Last Name
        Weston,Horton
        ...

    Args:
        filepath: Path to the player CSV file.

    Returns:
        List of Player instances.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If required columns are missing.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Player file not found: {filepath}")

    players = []
    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV file: {filepath}")

        # Normalize header names
        headers = [h.strip().lower() for h in reader.fieldnames]
        if "first name" not in headers or "last name" not in headers:
            raise ValueError(
                f"Player CSV must have 'First Name' and 'Last Name' columns. "
                f"Found: {reader.fieldnames}"
            )

        for row in reader:
            # Match headers case-insensitively
            first = ""
            last = ""
            for key, value in row.items():
                if key.strip().lower() == "first name":
                    first = value.strip()
                elif key.strip().lower() == "last name":
                    last = value.strip()
            players.append(Player(first_name=first, last_name=last))

    return players


def read_positions(filepath: str, sport_config: SportConfig) -> List[Position]:
    """Read positions from a CSV file and attach group info from sport config.

    Expected CSV format:
        position
        catcher
        pitcher
        ...

    Args:
        filepath: Path to the positions CSV file.
        sport_config: Sport config for mapping positions to groups.

    Returns:
        List of Position instances with group assignments.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If required columns are missing.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Positions file not found: {filepath}")

    positions = []
    with open(filepath, "r", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty CSV file: {filepath}")

        headers = [h.strip().lower() for h in reader.fieldnames]
        if "position" not in headers:
            raise ValueError(
                f"Positions CSV must have a 'position' column. "
                f"Found: {reader.fieldnames}"
            )

        for row in reader:
            pos_name = ""
            for key, value in row.items():
                if key.strip().lower() == "position":
                    pos_name = value.strip()
                    break

            # Determine group from sport config
            group = sport_config.get_position_group(pos_name)
            group_name = group.name if group else None
            positions.append(Position(name=pos_name, group=group_name))

    return positions


def write_roster_csv(
    game_roster: GameRoster,
    output_path: str,
    sport_config: SportConfig,
) -> None:
    """Write a game roster to a CSV file.

    Output format:
        Position,Player,{ordering_name},Game Ball
        Catcher,Weston Horton,1,
        ...

    Args:
        game_roster: The game roster to write.
        output_path: Path to write the CSV file.
        sport_config: Sport config for column naming.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    ordering_col = sport_config.ordering.name or "Order"
    game_ball_col = "Game Ball" if sport_config.game_ball.enabled else None

    fieldnames = ["Position", "Player", ordering_col]
    if game_ball_col:
        fieldnames.append(game_ball_col)

    # Sort slots by ordering position (e.g., batting order) for readability
    sorted_slots = sorted(
        game_roster.slots,
        key=lambda s: s.order_position if s.order_position is not None else 999,
    )

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for slot in sorted_slots:
            player_name = slot.player.full_name if slot.player else ""
            order_pos = slot.order_position if slot.order_position is not None else ""

            row = {
                "Position": slot.position,
                "Player": player_name,
                ordering_col: order_pos,
            }

            if game_ball_col:
                is_recipient = slot.player in game_roster.game_ball_recipients if slot.player else False
                row[game_ball_col] = "Yes" if is_recipient else ""

            writer.writerow(row)


def get_output_filename(players_path: str, game_number: int) -> str:
    """Generate the output filename for a game roster.

    From 'player-lists/collegiate_2026.csv' and game 1:
    -> 'collegiate_2026_game_1_roster.csv'

    Args:
        players_path: Path to the original players CSV.
        game_number: Game number (1-indexed).

    Returns:
        The output filename (not full path).
    """
    stem = Path(players_path).stem
    return f"{stem}_game_{game_number}_roster.csv"
