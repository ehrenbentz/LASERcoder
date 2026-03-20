# debug_logger.py

import os
import sys
import logging
import shutil
import tempfile
from datetime import datetime


class FlushFileHandler(logging.FileHandler):
    """FileHandler that flushes after every emit for crash resilience"""

    def emit(self, record):
        super().emit(record)
        self.flush()


class TeeStream:
    """Redirect a stream (stdout/stderr) to both the original and a logger"""

    def __init__(self, original, logger, level=logging.INFO):
        self._original = original
        self._logger = logger
        self._level = level

    def write(self, text):
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        if text and text.strip():
            try:
                self._logger.log(self._level, text.rstrip())
            except Exception:
                pass

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise OSError("no fileno")

    def isatty(self):
        return False


class DebugLogger:
    """Singleton logger with two-phase file output"""

    def __init__(self, debug_mode):
        self._debug_mode = debug_mode
        self._logger = logging.getLogger("LaserTAG")
        self._logger.setLevel(logging.DEBUG if debug_mode else logging.WARNING)
        self._logger.propagate = False
        self._handler = None
        self._temp_log_path = None
        self._final_log_path = None
        self._switched = False

        if not debug_mode:
            self._logger.addHandler(logging.NullHandler())
            return

        # Phase 1: log to temp dir
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._log_filename = f"debug_{ts}.log"
        temp_dir = os.path.join(tempfile.gettempdir(), "LaserTAG_Debug")
        os.makedirs(temp_dir, exist_ok=True)
        self._temp_log_path = os.path.join(temp_dir, self._log_filename)

        fmt = logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(levelname)s] %(module)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self._handler = FlushFileHandler(self._temp_log_path, encoding="utf-8")
        self._handler.setFormatter(fmt)
        self._logger.addHandler(self._handler)

        # Redirect stdout/stderr
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = TeeStream(sys.stdout, self._logger, logging.INFO)
        sys.stderr = TeeStream(sys.stderr, self._logger, logging.ERROR)

        # Unhandled exception hook
        self._orig_excepthook = sys.excepthook
        sys.excepthook = self._excepthook

        self._logger.info("=== LaserTAG debug logging started ===")

    def _excepthook(self, exc_type, exc_value, exc_tb):
        import traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        self._logger.critical("Unhandled exception:\n" + "".join(tb_lines))
        if self._orig_excepthook:
            self._orig_excepthook(exc_type, exc_value, exc_tb)

    def switch_to_output_dir(self, output_dir):
        """Phase 2: copy temp log to output_dir/Debug/ and switch handler"""
        if not self._debug_mode or self._switched:
            return
        self._switched = True

        debug_dir = os.path.join(output_dir, "Debug")
        try:
            os.makedirs(debug_dir, exist_ok=True)
        except OSError:
            return

        self._final_log_path = os.path.join(debug_dir, self._log_filename)

        # Flush and close temp handler, copy contents, open new handler
        if self._handler:
            self._handler.flush()
            self._handler.close()
            self._logger.removeHandler(self._handler)

        try:
            if self._temp_log_path and os.path.exists(self._temp_log_path):
                shutil.copy2(self._temp_log_path, self._final_log_path)
        except OSError:
            pass

        fmt = logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(levelname)s] %(module)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        self._handler = FlushFileHandler(
            self._final_log_path, mode="a", encoding="utf-8")
        self._handler.setFormatter(fmt)
        self._logger.addHandler(self._handler)
        self._logger.info(
            "Switched log output to %s", self._final_log_path)

    # Proxy common logging methods
    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._logger.exception(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)


_instance = None


def init_logging(debug_mode=False):
    """Call once at startup"""
    global _instance
    if _instance is None:
        _instance = DebugLogger(debug_mode)
    return _instance


def get_logger():
    """Return the logger"""
    global _instance
    if _instance is None:
        _instance = DebugLogger(False)
    return _instance
