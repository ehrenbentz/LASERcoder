from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QPainter, QPen

import theme

class ProgressBar(QWidget):

    def __init__(self, parent=None, annotator=None):
        super().__init__(parent)
        self._progress = 0.0
        self._left_text = "0m0.00s"
        self._center_text = "(1.0x)"
        self._right_text = "Total Time"
        self._annotator = annotator
        self._custom_fill_color = None
        self.setMouseTracking(True)

        # Floating hover-timestamp label
        self._hover_label = None
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0))
        self.setPalette(palette)

    def set_progress(self, value):
        self._progress = max(0.0, min(1.0, value))

    def set_left_text(self, text):
        self._left_text = text

    def set_center_text(self, text):
        self._center_text = text

    def set_right_text(self, text):
        self._right_text = text

    def set_fill_color(self, color):
        self._custom_fill_color = color

    # painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_h = self.height() - 4  # leave 4px black buffer at bottom

        # Black background for full widget (bottom buffer)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(0, 0, 0))

        # Bar background
        painter.fillRect(0, 0, self.width(), bar_h, theme.qcolor("progress_bg"))

        # Progress fill
        if self._progress > 0:
            progress_width = int(self.width() * self._progress)
            fill = self._custom_fill_color or theme.qcolor("progress_fill")
            painter.fillRect(0, 0, progress_width, bar_h, fill)

        # Coding-end indicator (skip when timeline is limited to coding segment)
        ann = self._annotator
        if ann is not None and not getattr(ann, 'limit_timeline_to_coding', False):
            coding_end = getattr(ann, "coding_end", None)
            duration = getattr(ann, "player", None)
            if coding_end is not None and duration is not None:
                total = ann.player.duration
                if total and total > 0:
                    ratio = coding_end / total
                    if 0 <= ratio <= 1:
                        x = int(self.width() * ratio)
                        painter.setPen(QPen(theme.qcolor("progress_text"), 2))
                        painter.drawLine(x, 0, x, bar_h)

        # Text
        painter.setPen(theme.qcolor("progress_text"))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)

        text_y = bar_h // 2 + 5

        # Left (current time)
        painter.drawText(10, text_y, self._left_text)

        # Center (speed)
        cx = (self.width() - painter.fontMetrics().horizontalAdvance(self._center_text)) // 2
        painter.drawText(cx, text_y, self._center_text)

        # Right (total time)
        rx = self.width() - painter.fontMetrics().horizontalAdvance(self._right_text) - 10
        painter.drawText(rx, text_y, self._right_text)

        painter.end()

    # Mouse

    def _ensure_hover_label(self):
        if self._hover_label is not None:
            return
        self._hover_label = QLabel()
        self._hover_label.setWindowFlags(Qt.WindowType.ToolTip)
        self._hover_label.setStyleSheet(
            f"background-color: {theme.color('progress_bg')};"
            f" color: {theme.color('progress_text')};"
            " font-weight: bold;"
            " padding: 2px 5px;"
            f" border: 1px solid {theme.color('progress_text')};"
        )
        self._hover_label.hide()

    def mouseMoveEvent(self, event):
        if self._annotator is None:
            return
        total = getattr(getattr(self._annotator, "player", None), "duration", None)
        if not total or total <= 0:
            if self._hover_label is not None:
                self._hover_label.hide()
            return

        self._ensure_hover_label()
        if self._hover_label is None:
            return

        hover_x = event.position().x()
        ratio = max(0.0, min(1.0, hover_x / self.width()))
        ann = self._annotator
        if ann is not None and hasattr(ann, '_ratio_to_time'):
            secs = ann._ratio_to_time(ratio)
        else:
            secs = ratio * total
        self._hover_label.setText(_format_hover_time(secs))
        self._hover_label.adjustSize()

        global_pos = self.mapToGlobal(QPoint(int(hover_x), 0))
        bar_left = self.mapToGlobal(QPoint(0, 0)).x()
        label_w = self._hover_label.width()
        label_h = self._hover_label.height()
        lx = global_pos.x() - label_w // 2
        lx = max(bar_left, min(lx, bar_left + self.width() - label_w))
        ly = global_pos.y() - label_h - 2
        self._hover_label.move(lx, ly)
        self._hover_label.show()

    def leaveEvent(self, event):
        if self._hover_label is not None:
            self._hover_label.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._annotator is not None:
            ratio = event.position().x() / self.width()
            ratio = max(0.0, min(1.0, ratio))
            self._annotator.on_progress_click(ratio)


def _format_hover_time(secs):
    """Format seconds as H:MM:SS or M:SS"""
    secs = int(secs)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
