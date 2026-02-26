"""Data models for the roster builder."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Player:
    """Represents a player on the team."""

    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __hash__(self) -> int:
        return hash((self.first_name, self.last_name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Player):
            return NotImplemented
        return self.first_name == other.first_name and self.last_name == other.last_name

    def __repr__(self) -> str:
        return f"Player({self.full_name!r})"


@dataclass
class Position:
    """Represents a field position."""

    name: str
    group: Optional[str] = None  # e.g., "outfield" for baseball OF positions

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.name == other.name

    def __repr__(self) -> str:
        return f"Position({self.name!r})"


@dataclass
class SpecialSlot:
    """A roster slot that isn't a field position (e.g., Designated Hitter)."""

    name: str
    has_player: bool = False


@dataclass
class RosterSlot:
    """A single slot in a game roster: position + player + ordering position."""

    position: str
    player: Optional[Player] = None
    order_position: Optional[int] = None
    is_special: bool = False


@dataclass
class GameRoster:
    """Complete roster for a single game."""

    game_number: int
    slots: List[RosterSlot] = field(default_factory=list)
    game_ball_recipients: List[Player] = field(default_factory=list)
    sitting_out: List[Player] = field(default_factory=list)


@dataclass
class SeasonSchedule:
    """The full season of game rosters."""

    games: List[GameRoster] = field(default_factory=list)

    def get_game(self, game_number: int) -> Optional[GameRoster]:
        """Get a specific game roster by number."""
        for game in self.games:
            if game.game_number == game_number:
                return game
        return None
