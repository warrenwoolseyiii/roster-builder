#!/usr/bin/env python3
"""Validate generated rosters against constraints."""
import csv
import sys


def get_top_count(num_players: int, game_number: int) -> int:
    """Compute top half size using the same alternating logic as the generator.
    
    Odd game numbers: top half is larger (when odd player count).
    Even game numbers: bottom half is larger (when odd player count).
    """
    base_half = num_players // 2
    remainder = num_players % 2
    if remainder == 0:
        return base_half
    else:
        if game_number % 2 == 1:
            return base_half + 1
        else:
            return base_half


def main():
    games = []
    for i in range(1, 11):
        path = f"rosters/collegiate_2026_game_{i}_roster.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        games.append(rows)

    outfield = {
        "Left Field",
        "Center Field",
        "Right Field",
        "Left Center Field",
        "Right Center Field",
    }

    all_pass = True

    print("=== OUTFIELD CONSTRAINT CHECK ===")
    for i in range(1, len(games)):
        prev_of = {
            r["Player"]
            for r in games[i - 1]
            if r["Position"] in outfield and r["Player"]
        }
        curr_of = {
            r["Player"]
            for r in games[i]
            if r["Position"] in outfield and r["Player"]
        }
        overlap = prev_of & curr_of
        if overlap:
            print(f"  Game {i} -> Game {i+1}: FAIL: {overlap}")
            all_pass = False
        else:
            print(f"  Game {i} -> Game {i+1}: PASS")

    print()
    print("=== BATTING ORDER HALF CONSTRAINT CHECK ===")
    print("  (Using dynamic alternating midpoint)")
    for i in range(1, len(games)):
        prev_game_num = i      # game number is 1-indexed
        curr_game_num = i + 1

        # Get players with their batting order from previous game
        prev_players = sorted(
            [
                (r["Player"], int(r["Batting Order"]))
                for r in games[i - 1]
                if r["Player"] and r["Batting Order"]
            ],
            key=lambda x: x[1],
        )
        curr_players = sorted(
            [
                (r["Player"], int(r["Batting Order"]))
                for r in games[i]
                if r["Player"] and r["Batting Order"]
            ],
            key=lambda x: x[1],
        )

        prev_top_count = get_top_count(len(prev_players), prev_game_num)
        curr_top_count = get_top_count(len(curr_players), curr_game_num)

        prev_top = {p[0] for p in prev_players[:prev_top_count]}
        prev_bot = {p[0] for p in prev_players[prev_top_count:]}
        curr_top = {p[0] for p in curr_players[:curr_top_count]}
        curr_bot = {p[0] for p in curr_players[curr_top_count:]}

        top_repeat = prev_top & curr_top
        bot_repeat = prev_bot & curr_bot

        if top_repeat or bot_repeat:
            print(f"  Game {i} -> Game {i+1}: FAIL top={top_repeat} bot={bot_repeat}")
            print(f"    Prev top({prev_top_count}): {sorted(prev_top)}")
            print(f"    Curr top({curr_top_count}): {sorted(curr_top)}")
            print(f"    Prev bot({len(prev_bot)}): {sorted(prev_bot)}")
            print(f"    Curr bot({len(curr_bot)}): {sorted(curr_bot)}")
            all_pass = False
        else:
            print(f"  Game {i} -> Game {i+1}: PASS (prev top={prev_top_count}, curr top={curr_top_count})")

    print()
    print("=== GAME 1 ROSTER ===")
    for r in games[0]:
        gb = r.get("Game Ball", "")
        print(
            f"  {r['Position']:25s} {r['Player']:20s} Bat#{r['Batting Order']:3s} {gb}"
        )

    print()
    print("=== GAME 2 ROSTER ===")
    for r in games[1]:
        gb = r.get("Game Ball", "")
        print(
            f"  {r['Position']:25s} {r['Player']:20s} Bat#{r['Batting Order']:3s} {gb}"
        )

    if all_pass:
        print("\n✅ All constraints satisfied!")
    else:
        print("\n❌ Some constraints violated!")
        sys.exit(1)


if __name__ == "__main__":
    main()
