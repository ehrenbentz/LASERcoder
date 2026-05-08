"""
spectrogram_widget.py

Displays a scrolling spectrogram window centered on the current playback
position.  Audio is extracted in a background thread using a headless MPV
instance; the Short-Time Fourier Transform and colormap rendering are
performed with numpy.  The main thread only ever paints a pre-rendered
QImage, so the GUI stays responsive.

"""

import os
import sys
import tempfile
import locale

import numpy as np

from PySide6.QtCore import (
    Qt, QThread, Signal, QMutex, QMutexLocker,
    QTimer, QRectF, QPoint,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget, QLabel

import theme
from debug_logger import get_logger

logger = get_logger()


def _stft_spectrogram(samples, fs, nperseg, noverlap):
    """NumPy Short-Time Fourier Transform.
    Returns freqs, times, Sxx where Sxx has shape (n_freqs, n_frames).
    """
    samples = np.asarray(samples, dtype=np.float32)
    step = nperseg - noverlap
    if samples.size < nperseg:
        freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
        return freqs, np.zeros(0, dtype=np.float32), np.zeros(
            (freqs.size, 0), dtype=np.float32)

    n_frames = 1 + (samples.size - nperseg) // step
    window = np.hanning(nperseg).astype(np.float32)

    # Build a 2D view of overlapping frames without copying, then window.
    frames = np.lib.stride_tricks.as_strided(
        samples,
        shape=(n_frames, nperseg),
        strides=(step * samples.strides[0], samples.strides[0]),
        writeable=False,
    ) * window

    # One-sided FFT, density-scaled magnitude squared.
    spectra = np.fft.rfft(frames, axis=1)
    scale = 1.0 / (fs * (window * window).sum())
    Sxx = (np.abs(spectra) ** 2) * scale
    if nperseg % 2 == 0:
        Sxx[:, 1:-1] *= 2.0
    else:
        Sxx[:, 1:] *= 2.0
    Sxx = Sxx.T.astype(np.float32)  # shape (n_freqs, n_frames)

    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs).astype(np.float32)
    times = ((np.arange(n_frames) * step + nperseg / 2) / fs).astype(np.float32)

    return freqs, times, Sxx


#  Constants

SAMPLE_RATE = 44100          # Hz must be >= 2 * max display frequency
STFT_NPERSEG = 1024          # FFT window size (freq resolution ~ 43 Hz)
STFT_NOVERLAP = 768          # 75 % overlap gives good time resolution
DYNAMIC_RANGE_DB = 80.0      # dB range mapped to the colormap
MAX_PLAYBACK_SPEED = 8.0     # disable spectrogram above this speed
WORKER_POLL_MS = 50          # worker thread sleep between polls
BUFFER_CHECK_MS = 200        # widget timer interval for buffer freshness
REBUFFER_MARGIN_S = 8.0      # request new buffer well before the edge


#  Colormaps

def _build_lut(control_points):
    """Interpolate (position, R, G, B) control points into a 256x3 uint8 LUT."""
    positions = np.array([p[0] for p in control_points])
    lut = np.zeros((256, 3), dtype=np.uint8)
    x = np.linspace(0.0, 1.0, 256)
    for ch in range(3):
        vals = np.array([p[ch + 1] for p in control_points], dtype=np.float64)
        lut[:, ch] = np.clip(np.interp(x, positions, vals), 0, 255).astype(np.uint8)
    return lut


COLORMAPS = {
    "viridis": _build_lut([
        (0.00,  68,   1,  84),
        (0.10,  72,  31, 112),
        (0.20,  62,  74, 137),
        (0.30,  49, 104, 142),
        (0.40,  38, 130, 142),
        (0.50,  31, 158, 137),
        (0.60,  53, 183, 121),
        (0.70, 110, 206,  88),
        (0.80, 181, 222,  43),
        (0.90, 229, 228,  32),
        (1.00, 253, 231,  37),
    ]),
    "magma": _build_lut([
        (0.00,   0,   0,   4),
        (0.10,  18,  13,  54),
        (0.20,  68,  15, 115),
        (0.30, 114,  31, 129),
        (0.40, 158,  47, 122),
        (0.50, 203,  70, 107),
        (0.60, 237, 100,  90),
        (0.70, 251, 143,  97),
        (0.80, 254, 191, 132),
        (0.90, 254, 232, 175),
        (1.00, 252, 253, 191),
    ]),
    "jet": _build_lut([
        (0.00,   0,   0, 127),
        (0.10,   0,   0, 255),
        (0.35,   0, 255, 255),
        (0.50,   0, 255,   0),
        (0.65, 255, 255,   0),
        (0.90, 255,   0,   0),
        (1.00, 127,   0,   0),
    ]),
    "hot": _build_lut([
        (0.00,   0,   0,   0),
        (0.33, 200,   0,   0),
        (0.66, 255, 200,   0),
        (1.00, 255, 255, 255),
    ]),
    "cold": _build_lut([
        (0.00,   0,   0,   0),
        (0.33,   0,   0, 200),
        (0.66,   0, 200, 255),
        (1.00, 255, 255, 255),
    ]),
    "grayscale": _build_lut([
        (0.00,   0,   0,   0),
        (1.00, 255, 255, 255),
    ]),
}


#  SpectrogramWorker (QThread)

class SpectrogramWorker(QThread):
    """Background thread: extracts audio via headless MPV, computes the STFT,
    maps through a colormap, and emits a ready-to-paint QImage.

    Signals:
    result_ready(QImage, float, float)
        The rendered spectrogram image and the time range it covers
        (buffer_start, buffer_end) in seconds.
    """

    result_ready = Signal(QImage, float, float)

    def __init__(self, video_path):
        super().__init__()
        self._video_path = video_path
        self._running = True

        # Shared state (guarded by _mutex)
        self._mutex = QMutex()
        self._pending_pos = None

        self._extract_player = None    # mpv.MPV instance (if active)

        # Pre-extracted audio data (macOS: main-thread extraction)
        self._preloaded_samples = None
        self._preloaded_buf_start = 0.0
        self._preloaded_buf_end = 0.0

        # Settings (read under mutex at the start of each computation)
        self._window_duration = 10.0     # display window, seconds
        self._buffer_margin = 10.0       # extra seconds per side
        self._freq_low = 0               # Hz
        self._freq_high = 15000          # Hz
        self._colormap_name = "viridis"

    # public, called from main thread

    def request_update(self, position_seconds):
        """Queue a request to (re)compute the spectrogram at *position*."""
        with QMutexLocker(self._mutex):
            self._pending_pos = position_seconds

    def update_settings(self, **kwargs):
        """Update one or more settings.  Valid keys: window_duration,
        buffer_margin, freq_low, freq_high, colormap_name."""
        with QMutexLocker(self._mutex):
            for key, value in kwargs.items():
                attr = f"_{key}"
                if hasattr(self, attr):
                    setattr(self, attr, value)

    def stop(self):
        """Signal the thread to exit and wait for it."""
        self._running = False
        # Interrupt any in-progress MPV extraction
        player = self._extract_player
        if player is not None:
            try:
                player.quit()
            except Exception:
                pass
        if not self.wait(5000):
            self.terminate()
            self.wait(2000)

    # thread entry

    def run(self):
        while self._running:
            with QMutexLocker(self._mutex):
                pos = self._pending_pos
                self._pending_pos = None

            if pos is None:
                self.msleep(WORKER_POLL_MS)
                continue

            if not self._running:
                break

            try:
                self._process(pos)
            except Exception as exc:
                logger.debug("Spectrogram computation error: %s", exc)

    # internal

    def _read_settings(self):
        """Snapshot current settings under the mutex."""
        with QMutexLocker(self._mutex):
            return (
                self._window_duration,
                self._buffer_margin,
                self._freq_low,
                self._freq_high,
                self._colormap_name,
            )

    def _process(self, center_pos):
        win_dur, buf_margin, freq_lo, freq_hi, cmap_name = self._read_settings()

        half = win_dur / 2.0
        buf_start = max(0.0, center_pos - half - buf_margin)
        buf_end = center_pos + half + buf_margin
        extract_dur = buf_end - buf_start

        # extract audio
        # On macOS, MPV must be created on the main thread (Cocoa
        # requirement).  The widget pre-extracts audio on the main
        # thread and stores it for us before queuing the request.
        if sys.platform == "darwin":
            with QMutexLocker(self._mutex):
                samples = self._preloaded_samples
                buf_start = self._preloaded_buf_start
                self._preloaded_samples = None
        else:
            samples = self._extract_pcm(buf_start, extract_dur)
        if samples is None or samples.size == 0:
            return

        # Adjust buf_end to match actual extracted length
        actual_dur = samples.size / SAMPLE_RATE
        buf_end = buf_start + actual_dur

        # STFT
        freqs, times, sxx = _stft_spectrogram(
            samples,
            fs=SAMPLE_RATE,
            nperseg=STFT_NPERSEG,
            noverlap=STFT_NOVERLAP,
        )

        # Slice to requested frequency band
        freq_mask = (freqs >= freq_lo) & (freqs <= freq_hi)
        sxx = sxx[freq_mask, :]

        if sxx.size == 0:
            return

        # dB conversion and normalisation
        power_db = 10.0 * np.log10(sxx + 1e-10)
        db_max = power_db.max()
        db_min = db_max - DYNAMIC_RANGE_DB
        normalized = np.clip((power_db - db_min) / (db_max - db_min), 0.0, 1.0)

        # colormap mapping
        lut = COLORMAPS.get(cmap_name, COLORMAPS["viridis"])
        indices = (normalized * 255).astype(np.uint8)
        rgb = lut[indices]  # shape (n_freqs, n_times, 3)

        # Flip vertically so low frequencies sit at the bottom
        rgb = np.ascontiguousarray(rgb[::-1])

        # build QImage
        img_h, img_w = rgb.shape[:2]
        bytes_per_line = img_w * 3
        qimg = QImage(rgb.data, img_w, img_h, bytes_per_line,
                       QImage.Format.Format_RGB888).copy()

        # Always emit the result never discard completed work
        self.result_ready.emit(qimg, buf_start, buf_end)

        # If a new request arrived during computation but it falls inside
        # the buffer we just computed, clear it (already covered)
        with QMutexLocker(self._mutex):
            if self._pending_pos is not None:
                margin = REBUFFER_MARGIN_S
                if (self._pending_pos >= buf_start + margin
                        and self._pending_pos <= buf_end - margin):
                    self._pending_pos = None

    def _extract_pcm(self, start_time, duration):
        """Decode a segment of audio to raw 16-bit mono PCM via headless MPV."""
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
                af=(
                    "aresample={sr},"
                    "aformat=sample_fmts=s16:channel_layouts=mono".format(sr=SAMPLE_RATE)
                ),
                start=str(start_time),
                end=str(start_time + duration),
                log_handler=lambda level, component, message: logger.debug(
                    "mpv [%s] %s: %s", level, component, message),
            )
            self._extract_player = player
            player.play(self._video_path)
            logger.debug("mpv ao=%s, audio-codec=%s, path=%s",
                         player.audio_out_params, player.audio_codec, self._video_path)
            player.wait_for_playback()
            player.terminate()
            self._extract_player = None

            with open(tmp_path, "rb") as fh:
                raw = fh.read()
            logger.debug("PCM temp file size: %d bytes", len(raw) if raw else 0)
            if not raw:
                return None

            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        except Exception as exc:
            self._extract_player = None
            if self._running:
                logger.warning("Spectrogram audio extraction failed: %s", exc)
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


#  SpectrogramWidget (QWidget)

class SpectrogramWidget(QWidget):
    """Custom-painted widget that displays a scrolling spectrogram centred on
    the current playback position.

    The heavy lifting is done by :class:`SpectrogramWorker`; this widget only
    blits a cached QImage and draws the centre playhead line.
    """

    def __init__(self, parent=None, annotator=None):
        super().__init__(parent)
        self._annotator = annotator
        self._worker = None

        # Rendering state
        self._cached_image = None     # QImage from the worker
        self._buffer_start = 0.0      # time range the image covers
        self._buffer_end = 0.0
        self._current_pos = 0.0       # playhead position in seconds

        # Settings (mirrored to the worker when it is created)
        self._window_duration = 10.0
        self._buffer_margin = 10.0
        self._freq_low = 0
        self._freq_high = 15000
        self._colormap_name = "viridis"
        self._opacity = 0.8

        self._update_in_flight = False   # True while the worker is processing

        # UI state
        self._placeholder_text = None
        self._video_path = None
        self._active = False          # True while a video is loaded and
                                      # the widget is logically enabled

        # Timer that checks whether the buffer needs refreshing
        self._buffer_timer = QTimer(self)
        self._buffer_timer.setInterval(BUFFER_CHECK_MS)
        self._buffer_timer.timeout.connect(self._check_buffer)

        # Hover label (created lazily)
        self._hover_label = None
        self.setMouseTracking(True)

        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(0, 0, 0))
        self.setPalette(pal)

    # public API (called from video_annotator)

    def start_spectrogram(self, video_path):
        """Begin spectrogram processing for *video_path*."""
        self.stop_spectrogram()
        self._video_path = video_path
        self._active = True
        self._placeholder_text = "Computing Spectrogram..."
        self._cached_image = None
        self._update_in_flight = False
        self.update()

        self._worker = SpectrogramWorker(video_path)
        self._worker.update_settings(
            window_duration=self._window_duration,
            buffer_margin=self._buffer_margin,
            freq_low=self._freq_low,
            freq_high=self._freq_high,
            colormap_name=self._colormap_name,
        )
        self._worker.result_ready.connect(self._on_result)
        self._worker.start()
        self._buffer_timer.start()
        self._update_in_flight = True
        if sys.platform == "darwin":
            half = self._window_duration / 2.0
            buf_start = max(0.0, self._current_pos - half - self._buffer_margin)
            extract_dur = self._window_duration + 2 * self._buffer_margin
            self._start_extract_for_worker(buf_start, extract_dur)
        else:
            self._worker.request_update(self._current_pos)

    def stop_spectrogram(self):
        """Halt processing and release resources."""
        self._buffer_timer.stop()
        if hasattr(self, '_spec_poll_timer') and self._spec_poll_timer is not None:
            self._spec_poll_timer.stop()
        self._cleanup_spec_player()
        self._active = False
        if self._worker is not None:
            try:
                self._worker.result_ready.disconnect(self._on_result)
            except (RuntimeError, TypeError):
                pass
            self._worker.stop()
            self._worker = None
        self._cached_image = None
        self._placeholder_text = None
        self.update()

    def _start_extract_for_worker(self, buf_start, extract_dur):
        """Start non-blocking MPV audio extraction on the main thread (macOS)."""
        import mpv

        if hasattr(self, '_spec_extract_player') and self._spec_extract_player is not None:
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".pcm", delete=False)
        self._spec_tmp_path = tmp.name
        tmp.close()
        self._spec_extract_start = buf_start
        self._spec_extract_dur = extract_dur

        try:
            locale.setlocale(locale.LC_NUMERIC, "C")
            player = mpv.MPV(
                vid="no",
                untimed=True,
                ao="pcm",
                ao_pcm_waveheader="no",
                ao_pcm_file=self._spec_tmp_path,
                af=(
                    "aresample={sr},"
                    "aformat=sample_fmts=s16:channel_layouts=mono".format(sr=SAMPLE_RATE)
                ),
                start=str(buf_start),
                end=str(buf_start + extract_dur),
                log_handler=lambda level, component, message: logger.debug(
                    "mpv [%s] %s: %s", level, component, message),
            )
            self._spec_extract_player = player
            player.play(self._video_path)
            logger.debug("mpv ao=%s, audio-codec=%s, path=%s",
                         player.audio_out_params, player.audio_codec, self._video_path)

            if not hasattr(self, '_spec_poll_timer') or self._spec_poll_timer is None:
                self._spec_poll_timer = QTimer(self)
                self._spec_poll_timer.setInterval(50)
                self._spec_poll_timer.timeout.connect(self._poll_spec_extraction)
            self._spec_poll_timer.start()
            logger.debug("Spectrogram: started non-blocking extraction %.1f-%.1f (macOS)",
                         buf_start, buf_start + extract_dur)
        except Exception as exc:
            logger.warning("Spectrogram: MPV extraction failed to start: %s", exc)
            self._cleanup_spec_player()
            self._update_in_flight = False

    def _poll_spec_extraction(self):
        """Poll spectrogram MPV extraction (macOS only)."""
        try:
            if self._spec_extract_player is None:
                self._spec_poll_timer.stop()
                self._update_in_flight = False
                return
            if self._spec_extract_player.core_idle:
                self._spec_poll_timer.stop()
                import os as _os
                tmp_size = _os.path.getsize(self._spec_tmp_path) if _os.path.exists(self._spec_tmp_path) else 0
                logger.debug("Extraction done, temp file size: %d bytes", tmp_size)
                logger.debug("Spectrogram: extraction complete (macOS)")
                buf_start = self._spec_extract_start

                try:
                    with open(self._spec_tmp_path, "rb") as fh:
                        raw = fh.read()
                    if raw:
                        samples = np.frombuffer(raw, dtype=np.int16).astype(
                            np.float32) / 32768.0
                    else:
                        samples = None
                except OSError:
                    samples = None

                self._cleanup_spec_player()

                if samples is not None and self._worker is not None:
                    actual_dur = samples.size / SAMPLE_RATE
                    with QMutexLocker(self._worker._mutex):
                        self._worker._preloaded_samples = samples
                        self._worker._preloaded_buf_start = buf_start
                        self._worker._preloaded_buf_end = buf_start + actual_dur
                    self._worker.request_update(self._current_pos)
                else:
                    self._update_in_flight = False
        except Exception as exc:
            logger.warning("Spectrogram: poll error: %s", exc)
            self._spec_poll_timer.stop()
            self._cleanup_spec_player()
            self._update_in_flight = False

    def _cleanup_spec_player(self):
        """Clean up temporary MPV instance and temp file (macOS)."""
        if hasattr(self, '_spec_extract_player') and self._spec_extract_player is not None:
            try:
                self._spec_extract_player.terminate()
            except Exception:
                pass
            self._spec_extract_player = None
        if hasattr(self, '_spec_tmp_path') and self._spec_tmp_path:
            try:
                os.unlink(self._spec_tmp_path)
            except OSError:
                pass
            self._spec_tmp_path = None

    def reset(self):
        """Full reset when loading a new video."""
        self.stop_spectrogram()
        self._current_pos = 0.0

    def set_position(self, seconds):
        """Update the playhead position.  Called from the annotator's
        time-position handler at up to ~30 fps."""
        self._current_pos = seconds
        self.update()

    def set_playback_speed(self, speed):
        """Enable or disable the spectrogram based on playback speed."""
        if abs(speed) > MAX_PLAYBACK_SPEED:
            if self._active and self._worker is not None:
                self._buffer_timer.stop()
                self._placeholder_text = (
                    f"Spectrogram paused (speed > {MAX_PLAYBACK_SPEED:.0f}x)"
                )
                self.update()
        else:
            if self._active and self._worker is not None:
                self._buffer_timer.start()
                if self._cached_image is None:
                    self._placeholder_text = "Computing Spectrogram..."
                else:
                    self._placeholder_text = None
                self.update()

    # settings

    def set_opacity(self, value):
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def set_colormap(self, name):
        if name in COLORMAPS:
            self._colormap_name = name
            if self._worker:
                self._worker.update_settings(colormap_name=name)
                self._force_refresh()

    def set_freq_range(self, low, high):
        self._freq_low = max(0, int(low))
        self._freq_high = min(SAMPLE_RATE // 2, int(high))
        if self._worker:
            self._worker.update_settings(
                freq_low=self._freq_low,
                freq_high=self._freq_high,
            )
            self._force_refresh()

    def set_window_duration(self, seconds):
        self._window_duration = max(2.0, min(30.0, float(seconds)))
        margin = self._window_duration
        self._buffer_margin = margin
        if self._worker:
            self._worker.update_settings(
                window_duration=self._window_duration,
                buffer_margin=margin,
            )
            self._force_refresh()

    # internal slots

    def _on_result(self, image, buf_start, buf_end):
        self._cached_image = image
        self._buffer_start = buf_start
        self._buffer_end = buf_end
        self._placeholder_text = None
        self._update_in_flight = False
        self.update()

    def _check_buffer(self):
        """Periodically verify whether the playhead is approaching the
        edge of the buffered region and request a fresh buffer if so."""
        if self._worker is None:
            return
        # Don't spam requests while the worker is busy
        if self._update_in_flight:
            return
        if self._cached_image is None:
            # No image yet request once and wait
            self._update_in_flight = True
            if sys.platform == "darwin":
                half = self._window_duration / 2.0
                buf_start = max(0.0, self._current_pos - half - self._buffer_margin)
                extract_dur = self._window_duration + 2 * self._buffer_margin
                self._start_extract_for_worker(buf_start, extract_dur)
            else:
                self._worker.request_update(self._current_pos)
            return
        # Check if playhead is approaching the buffer edge
        if (self._current_pos < self._buffer_start + REBUFFER_MARGIN_S
                or self._current_pos > self._buffer_end - REBUFFER_MARGIN_S):
            self._update_in_flight = True
            if sys.platform == "darwin":
                half = self._window_duration / 2.0
                buf_start = max(0.0, self._current_pos - half - self._buffer_margin)
                extract_dur = self._window_duration + 2 * self._buffer_margin
                self._start_extract_for_worker(buf_start, extract_dur)
            else:
                self._worker.request_update(self._current_pos)

    def _force_refresh(self):
        """Discard the cached image and request an immediate recompute."""
        self._cached_image = None
        self._placeholder_text = "Computing Spectrogram..."
        self._update_in_flight = True
        self.update()
        if self._worker:
            if sys.platform == "darwin":
                half = self._window_duration / 2.0
                buf_start = max(0.0, self._current_pos - half - self._buffer_margin)
                extract_dur = self._window_duration + 2 * self._buffer_margin
                self._start_extract_for_worker(buf_start, extract_dur)
            else:
                self._worker.request_update(self._current_pos)

    # painting

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, theme.qcolor("progress_bg"))

        if self._cached_image is not None and not self._cached_image.isNull():
            self._paint_spectrogram(painter, w, h)
        elif self._placeholder_text:
            painter.setPen(theme.qcolor("progress_text"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                self._placeholder_text,
            )

        # Centre playhead line
        painter.setPen(QPen(theme.qcolor("progress_text"), 2))
        center_x = w // 2
        painter.drawLine(center_x, 0, center_x, h)

        painter.end()

    def _paint_spectrogram(self, painter, w, h):
        buf_dur = self._buffer_end - self._buffer_start
        if buf_dur <= 0:
            return

        half_win = self._window_duration / 2.0
        view_start = self._current_pos - half_win
        view_end = self._current_pos + half_win
        img_w = self._cached_image.width()
        img_h = self._cached_image.height()

        # Source rect: portion of the QImage corresponding to the view window
        src_x0 = (view_start - self._buffer_start) / buf_dur * img_w
        src_x1 = (view_end - self._buffer_start) / buf_dur * img_w

        # Destination rect: default is the full widget
        dst_x0 = 0.0
        dst_x1 = float(w)

        # Handle edges: if the view extends beyond the buffer, shrink both
        # the source and destination rectangles proportionally so that the
        # spectrogram stays time-aligned and any out-of-range area is black.
        if src_x0 < 0:
            # View starts before the buffer shift destination right
            overshoot_frac = -src_x0 / (src_x1 - src_x0)
            dst_x0 = overshoot_frac * w
            src_x0 = 0.0

        if src_x1 > img_w:
            # View ends after the buffer shrink destination on the right
            overshoot_frac = (src_x1 - img_w) / (src_x1 - src_x0)
            dst_x1 = w - overshoot_frac * w
            src_x1 = float(img_w)

        src_rect = QRectF(src_x0, 0, src_x1 - src_x0, img_h)
        dst_rect = QRectF(dst_x0, 0, dst_x1 - dst_x0, h)

        painter.setOpacity(self._opacity)
        painter.drawImage(dst_rect, self._cached_image, src_rect)
        painter.setOpacity(1.0)

    # mouse interaction: click-to-seek

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._annotator is None:
            return
        secs = self._x_to_time(event.position().x())
        if secs is not None and hasattr(self._annotator, "player"):
            self._annotator.player.seek(secs, "absolute", "exact")

    # mouse interaction: hover timestamp

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
        secs = self._x_to_time(event.position().x())
        if secs is None:
            if self._hover_label is not None:
                self._hover_label.hide()
            return

        self._ensure_hover_label()
        self._hover_label.setText(_format_hover_time(secs))
        self._hover_label.adjustSize()

        hover_x = event.position().x()
        global_pos = self.mapToGlobal(QPoint(int(hover_x), 0))
        bar_left = self.mapToGlobal(QPoint(0, 0)).x()
        lw = self._hover_label.width()
        lh = self._hover_label.height()
        lx = max(bar_left, min(global_pos.x() - lw // 2,
                               bar_left + self.width() - lw))
        ly = global_pos.y() - lh - 2
        self._hover_label.move(lx, ly)
        self._hover_label.show()

    def leaveEvent(self, event):
        if self._hover_label is not None:
            self._hover_label.hide()

    # helpers-

    def _x_to_time(self, x):
        """Map a widget X coordinate to a time in seconds."""
        if self.width() <= 0:
            return None
        half_win = self._window_duration / 2.0
        ratio = x / self.width()
        return self._current_pos - half_win + ratio * self._window_duration


#  Utility

def _format_hover_time(secs):
    secs = max(0, int(secs))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
