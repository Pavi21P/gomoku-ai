"""Pattern-based, bounded negamax search with alpha-beta pruning.

This is an explainable heuristic opponent, not a trained neural network.
Immediate tactics are checked before selective pruning of quiet moves.
"""
from dataclasses import dataclass
from threading import Event
from time import perf_counter

from .game import Board, DIRECTIONS, EMPTY

WIN = 10_000_000
PATTERNS = (
    (".XXXX.", 160_000, "open four"),
    ("XXXX.", 28_000, "four"), (".XXXX", 28_000, "four"),
    ("XXX.X", 28_000, "broken four"), ("XX.XX", 28_000, "broken four"),
    ("X.XXX", 28_000, "broken four"),
    (".XXX.", 7_000, "open three"),
    (".XX.X.", 5_000, "broken three"), (".X.XX.", 5_000, "broken three"),
    ("XXX..", 650, "three"), ("..XXX", 650, "three"),
    ("XX.X.", 500, "three"), (".X.XX", 500, "three"),
    (".XX.", 250, "open two"), (".X.X.", 180, "split two"),
    (".X.", 25, "single"),
)


@dataclass(frozen=True)
class Level:
    seconds: float
    depth: int
    width: int
    nodes: int


LEVELS = {
    "Easy": Level(0.20, 1, 6, 800),
    "Medium": Level(0.65, 3, 10, 5_000),
    "Hard": Level(1.40, 5, 14, 15_000),
}


@dataclass(frozen=True)
class Analysis:
    move: tuple[int, int] | None
    reason: str
    nodes: int
    depth: int
    seconds: float
    score: int = 0
    cutoffs: int = 0


def threat(board: Board, row: int, col: int, player: int):
    """Score the four lines through a hypothetical or existing stone.

Only patterns containing the evaluated stone count. Board edges are blockers.
The strongest pattern per direction prevents overlapping-window inflation.
"""
    total, strongest, label = 0, 0, "position"
    forcing, threes = 0, 0
    for dr, dc in DIRECTIONS:
        chars = []
        for offset in range(-5, 6):
            r, c = row + dr * offset, col + dc * offset
            if offset == 0:
                chars.append("X")
            elif not board.inside(r, c):
                chars.append("#")
            else:
                value = board.cells[r][c]
                chars.append("." if value == EMPTY else "X" if value == player else "#")
        line = "".join(chars)
        best, name = 0, "position"
        for pattern, weight, title in (("XXXXX", WIN, "five in a row"),) + PATTERNS:
            start = line.find(pattern)
            while start >= 0:
                if start <= 5 < start + len(pattern):
                    if weight > best:
                        best, name = weight, title
                    break
                start = line.find(pattern, start + 1)
        total += best
        if best > strongest:
            strongest, label = best, name
        forcing += best >= 28_000
        threes += 5_000 <= best < 28_000
    if forcing >= 2 or (forcing and threes):
        total += 180_000
        label = "fork threat"
    elif threes >= 2:
        total += 60_000
        label = "double three"
    return total, label


class SearchStopped(Exception):
    pass


class GomokuAI:
    def choose(self, board: Board, player: int, difficulty="Medium", cancel=None):
        self.board = board.copy()
        self.level = LEVELS[difficulty]
        self.cancel = cancel or Event()
        self.started = perf_counter()
        self.deadline = self.started + self.level.seconds
        self.nodes = self.cutoffs = 0
        # Per-search cache; immutable full position keys avoid hash collisions.
        self.table = {}
        if board.full or (board.history and board.winning_line(board.history[-1].row, board.history[-1].col)):
            return self.result(None, "Game finished", 0)
        candidates = self.board.candidates()
        if not candidates:
            return self.result(None, "No legal moves", 0)
        fallback = candidates[0]
        if not board.history:
            return self.result(fallback, "Take the center", 0)
        try:
            ordered, mode = self.ordered(player, self.level.width)
            fallback = ordered[0]
            if mode == "win":
                return self.result(fallback, "Complete five in a row", 0, WIN)
            if mode == "block" and len(ordered) == 1:
                return self.result(fallback, "Block an immediate win", 0)
            best, score, completed = fallback, 0, 0
            for depth in range(1, self.level.depth + 1):
                iteration_move, iteration_score = best, -WIN * 2
                alpha = -WIN * 2
                # Previous completed iteration's best move gets first search.
                moves = [best] + [m for m in ordered if m != best]
                for row, col in moves:
                    self.check()
                    self.board.place(row, col, player)
                    try:
                        value = -self.search(depth - 1, 3 - player, -WIN * 2, -alpha, 1)
                    finally:
                        self.board.undo()
                    if value > iteration_score:
                        iteration_move, iteration_score = (row, col), value
                    alpha = max(alpha, value)
                best, score, completed = iteration_move, iteration_score, depth
                fallback = best
                if abs(score) >= WIN - 225:
                    break
        except SearchStopped:
            # A partially searched depth never overwrites the last complete one.
            best = locals().get("best", fallback)
            score = locals().get("score", 0)
            completed = locals().get("completed", 0)
        attack, attack_label = threat(self.board, *best, player)
        defense, defense_label = threat(self.board, *best, 3 - player)
        if locals().get("mode") == "block":
            reason = "Defend against multiple winning threats"
        elif defense > attack * 1.15 and defense >= 5_000:
            reason = "Defend: " + defense_label
        elif attack >= 5_000:
            reason = "Build: " + attack_label
        else:
            reason = "Develop connected stones"
        return self.result(best, reason, completed, score)

    def result(self, move, reason, depth, score=0):
        return Analysis(move, reason, self.nodes, depth, perf_counter() - self.started, score, self.cutoffs)

    def check(self):
        if self.cancel.is_set() or self.nodes >= self.level.nodes or perf_counter() >= self.deadline:
            raise SearchStopped

    def ordered(self, player, limit):
        candidates = self.board.candidates()
        wins, blocks = [], []
        # Never let the beam discard an immediate win or mandatory defense.
        for row, col in candidates:
            self.check()
            if self.board.would_win(row, col, player):
                wins.append((row, col))
            if self.board.would_win(row, col, 3 - player):
                blocks.append((row, col))
        if wins:
            return wins, "win"
        if blocks:
            return blocks, "block"
        ranked = []
        center = self.board.size // 2
        for row, col in candidates:
            self.check()
            attack = threat(self.board, row, col, player)[0]
            defense = threat(self.board, row, col, 3 - player)[0]
            score = attack + defense * 1.12 - abs(row - center) - abs(col - center)
            ranked.append((score, row, col))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [(r, c) for _, r, c in ranked[:limit]], "quiet"

    def evaluate(self, player):
        scores = {player: 0, 3 - player: 0}
        for move in self.board.history:
            self.check()
            scores[move.player] += threat(self.board, move.row, move.col, move.player)[0]
        # Tactical terminal scores always dominate heuristic estimates.
        return max(-WIN // 2, min(WIN // 2, scores[player] - scores[3 - player]))

    def search(self, depth, player, alpha, beta, ply):
        self.check()
        self.nodes += 1
        last = self.board.history[-1]
        if self.board.winning_line(last.row, last.col):
            return -WIN + ply
        if self.board.full:
            return 0
        if depth == 0:
            return self.evaluate(player)
        key = (tuple(tuple(row) for row in self.board.cells), player)
        entry = self.table.get(key)
        alpha_start, beta_start = alpha, beta
        if entry and entry[0] >= depth:
            _, value, flag = entry
            if flag == "exact":
                return value
            if flag == "lower":
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value
        moves, mode = self.ordered(player, self.level.width)
        if mode == "win":
            return WIN - ply - 1
        if mode == "block" and len(moves) > 1:
            return -WIN + ply + 2
        if not moves:
            return 0
        best = -WIN * 2
        for row, col in moves:
            self.board.place(row, col, player)
            try:
                value = -self.search(depth - 1, 3 - player, -beta, -alpha, ply + 1)
            finally:
                self.board.undo()
            best = max(best, value)
            alpha = max(alpha, value)
            if alpha >= beta:
                self.cutoffs += 1
                break
        flag = "upper" if best <= alpha_start else "lower" if best >= beta_start else "exact"
        self.table[key] = (depth, best, flag)
        return best
