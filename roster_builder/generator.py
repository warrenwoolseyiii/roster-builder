"""Roster generation algorithm.

Generates a full season of game rosters respecting all sport-specific
constraints defined in the YAML configuration.
"""

import random
from typing import Dict, List, Optional, Set

from roster_builder.config import SportConfig
from roster_builder.constraints import (
    distribute_game_balls,
    get_ordering_blocked_players,
    get_outfield_blocked_players,
    select_sit_outs,
)
from roster_builder.models import (
    GameRoster,
    Player,
    Position,
    RosterSlot,
    SeasonSchedule,
)


def generate_season(
    players: List[Player],
    positions: List[Position],
    num_games: int,
    sport_config: SportConfig,
    seed: Optional[int] = None,
) -> SeasonSchedule:
    """Generate a full season of game rosters.

    Args:
        players: All players on the team.
        positions: All field positions for the sport.
        num_games: Number of games in the season.
        sport_config: Sport configuration with constraints.
        seed: Optional random seed for reproducibility.

    Returns:
        A SeasonSchedule with all game rosters.
    """
    if seed is not None:
        random.seed(seed)

    schedule = SeasonSchedule()
    sit_out_counts: Dict[Player, int] = {p: 0 for p in players}
    game_ball_counts: Dict[Player, int] = {p: 0 for p in players}
    previous_games: List[GameRoster] = []

    # Determine number of active players per game
    num_field_positions = len(positions)
    num_special = len(sport_config.special_slots)
    # Active slots = field positions (special slots don't consume a player
    # unless has_player is True)
    num_player_slots = num_field_positions + sum(
        1 for s in sport_config.special_slots if s.has_player
    )
    num_active = min(len(players), num_player_slots)

    for game_num in range(1, num_games + 1):
        game_roster = _generate_game(
            game_number=game_num,
            players=players,
            positions=positions,
            num_active=num_active,
            sport_config=sport_config,
            previous_games=previous_games,
            sit_out_counts=sit_out_counts,
            game_ball_counts=game_ball_counts,
            num_games=num_games,
        )
        schedule.games.append(game_roster)
        previous_games.append(game_roster)

        # Update sit-out counts
        for p in game_roster.sitting_out:
            sit_out_counts[p] = sit_out_counts.get(p, 0) + 1

        # Update game ball counts
        for p in game_roster.game_ball_recipients:
            game_ball_counts[p] = game_ball_counts.get(p, 0) + 1

    return schedule


def _generate_game(
    game_number: int,
    players: List[Player],
    positions: List[Position],
    num_active: int,
    sport_config: SportConfig,
    previous_games: List[GameRoster],
    sit_out_counts: Dict[Player, int],
    game_ball_counts: Dict[Player, int],
    num_games: int,
) -> GameRoster:
    """Generate a single game roster.

    Steps:
        1. Determine sit-outs (fair rotation)
        2. Assign positions (respecting group constraints)
        3. Assign ordering positions (respecting half constraints)
        4. Assign game ball recipients
    """
    # Step 1: Determine sit-outs
    sitting_out = select_sit_outs(players, num_active, sit_out_counts)
    active_players = [p for p in players if p not in sitting_out]

    # Step 2: Assign positions
    slots = _assign_positions(
        active_players=active_players,
        positions=positions,
        sport_config=sport_config,
        previous_games=previous_games,
    )

    # Step 3: Assign ordering (batting order)
    if sport_config.ordering.enabled:
        _assign_ordering(
            slots=slots,
            sport_config=sport_config,
            previous_games=previous_games,
        )

    # Step 4: Assign game ball recipients
    game_ball_recipients = distribute_game_balls(
        players=players,
        num_games=num_games,
        current_game=game_number,
        game_ball_counts=game_ball_counts,
        sport_config=sport_config,
    )

    return GameRoster(
        game_number=game_number,
        slots=slots,
        game_ball_recipients=game_ball_recipients,
        sitting_out=sitting_out,
    )


def _assign_positions(
    active_players: List[Player],
    positions: List[Position],
    sport_config: SportConfig,
    previous_games: List[GameRoster],
) -> List[RosterSlot]:
    """Assign players to positions respecting group constraints.

    Strategy:
        1. Get blocked players per group from constraint engine.
        2. Separate positions into constrained groups and unconstrained.
        3. Assign constrained positions first (from non-blocked players).
        4. Assign remaining players to remaining positions.
        5. Append special slots.
    """
    # Get group blocks
    group_blocked = get_outfield_blocked_players(previous_games, sport_config)

    # Categorize positions
    group_positions: List[Position] = []  # positions in a constrained group
    free_positions: List[Position] = []  # positions not in any group

    for pos in positions:
        if pos.group and pos.group in group_blocked:
            group_positions.append(pos)
        else:
            free_positions.append(pos)

    # Players available for assignment
    remaining_players = list(active_players)
    random.shuffle(remaining_players)

    slots: List[RosterSlot] = []
    assigned_players: Set[Player] = set()

    # Assign constrained group positions first
    for group_name, blocked_players in group_blocked.items():
        group_pos_list = [p for p in group_positions if p.group == group_name]
        eligible = [
            p for p in remaining_players
            if p not in blocked_players and p not in assigned_players
        ]
        random.shuffle(eligible)

        for pos in group_pos_list:
            if eligible:
                player = eligible.pop(0)
                slots.append(RosterSlot(position=pos.name, player=player))
                assigned_players.add(player)
            else:
                # Fallback: if not enough non-blocked players, relax constraint
                # and pick from remaining (this shouldn't happen with normal rosters)
                fallback = [
                    p for p in remaining_players if p not in assigned_players
                ]
                if fallback:
                    player = fallback[0]
                    slots.append(RosterSlot(position=pos.name, player=player))
                    assigned_players.add(player)

    # Assign free positions
    unassigned = [p for p in remaining_players if p not in assigned_players]
    random.shuffle(unassigned)
    random.shuffle(free_positions)

    for pos in free_positions:
        if unassigned:
            player = unassigned.pop(0)
            slots.append(RosterSlot(position=pos.name, player=player))
            assigned_players.add(player)

    # Sort slots to match the original position order
    position_order = {pos.name: i for i, pos in enumerate(positions)}
    slots.sort(key=lambda s: position_order.get(s.position, 999))

    # Append special slots
    for special in sport_config.special_slots:
        slots.append(
            RosterSlot(
                position=special.name,
                player=None,
                is_special=True,
            )
        )

    return slots


def _assign_ordering(
    slots: List[RosterSlot],
    sport_config: SportConfig,
    previous_games: List[GameRoster],
) -> None:
    """Assign ordering positions (e.g., batting order) to slots.

    When the number of active players is odd relative to the half split,
    the algorithm alternates which half is larger each game. This ensures
    the no-repeat-half constraint is always satisfiable.

    For example, with 11 players and a 6/6 config split:
        - Odd games:  top=6, bottom=5  (DH gets slot 12)
        - Even games: top=5, bottom=6  (DH gets slot 12)
    
    This way players from the larger half always fit into the larger
    opposite half next game.

    Strategy:
        1. Determine dynamic half sizes based on player count and game parity.
        2. Get blocked players per half from constraint engine.
        3. Players who were in top go to bottom, and vice versa.
        4. Randomize within each half.
        5. Assign order positions sequentially.
        6. Special slots (e.g., DH) get the leftover order position.
    """
    top_half_cfg = sport_config.ordering.top_half
    bottom_half_cfg = sport_config.ordering.bottom_half

    if not top_half_cfg or not bottom_half_cfg:
        # No halves defined — just randomize
        indices = list(range(1, sport_config.ordering.total_slots + 1))
        random.shuffle(indices)
        for i, slot in enumerate(slots):
            if i < len(indices):
                slot.order_position = indices[i]
        return

    # Collect players from slots (only those with actual players)
    players_in_slots = [s.player for s in slots if s.player is not None]
    num_players = len(players_in_slots)
    total_order_slots = sport_config.ordering.total_slots

    # Determine the current game number from context
    current_game_num = len(previous_games) + 1

    # Dynamic half sizing: split players as evenly as possible,
    # alternating which half gets the extra player on odd counts.
    base_half = num_players // 2
    remainder = num_players % 2

    if remainder == 0:
        # Even split
        actual_top_size = base_half
        actual_bottom_size = base_half
    else:
        # Odd number of players: alternate which half is larger
        if current_game_num % 2 == 1:
            actual_top_size = base_half + 1
            actual_bottom_size = base_half
        else:
            actual_top_size = base_half
            actual_bottom_size = base_half + 1

    # Get blocked players from the constraint engine
    # blocked_from_top = players who were in top last game (should NOT be in top)
    # blocked_from_bottom = players who were in bottom last game (should NOT be in bottom)
    blocked_from_top, blocked_from_bottom = get_ordering_blocked_players(
        previous_games, sport_config
    )

    # Separate into candidates for each half
    must_go_bottom = [p for p in players_in_slots if p in blocked_from_top and p not in blocked_from_bottom]
    must_go_top = [p for p in players_in_slots if p in blocked_from_bottom and p not in blocked_from_top]
    blocked_both = [p for p in players_in_slots if p in blocked_from_top and p in blocked_from_bottom]
    flexible = [
        p for p in players_in_slots
        if p not in blocked_from_top and p not in blocked_from_bottom
    ]

    random.shuffle(must_go_bottom)
    random.shuffle(must_go_top)
    random.shuffle(blocked_both)
    random.shuffle(flexible)

    # Build top half list
    top_players: List[Player] = []
    top_players.extend(must_go_top[:actual_top_size])

    remaining_top = actual_top_size - len(top_players)
    if remaining_top > 0:
        fill = flexible[:remaining_top]
        top_players.extend(fill)
        flexible = flexible[remaining_top:]

    # Build bottom half list
    bottom_players: List[Player] = []
    bottom_players.extend(must_go_bottom[:actual_bottom_size])

    remaining_bottom = actual_bottom_size - len(bottom_players)
    if remaining_bottom > 0:
        fill = flexible[:remaining_bottom]
        bottom_players.extend(fill)
        flexible = flexible[remaining_bottom:]

    # Handle any overflow (shouldn't happen with proper alternation,
    # but safety net for edge cases)
    unplaced: List[Player] = []
    unplaced.extend(must_go_top[actual_top_size:])
    unplaced.extend(must_go_bottom[actual_bottom_size:])
    unplaced.extend(blocked_both)
    unplaced.extend(flexible)
    random.shuffle(unplaced)

    for p in unplaced:
        if len(top_players) < actual_top_size:
            top_players.append(p)
        elif len(bottom_players) < actual_bottom_size:
            bottom_players.append(p)

    # Randomize within each half
    random.shuffle(top_players)
    random.shuffle(bottom_players)

    # Map player -> order position
    # Top half gets positions starting from top_half_cfg.start
    # Bottom half gets positions starting from top_half_cfg.start + actual_top_size
    player_order: Dict[Player, int] = {}
    for i, player in enumerate(top_players):
        player_order[player] = top_half_cfg.start + i

    for i, player in enumerate(bottom_players):
        player_order[player] = top_half_cfg.start + actual_top_size + i

    # Assign to slots
    for slot in slots:
        if slot.player is not None and slot.player in player_order:
            slot.order_position = player_order[slot.player]
        elif slot.is_special and slot.player is None:
            # Special slots like DH get the next available order position
            used_positions = set(player_order.values())
            for pos in range(1, total_order_slots + 1):
                if pos not in used_positions:
                    slot.order_position = pos
                    used_positions.add(pos)
                    break
