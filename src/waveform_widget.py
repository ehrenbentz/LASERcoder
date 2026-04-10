import os
import hashlib
import tempfile
import locale

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QLabel

import theme
from debug_logger import get_logger

logger = get_logger()

CACHE_BINS = 4096


class WaveformExtractor(QThread):
    """Background thread that extracts audio amplitude data from a video file."""

    finished = Signal(np.ndarray)
    error = Signal(str)

    def __init__(self, video_path, resume_dir, bin_count):
        super().__init__()
        self._video_path = video_path
        self._resume_dir = resume_dir
        self._bin_count = max(1, bin_count)

    def _cache_path(self):
        try:
            mtime = os.path.getmtime(self._video_path)
        except OSError:
            mtime = 0
        digest = hashlib.sha1(
            f"{self._video_path}|{mtime}".encode()).hexdigest()[:16]
        return os.path.join(self._resume_dir, f"waveform_{digest}.npy")

    def run(self):
        try:
            cache = self._cache_path()

            # Try cached data first
            if os.path.isfile(cache) and os.path.getsize(cache) > 0:
                try:
                    data = np.load(cache)
                    if data.size > 0:
                        self.finished.emit(self._rebin(data, self._bin_count))
                        return
                except Exception:
                    pass

            # Extract audio via headless mpv instance
            raw = self._extract_pcm()
            if not raw:
                self.finished.emit(np.zeros(self._bin_count, dtype=np.float32))
                return

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            # Compute RMS at cache resolution
            n_bins = min(CACHE_BINS, len(samples))
            if n_bins < 1:
                self.finished.emit(np.zeros(self._bin_count, dtype=np.float32))
                return

            chunks = np.array_split(samples, n_bins)
            rms = np.array(
                [np.sqrt(np.mean(c ** 2)) for c in chunks], dtype=np.float32)

            # Save to cache
            try:
                os.makedirs(self._resume_dir, exist_ok=True)
                np.save(cache, rms)
            except Exception as exc:
                logger.debug("Failed to save waveform cache: %s", exc)

            self.finished.emit(self._rebin(rms, self._bin_count))

        except Exception as exc:
            logger.debug("Waveform extraction error: %s", exc)
            self.error.emit(str(exc))
            self.finished.emit(np.zeros(self._bin_count, dtype=np.float32))

    def _extract_pcm(self):
        """Use a headless mpv instance to decode audio to raw PCM."""
        import mpv

        tmp = tempfile.NamedTemporaryFile(suffix=".pcm", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
            player = mpv.MPV(
                vid="no",
                untimed=True,
                ao="pcm",
                ao_pcm_waveheader="no",
                ao_pcm_file=tmp_path,
                af="lavfi=[aresample=2000,pan=mono|c0=c0,aformat=sample_fmts=s16]",
                log_handler=lambda *a: None,
            )
            player.play(self._video_path)
            player.wait_for_playback()
            player.terminate()

            with open(tmp_path, "rb") as f:
                raw = f.read()
            return raw
        except Exception as exc:
            logger.warning("MPV audio extraction failed: %s", exc)
            return b""
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _rebin(data, n_bins):
        if data.size == n_bins:
            return data.astype(np.float32)
        old_x = np.linspace(0, 1, data.size)
        new_x = np.linspace(0, 1, n_bins)
        return np.interp(new_x, old_x, data).astype(np.float32)


class WaveformWidget(QWidget):
    """Custom-painted widget that renders a waveform amplitude overview."""

    def __init__(self, parent=None, annotator=None):
        super().__init__(parent)
        self._annotator = annotator
        self._rms_data = None
        self._rebinned = None
        self._progress = 0.0
        self._fill_color = QColor(0, 150, 255)
        self._opacity = 0.8
        self._hover_label = None
        self._placeholder_text = None
        self._extractor = None
        self._extracted = False

        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0))
        self.setPalette(palette)

    def set_progress(self, value):
        self._progress = max(0.0, min(1.0, value))

    def set_fill_color(self, color):
        if isinstance(color, str):
            color = QColor(color)
        self._fill_color = color
        self.update()

    def set_opacity(self, value):
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def set_rms_data(self, data):
        self._rms_data = data
        self._rebinned = None
        self._placeholder_text = None
        self.update()

    def start_extraction(self, video_path, resume_dir):
        if self._extracted:
            return
        if self._extractor is not None and self._extractor.isRunning():
            return
        self._placeholder_text = "Generating waveform..."
        self._rms_data = None
        self._rebinned = None
        self.update()

        self._extractor = WaveformExtractor(
            video_path, resume_dir, max(1, self.width()))
        self._extractor.finished.connect(self._on_extraction_done)
        self._extractor.error.connect(self._on_extraction_error)
        self._extractor.start()

    def cancel_extraction(self):
        if self._extractor is not None and self._extractor.isRunning():
            self._extractor.terminate()
            self._extractor.wait(2000)

    def _on_extraction_done(self, data):
        self._extracted = True
        self.set_rms_data(data)

    def _on_extraction_error(self, msg):
        logger.debug("Waveform extraction error: %s", msg)

    def reset(self):
        """Clear waveform data. Call when loading a new video file."""
        self._rms_data = None
        self._rebinned = None
        self._extracted = False
        self._placeholder_text = None
        self.update()

    # Painting

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, theme.qcolor("progress_bg"))

        if self._rms_data is not None and self._rms_data.size > 0:
            self._paint_waveform(painter, w, h)
        elif self._placeholder_text:
            painter.setPen(theme.qcolor("progress_text"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             self._placeholder_text)

        # Playhead
        px = int(w * self._progress)
        painter.setPen(QPen(theme.qcolor("progress_text"), 1))
        painter.drawLine(px, 0, px, h)

        # Coding-end indicator (skip when timeline is limited to coding segment)
        ann = self._annotator
        if ann is not None and not getattr(ann, 'limit_timeline_to_coding', False):
            coding_end = getattr(ann, "coding_end", None)
            if coding_end is not None:
                total = getattr(ann, "_mpv_duration", None)
                if not total and hasattr(ann, "player") and ann.player:
                    total = ann.player.duration
                if total and total > 0:
                    ratio = coding_end / total
                    if 0 <= ratio <= 1:
                        cx = int(w * ratio)
                        painter.setPen(QPen(theme.qcolor("progress_text"), 2))
                        painter.drawLine(cx, 0, cx, h)

        painter.end()

    def _get_display_data(self):
        """Return the RMS data slice appropriate for the current timeline view."""
        if self._rms_data is None:
            return None
        ann = self._annotator
        if (ann is not None
                and getattr(ann, 'limit_timeline_to_coding', False)
                and ann.coding_start is not None
                and ann.coding_end is not None
                and ann.coding_end > ann.coding_start):
            total = (getattr(ann, '_mpv_duration', None)
                     or getattr(getattr(ann, 'player', None), 'duration', None)
                     or 0)
            if total > 0:
                n = self._rms_data.size
                i_start = max(0, min(n, int((ann.coding_start / total) * n)))
                i_end = max(i_start + 1, min(n, int((ann.coding_end / total) * n)))
                return self._rms_data[i_start:i_end]
        return self._rms_data

    def _paint_waveform(self, painter, w, h):
        data = self._get_display_data()
        if data is None or data.size == 0:
            return

        # Rebin to widget width (always fresh since display data may change)
        normalized = WaveformExtractor._rebin(data, max(1, w))

        peak = normalized.max()
        if peak < 1e-6:
            return
        normalized = np.sqrt(normalized / peak)

        painter.setOpacity(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._fill_color)

        half_h = h / 2
        for x in range(w):
            bar_h = int(normalized[x] * half_h)
            if bar_h > 0:
                painter.drawRect(x, int(half_h - bar_h), 1, bar_h * 2)

        painter.setOpacity(1.0)

    # Mouse interaction — click-to-seek

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._annotator is not None:
            ratio = event.position().x() / self.width()
            ratio = max(0.0, min(1.0, ratio))
            self._annotator.on_progress_click(ratio)

    # Mouse interaction — hover timestamp

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


def _format_hover_time(secs):
    secs = int(secs)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
