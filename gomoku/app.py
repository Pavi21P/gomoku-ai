"""Pygame presentation and input. Only the main thread touches the UI."""
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pygame

from .ai import GomokuAI, LEVELS
from .game import BLACK, WHITE, Game

WIDTH, HEIGHT = 1120, 800
BG = (239, 237, 229)
INK = (30, 49, 46)
MUTED = (102, 116, 105)
GREEN = (37, 100, 79)
PALE = (221, 231, 217)
WHITE_UI = (250, 250, 244)
WOOD = (221, 194, 148)
GRID = (156, 128, 87)
ORIGIN, STEP = (76, 166), 41


class App:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        desktop = pygame.display.get_desktop_sizes()[0]
        scale = min(1.0, desktop[0] / WIDTH * 0.94, desktop[1] / HEIGHT * 0.90)
        self.window = pygame.display.set_mode((int(WIDTH * scale), int(HEIGHT * scale)), pygame.RESIZABLE)
        pygame.display.set_caption("Gomoku | Five in a row")
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = {}
        self.buttons = []
        self.screen = "menu"
        self.difficulty = "Medium"
        self.human = BLACK
        self.game = Game()
        self.analysis = None
        self.error = ""
        self.result_open = False
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gomoku-ai")
        self.future = None
        self.cancel = Event()
        self.revision = 0
        self.job_revision = 0
        self.started_at = 0

    def text(self, value, x, y, size=20, color=INK, bold=False, center=False):
        key = size, bold
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont("segoeui", size, bold=bold)
        image = self.fonts[key].render(str(value), True, color)
        rect = image.get_rect(midtop=(x, y)) if center else image.get_rect(topleft=(x, y))
        self.canvas.blit(image, rect)
        return rect

    def wrap(self, value, x, y, width, size=18, color=MUTED):
        self.text("", 0, 0, size)
        font = self.fonts[size, False]
        line = ""
        for word in value.split():
            next_line = (line + " " + word).strip()
            if font.size(next_line)[0] > width and line:
                self.text(line, x, y, size, color)
                y += size + 8
                line = word
            else:
                line = next_line
        if line:
            self.text(line, x, y, size, color)
            y += size + 8
        return y

    def panel(self, rect, color=WHITE_UI, radius=18):
        pygame.draw.rect(self.canvas, color, rect, border_radius=radius)

    def mouse_position(self):
        return self.to_canvas(pygame.mouse.get_pos())

    def to_canvas(self, pos):
        w, h = self.window.get_size()
        scale = min(w / WIDTH, h / HEIGHT)
        return ((pos[0] - (w - WIDTH * scale) / 2) / scale,
                (pos[1] - (h - HEIGHT * scale) / 2) / scale)

    def button(self, label, rect, action, primary=False, enabled=True):
        rect = pygame.Rect(rect)
        hovered = enabled and rect.collidepoint(self.mouse_position())
        color = GREEN if primary else PALE
        if hovered:
            color = (48, 118, 93) if primary else (206, 220, 200)
        if not enabled:
            color = (229, 229, 219)
        self.panel(rect, color, 10)
        self.text(label, rect.centerx, rect.y + (rect.height - 25) // 2, 19,
                  WHITE_UI if primary else INK if enabled else MUTED, True, True)
        self.buttons.append((rect, action, enabled))

    def cancel_job(self):
        self.cancel.set()
        if self.future is not None:
            self.future.cancel()
        self.future = None
        self.revision += 1

    def start_game(self):
        self.cancel_job()
        self.game = Game(self.human)
        self.analysis, self.error = None, ""
        self.result_open = False
        self.screen = "play"
        self.started_at = pygame.time.get_ticks()

    def menu(self):
        self.cancel_job()
        self.screen = "menu"

    def undo(self):
        if self.game.undo_turn():
            self.cancel_job()
            self.analysis, self.error = None, ""
            self.result_open = False

    def retry(self):
        self.error = ""

    def update(self):
        if self.screen != "play":
            return
        if self.future is not None and self.future.done():
            future, self.future = self.future, None
            if self.job_revision == self.revision:
                try:
                    analysis = future.result()
                    if analysis.move is None or not self.game.play(*analysis.move):
                        raise RuntimeError("The AI returned no legal move.")
                    self.analysis = analysis
                    self.result_open = self.game.finished
                except Exception as exc:
                    self.error = "AI search stopped. Select Retry AI or undo your move."
                    print(f"AI error: {exc}", file=sys.stderr)
        if (not self.game.finished and self.game.turn == self.game.ai
                and self.future is None and not self.error):
            self.cancel = Event()
            self.job_revision = self.revision
            self.future = self.executor.submit(GomokuAI().choose, self.game.board.copy(),
                                               self.game.ai, self.difficulty, self.cancel)

    def event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.menu() if self.screen == "play" else setattr(self, "running", False)
            elif event.key == pygame.K_RETURN and self.screen == "menu":
                self.start_game()
            elif self.screen == "play":
                if event.key == pygame.K_r:
                    self.start_game()
                elif event.key == pygame.K_u:
                    self.undo()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.to_canvas(event.pos)
            for rect, action, enabled in reversed(self.buttons):
                if rect.collidepoint(pos):
                    if enabled:
                        action()
                    return
            if self.screen != "play" or self.result_open or self.game.finished or self.game.turn != self.human:
                return
            cell = self.cell_at(pos)
            if cell is not None and self.game.play(*cell):
                self.result_open = self.game.finished

    def cell_at(self, pos):
        col = round((pos[0] - ORIGIN[0]) / STEP)
        row = round((pos[1] - ORIGIN[1]) / STEP)
        if not self.game.board.inside(row, col):
            return None
        x, y = self.point(row, col)
        return (row, col) if abs(x - pos[0]) <= STEP * 0.46 and abs(y - pos[1]) <= STEP * 0.46 else None

    @staticmethod
    def point(row, col):
        return ORIGIN[0] + col * STEP, ORIGIN[1] + row * STEP

    def stone(self, row, col, player, ghost=False):
        x, y = self.point(row, col)
        if ghost:
            pygame.draw.circle(self.canvas, GREEN, (x, y), 15, 2)
            pygame.draw.circle(self.canvas, GREEN, (x, y), 3)
            return
        pygame.draw.circle(self.canvas, (178, 151, 109), (x + 2, y + 3), 18)
        pygame.draw.circle(self.canvas, (30, 40, 40) if player == BLACK else (247, 246, 230), (x, y), 18)
        pygame.draw.circle(self.canvas, (57, 68, 65) if player == BLACK else (255, 255, 247), (x - 4, y - 5), 7)
        pygame.draw.circle(self.canvas, (24, 34, 33) if player == BLACK else (213, 210, 190), (x, y), 18, 1)

    def draw_board(self):
        self.panel((32, 122, 662, 660), WOOD)
        for i in range(15):
            x, y = self.point(i, i)
            pygame.draw.line(self.canvas, GRID, (ORIGIN[0], y), (ORIGIN[0] + STEP * 14, y))
            pygame.draw.line(self.canvas, GRID, (x, ORIGIN[1]), (x, ORIGIN[1] + STEP * 14))
            self.text(chr(65 + i), x, 133, 14, (105, 83, 52), center=True)
            self.text(str(i + 1), 49, y - 10, 14, (105, 83, 52), center=True)
        for row, col in ((3, 3), (3, 11), (7, 7), (11, 3), (11, 11)):
            pygame.draw.circle(self.canvas, GRID, self.point(row, col), 4)
        for move in self.game.board.history:
            self.stone(move.row, move.col, move.player)
        if self.game.board.history:
            last = self.game.board.history[-1]
            pygame.draw.circle(self.canvas, (210, 126, 65), self.point(last.row, last.col), 5, 2)
        if self.game.win_line:
            pygame.draw.line(self.canvas, GREEN, self.point(*self.game.win_line[0]),
                             self.point(*self.game.win_line[-1]), 4)
        if self.screen == "play" and not self.game.finished and self.game.turn == self.human and not self.result_open:
            cell = self.cell_at(self.mouse_position())
            if cell and self.game.board.legal(*cell):
                self.stone(*cell, self.human, ghost=True)

    def draw_header(self):
        self.text("GOMOKU", 32, 24, 37, bold=True)
        self.text("FIVE IN A ROW  /  A GAME OF PATTERNS", 34, 75, 14, MUTED)
        self.panel((878, 32, 210, 40), PALE, 20)
        self.text("HUMAN  vs  HEURISTIC AI", 983, 42, 13, GREEN, True, True)

    def draw_sidebar(self):
        x = 720
        self.panel((x, 122, 368, 144))
        self.text("THE MATCH", x + 22, 140, 13, MUTED, True)
        if self.game.finished:
            status = "Draw game" if self.game.draw else "You win!" if self.game.winner == self.human else "AI wins"
        elif self.game.turn == self.human:
            status = "Your move"
        else:
            status = "AI is thinking" + "." * (1 + pygame.time.get_ticks() // 450 % 3)
        self.text(status, x + 22, 163, 30, GREEN, True)
        self.text(f"{len(self.game.board.history):02d} moves played  /  {self.difficulty}", x + 22, 214, 17, MUTED)

        self.panel((x, 282, 368, 78))
        for player, cx, title in ((self.human, x + 28, "YOU"), (self.game.ai, x + 212, "COMPUTER")):
            pygame.draw.circle(self.canvas, INK if player == BLACK else (224, 224, 212), (cx, 321), 12)
            self.text(title, cx + 24, 298, 12, MUTED, True)
            self.text("Black / first" if player == BLACK else "White / second", cx + 24, 319, 15)

        self.panel((x, 376, 368, 222))
        self.text("INSIDE THE AI", x + 22, 394, 13, MUTED, True)
        if self.error:
            self.wrap(self.error, x + 22, 426, 324, 18)
        elif self.analysis:
            a = self.analysis
            row, col = a.move
            self.text(f"Last move: {chr(65 + col)}{row + 1}", x + 22, 423, 22, INK, True)
            self.wrap(a.reason, x + 22, 462, 320)
            self.text(f"{a.nodes:,} nodes  /  depth {a.depth}", x + 22, 530, 16, MUTED)
            self.text(f"{a.seconds * 1000:.0f} ms  /  {a.cutoffs} cutoffs", x + 22, 555, 16, MUTED)
        else:
            self.wrap("The AI checks wins and blocks, recognizes threats, then searches ahead.", x + 22, 427, 318, 19)
            self.text("Its last decision will appear here.", x + 22, 554, 16, MUTED)

        can_undo = any(m.player == self.human for m in self.game.board.history)
        self.button("Undo turn  [U]", (x, 614, 176, 46), self.undo, enabled=can_undo)
        self.button("New game  [R]", (x + 190, 614, 178, 46), self.start_game)
        if self.error:
            self.button("Retry AI", (x, 674, 368, 44), self.retry, True)
        elif self.game.finished:
            self.button("View result", (x, 674, 368, 44), lambda: setattr(self, "result_open", True), True)
        else:
            self.button("Settings / menu  [Esc]", (x, 674, 368, 44), self.menu)
        self.wrap("Connect five or more stones. Black goes first. No forbidden moves.", x + 6, 735, 354, 15)

    def veil(self):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((23, 43, 36, 150))
        self.canvas.blit(shade, (0, 0))

    def draw_menu(self):
        self.veil()
        self.buttons = []
        self.panel((260, 94, 600, 612))
        self.text("A LITTLE FORESIGHT GOES A LONG WAY", 560, 127, 13, GREEN, True, True)
        self.text("Five in a row.", 560, 159, 49, INK, True, True)
        self.text("One move ahead.", 560, 218, 39, GREEN, False, True)
        self.text("Read the board. Build a threat. Make your move.", 560, 287, 18, MUTED, center=True)
        self.text("CHOOSE YOUR CHALLENGE", 306, 344, 13, MUTED, True)
        for i, name in enumerate(LEVELS):
            self.button(name, (306 + i * 174, 372, 160, 44),
                        lambda name=name: setattr(self, "difficulty", name), self.difficulty == name)
        descriptions = {
            "Easy": "Quick pattern play. A good place to learn.",
            "Medium": "Threat-aware search with a short thinking budget.",
            "Hard": "A wider, deeper search. Up to 1.4 seconds per move.",
        }
        self.text(descriptions[self.difficulty], 306, 430, 16, MUTED)
        self.text("YOUR STONES", 306, 473, 13, MUTED, True)
        self.button("Black / you start", (306, 500, 247, 44), lambda: setattr(self, "human", BLACK), self.human == BLACK)
        self.button("White / AI starts", (567, 500, 247, 44), lambda: setattr(self, "human", WHITE), self.human == WHITE)
        self.button("Start playing", (306, 574, 508, 54), self.start_game, True)
        self.text("15 x 15 board  /  Five or more wins  /  Enter to start", 560, 652, 15, MUTED, center=True)

    def draw_result(self):
        self.veil()
        self.buttons = []
        self.panel((302, 200, 516, 400))
        win = self.game.winner == self.human
        title = "Board complete" if self.game.draw else "Beautifully played." if win else "A lesson in foresight."
        subtitle = "It's a draw." if self.game.draw else "You win!" if win else "The AI wins this round."
        self.text("MATCH COMPLETE", 560, 232, 14, GREEN, True, True)
        self.text(title, 560, 278, 34, INK, True, True)
        self.text(subtitle, 560, 334, 24, GREEN, center=True)
        self.text(f"{len(self.game.board.history)} moves  /  {self.difficulty} difficulty", 560, 384, 18, MUTED, center=True)
        self.button("Play again", (342, 435, 436, 50), self.start_game, True)
        self.button("Review board", (342, 503, 212, 46), lambda: setattr(self, "result_open", False))
        self.button("Main menu", (566, 503, 212, 46), self.menu)

    def draw(self):
        self.buttons = []
        self.canvas.fill(BG)
        self.draw_header()
        self.draw_board()
        self.draw_sidebar()
        if self.screen == "menu":
            self.draw_menu()
        elif self.result_open:
            self.draw_result()
        w, h = self.window.get_size()
        scale = min(w / WIDTH, h / HEIGHT)
        size = max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale))
        self.window.fill(INK)
        image = self.canvas if size == (WIDTH, HEIGHT) else pygame.transform.smoothscale(self.canvas, size)
        self.window.blit(image, ((w - size[0]) // 2, (h - size[1]) // 2))
        pygame.display.flip()

    def close(self):
        self.cancel_job()
        self.executor.shutdown(wait=True, cancel_futures=True)
        pygame.quit()

    def run(self):
        try:
            self.draw()
            while self.running:
                for event in pygame.event.get():
                    self.event(event)
                    # Rebuild hit targets after a screen-changing input event.
                    if self.running:
                        self.draw()
                self.update()
                self.draw()
                self.clock.tick(60)
        finally:
            self.close()


def main():
    App().run()
