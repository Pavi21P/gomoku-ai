import unittest

from gomoku.game import BLACK, WHITE, Board, Game


class BoardTests(unittest.TestCase):
    def test_wins_in_all_directions_including_overlines(self):
        for dr, dc, row, col in ((0, 1, 0, 0), (1, 0, 0, 14), (1, 1, 0, 0), (1, -1, 0, 14)):
            for length in (5, 6):
                with self.subTest(direction=(dr, dc), length=length):
                    board = Board()
                    for i in range(length):
                        board.place(row + i * dr, col + i * dc, BLACK)
                    self.assertEqual(length, len(board.winning_line(row, col)))

    def test_gap_and_opponent_interrupt_lines(self):
        for middle in (0, WHITE):
            board = Board()
            for col in range(5):
                if col != 2:
                    board.place(0, col, BLACK)
                elif middle:
                    board.place(0, col, middle)
            self.assertFalse(board.winning_line(0, 0))

    def test_illegal_moves_and_copy_isolation(self):
        board = Board()
        board.place(7, 7, BLACK)
        for row, col, player in ((7, 7, WHITE), (-1, 0, BLACK), (15, 0, BLACK), (0, 0, 3)):
            with self.assertRaises(ValueError):
                board.place(row, col, player)
        other = board.copy()
        other.undo()
        self.assertEqual(BLACK, board.cells[7][7])
        self.assertEqual(1, len(board.history))

    def test_terminal_game_rejects_moves_and_undo_restores_turn(self):
        game = Game()
        for col in range(4):
            game.play(0, col)
            game.play(2, col)
        game.play(0, 4)
        self.assertEqual(BLACK, game.winner)
        self.assertFalse(game.play(4, 4))
        self.assertTrue(game.undo_turn())
        self.assertFalse(game.finished)
        self.assertEqual(BLACK, game.turn)

    def test_undo_removes_human_move_and_reply(self):
        for human in (BLACK, WHITE):
            game = Game(human)
            if human == WHITE:
                game.play(7, 7)
                self.assertFalse(game.undo_turn())
            count = len(game.board.history)
            game.play(0, 0)
            game.play(1, 1)
            self.assertTrue(game.undo_turn())
            self.assertEqual(count, len(game.board.history))
            self.assertEqual(human, game.turn)

    def test_full_board_draw(self):
        # Alternating paired rows break both diagonals; no run exceeds four.
        game = Game()
        for row in range(15):
            for col in range(15):
                game.turn = BLACK if (col + row // 2) % 2 == 0 else WHITE
                self.assertTrue(game.play(row, col))
        self.assertTrue(game.draw)
        self.assertEqual(0, game.winner)
        self.assertTrue(game.board.full)


if __name__ == "__main__":
    unittest.main()
