"""Game rules, independent of graphics and AI. Coordinates are (row, column)."""
from dataclasses import dataclass

EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
SIZE = 15


@dataclass(frozen=True)
class Move:
    row: int
    col: int
    player: int


class Board:
    def __init__(self, size: int = SIZE):
        if size < 5:
            raise ValueError("The board must be at least 5 by 5.")
        self.size = size
        self.cells = [[EMPTY] * size for _ in range(size)]
        self.history: list[Move] = []

    def copy(self):
        other = Board(self.size)
        other.cells = [row[:] for row in self.cells]
        other.history = self.history[:]
        return other

    def inside(self, row, col):
        return 0 <= row < self.size and 0 <= col < self.size

    def legal(self, row, col):
        return self.inside(row, col) and self.cells[row][col] == EMPTY

    def place(self, row, col, player):
        if player not in (BLACK, WHITE) or not self.legal(row, col):
            raise ValueError("Illegal move")
        self.cells[row][col] = player
        self.history.append(Move(row, col, player))

    def undo(self):
        if not self.history:
            return None
        move = self.history.pop()
        self.cells[move.row][move.col] = EMPTY
        return move

    @property
    def full(self):
        return len(self.history) == self.size * self.size

    def winning_line(self, row, col):
        if not self.inside(row, col) or self.cells[row][col] == EMPTY:
            return []
        player = self.cells[row][col]
        for dr, dc in DIRECTIONS:
            before, after = [], []
            for sign, segment in ((-1, before), (1, after)):
                r, c = row + sign * dr, col + sign * dc
                while self.inside(r, c) and self.cells[r][c] == player:
                    segment.append((r, c))
                    r, c = r + sign * dr, c + sign * dc
            line = before[::-1] + [(row, col)] + after
            if len(line) >= 5:
                return line
        return []

    def would_win(self, row, col, player):
        if not self.legal(row, col):
            return False
        self.cells[row][col] = player
        try:
            return bool(self.winning_line(row, col))
        finally:
            self.cells[row][col] = EMPTY

    def candidates(self):
        """Only intersections within two squares of an existing stone."""
        if not self.history:
            return [(self.size // 2, self.size // 2)]
        found = set()
        for move in self.history:
            for r in range(max(0, move.row - 2), min(self.size, move.row + 3)):
                for c in range(max(0, move.col - 2), min(self.size, move.col + 3)):
                    if self.cells[r][c] == EMPTY:
                        found.add((r, c))
        return sorted(found)


class Game:
    """Owns turns and terminal states; search never mutates this board."""
    def __init__(self, human=BLACK):
        self.board = Board()
        self.human = human
        self.ai = 3 - human
        self.turn = BLACK
        self.winner = EMPTY
        self.win_line = []
        self.draw = False

    @property
    def finished(self):
        return self.winner != EMPTY or self.draw

    def play(self, row, col):
        if self.finished or not self.board.legal(row, col):
            return False
        self.board.place(row, col, self.turn)
        self.win_line = self.board.winning_line(row, col)
        if self.win_line:
            self.winner = self.turn
        elif self.board.full:
            self.draw = True
        else:
            self.turn = 3 - self.turn
        return True

    def undo_turn(self):
        """Remove the latest human move and any subsequent computer reply."""
        if not any(m.player == self.human for m in self.board.history):
            return False
        while self.board.history:
            if self.board.undo().player == self.human:
                break
        self.turn = self.human
        self.winner, self.win_line, self.draw = EMPTY, [], False
        return True
