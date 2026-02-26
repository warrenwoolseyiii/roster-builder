"""Constraint engine for roster generation.

Provides functions that check and enforce sport-specific rules during
roster generation. Each constraint operates on game history to determine
valid assignments.
"""

from typing import Dict, List, Optional, Set, Tuple

from roster_builder.config import SportConfig
from roster_builder.models import GameRoster, Player


def get_outfield_blocked_players(
    previous_games: List[GameRoster],
    sport_config: SportConfig,
) -> Dict[str, Set[Player]]:
    """Determine which players are blocked from each position group.

    For each position group with a no_repeat_group constraint, look back
    `cooldown` games and collect players who played in that group.

    Args:
        previous_games: List of prior game rosters (most recent last).
        sport_config: The sport configuration.

    Returns:
        Dict mapping group name -> set of blocked players.
    """
    blocked: Dict[str, Set[Player]] = {}

    for group in sport_config.position_groups:
        for constraint in group.constraints:
            if constraint.type == "no_repeat_group":
                cooldown = constraint.cooldown
                blocked_players: Set[Player] = set()

                # Look back `cooldown` number of games
                recent_games = previous_games[-cooldown:]
                for game in recent_games:
                    for slot in game.slots:
                        if (
                            slot.player is not None
                            and sport_config.is_position_in_group(
                                slot.position, group.name
                            )
                        ):
                            blocked_players.add(slot.player)

                blocked[group.name] = blocked_players

    return blocked


def get_ordering_blocked_players(
    previous_games: List[GameRoster],
    sport_config: SportConfig,
) -> Tuple[Set[Player], Set[Player]]:
    """Determine which players are blocked from each ordering half.

    For the no_repeat_half constraint, players in the top half last game
    cannot be in the top half this game (and same for bottom).

    The half boundary is computed dynamically from the actual player
    assignments in each previous game, rather than using fixed config
    boundaries. This supports alternating half sizes when the player
    count is odd.

    Args:
        previous_games: List of prior game rosters (most recent last).
        sport_config: The sport configuration.

    Returns:
        Tuple of (blocked_from_top, blocked_from_bottom) player sets.
    """
    blocked_from_top: Set[Player] = set()
    blocked_from_bottom: Set[Player] = set()

    if not sport_config.ordering.enabled:
        return blocked_from_top, blocked_from_bottom

    for constraint in sport_config.ordering.constraints:
        if constraint.type == "no_repeat_half":
            cooldown = constraint.cooldown
            recent_games = previous_games[-cooldown:]

            for game in recent_games:
                # Collect all player order positions from this game
                player_positions = [
                    (slot.player, slot.order_position)
                    for slot in game.slots
                    if slot.player is not None and slot.order_position is not None
                ]

                if not player_positions:
                    continue

                # Sort by order position to find the dynamic midpoint
                player_positions.sort(key=lambda x: x[1])
                num_players = len(player_positions)

                # Use the game's own number for alternating logic
                prev_game_num = game.game_number

                base_half = num_players // 2
                remainder = num_players % 2
                if remainder == 0:
                    top_count = base_half
                else:
                    # Odd games: top is larger. Even games: bottom is larger.
                    if prev_game_num % 2 == 1:
                        top_count = base_half + 1
                    else:
                        top_count = base_half

                for idx, (player, _) in enumerate(player_positions):
                    if idx < top_count:
                        blocked_from_top.add(player)
                    else:
                        blocked_from_bottom.add(player)

    return blocked_from_top, blocked_from_bottom


def select_sit_outs(
    players: List[Player],
    num_active: int,
    sit_out_counts: Dict[Player, int],
) -> List[Player]:
    """Select players to sit out, favoring those with fewest sit-outs.

    Args:
        players: All players on the team.
        num_active: Number of players that will be active this game.
        sit_out_counts: Cumulative sit-out counts per player.

    Returns:
        List of players who will sit out this game.
    """
    import random

    num_sit_out = len(players) - num_active
    if num_sit_out <= 0:
        return []

    # Sort by sit-out count ascending, then shuffle ties
    sorted_players = sorted(players, key=lambda p: sit_out_counts.get(p, 0))

    # Group by sit-out count to randomize within the same count
    groups: Dict[int, List[Player]] = {}
    for p in sorted_players:
        count = sit_out_counts.get(p, 0)
        groups.setdefault(count, []).append(p)

    # Select sit-outs from highest count first (fewest sit-outs at end)
    # We want to sit out the players with the FEWEST sit-outs? No —
    # we want fairness: sit out those who have sat out the LEAST so far.
    # Wait — that would be unfair. We want to sit out those who have
    # sat out the least, so they catch up. Actually no: to be FAIR,
    # we should sit out those who have played the MOST (sat out the LEAST).
    #
    # Correct logic: sit out players with the LOWEST sit-out count
    # (they've played the most), so everyone's sit-out count converges.

    candidates: List[Player] = []
    for count in sorted(groups.keys()):
        group = groups[count]
        random.shuffle(group)
        candidates.extend(group)

    return candidates[:num_sit_out]


def distribute_game_balls(
    players: List[Player],
    num_games: int,
    current_game: int,
    game_ball_counts: Dict[Player, int],
    sport_config: SportConfig,
) -> List[Player]:
    """Determine game ball recipients for a game.

    Ensures all players receive at least one game ball across the season.
    If there are more players than remaining games, multiple players
    receive the game ball in a single game.

    Args:
        players: All players on the team.
        num_games: Total number of games in the season.
        current_game: Current game number (1-indexed).
        game_ball_counts: Cumulative game ball counts per player.
        sport_config: The sport configuration.

    Returns:
        List of players receiving the game ball this game.
    """
    import random

    if not sport_config.game_ball.enabled:
        return []

    remaining_games = num_games - current_game + 1
    players_without = [p for p in players if game_ball_counts.get(p, 0) == 0]
    min_per_game = sport_config.game_ball.min_per_game

    if sport_config.game_ball.rule == "all_players_receive_at_least_one":
        # How many must we give out this game at minimum?
        if remaining_games <= 0:
            # Last game or past — give to all remaining without
            recipients = players_without[:] if players_without else []
        elif len(players_without) <= remaining_games:
            # Enough games left — give min_per_game, prioritizing uncovered
            if players_without:
                random.shuffle(players_without)
                recipients = players_without[:min_per_game]
            else:
                # Everyone has one; pick random player(s)
                recipients = random.sample(
                    players, min(min_per_game, len(players))
                )
        else:
            # More uncovered players than remaining games — must give multiple
            num_needed = len(players_without) - remaining_games + 1
            num_to_give = max(min_per_game, num_needed)
            random.shuffle(players_without)
            recipients = players_without[:num_to_give]
    else:
        # Default: just pick min_per_game random players
        recipients = random.sample(players, min(min_per_game, len(players)))

    return recipients
