# help_dialog.py
#
# The "?" help window: a short, tabbed version of the README.
#
# Opened from the start dialog and from the annotator (button or F1).
# The Getting Started, Annotating and Files and Analysis tabs show the
# Markdown files in src/help/ (see src/help/README.txt), so the text can
# be edited without touching code.  The Keyboard Shortcuts tab is built
# here from the current settings, and from the annotator it also lists
# the event and subject keys loaded for the open video, so it always
# matches what the keys actually do.

import os
import sys
from html import escape

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QTabWidget, QTextBrowser, QPushButton,
                               QLabel)
from PySide6.QtCore import Qt

import theme
from config_manager import get_config
from display_utils import get_screen_geometry

GITHUB_URL = "https://github.com/ehrenbentz/LASERcoder"

# Markdown file shown in each text tab (in the help/ folder)
_HELP_FILES = {
    "start": "getting_started.md",
    "annotating": "annotating.md",
    "files": "files_and_analysis.md",
}

# Tab order; the start dialog opens on "start", the annotator on "keys"
TAB_START = "start"
TAB_KEYS = "keys"
TAB_ANNOTATING = "annotating"
TAB_FILES = "files"

_IS_MAC = sys.platform == "darwin"


# Formatting helpers

def _key(text):
    """A key name shown as a key cap."""
    return (f'<span style="font-family: monospace; '
            f'background-color: {theme.color("input_bg")}; '
            f'color: {theme.color("text")};">&nbsp;{escape(text)}&nbsp;</span>')


def _keys(*names):
    return " or ".join(_key(n) for n in names)


def _table(headers, rows):
    """A table with a header row.  *rows* hold ready-made HTML cells."""
    border = theme.color("border_light")
    head_bg = theme.color("tree_header_bg")
    html = [f'<table width="100%" cellspacing="0" cellpadding="5" '
            f'border="1" style="border-color: {border}; '
            f'border-style: solid; border-collapse: collapse;">',
            "<tr>"]
    for h in headers:
        html.append(f'<th align="left" style="background-color: '
                    f'{head_bg};">{escape(h)}</th>')
    html.append("</tr>")
    for row in rows:
        html.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    html.append("</table>")
    return "".join(html)


def _page(body):
    text = theme.color("text")
    muted = theme.color("text_secondary")
    link = theme.color("accent")
    return (f'<html><head><style>'
            f'body {{ color: {text}; }}'
            f'h2 {{ margin-top: 14px; margin-bottom: 4px; }}'
            f'h3 {{ margin-top: 12px; margin-bottom: 2px; }}'
            f'p, li {{ margin-top: 3px; margin-bottom: 3px; }}'
            f'.muted {{ color: {muted}; }}'
            f'a {{ color: {link}; }}'
            f'</style></head><body>{body}</body></html>')


def _fmt_seconds(value):
    value = float(value)
    return f"{value:g} s"


# Tab content

def _help_dir_candidates():
    """Folders that may hold the help/ files: next to this module when
    run from source, next to the executable in a compiled build."""
    seen = []
    for base in (os.path.dirname(os.path.abspath(__file__)),
                 os.path.dirname(os.path.abspath(sys.executable)),
                 os.path.dirname(os.path.abspath(sys.argv[0] or "."))):
        folder = os.path.join(base, "help")
        if folder not in seen:
            seen.append(folder)
    return seen


def _load_help_markdown(tab):
    """Text of the Markdown file for *tab*, with placeholders filled
    in, or a short notice if the file cannot be found."""
    name = _HELP_FILES[tab]
    for folder in _help_dir_candidates():
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        return text.replace("{MOD}", "Cmd" if _IS_MAC else "Ctrl")
    return (f"## Help text not found\n\nThe file `help/{name}` is missing "
            f"from this installation. The full documentation is at "
            f"<{GITHUB_URL}>.")


def _shortcuts_html(annotator=None):
    cfg = get_config()
    small = _fmt_seconds(cfg.get_small_skip_seconds())
    large = _fmt_seconds(cfg.get_large_skip_seconds())
    wasd = cfg.get_wasd_navigation()
    number_speed = cfg.get_number_key_speed()
    mod = "Cmd" if _IS_MAC else "Ctrl"

    def nav(arrow, letter):
        return _keys(arrow, letter) if wasd else _key(arrow)

    rows = [
        ["Play / pause", _key("Space")],
        [f"Skip forward / back {large}",
         f"{nav('→', 'D')} / {nav('←', 'A')}"],
        [f"Skip forward / back {small}",
         f"{nav('Shift+→', 'Shift+D')} / {nav('Shift+←', 'Shift+A')}"],
    ]
    if wasd:
        rows.append(["Skip forward / back 10 s",
                     f"{_key('W')} / {_key('S')}"])
    rows += [
        ["Step one frame forward / back", f"{_key('.')} / {_key(',')}"],
        ["Faster / slower", f"{_key('+')} / {_key('-')}"],
        ["Reset speed to 1x", _key("Backspace")],
    ]
    if number_speed:
        rows.append(["Set speed 1x to 9x / 10x",
                     f"{_key('1')} to {_key('9')} / {_key('0')}"])
    rows += [
        ["Move through the annotation list", f"{_key('↑')} / {_key('↓')}"],
        ["Delete the selected annotation", _key("Delete")],
        ["Undo the last delete", _key(f"{mod}+Z")],
        ["Fullscreen / window", _keys("F11", f"{mod}+Shift+W")],
        ["This help", _key("F1")],
        ["Close the video and return to the file list", _key("Escape")],
    ]

    notes = [
        f"Skip intervals are set in the settings menu (gear) under "
        f"<b>Audio and Video Settings</b>.",
        ("The W, A, S, D navigation keys are on. Turn them off in the "
         "event key editor to use those letters for events."
         if wasd else
         "The W, A, S, D navigation keys are off; they can be turned on "
         "in the event key editor."),
        ("The number keys set the playback speed (gear menu: <b>Number "
         "Keys Set Speed</b>)."
         if number_speed else
         "The number keys can be set to choose the playback speed (gear "
         "menu: <b>Number Keys Set Speed</b>)."),
        "Shortcuts do nothing while a dialog is open.",
    ]

    body = ["<h2>Video controls</h2>",
            _table(["Action", "Key"], rows),
            "<ul>" + "".join(f'<li class="muted">{n}</li>' for n in notes)
            + "</ul>"]

    body.append("<h2>Mouse</h2>")
    body.append(_table(["Action", "How"], [
        ["Jump to a time", "Click the progress bar, audio track, or "
                           "spectrogram"],
        ["Zoom into the video", "Turn on the zoom button (top right of "
                                "the video), then click the video; drag "
                                "to move around"],
        ["Annotation actions", "Right-click an annotation in the list"],
        ["Sort the annotation list", "Click a column header (click again "
                                     "to reverse, a third time to return "
                                     "to recording order)"],
    ]))

    if annotator is not None:
        body.append(_event_keys_html(annotator))
        body.append(_subject_keys_html(annotator))
    else:
        body.append('<p class="muted">The event and subject keys of the '
                    'open video are listed here when this help is opened '
                    'from the annotator.</p>')
    return _page("".join(body))


def _event_keys_html(annotator):
    store = getattr(annotator, "store", None)
    events = list(getattr(store, "events", []) or [])
    html = ["<h2>Event keys for this video</h2>"]
    if not events:
        html.append('<p class="muted">No event key is loaded.</p>')
        return "".join(html)
    rows = []
    for name, key, btype, me_group in events:
        key_cell = (_key(key.upper())
                    if key and not key.startswith("__nokey_")
                    else '<span class="muted">button only</span>')
        rows.append([escape(name), key_cell,
                     "State" if btype == "state" else "Point",
                     escape(me_group or "")])
    html.append(_table(["Event", "Key", "Type", "ME group"], rows))
    return "".join(html)


def _subject_keys_html(annotator):
    names = list(getattr(annotator, "subject_names", []) or [])
    html = ["<h2>Subject keys for this video</h2>"]
    if not names:
        html.append('<p class="muted">No subject key is loaded. Use the '
                    '<b>Subjects</b> button to create or load one.</p>')
        return "".join(html)
    key_for = {name: key for key, name in
               (getattr(annotator, "subject_key_map", {}) or {}).items()}
    groups = getattr(annotator, "subject_me_groups", {}) or {}
    rows = []
    for name in names:
        key = key_for.get(name)
        rows.append([escape(name),
                     _key(key.upper()) if key else
                     '<span class="muted">button only</span>',
                     escape(groups.get(name) or "")])
    html.append(_table(["Subject", "Key", "ME group"], rows))
    html.append('<p class="muted">Press a subject key to make that subject '
                'active or inactive. Subjects cannot be changed while a '
                'state annotation is open; end the state first.</p>')
    return "".join(html)


# Dialog

class HelpDialog(QDialog):
    """Tabbed help window.  Build with show_help_dialog()."""

    def __init__(self, parent, start_tab=TAB_START, annotator=None):
        super().__init__(parent)
        self.setWindowTitle("LASERcoder Help")
        theme.apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid "
            f"{theme.color('border_light')}; }}"
            f"QTabBar::tab {{ background: {theme.color('input_bg')};"
            f" color: {theme.color('text')}; padding: 6px 14px;"
            f" border: 1px solid {theme.color('border_light')};"
            f" border-bottom: none; }}"
            f"QTabBar::tab:selected {{ background: "
            f"{theme.color('button_hover')};"
            f" color: {theme.color('text_on_accent')}; }}"
            f"QTextBrowser {{ background-color: {theme.color('dialog_bg')};"
            f" color: {theme.color('text')}; border: none; }}")

        self._tab_index = {}
        for key, title in (
                (TAB_START, "Getting Started"),
                (TAB_KEYS, "Keyboard Shortcuts"),
                (TAB_ANNOTATING, "Annotating"),
                (TAB_FILES, "Files and Analysis")):
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            if key == TAB_KEYS:
                browser.setHtml(_shortcuts_html(annotator))
            else:
                browser.setMarkdown(_load_help_markdown(key))
            self._tab_index[key] = self._tabs.addTab(browser, title)
        self._tabs.setCurrentIndex(self._tab_index.get(start_tab, 0))
        layout.addWidget(self._tabs, 1)

        bottom = QHBoxLayout()
        hint = QLabel("Press F1 to open this help at any time.")
        hint.setStyleSheet(f"color: {theme.color('text_secondary')};"
                           " background: transparent;")
        bottom.addWidget(hint)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setAutoDefault(False)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        screen = get_screen_geometry()
        self.resize(int(screen["width"] * 0.5), int(screen["height"] * 0.75))
        self.setMinimumSize(520, 420)


def show_help_dialog(parent, start_tab=TAB_START, annotator=None,
                     on_closed=None):
    """Open the help window over *parent* (window-modal, non-blocking).

    *annotator*: the VideoAnnotator, to list the keys of the open video.
    *on_closed*: called with no arguments when the window closes.
    """
    dlg = HelpDialog(parent, start_tab=start_tab, annotator=annotator)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if on_closed is not None:
        dlg.finished.connect(lambda _result: on_closed())
    dlg.open()
    return dlg
