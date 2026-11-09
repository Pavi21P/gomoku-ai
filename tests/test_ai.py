import unittest
from threading import Event
from time import perf_counter

from gomoku.ai import GomokuAI, threat
from gomoku.game import BLACK, WHITE, Board


class AITests(unittest.TestCase):
    def test_center_opening(self):
        self.assertEqual((7, 7), GomokuAI().choose(Board(), BLACK).move)

    def test_immediate_wins_in_all_directions(self):
        for dr, dc, row, col in ((0, 1, 0, 0), (1, 0, 0, 14), (1, 1, 0, 0), (1, -1, 0, 14)):
            with self.subTest(direction=(dr, dc)):
                board = Board()
                for i in range(4):
                    board.place(row + i * dr, col + i * dc, WHITE)
                self.assertEqual((row + 4 * dr, col + 4 * dc), GomokuAI().choose(board, WHITE).move)

    def test_blocks_straight_and_broken_fours(self):
        for columns, expected in (((0, 1, 2, 3), 4), ((0, 1, 3, 4), 2), ((0, 2, 3, 4), 1)):
            with self.subTest(columns=columns):
                board = Board()
                for col in columns:
                    board.place(0, col, BLACK)
                result = GomokuAI().choose(board, WHITE)
                self.assertEqual((0, expected), result.move)
                self.assertIn("Block", result.reason)

    def test_winning_move_takes_priority_over_defense(self):
        board = Board()
        for col in range(4):
            board.place(0, col, BLACK)
            board.place(2, col, WHITE)
        self.assertEqual((2, 4), GomokuAI().choose(board, WHITE).move)

    def test_pattern_recognition_and_edges(self):
        board = Board()
        for col in (6, 8):
            board.place(7, col, WHITE)
        score, name = threat(board, 7, 7, WHITE)
        self.assertEqual("open three", name)
        for row in (6, 8):
            board.place(row, 7, WHITE)
        fork, name = threat(board, 7, 7, WHITE)
        self.assertEqual("double three", name)
        self.assertGreater(fork, score * 2)
        edge = Board()
        for col in (0, 1):
            edge.place(0, col, WHITE)
        self.assertNotEqual("open three", threat(edge, 0, 2, WHITE)[1])

    def test_blocks_developing_open_three(self):
        board = Board()
        for col in (6, 7, 8):
            board.place(7, col, BLACK)
        board.place(5, 5, WHITE)
        self.assertIn(GomokuAI().choose(board, WHITE, "Easy").move, ((7, 5), (7, 9)))

    def test_search_preserves_board_and_obeys_budget(self):
        board = Board()
        for row, col, player in ((7, 7, BLACK), (6, 7, WHITE), (7, 8, BLACK), (8, 8, WHITE)):
            board.place(row, col, player)
        snapshot = board.copy()
        started = perf_counter()
        result = GomokuAI().choose(board, BLACK, "Medium")
        self.assertLess(perf_counter() - started, 2.5)
        self.assertTrue(board.legal(*result.move))
        self.assertEqual(snapshot.cells, board.cells)
        self.assertEqual(snapshot.history, board.history)
        self.assertGreaterEqual(result.depth, 1)

    def test_cancelled_search_returns_legal_fallback(self):
        board = Board()
        board.place(7, 7, BLACK)
        cancelled = Event()
        cancelled.set()
        result = GomokuAI().choose(board, WHITE, "Hard", cancelled)
        self.assertTrue(board.legal(*result.move))
        self.assertLess(result.seconds, 0.1)

    def test_no_move_after_game_over(self):
        board = Board()
        for col in range(5):
            board.place(0, col, BLACK)
        self.assertIsNone(GomokuAI().choose(board, WHITE).move)


if __name__ == "__main__":
    unittest.main()
