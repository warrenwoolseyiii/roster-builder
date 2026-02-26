"""Sport configuration loader for YAML config files."""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class GroupConstraint:
    """A constraint applied to a position group."""

    type: str  # e.g., "no_repeat_group"
    cooldown: int = 1  # number of games before a player can return


@dataclass
class PositionGroup:
    """A named group of positions with shared constraints."""

    name: str
    positions: List[str] = field(default_factory=list)
    constraints: List[GroupConstraint] = field(default_factory=list)


@dataclass
class SpecialSlotConfig:
    """Configuration for a special roster slot."""

    name: str
    has_player: bool = False


@dataclass
class OrderingHalf:
    """Defines a half of the ordering (e.g., top/bottom of batting order)."""

    start: int
    end: int


@dataclass
class OrderingConstraint:
    """A constraint on the ordering system."""

    type: str  # e.g., "no_repeat_half"
    cooldown: int = 1


@dataclass
class OrderingConfig:
    """Configuration for the ordering system (e.g., batting order)."""

    name: Optional[str] = None
    total_slots: int = 0
    top_half: Optional[OrderingHalf] = None
    bottom_half: Optional[OrderingHalf] = None
    constraints: List[OrderingConstraint] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.name is not None


@dataclass
class GameBallConfig:
    """Configuration for game ball distribution."""

    enabled: bool = True
    min_per_game: int = 1
    rule: str = "all_players_receive_at_least_one"


@dataclass
class SportConfig:
    """Complete sport configuration loaded from YAML."""

    sport: str
    position_groups: List[PositionGroup] = field(default_factory=list)
    special_slots: List[SpecialSlotConfig] = field(default_factory=list)
    ordering: OrderingConfig = field(default_factory=OrderingConfig)
    game_ball: GameBallConfig = field(default_factory=GameBallConfig)

    def get_position_group(self, position_name: str) -> Optional[PositionGroup]:
        """Find which group a position belongs to, if any."""
        normalized = position_name.lower().strip()
        for group in self.position_groups:
            for pos in group.positions:
                if pos.lower().strip() == normalized:
                    return group
        return None

    def is_position_in_group(self, position_name: str, group_name: str) -> bool:
        """Check if a position belongs to a specific group."""
        group = self.get_position_group(position_name)
        return group is not None and group.name == group_name


def load_sport_config(sport_name: str, sports_dir: str = "sports") -> SportConfig:
    """Load a sport configuration from a YAML file.

    Args:
        sport_name: Name of the sport (maps to {sport_name}.yaml)
        sports_dir: Directory containing sport YAML files

    Returns:
        SportConfig instance

    Raises:
        FileNotFoundError: If the sport config file doesn't exist
        ValueError: If the config is malformed
    """
    config_path = os.path.join(sports_dir, f"{sport_name}.yaml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Sport config not found: {config_path}. "
            f"Available sports: {_list_available_sports(sports_dir)}"
        )

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    return _parse_config(raw)


def _list_available_sports(sports_dir: str) -> List[str]:
    """List available sport configs in the directory."""
    if not os.path.isdir(sports_dir):
        return []
    return [
        f.replace(".yaml", "")
        for f in os.listdir(sports_dir)
        if f.endswith(".yaml")
    ]


def _parse_config(raw: Dict[str, Any]) -> SportConfig:
    """Parse raw YAML dict into a SportConfig."""
    sport = raw.get("sport", "unknown")

    # Parse position groups
    position_groups = []
    for group_name, group_data in raw.get("position_groups", {}).items():
        constraints = [
            GroupConstraint(type=c["type"], cooldown=c.get("cooldown", 1))
            for c in group_data.get("constraints", [])
        ]
        position_groups.append(
            PositionGroup(
                name=group_name,
                positions=group_data.get("positions", []),
                constraints=constraints,
            )
        )

    # Parse special slots
    special_slots = [
        SpecialSlotConfig(
            name=s["name"],
            has_player=s.get("has_player", False),
        )
        for s in raw.get("special_slots", [])
    ]

    # Parse ordering config
    ordering_raw = raw.get("ordering", {})
    ordering = OrderingConfig(name=ordering_raw.get("name"))
    if ordering.name:
        ordering.total_slots = ordering_raw.get("total_slots", 0)
        halves = ordering_raw.get("halves", {})
        if "top" in halves:
            ordering.top_half = OrderingHalf(
                start=halves["top"][0], end=halves["top"][1]
            )
        if "bottom" in halves:
            ordering.bottom_half = OrderingHalf(
                start=halves["bottom"][0], end=halves["bottom"][1]
            )
        ordering.constraints = [
            OrderingConstraint(type=c["type"], cooldown=c.get("cooldown", 1))
            for c in ordering_raw.get("constraints", [])
        ]

    # Parse game ball config
    gb_raw = raw.get("game_ball", {})
    game_ball = GameBallConfig(
        enabled=gb_raw.get("enabled", True),
        min_per_game=gb_raw.get("min_per_game", 1),
        rule=gb_raw.get("rule", "all_players_receive_at_least_one"),
    )

    return SportConfig(
        sport=sport,
        position_groups=position_groups,
        special_slots=special_slots,
        ordering=ordering,
        game_ball=game_ball,
    )
