from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen

class ProgressBarWithText(QWidget):
    """
    Progress bar that displays current time, speed, and total time.

    """

    def __init__(self, parent=None, annotator=None):
        super().__init__(parent)
        self._progress = 0.0
        self._left_text = "0m0.00s"
        self._center_text = "(1.0x)"
        self._right_text = "Total Time"
        self._annotator = annotator
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0))
        self.setPalette(palette)

    # --- public setters ------------------------------------------------

    def set_progress(self, value):
        self._progress = max(0.0, min(1.0, value))
        self.update()

    def set_left_text(self, text):
        self._left_text = text
        self.update()

    def set_center_text(self, text):
        self._center_text = text
        self.update()

    def set_right_text(self, text):
        self._right_text = text
        self.update()

    # --- painting ------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(event.rect(), QColor(0, 0, 0))
        painter.fillRect(0, 0, self.width(), self.height(), QColor(40, 40, 40))

        # Progress fill
        if self._progress > 0:
            progress_width = int(self.width() * self._progress)
            painter.fillRect(0, 0, progress_width, self.height(), QColor(0, 0, 150))

        # Coding-end indicator
        ann = self._annotator
        if ann is not None:
            coding_end = getattr(ann, "coding_end", None)
            duration = getattr(ann, "player", None)
            if coding_end is not None and duration is not None:
                total = ann.player.duration
                if total and total > 0:
                    ratio = coding_end / total
                    if 0 <= ratio <= 1:
                        x = int(self.width() * ratio)
                        painter.setPen(QPen(QColor(255, 255, 255), 2))
                        painter.drawLine(x, 0, x, self.height())

        # Text
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        text_y = self.height() // 2 + 5

        # Left (current time)
        painter.drawText(10, text_y, self._left_text)

        # Center (speed)
        cx = (self.width() - painter.fontMetrics().horizontalAdvance(self._center_text)) // 2
        painter.drawText(cx, text_y, self._center_text)

        # Right (total time)
        rx = self.width() - painter.fontMetrics().horizontalAdvance(self._right_text) - 10
        painter.drawText(rx, text_y, self._right_text)

    # --- mouse ---------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._annotator is not None:
            ratio = event.position().x() / self.width()
            ratio = max(0.0, min(1.0, ratio))
            self._annotator.on_progress_click(ratio)
