from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen

import theme

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
        self._hover_x = None
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
        painter.fillRect(event.rect(), theme.qcolor("progress_bg"))
        painter.fillRect(0, 0, self.width(), self.height(), theme.qcolor("progress_bg"))

        # Progress fill
        if self._progress > 0:
            progress_width = int(self.width() * self._progress)
            painter.fillRect(0, 0, progress_width, self.height(), theme.qcolor("progress_fill"))

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
                        painter.setPen(QPen(theme.qcolor("progress_text"), 2))
                        painter.drawLine(x, 0, x, self.height())

        # Text
        painter.setPen(theme.qcolor("progress_text"))
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

        # Hover timestamp tooltip
        if self._hover_x is not None and self._annotator is not None:
            total = getattr(getattr(self._annotator, "player", None), "duration", None)
            if total and total > 0:
                ratio = max(0.0, min(1.0, self._hover_x / self.width()))
                secs = ratio * total
                label = _format_hover_time(secs)

                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(label)
                text_h = fm.height()
                pad_x, pad_y = 5, 2
                box_w = text_w + pad_x * 2
                box_h = text_h + pad_y * 2

                # Align right edge of box to cursor; clamp to widget edges
                bx = int(self._hover_x) - box_w
                bx = max(0, min(bx, self.width() - box_w))
                by = 2  # top of bar

                bg = theme.qcolor("progress_bg")
                border = theme.qcolor("progress_text")
                painter.setBrush(bg)
                painter.setPen(QPen(border, 1))
                painter.drawRect(QRect(bx, by, box_w, box_h))

                painter.setPen(theme.qcolor("progress_text"))
                painter.drawText(bx + pad_x, by + pad_y + fm.ascent(), label)

        painter.end()

    # --- mouse ---------------------------------------------------------

    def mouseMoveEvent(self, event):
        self._hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event):
        self._hover_x = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._annotator is not None:
            ratio = event.position().x() / self.width()
            ratio = max(0.0, min(1.0, ratio))
            self._annotator.on_progress_click(ratio)


def _format_hover_time(secs):
    """Format seconds as H:MM:SS or M:SS for the hover tooltip."""
    secs = int(secs)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
