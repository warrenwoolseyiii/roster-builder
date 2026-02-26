#!/usr/bin/env python3
"""CLI entry point for the roster builder.

Usage:
    python scripts/generate_rosters.py \\
        --players=player-lists/collegiate_2026.csv \\
        --positions=positions/collegiate_positions_2026.csv \\
        --games=10 \\
        --sport=baseball

Optional:
    --output=rosters/        Output directory (default: rosters/)
    --seed=42                Random seed for reproducibility
"""

import argparse
import os
import sys

# Add the project root to the Python path so we can import roster_builder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roster_builder.config import load_sport_config
from roster_builder.generator import generate_season
from roster_builder.io import get_output_filename, read_players, read_positions, write_roster_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate game rosters for a season.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--players",
        required=True,
        help="Path to player list CSV file",
    )
    parser.add_argument(
        "--positions",
        required=True,
        help="Path to positions CSV file",
    )
    parser.add_argument(
        "--games",
        required=True,
        type=int,
        help="Number of games in the season",
    )
    parser.add_argument(
        "--sport",
        required=True,
        help="Sport name (maps to sports/{sport}.yaml config)",
    )
    parser.add_argument(
        "--output",
        default="rosters",
        help="Output directory for roster CSVs (default: rosters/)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible output",
    )

    args = parser.parse_args()

    # Load sport config
    print(f"Loading sport config: {args.sport}")
    sport_config = load_sport_config(args.sport)

    # Read input files
    print(f"Reading players from: {args.players}")
    players = read_players(args.players)
    print(f"  Found {len(players)} players")

    print(f"Reading positions from: {args.positions}")
    positions = read_positions(args.positions, sport_config)
    print(f"  Found {len(positions)} positions")

    # Generate season
    print(f"\nGenerating {args.games}-game season...")
    if args.seed is not None:
        print(f"  Using random seed: {args.seed}")

    schedule = generate_season(
        players=players,
        positions=positions,
        num_games=args.games,
        sport_config=sport_config,
        seed=args.seed,
    )

    # Write roster CSVs
    os.makedirs(args.output, exist_ok=True)
    print(f"\nWriting rosters to: {args.output}/")

    for game in schedule.games:
        filename = get_output_filename(args.players, game.game_number)
        output_path = os.path.join(args.output, filename)
        write_roster_csv(game, output_path, sport_config)

        # Summary
        active_count = sum(1 for s in game.slots if s.player is not None)
        sit_out_names = ", ".join(p.full_name for p in game.sitting_out)
        ball_names = ", ".join(p.full_name for p in game.game_ball_recipients)

        print(f"  Game {game.game_number}: {filename}")
        print(f"    Active: {active_count} players")
        if game.sitting_out:
            print(f"    Sitting out: {sit_out_names}")
        if game.game_ball_recipients:
            print(f"    Game ball: {ball_names}")

    # Validate game ball coverage
    all_recipients = set()
    for game in schedule.games:
        all_recipients.update(game.game_ball_recipients)

    uncovered = [p for p in players if p not in all_recipients]
    if uncovered:
        print(f"\n⚠️  WARNING: {len(uncovered)} player(s) did not receive a game ball:")
        for p in uncovered:
            print(f"    - {p.full_name}")
    else:
        print(f"\n✅ All {len(players)} players received at least one game ball.")

    print(f"\nDone! Generated {args.games} roster files.")


if __name__ == "__main__":
    main()
