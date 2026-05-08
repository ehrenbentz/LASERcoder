import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QGridLayout, QDialogButtonBox, QMessageBox, QWidget,
    QRadioButton, QSlider, QFrame, QColorDialog, QApplication,
    QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from annotation_store import format_time_human, parse_time
from config_manager import get_config
from debug_logger import get_logger
import theme

logger = get_logger()


class _NoScrollSlider(QSlider):
    """QSlider that ignores wheel events so scrolling propagates to the parent."""

    def wheelEvent(self, event):
        event.ignore()


class _NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class _NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class _NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


def _make_reset_button(callback):
    """Compact per-value reset button showing the ↺ glyph."""
    btn = QPushButton("\u21BA")
    btn.setFixedSize(22, 22)
    btn.setStyleSheet("QPushButton { padding: 0px; }")
    btn.setToolTip("Reset to default")
    btn.clicked.connect(callback)
    return btn


def _apply_dialog_theme(dialog):
    theme.apply_dialog_theme(dialog)


def _cleanup_dialog(dlg, annotator):
    """Clean up after a dialog closes"""
    logger.debug("Dialog cleanup: %s", dlg.windowTitle())
    dlg.deleteLater()


# Coding-start / duration dialog

def show_coding_start_dialog(annotator):
    """Present the "Set Coding Start and Duration" dialog"""
    was_playing = False
    if hasattr(annotator, "player") and annotator.player:
        was_playing = not annotator.player.pause
        annotator.player.pause = True

    annotator.dialog_open = True
    logger.info("Opening coding start dialog")

    dialog = QDialog(annotator.parent)
    dialog.setWindowTitle("Set Coding Start and Duration")
    _apply_dialog_theme(dialog)
    dialog.resize(400, 300)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(10)

    # Current position
    current_time = annotator.player.time_pos or 0
    formatted = format_time_human(current_time)

    cur_group = QGroupBox("Current Position")
    cur_layout = QVBoxLayout(cur_group)
    cur_layout.addWidget(QLabel(f"Current Time: {formatted}"))
    layout.addWidget(cur_group)

    # Method selection
    method_group = QGroupBox("Coding Method")
    method_layout = QVBoxLayout(method_group)
    duration_radio = QRadioButton("Set Start Time and Duration")
    end_time_radio = QRadioButton("Set Start Time and End Time")

    has_end = getattr(annotator, "coding_end", None) is not None
    has_dur = getattr(annotator, "coding_duration", None) is not None
    if has_end and not has_dur:
        end_time_radio.setChecked(True)
    else:
        duration_radio.setChecked(True)

    method_layout.addWidget(duration_radio)
    method_layout.addWidget(end_time_radio)
    layout.addWidget(method_group)

    # Coding parameters
    coding_group = QGroupBox("Coding Parameters")
    grid = QGridLayout(coding_group)
    grid.setColumnStretch(2, 1)

    # Row 0 — start time
    grid.addWidget(QLabel("Start Time:"), 0, 0, Qt.AlignmentFlag.AlignLeft)
    start_input = QLineEdit()
    if annotator.coding_start and annotator.coding_start > 0:
        start_input.setText(format_time_human(annotator.coding_start))
    grid.addWidget(start_input, 0, 1)

    use_cur_start = QPushButton("Use Current Position")
    use_cur_start.clicked.connect(lambda: start_input.setText(formatted))
    grid.addWidget(use_cur_start, 0, 2)

    # Row 1 — duration inputs (duration mode)
    dur_label = QLabel("Duration:")
    grid.addWidget(dur_label, 1, 0, Qt.AlignmentFlag.AlignLeft)

    dur_widget = QWidget()
    dur_lay = QHBoxLayout(dur_widget)
    dur_lay.setContentsMargins(0, 0, 0, 0)
    hours_in = QLineEdit(); hours_in.setFixedWidth(40); hours_in.setPlaceholderText("HH")
    mins_in  = QLineEdit(); mins_in.setFixedWidth(40);  mins_in.setPlaceholderText("MM")
    secs_in  = QLineEdit(); secs_in.setFixedWidth(40);  secs_in.setPlaceholderText("SS")

    if annotator.coding_duration is not None and annotator.coding_duration > 0:
        total = int(annotator.coding_duration)
        hours_in.setText(str(total // 3600))
        mins_in.setText(str((total % 3600) // 60))
        secs_in.setText(str(total % 60))

    for lbl, inp in [("Hours:", hours_in), ("Minutes:", mins_in), ("Seconds:", secs_in)]:
        dur_lay.addWidget(QLabel(lbl)); dur_lay.addWidget(inp)
    dur_lay.addStretch()
    grid.addWidget(dur_widget, 1, 1, 1, 2)

    # Row 2 — calculated end (duration mode)
    dur_end_label = QLabel("End Time:")
    grid.addWidget(dur_end_label, 2, 0, Qt.AlignmentFlag.AlignLeft)
    dur_end_value = QLabel("Not set")
    if annotator.coding_start is not None and annotator.coding_duration is not None:
        dur_end_value.setText(format_time_human(annotator.coding_start + annotator.coding_duration))
    grid.addWidget(dur_end_value, 2, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)

    # Row 3 — end-time input (end-time mode)
    et_label = QLabel("End Time:")
    grid.addWidget(et_label, 3, 0, Qt.AlignmentFlag.AlignLeft)
    et_input = QLineEdit()
    if getattr(annotator, "coding_end", None) and annotator.coding_end > 0:
        et_input.setText(format_time_human(annotator.coding_end))
    grid.addWidget(et_input, 3, 1)

    use_cur_end = QPushButton("Use Current Position")
    use_cur_end.clicked.connect(lambda: et_input.setText(formatted))
    grid.addWidget(use_cur_end, 3, 2)

    # Row 4 — calculated duration (end-time mode)
    et_dur_label = QLabel("Duration:")
    grid.addWidget(et_dur_label, 4, 0, Qt.AlignmentFlag.AlignLeft)
    et_dur_value = QLabel("Not set")
    grid.addWidget(et_dur_value, 4, 1, 1, 2, Qt.AlignmentFlag.AlignLeft)

    # Row 5 — clear button
    clear_btn = QPushButton("Clear")

    def _clear():
        start_input.clear(); hours_in.clear(); mins_in.clear(); secs_in.clear()
        et_input.clear(); dur_end_value.setText("Not set"); et_dur_value.setText("Not set")
        annotator.coding_start = 0
        annotator.coding_duration = None
        annotator.coding_end = None
        annotator.limit_timeline_to_coding = False
        limit_cb.setChecked(False)
        annotator.update_coding_info_display()

    clear_btn.clicked.connect(_clear)

    layout.addWidget(coding_group)

    # Timeline limiting checkbox
    from PySide6.QtWidgets import QCheckBox
    limit_cb = QCheckBox("Show only coding segment in timeline")
    limit_cb.setChecked(getattr(annotator, 'limit_timeline_to_coding', False))
    limit_cb.setToolTip(
        "When checked, the progress bar and audio track show only the\n"
        "coding segment instead of the full video.")
    layout.addWidget(limit_cb)

    # Visibility toggle
    def _update_vis():
        is_dur = duration_radio.isChecked()
        for w in (dur_label, dur_widget, dur_end_label, dur_end_value):
            w.setVisible(is_dur)
        for w in (et_label, et_input, use_cur_end, et_dur_label, et_dur_value):
            w.setVisible(not is_dur)

    duration_radio.toggled.connect(_update_vis)
    _update_vis()

    # Live calculation
    def _calc():
        try:
            st = parse_time(start_input.text().strip()) if start_input.text().strip() else 0
            if duration_radio.isChecked():
                h = int(hours_in.text() or 0)
                m = int(mins_in.text() or 0)
                s = int(secs_in.text() or 0)
                if h or m or s:
                    dur_end_value.setText(format_time_human(st + h * 3600 + m * 60 + s))
                else:
                    dur_end_value.setText("Not set")
            else:
                ets = et_input.text().strip()
                if ets and start_input.text().strip():
                    et = parse_time(ets)
                    if et > st:
                        d = et - st
                        et_dur_value.setText(
                            f"{d // 3600:.0f}h {(d % 3600) // 60:.0f}m {d % 60:.0f}s")
                    else:
                        et_dur_value.setText("Invalid (end <= start)")
                else:
                    et_dur_value.setText("Not set")
        except (ValueError, Exception):
            pass

    for w in (start_input, hours_in, mins_in, secs_in, et_input):
        w.textChanged.connect(_calc)

    # Buttons
    bbox = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save
        | QDialogButtonBox.StandardButton.Cancel)
    bbox.button(QDialogButtonBox.StandardButton.Cancel).setText("Close")

    def _save():
        try:
            annotator.coding_start = (
                parse_time(start_input.text().strip())
                if start_input.text().strip() else 0)

            if duration_radio.isChecked():
                h = int(hours_in.text() or 0)
                m = int(mins_in.text() or 0)
                s = int(secs_in.text() or 0)
                if h or m or s:
                    annotator.coding_duration = h * 3600 + m * 60 + s
                    annotator.coding_end = annotator.coding_start + annotator.coding_duration
                else:
                    annotator.coding_duration = None
                    annotator.coding_end = None
            else:
                ets = et_input.text().strip()
                if ets:
                    annotator.coding_end = parse_time(ets)
                    if annotator.coding_end > annotator.coding_start:
                        annotator.coding_duration = annotator.coding_end - annotator.coding_start
                    else:
                        raise ValueError("End time must be greater than start time")
                else:
                    annotator.coding_end = None
                    annotator.coding_duration = None

            annotator.coding_end_reached = False

            # Set timeline limiting flag
            if annotator.coding_end is not None and annotator.coding_duration is not None:
                annotator.limit_timeline_to_coding = limit_cb.isChecked()
            else:
                annotator.limit_timeline_to_coding = False

            annotator.update_coding_info_display()

            if annotator.coding_start > 0:
                annotator.player.time_pos = annotator.coding_start

            annotator.update_progress()
            annotator.save_session_state()
            dialog.accept()
        except ValueError as exc:
            show_message(dialog, "Invalid Input",
                               f"Please check your input values: {exc}")

    bbox.accepted.connect(_save)
    bbox.rejected.connect(dialog.reject)

    btn_row = QHBoxLayout()
    btn_row.addWidget(clear_btn)
    btn_row.addStretch()
    btn_row.addWidget(bbox)
    layout.addLayout(btn_row)

    def _on_finished(_result):
        annotator.dialog_open = False
        dialog.deleteLater()
        if hasattr(annotator, "player") and annotator.player and was_playing:
            annotator.player.pause = False

    dialog.finished.connect(_on_finished)
    dialog.open()



# Add-note dialog


def show_note_dialog(annotator):
    """Show dialog to add/edit a note on the selected annotation"""
    if not hasattr(annotator, "selected_treeview") or not annotator.selected_item:
        return

    if annotator.selected_treeview == annotator.state_annotations_tree:
        annotation = annotator.store.state_events[annotator.selected_index]
    else:
        annotation = annotator.store.point_events[annotator.selected_index]

    annotator.dialog_open = True

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Add Note")

    _apply_dialog_theme(dlg)
    dlg.resize(400, 300)

    layout = QVBoxLayout(dlg)

    info = f"Adding note to: {annotation['Event']}"
    if annotator.selected_treeview == annotator.state_annotations_tree:
        info += f" ({format_time_human(annotation['start_time'])})"
    else:
        info += f" ({annotation['time']})"
    layout.addWidget(QLabel(info))

    existing = annotation.get("Notes", "").replace(" . ", "\n")
    layout.addWidget(QLabel("Note:"))
    note_text = QTextEdit()
    note_text.setMinimumHeight(150)
    note_text.setText(existing)
    layout.addWidget(note_text)

    btn_frame = QWidget()
    btn_lay = QHBoxLayout(btn_frame)

    def _save():
        if not annotator.store.check_file_access():
            if hasattr(annotator, "player") and annotator.player:
                annotator.player.pause = True
            annotator.on_write_error()
            _close()
            return
        note = note_text.toPlainText().strip().replace("\n", " . ").replace("\r", " . ")
        original = annotation.get("Notes", "")
        annotation["Notes"] = note
        if not annotator.store.save_sorted_annotations():
            annotation["Notes"] = original
            _close()
            return
        _close()

    def _close():
        annotator.dialog_open = False
        dlg.accept()

    save_btn = QPushButton("Save")
    save_btn.clicked.connect(_save)
    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(_close)
    btn_lay.addStretch()
    btn_lay.addWidget(save_btn)
    btn_lay.addWidget(cancel_btn)
    layout.addWidget(btn_frame)

    def _on_finished(_result):
        annotator.dialog_open = False
        dlg.deleteLater()

    dlg.finished.connect(_on_finished)
    dlg.open()



# View annotation details


def show_annotation_details(annotator):
    """Display an editable details dialog for the selected annotation"""
    if not hasattr(annotator, "selected_treeview") or not annotator.selected_item:
        return

    if annotator.selected_treeview == annotator.state_annotations_tree:
        annotation = annotator.store.state_events[annotator.selected_index]
        atype = "State"
    else:
        annotation = annotator.store.point_events[annotator.selected_index]
        atype = "Point"

    annotator.dialog_open = True

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle(f"Annotation Details - {annotation['Event']}")
    _apply_dialog_theme(dlg)
    dlg.resize(500, 500)

    main_lay = QVBoxLayout(dlg)
    main_lay.setContentsMargins(15, 15, 15, 15)

    # Read-only info section (Event is editable via dropdown)
    info_w = QWidget()
    grid = QGridLayout(info_w)
    grid.setColumnStretch(1, 1)

    # Event selector: dropdown populated with events of matching type.
    # The user cannot type free text; only existing event names are valid.
    event_combo = QComboBox()
    event_combo.setEditable(False)
    matching_events = [
        name for name, key, btype, me_group in annotator.store.events
        if name and btype == atype.lower()]
    # Preserve the current annotation's event even if it is no longer
    # defined in the event key file, so the user can leave it unchanged.
    current_event = annotation["Event"]
    if current_event and current_event not in matching_events:
        matching_events.insert(0, current_event)
    event_combo.addItems(matching_events)
    event_combo.setCurrentText(current_event)

    event_lbl = QLabel("Event:")
    event_lbl.setStyleSheet("font-weight: bold;")
    grid.addWidget(event_lbl, 0, 0)
    grid.addWidget(event_combo, 0, 1)

    # Remaining read-only fields, starting at row 1
    remaining = [
        ("Type:", atype),
        ("Video:", annotator.store.video_name),
    ]
    if atype == "State":
        remaining.append(("Mutually Exclusive:",
                           annotation.get("Mutually_Exclusive", "False")))
    for row_idx, (lbl, val) in enumerate(remaining, start=1):
        l = QLabel(lbl); l.setStyleSheet("font-weight: bold;")
        grid.addWidget(l, row_idx, 0)
        grid.addWidget(QLabel(val), row_idx, 1)
    main_lay.addWidget(info_w)

    # Editable timestamp section
    form = QFormLayout()
    entries = {}
    if atype == "State":
        start_entry = QLineEdit()
        start_entry.setText(format_time_human(annotation["start_time"]))
        form.addRow("Start:", start_entry)
        entries["H_Start"] = start_entry

        end_entry = QLineEdit()
        if annotation["end_time"] is not None:
            end_entry.setText(format_time_human(annotation["end_time"]))
        form.addRow("End:", end_entry)
        entries["H_End"] = end_entry

        dur = (format_time_human(annotation["end_time"] - annotation["start_time"])
               if annotation["end_time"] is not None
               and annotation["start_time"] is not None
               else "NA")
        dur_label = QLabel(dur)
        form.addRow("Duration:", dur_label)
    else:
        time_entry = QLineEdit()
        time_entry.setText(annotation["time"])
        form.addRow("Time:", time_entry)
        entries["H_Start"] = time_entry
    main_lay.addLayout(form)

    # Separator
    sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    main_lay.addWidget(sep)

    # Notes section
    main_lay.addWidget(QLabel("Notes:"))
    notes_text = QTextEdit()
    notes_text.setMinimumHeight(120)
    notes_text.setText(annotation.get("Notes", "").replace(" . ", "\n"))
    main_lay.addWidget(notes_text)

    # Store originals for rollback
    originals = {"Event": annotation["Event"],
                 "Notes": annotation.get("Notes", "")}
    if atype == "State":
        originals["start_time"] = annotation["start_time"]
        originals["end_time"] = annotation["end_time"]
    else:
        originals["time"] = annotation["time"]

    # Buttons
    btn_f = QWidget()
    btn_l = QHBoxLayout(btn_f)

    def _save():
        if not annotator.store.check_file_access():
            annotator.on_write_error()
            return
        vals = {f: e.text().strip() for f, e in entries.items()}
        new_note = (notes_text.toPlainText().strip()
                    .replace("\n", " . ").replace("\r", " . "))
        new_event = event_combo.currentText().strip()

        if atype == "State":
            try:
                new_start = parse_time(vals["H_Start"])
            except ValueError:
                show_message(annotator.parent, "Invalid Time Format",
                             "Could not parse start time.")
                return

            # Allow empty H_End for annotations that remain open
            # (active state events).  Only parse if a value is present.
            if vals["H_End"]:
                try:
                    new_end = parse_time(vals["H_End"])
                except ValueError:
                    show_message(annotator.parent, "Invalid Time Format",
                                 "Could not parse end time.")
                    return
            else:
                new_end = None

            # If an active annotation's Event is being changed, the
            # hotkey-keyed active_state_events dict must follow the rename
            # so the new hotkey closes the annotation and the old hotkey
            # is freed to start a new state.
            active_rename = (
                annotation["end_time"] is None
                and new_end is None
                and new_event != annotation["Event"])

            if active_rename:
                name_to_key = {
                    v: k for k, v in annotator.store.state_event_keys.items()}
                old_key = name_to_key.get(annotation["Event"])
                new_key = name_to_key.get(new_event)
                if (new_key is not None
                        and new_key != old_key
                        and new_key in annotator.active_state_events):
                    show_message(
                        annotator.parent, "Active Event Conflict",
                        f"Cannot change to \"{new_event}\":\n"
                        "this event is already active on another "
                        "annotation.\n\n"
                        "End the other instance first.")
                    return
                if (old_key is not None
                        and old_key in annotator.active_state_events):
                    start_ts = annotator.active_state_events.pop(old_key)
                    if new_key is not None:
                        annotator.active_state_events[new_key] = start_ts

            if (annotation["Event"] != new_event
                    or annotation["start_time"] != new_start
                    or annotation["end_time"] != new_end):
                annotation["Manual_Edit"] = True
            annotation["Event"] = new_event
            annotation["start_time"] = new_start
            annotation["end_time"] = new_end
            annotation["Notes"] = new_note
        else:
            if (annotation["Event"] != new_event
                    or annotation["time"] != vals["H_Start"]):
                annotation["Manual_Edit"] = True
            annotation["Event"] = new_event
            annotation["time"] = vals["H_Start"]
            annotation["Notes"] = new_note

        if not annotator.store.save_sorted_annotations():
            annotation.update(originals)
            return

        annotator._update_annotations()
        # Event-tree highlight may have shifted if an active rename moved
        # the hotkey mapping in active_state_events.
        if atype == "State":
            annotator._populate_event_trees()
        annotator.dialog_open = False
        dlg.accept()

    def _cancel():
        annotator.dialog_open = False
        dlg.reject()

    save_btn = QPushButton("Save"); save_btn.clicked.connect(_save)
    cancel_btn = QPushButton("Cancel"); cancel_btn.clicked.connect(_cancel)
    btn_l.addStretch(); btn_l.addWidget(save_btn); btn_l.addWidget(cancel_btn)
    main_lay.addWidget(btn_f)

    def _on_finished(_result):
        annotator.dialog_open = False
        dlg.deleteLater()

    dlg.finished.connect(_on_finished)
    dlg.open()



# Simple edit dialogs (point / state)


def show_edit_point_dialog(annotator):
    """Edit a point annotation's name and time"""
    if annotator.store.active_state_events if hasattr(annotator.store, 'active_state_events') else annotator.active_state_events:
        show_message(annotator, "Active Annotation",
                           "Please end the active state before editing.")
        return
    if annotator.selected_index is None:
        return
    if not annotator.store.check_file_access():
        if hasattr(annotator, "player") and annotator.player:
            annotator.player.pause = True
        annotator.on_write_error()
        return

    annotator.dialog_open = True
    sel = annotator.store.point_events[annotator.selected_index]
    latest = annotator.load_annotation_data(sel, "Event", "H_Start")

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Edit Point Annotation")

    _apply_dialog_theme(dlg)
    dlg.resize(275, 250)

    layout = QVBoxLayout(dlg)

    cur_grp = QGroupBox("Current Annotation")
    cur_lay = QFormLayout()
    cur_lay.addRow("Event:", QLabel(latest["Event"]))
    cur_lay.addRow("Time:", QLabel(latest["H_Start"]))
    cur_grp.setLayout(cur_lay)
    layout.addWidget(cur_grp)

    new_grp = QGroupBox("New Annotation")
    new_lay = QFormLayout()
    entries = {}
    for field in ("Event", "H_Start"):
        e = QLineEdit(); e.setText(latest.get(field, ""))
        new_lay.addRow(field.replace("H_", "") + ":", e)
        entries[field] = e
    new_grp.setLayout(new_lay)
    layout.addWidget(new_grp)

    bbox = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    bbox.accepted.connect(
        lambda: annotator.save_point_annotation(entries, dlg, sel, latest["H_Start"]))
    bbox.rejected.connect(dlg.reject)
    layout.addWidget(bbox)

    def _on_finished(_result):
        annotator.dialog_open = False
        dlg.deleteLater()

    dlg.finished.connect(_on_finished)
    dlg.open()


def show_av_settings_dialog(annotator):
    """Show a combined audio & video settings dialog"""
    annotator.dialog_open = True
    VIDEO_PROPS = ("brightness", "contrast", "gamma", "saturation", "hue")

    # Snapshot current values for Cancel rollback
    vid_originals = {}
    for prop in VIDEO_PROPS:
        try:
            vid_originals[prop] = int(getattr(annotator.player, prop, 0) or 0)
        except Exception:
            vid_originals[prop] = 0

    import math

    def _read_pitch_semitones():
        """Derive current pitch semitones from the player's af property"""
        try:
            af_val = annotator.player.af
            graph = ""
            if isinstance(af_val, list):
                for entry in af_val:
                    p = entry.get("params", {}) if isinstance(entry, dict) else {}
                    graph = p.get("graph", "")
                    if "rubberband=pitch=" in graph:
                        break
            elif isinstance(af_val, str):
                graph = af_val
            if "rubberband=pitch=" in graph:
                factor = float(graph.split("rubberband=pitch=")[1].split("]")[0])
                return int(round(12 * math.log2(factor)))
        except Exception:
            pass
        return 0

    aud_originals = {
        "volume": int(annotator.player.volume or 100),
        "audio_delay": float(annotator.player.audio_delay or 0),
        "audio_pitch_correction": bool(
            getattr(annotator.player, "audio_pitch_correction", True)),
        "pitch_semitones": _read_pitch_semitones(),
    }

    cfg = get_config()
    per_video = annotator.store.load_video_settings()
    global_settings = cfg.get_video_settings()
    per_video_audio = annotator.store.load_audio_settings()
    global_audio = {
        "volume": cfg.get_volume(),
        "audio_delay": cfg.get_audio_delay(),
        "pitch_semitones": cfg.get_pitch_semitones(),
        "audio_pitch_correction": cfg.get_audio_pitch_correction(),
    }
    dr_original = cfg.get_waveform_dynamic_range()
    waveform_height_original = cfg.get_waveform_height_multiplier()
    spec_originals = {
        "colormap": cfg.get_spectrogram_colormap(),
        "freq_low": cfg.get_spectrogram_freq_low(),
        "freq_high": cfg.get_spectrogram_freq_high(),
        "window": cfg.get_spectrogram_window(),
        "height_multiplier": cfg.get_spectrogram_height_multiplier(),
    }

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Audio and Video Settings")
    _apply_dialog_theme(dlg)
    dlg.resize(500, 600)

    from PySide6.QtWidgets import QScrollArea
    outer_lay = QVBoxLayout(dlg)
    outer_lay.setContentsMargins(0, 0, 0, 10)
    outer_lay.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(15, 15, 15, 15)
    layout.setSpacing(8)
    scroll.setWidget(content)
    outer_lay.addWidget(scroll, 1)

    _slider_style = (
        "QSlider::groove:horizontal { background: #555; height: 6px;"
        "  border-radius: 3px; }"
        "QSlider::handle:horizontal { background: #ccc; width: 12px;"
        "  margin: -3px 0; border-radius: 6px; }"
        "QSlider::sub-page:horizontal { background: #888; border-radius: 3px; }"
    )

    # --- Video sliders ---
    vid_sliders = {}
    vid_labels = {}

    vid_group = QGroupBox("Video")
    vid_layout = QGridLayout(vid_group)
    vid_layout.setColumnStretch(1, 1)

    for row, prop in enumerate(VIDEO_PROPS):
        lbl = QLabel(prop.capitalize() + ":")
        vid_layout.addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignLeft)

        slider = _NoScrollSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(-100)
        slider.setMaximum(100)
        slider.setTickInterval(25)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setStyleSheet(_slider_style)
        vid_sliders[prop] = slider
        vid_layout.addWidget(slider, row, 1)

        val_lbl = QLabel("0")
        val_lbl.setFixedWidth(30)
        val_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vid_labels[prop] = val_lbl
        vid_layout.addWidget(val_lbl, row, 2)

        reset_btn = _make_reset_button(
            lambda _=False, p=prop: vid_sliders[p].setValue(0))
        vid_layout.addWidget(reset_btn, row, 3)

    speed_25x_cb = QCheckBox("Allow 25x maximum video playback speed")
    speed_25x_cb.setChecked(cfg.get_allow_25x_speed())
    vid_layout.addWidget(speed_25x_cb, len(VIDEO_PROPS), 0, 1, 4)

    def _on_25x_toggled(checked):
        # Only warn on the off->on transition.
        if not checked:
            return
        # Parent the warning to the AV dialog (`dlg`) so it stacks
        # correctly above it, just like the other modal popups.
        show_message(
            dlg,
            "25x Playback Speed",
            "Not all systems can realistically achieve 25x playback "
            "speed. Your actual max playback speed may be lower than "
            "the displayed speed.",
            icon="warning",
        )
    speed_25x_cb.toggled.connect(_on_25x_toggled)

    video_scope_cb = QCheckBox("Apply video settings to all videos")
    video_scope_cb.setChecked(not bool(per_video))
    vid_layout.addWidget(video_scope_cb, len(VIDEO_PROPS) + 1, 0, 1, 4)

    layout.addWidget(vid_group)

    # --- Audio controls ---
    aud_group = QGroupBox("Audio")
    aud_layout = QGridLayout(aud_group)
    aud_layout.setColumnStretch(1, 1)

    # Volume (0-200)
    aud_layout.addWidget(QLabel("Volume:"), 0, 0)
    vol_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    vol_slider.setMinimum(0)
    vol_slider.setMaximum(100)
    vol_slider.setTickInterval(25)
    vol_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    vol_slider.setStyleSheet(_slider_style)
    vol_slider.setValue(aud_originals["volume"])
    aud_layout.addWidget(vol_slider, 0, 1)
    vol_lbl = QLabel(str(aud_originals["volume"]))
    vol_lbl.setFixedWidth(30)
    vol_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    aud_layout.addWidget(vol_lbl, 0, 2)
    vol_reset = _make_reset_button(lambda: vol_slider.setValue(100))
    aud_layout.addWidget(vol_reset, 0, 3)

    # Audio delay (-2.0 to +2.0 seconds, stored as int ms in slider)
    aud_layout.addWidget(QLabel("A/V Sync (s):"), 1, 0)
    delay_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    delay_slider.setMinimum(-2000)
    delay_slider.setMaximum(2000)
    delay_slider.setTickInterval(500)
    delay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    delay_slider.setStyleSheet(_slider_style)
    delay_slider.setValue(int(aud_originals["audio_delay"] * 1000))
    aud_layout.addWidget(delay_slider, 1, 1)
    delay_lbl = QLabel(f"{aud_originals['audio_delay']:.2f}")
    delay_lbl.setFixedWidth(40)
    delay_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    aud_layout.addWidget(delay_lbl, 1, 2)
    delay_reset = _make_reset_button(lambda: delay_slider.setValue(0))
    aud_layout.addWidget(delay_reset, 1, 3)

    # Pitch shift (-12 to +12 semitones)
    aud_layout.addWidget(QLabel("Pitch (semitones):"), 2, 0)
    pitch_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    pitch_slider.setMinimum(-12)
    pitch_slider.setMaximum(12)
    pitch_slider.setTickInterval(1)
    pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    pitch_slider.setStyleSheet(_slider_style)
    _current_semitones = aud_originals["pitch_semitones"]
    pitch_slider.setValue(_current_semitones)
    aud_layout.addWidget(pitch_slider, 2, 1)
    pitch_lbl = QLabel(str(_current_semitones))
    pitch_lbl.setFixedWidth(30)
    pitch_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    aud_layout.addWidget(pitch_lbl, 2, 2)
    pitch_reset = _make_reset_button(lambda: pitch_slider.setValue(0))
    aud_layout.addWidget(pitch_reset, 2, 3)

    # Pitch correction checkbox
    pitch_cb = QCheckBox("Maintain pitch when speed changes")
    pitch_cb.setChecked(aud_originals["audio_pitch_correction"])
    aud_layout.addWidget(pitch_cb, 3, 0, 1, 4)

    audio_scope_cb = QCheckBox("Apply audio settings to all videos")
    audio_scope_cb.setChecked(not bool(per_video_audio))
    aud_layout.addWidget(audio_scope_cb, 4, 0, 1, 4)

    layout.addWidget(aud_group)

    # --- Navigation group ---
    nav_group = QGroupBox("Navigation")
    nav_layout = QGridLayout(nav_group)
    nav_layout.setColumnStretch(1, 1)

    def _lock_spin_text(spin):
        """Make the line-edit portion non-editable and non-focusable.
        Arrow buttons still work for stepping."""
        le = spin.lineEdit()
        le.setReadOnly(True)
        le.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        le.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

    nav_layout.addWidget(QLabel("Small Skip (s):"), 0, 0)
    small_skip_spin = _NoScrollDoubleSpinBox()
    small_skip_spin.setRange(0.1, 60.0)
    small_skip_spin.setSingleStep(0.1)
    small_skip_spin.setDecimals(1)
    small_skip_spin.setValue(cfg.get_small_skip_seconds())
    _lock_spin_text(small_skip_spin)
    nav_layout.addWidget(small_skip_spin, 0, 1, 1, 2)
    small_skip_reset = _make_reset_button(lambda: small_skip_spin.setValue(1.0))
    nav_layout.addWidget(small_skip_reset, 0, 3)

    nav_layout.addWidget(QLabel("Large Skip (s):"), 1, 0)
    large_skip_spin = _NoScrollDoubleSpinBox()
    large_skip_spin.setRange(0.1, 60.0)
    large_skip_spin.setSingleStep(1.0)
    large_skip_spin.setDecimals(1)
    large_skip_spin.setValue(cfg.get_large_skip_seconds())
    _lock_spin_text(large_skip_spin)
    nav_layout.addWidget(large_skip_spin, 1, 1, 1, 2)
    large_skip_reset = _make_reset_button(lambda: large_skip_spin.setValue(5.0))
    nav_layout.addWidget(large_skip_reset, 1, 3)

    layout.addWidget(nav_group)

    # --- Audio Track group ---
    _DR_STEPS = [
        ("Linear", 1.0),
        ("", 0.75),
        ("Moderate", 0.5),
        ("", 0.25),
        ("Compressed", 0.15),
    ]

    track_group = QGroupBox("Audio Track")
    track_layout = QGridLayout(track_group)
    track_layout.setColumnStretch(1, 1)

    # Height
    track_layout.addWidget(QLabel("Audio Track Height:"), 0, 0)
    height_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    height_slider.setRange(10, 30)
    height_slider.setValue(int(cfg.get_waveform_height_multiplier() * 10))
    height_slider.setTickInterval(5)
    height_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    height_slider.setStyleSheet(_slider_style)
    track_layout.addWidget(height_slider, 0, 1)
    height_lbl = QLabel(f"{cfg.get_waveform_height_multiplier():.1f}x")
    height_lbl.setFixedWidth(40)
    height_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    track_layout.addWidget(height_lbl, 0, 2)
    height_reset = _make_reset_button(lambda: height_slider.setValue(20))
    track_layout.addWidget(height_reset, 0, 3)

    def _on_height_changed(val):
        height_lbl.setText(f"{val / 10.0:.1f}x")
        if hasattr(annotator, 'waveform_widget'):
            new_h = int(annotator.progress_bar_height * (val / 10.0))
            annotator.waveform_widget.setFixedHeight(new_h)
        if hasattr(annotator, '_recalculate_video_height'):
            annotator._recalculate_video_height()

    height_slider.valueChanged.connect(_on_height_changed)

    # Dynamic Range
    track_layout.addWidget(QLabel("Dynamic Range:"), 1, 0)
    dynamic_range_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    dynamic_range_slider.setRange(0, len(_DR_STEPS) - 1)
    current_dr = cfg.get_waveform_dynamic_range()
    dr_idx = min(range(len(_DR_STEPS)),
                 key=lambda i: abs(_DR_STEPS[i][1] - current_dr))
    dynamic_range_slider.setValue(dr_idx)
    dynamic_range_slider.setTickInterval(1)
    dynamic_range_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    dynamic_range_slider.setStyleSheet(_slider_style)
    track_layout.addWidget(dynamic_range_slider, 1, 1)

    dr_lbl = QLabel(_DR_STEPS[dr_idx][0] or f"{_DR_STEPS[dr_idx][1]:.2f}")
    dr_lbl.setFixedWidth(80)
    dr_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    track_layout.addWidget(dr_lbl, 1, 2)

    dr_reset = _make_reset_button(lambda: dynamic_range_slider.setValue(0))
    track_layout.addWidget(dr_reset, 1, 3)

    def _on_dr_changed(idx):
        label, exp = _DR_STEPS[idx]
        dr_lbl.setText(label or f"{exp:.2f}")
        if hasattr(annotator, 'waveform_widget'):
            annotator.waveform_widget.set_dynamic_range(exp)

    dynamic_range_slider.valueChanged.connect(_on_dr_changed)

    layout.addWidget(track_group)

    # --- Spectrogram group ---
    from spectrogram_widget import COLORMAPS

    spec_group = QGroupBox("Spectrogram")
    spec_layout = QGridLayout(spec_group)
    spec_layout.setColumnStretch(1, 1)

    # Colormap dropdown
    spec_layout.addWidget(QLabel("Colormap:"), 0, 0)
    cmap_combo = _NoScrollComboBox()
    cmap_names = list(COLORMAPS.keys())
    cmap_combo.addItems(cmap_names)
    current_cmap = cfg.get_spectrogram_colormap()
    if current_cmap in cmap_names:
        cmap_combo.setCurrentIndex(cmap_names.index(current_cmap))
    spec_layout.addWidget(cmap_combo, 0, 1, 1, 2)
    cmap_reset = _make_reset_button(lambda: cmap_combo.setCurrentText("viridis"))
    spec_layout.addWidget(cmap_reset, 0, 3)

    # Frequency Low (Hz)
    spec_layout.addWidget(QLabel("Freq Low (Hz):"), 1, 0)
    freq_low_spin = _NoScrollSpinBox()
    freq_low_spin.setRange(0, 20000)
    freq_low_spin.setSingleStep(500)
    freq_low_spin.setValue(cfg.get_spectrogram_freq_low())
    _lock_spin_text(freq_low_spin)
    spec_layout.addWidget(freq_low_spin, 1, 1, 1, 2)
    freq_low_reset = _make_reset_button(lambda: freq_low_spin.setValue(0))
    spec_layout.addWidget(freq_low_reset, 1, 3)

    # Frequency High (Hz)
    spec_layout.addWidget(QLabel("Freq High (Hz):"), 2, 0)
    freq_high_spin = _NoScrollSpinBox()
    freq_high_spin.setRange(500, 22050)
    freq_high_spin.setSingleStep(500)
    freq_high_spin.setValue(cfg.get_spectrogram_freq_high())
    _lock_spin_text(freq_high_spin)
    spec_layout.addWidget(freq_high_spin, 2, 1, 1, 2)
    freq_high_reset = _make_reset_button(lambda: freq_high_spin.setValue(15000))
    spec_layout.addWidget(freq_high_reset, 2, 3)

    # Window duration (seconds)
    spec_layout.addWidget(QLabel("Window (s):"), 3, 0)
    window_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    window_slider.setRange(2, 30)
    window_slider.setValue(int(cfg.get_spectrogram_window()))
    window_slider.setTickInterval(5)
    window_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    window_slider.setStyleSheet(_slider_style)
    spec_layout.addWidget(window_slider, 3, 1)
    window_lbl = QLabel(f"{int(cfg.get_spectrogram_window())}s")
    window_lbl.setFixedWidth(30)
    window_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    spec_layout.addWidget(window_lbl, 3, 2)
    window_reset = _make_reset_button(lambda: window_slider.setValue(10))
    spec_layout.addWidget(window_reset, 3, 3)

    def _on_window_changed(val):
        window_lbl.setText(f"{val}s")
        if hasattr(annotator, 'spectrogram_widget'):
            annotator.spectrogram_widget.set_window_duration(float(val))

    window_slider.valueChanged.connect(_on_window_changed)

    def _on_cmap_changed(name):
        if hasattr(annotator, 'spectrogram_widget'):
            annotator.spectrogram_widget.set_colormap(name)

    cmap_combo.currentTextChanged.connect(_on_cmap_changed)

    def _on_freq_changed():
        if hasattr(annotator, 'spectrogram_widget'):
            annotator.spectrogram_widget.set_freq_range(
                freq_low_spin.value(), freq_high_spin.value())

    freq_low_spin.valueChanged.connect(lambda _: _on_freq_changed())
    freq_high_spin.valueChanged.connect(lambda _: _on_freq_changed())

    # Height
    spec_layout.addWidget(QLabel("Spectrogram Height:"), 4, 0)
    spec_height_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    spec_height_slider.setRange(20, 80)
    spec_height_slider.setValue(int(cfg.get_spectrogram_height_multiplier() * 10))
    spec_height_slider.setTickInterval(10)
    spec_height_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    spec_height_slider.setStyleSheet(_slider_style)
    spec_layout.addWidget(spec_height_slider, 4, 1)
    spec_height_lbl = QLabel(f"{cfg.get_spectrogram_height_multiplier():.1f}x")
    spec_height_lbl.setFixedWidth(40)
    spec_height_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    spec_layout.addWidget(spec_height_lbl, 4, 2)
    spec_height_reset = _make_reset_button(lambda: spec_height_slider.setValue(40))
    spec_layout.addWidget(spec_height_reset, 4, 3)

    def _on_spec_height_changed(val):
        spec_height_lbl.setText(f"{val / 10.0:.1f}x")
        if hasattr(annotator, 'spectrogram_widget'):
            new_h = int(annotator.progress_bar_height * (val / 10.0))
            annotator.spectrogram_widget.setFixedHeight(new_h)
        if hasattr(annotator, '_recalculate_video_height'):
            annotator._recalculate_video_height()

    spec_height_slider.valueChanged.connect(_on_spec_height_changed)

    layout.addWidget(spec_group)

    # --- Buttons ---
    btn_frame = QWidget()
    btn_lay = QHBoxLayout(btn_frame)
    reset_all_btn = QPushButton("Reset All")
    ok_btn = QPushButton("OK")
    cancel_btn = QPushButton("Cancel")

    def _reset_all():
        for prop in VIDEO_PROPS:
            vid_sliders[prop].setValue(0)
        vol_slider.setValue(100)
        delay_slider.setValue(0)
        pitch_slider.setValue(0)
        pitch_cb.setChecked(True)
        small_skip_spin.setValue(1.0)
        large_skip_spin.setValue(5.0)
        height_slider.setValue(20)
        dynamic_range_slider.setValue(0)
        speed_25x_cb.setChecked(False)
        cmap_combo.setCurrentText("viridis")
        freq_low_spin.setValue(0)
        freq_high_spin.setValue(15000)
        window_slider.setValue(10)
        spec_height_slider.setValue(40)

    reset_all_btn.clicked.connect(_reset_all)
    btn_lay.addWidget(reset_all_btn)
    btn_lay.addStretch()
    btn_lay.addWidget(cancel_btn)
    btn_lay.addSpacing(10)
    btn_lay.addWidget(ok_btn)
    btn_lay.setContentsMargins(15, 0, 15, 0)
    outer_lay.addWidget(btn_frame)

    # --- Wiring ---
    def _load_scope_values(settings):
        for prop in VIDEO_PROPS:
            val = int(settings.get(prop, 0)) if settings else 0
            vid_sliders[prop].blockSignals(True)
            vid_sliders[prop].setValue(val)
            vid_sliders[prop].blockSignals(False)
            vid_labels[prop].setText(str(val))
            try:
                setattr(annotator.player, prop, val)
            except Exception:
                pass

    def _on_video_scope_changed():
        if video_scope_cb.isChecked():
            _load_scope_values(global_settings)
        else:
            _load_scope_values(per_video or {})

    def _load_audio_values(settings):
        vol = int(settings.get("volume", 100))
        delay = float(settings.get("audio_delay", 0.0))
        semitones = int(settings.get("pitch_semitones", 0))
        pc = bool(settings.get("audio_pitch_correction", True))
        vol_slider.blockSignals(True)
        vol_slider.setValue(vol)
        vol_slider.blockSignals(False)
        vol_lbl.setText(str(vol))
        delay_slider.blockSignals(True)
        delay_slider.setValue(int(delay * 1000))
        delay_slider.blockSignals(False)
        delay_lbl.setText(f"{delay:.2f}")
        pitch_slider.blockSignals(True)
        pitch_slider.setValue(semitones)
        pitch_slider.blockSignals(False)
        pitch_lbl.setText(str(semitones))
        pitch_cb.blockSignals(True)
        pitch_cb.setChecked(pc)
        pitch_cb.blockSignals(False)
        try:
            annotator.player.volume = vol
            annotator.player.audio_delay = delay
            annotator.player.audio_pitch_correction = pc
            if semitones == 0:
                annotator.player.af = ""
            else:
                factor = 2 ** (semitones / 12.0)
                annotator.player.af = (
                    f"lavfi=[rubberband=pitch={factor:.4f}]")
        except Exception:
            pass

    def _on_audio_scope_changed():
        if audio_scope_cb.isChecked():
            _load_audio_values(global_audio)
        else:
            _load_audio_values(per_video_audio or global_audio)

    def _on_vid_slider_changed(val, prop):
        vid_labels[prop].setText(str(val))
        try:
            setattr(annotator.player, prop, val)
        except Exception:
            pass

    for prop in VIDEO_PROPS:
        vid_sliders[prop].valueChanged.connect(
            lambda val, p=prop: _on_vid_slider_changed(val, p))

    def _on_vol_changed(val):
        vol_lbl.setText(str(val))
        annotator.player.volume = val

    def _on_delay_changed(val):
        secs = val / 1000.0
        delay_lbl.setText(f"{secs:.2f}")
        annotator.player.audio_delay = secs

    def _apply_pitch(semitones):
        pitch_lbl.setText(str(semitones))
        if semitones == 0:
            annotator.player.af = ""
        else:
            factor = 2 ** (semitones / 12.0)
            annotator.player.af = f"lavfi=[rubberband=pitch={factor:.4f}]"

    vol_slider.valueChanged.connect(_on_vol_changed)
    delay_slider.valueChanged.connect(_on_delay_changed)
    pitch_slider.valueChanged.connect(_apply_pitch)
    pitch_cb.toggled.connect(
        lambda checked: setattr(
            annotator.player, "audio_pitch_correction", checked))
    video_scope_cb.toggled.connect(lambda _: _on_video_scope_changed())
    audio_scope_cb.toggled.connect(lambda _: _on_audio_scope_changed())

    def _save():
        # Video
        current = {prop: vid_sliders[prop].value() for prop in VIDEO_PROPS}
        if video_scope_cb.isChecked():
            cfg.update_video_settings(current)
            # Clear any per-video override so the global value wins
            annotator.store.save_video_settings({})
        else:
            annotator.store.save_video_settings(current)
        # Audio
        audio_current = {
            "volume": vol_slider.value(),
            "audio_delay": delay_slider.value() / 1000.0,
            "pitch_semitones": pitch_slider.value(),
            "audio_pitch_correction": pitch_cb.isChecked(),
        }
        if audio_scope_cb.isChecked():
            cfg.set_volume(audio_current["volume"])
            cfg.set_audio_delay(audio_current["audio_delay"])
            cfg.set_pitch_semitones(audio_current["pitch_semitones"])
            cfg.set_audio_pitch_correction(
                audio_current["audio_pitch_correction"])
            # Clear any per-video override so the global values win
            annotator.store.save_audio_settings({})
        else:
            annotator.store.save_audio_settings(audio_current)
        # Update the panel slider to match
        if hasattr(annotator, '_volume_slider'):
            annotator._volume_slider.blockSignals(True)
            annotator._volume_slider.setValue(
                min(vol_slider.value(), annotator._volume_slider.maximum()))
            annotator._volume_slider.blockSignals(False)
        # 25x speed
        cfg.set_allow_25x_speed(speed_25x_cb.isChecked())
        # Navigation
        cfg.set_small_skip_seconds(small_skip_spin.value())
        cfg.set_large_skip_seconds(large_skip_spin.value())
        # Audio Track
        cfg.set_waveform_height_multiplier(height_slider.value() / 10.0)
        if hasattr(annotator, 'waveform_widget'):
            new_h = int(annotator.progress_bar_height * (height_slider.value() / 10.0))
            annotator.waveform_widget.setFixedHeight(new_h)
        dr_exp = _DR_STEPS[dynamic_range_slider.value()][1]
        cfg.set_waveform_dynamic_range(dr_exp)
        # Spectrogram
        cfg.set_spectrogram_colormap(cmap_combo.currentText())
        cfg.set_spectrogram_freq_low(freq_low_spin.value())
        cfg.set_spectrogram_freq_high(freq_high_spin.value())
        cfg.set_spectrogram_window(float(window_slider.value()))
        cfg.set_spectrogram_height_multiplier(spec_height_slider.value() / 10.0)
        if hasattr(annotator, 'spectrogram_widget'):
            annotator.spectrogram_widget.set_colormap(cmap_combo.currentText())
            annotator.spectrogram_widget.set_freq_range(
                freq_low_spin.value(), freq_high_spin.value())
            annotator.spectrogram_widget.set_window_duration(
                float(window_slider.value()))
            new_h = int(annotator.progress_bar_height
                        * (spec_height_slider.value() / 10.0))
            annotator.spectrogram_widget.setFixedHeight(new_h)
        if hasattr(annotator, '_recalculate_video_height'):
            annotator._recalculate_video_height()
        dlg.accept()

    def _cancel():
        for prop in VIDEO_PROPS:
            try:
                setattr(annotator.player, prop, vid_originals[prop])
            except Exception:
                pass
        annotator.player.volume = aud_originals["volume"]
        annotator.player.audio_delay = aud_originals["audio_delay"]
        annotator.player.audio_pitch_correction = (
            aud_originals["audio_pitch_correction"])
        semitones = aud_originals["pitch_semitones"]
        try:
            if semitones == 0:
                annotator.player.af = ""
            else:
                factor = 2 ** (semitones / 12.0)
                annotator.player.af = f"lavfi=[rubberband=pitch={factor:.4f}]"
        except Exception:
            pass
        if hasattr(annotator, 'waveform_widget'):
            annotator.waveform_widget.set_dynamic_range(dr_original)
            new_h = int(
                annotator.progress_bar_height * waveform_height_original)
            annotator.waveform_widget.setFixedHeight(new_h)
        if hasattr(annotator, 'spectrogram_widget'):
            annotator.spectrogram_widget.set_colormap(spec_originals["colormap"])
            annotator.spectrogram_widget.set_freq_range(
                spec_originals["freq_low"], spec_originals["freq_high"])
            annotator.spectrogram_widget.set_window_duration(
                spec_originals["window"])
            new_h = int(annotator.progress_bar_height
                        * spec_originals["height_multiplier"])
            annotator.spectrogram_widget.setFixedHeight(new_h)
        if hasattr(annotator, '_recalculate_video_height'):
            annotator._recalculate_video_height()
        dlg.reject()

    ok_btn.clicked.connect(_save)
    cancel_btn.clicked.connect(_cancel)

    # Load initial slider values matching the scope each checkbox
    # was set to above (per-video if present, else global)
    _on_video_scope_changed()
    _on_audio_scope_changed()

    def _on_finished(_result):
        annotator.dialog_open = False
        dlg.deleteLater()

    dlg.finished.connect(_on_finished)
    dlg.open()


def show_edit_state_dialog(annotator):
    """Edit a state annotation's name, start, and end time"""
    if annotator.selected_index is None:
        return
    if not annotator.store.check_file_access():
        if hasattr(annotator, "player") and annotator.player:
            annotator.player.pause = True
        annotator.on_write_error()
        return

    sel = annotator.store.state_events[annotator.selected_index]

    if sel["end_time"] is None:
        show_message(annotator, "Edit Error",
                           "Please end the state event before editing.")
        return

    annotator.dialog_open = True

    latest = annotator.load_annotation_data(sel, "Event", "H_Start", "H_End")

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Edit State Annotation")

    _apply_dialog_theme(dlg)
    dlg.resize(250, 300)

    layout = QVBoxLayout(dlg)

    cur_grp = QGroupBox("Current Annotation")
    cur_lay = QFormLayout()
    cur_lay.addRow("Event:", QLabel(latest["Event"]))
    cur_lay.addRow("Start:", QLabel(latest["H_Start"]))
    cur_lay.addRow("End:", QLabel(latest["H_End"]))
    cur_grp.setLayout(cur_lay)
    layout.addWidget(cur_grp)

    new_grp = QGroupBox("New Annotation")
    new_lay = QFormLayout()
    entries = {}
    for field in ("Event", "H_Start", "H_End"):
        e = QLineEdit(); e.setText(latest.get(field, ""))
        new_lay.addRow(field.replace("H_", "") + ":", e)
        entries[field] = e
    new_grp.setLayout(new_lay)
    layout.addWidget(new_grp)

    bbox = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    bbox.accepted.connect(
        lambda: annotator.save_state_annotation(entries, dlg, sel, latest["H_Start"]))
    bbox.rejected.connect(dlg.reject)
    layout.addWidget(bbox)

    def _on_finished(_result):
        annotator.dialog_open = False
        dlg.deleteLater()

    dlg.finished.connect(_on_finished)
    dlg.open()



# Message box and input dialog

def show_message(parent, title, text, icon="warning", callback=None):
    """Show a themed QMessageBox"""
    icons = {
        "warning": QMessageBox.Icon.Warning,
        "critical": QMessageBox.Icon.Critical,
        "information": QMessageBox.Icon.Information,
        "question": QMessageBox.Icon.Question,
    }
    dlg = QMessageBox(parent)
    _apply_dialog_theme(dlg)
    dlg.setWindowTitle(title)
    dlg.setText(text)
    dlg.setIcon(icons.get(icon, QMessageBox.Icon.Warning))
    if icon == "question":
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setDefaultButton(QMessageBox.StandardButton.No)
    else:
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
    if callback is not None:
        def _on_finished(result):
            dlg.deleteLater()
            callback(result)
        dlg.finished.connect(_on_finished)
        dlg.open()
    else:
        result = dlg.exec()
        dlg.deleteLater()
        return result


def get_text(parent, title, label, text="", callback=None):
    """Show a input dialog"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    _apply_dialog_theme(dlg)

    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    line = QLineEdit(text)
    layout.addWidget(line)
    bbox = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok
        | QDialogButtonBox.StandardButton.Cancel)
    bbox.accepted.connect(dlg.accept)
    bbox.rejected.connect(dlg.reject)
    layout.addWidget(bbox)
    line.setFocus()
    if callback is not None:
        def _on_finished(result):
            ok = result == QDialog.DialogCode.Accepted
            text_result = line.text()
            dlg.deleteLater()
            callback(text_result, ok)
        dlg.finished.connect(_on_finished)
        dlg.open()
    else:
        # Fallback
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        result = line.text()
        dlg.deleteLater()
        return result, ok


def show_colors_theme_dialog(parent, on_accept=None):
    """Combined Colors & Theme dialog.

    parent: parent widget for the dialog.
    on_accept: callback(selected_theme, colors_dict) called on OK.
    """
    from PySide6.QtWidgets import QCheckBox, QScrollArea

    cfg = get_config()

    colors = {
        "state_highlight": (QColor(h) if (h := cfg.get_state_highlight_color())
                            else theme.qcolor("active_color")),
        "point_highlight": (QColor(h) if (h := cfg.get_point_highlight_color())
                            else theme.qcolor("highlight_color")),
        "progress_fill": (QColor(h) if (h := cfg.get_progress_bar_color())
                          else theme.qcolor("progress_fill")),
        "waveform_fill": (QColor(h) if (h := cfg.get_waveform_color())
                          else QColor(0, 150, 255)),
        "floating_toggle": (QColor(h) if (h := cfg.get_floating_toggle_color())
                            else theme.qcolor("float_toggle_bg")),
        "floating_controls": (QColor(h) if (h := cfg.get_floating_controls_color())
                              else theme.qcolor("float_control_bg")),
        "state_button": (QColor(h) if (h := cfg.get_state_button_color())
                         else theme.qcolor("float_state_bg")),
        "point_button": (QColor(h) if (h := cfg.get_point_button_color())
                         else theme.qcolor("float_point_bg")),
        "subject_button": (QColor(h) if (h := cfg.get_subject_button_color())
                           else QColor("#008080")),
        "floating_header": (QColor(h) if (h := cfg.get_floating_header_color())
                            else QColor(50, 50, 50)),
        "stationary_button": (QColor(h) if (h := cfg.get_stationary_button_color())
                              else theme.qcolor("button_bg")),
        "button_hover": (QColor(h) if (h := cfg.get_button_hover_color())
                         else theme.qcolor("button_hover")),
        "ui_bg": (QColor(h) if (h := cfg.get_ui_background_color())
                  else theme.qcolor("window_bg")),
        "tree_bg": (QColor(h) if (h := cfg.get_tree_background_color())
                    else theme.qcolor("tree_bg")),
    }
    initial_colors = {k: QColor(v) for k, v in colors.items()}
    selected_theme = [theme.current_theme()]

    # Snapshot cfg state at open so Cancel can fully revert.
    initial_cfg_state = {
        "state_highlight_color": cfg.get_state_highlight_color(),
        "point_highlight_color": cfg.get_point_highlight_color(),
        "progress_bar_color": cfg.get_progress_bar_color(),
        "waveform_color": cfg.get_waveform_color(),
        "floating_toggle_color": cfg.get_floating_toggle_color(),
        "floating_controls_color": cfg.get_floating_controls_color(),
        "state_button_color": cfg.get_state_button_color(),
        "point_button_color": cfg.get_point_button_color(),
        "subject_button_color": cfg.get_subject_button_color(),
        "floating_header_color": cfg.get_floating_header_color(),
        "floating_header_opacity": cfg.get_floating_header_opacity(),
        "floating_button_size": cfg.get_floating_button_size(),
        "annotation_tree_font_size": cfg.get_annotation_tree_font_size(),
        "stationary_button_color": cfg.get_stationary_button_color(),
        "button_hover_color": cfg.get_button_hover_color(),
        "ui_background_color": cfg.get_ui_background_color(),
        "tree_background_color": cfg.get_tree_background_color(),
        "progress_bar_opacity": cfg.get_progress_bar_opacity(),
        "waveform_opacity": cfg.get_waveform_opacity(),
        "spectrogram_opacity": cfg.get_spectrogram_opacity(),
        "floating_toggle_opacity": cfg.get_floating_toggle_opacity(),
        "floating_controls_opacity": cfg.get_floating_controls_opacity(),
        "floating_buttons_opacity": cfg.get_floating_buttons_opacity(),
        "theme": theme.current_theme(),
    }

    dlg = QDialog(parent)
    dlg.setWindowTitle("Appearance")
    _apply_dialog_theme(dlg)
    dlg.resize(420, 800)

    outer_lay = QVBoxLayout(dlg)
    outer_lay.setContentsMargins(0, 0, 0, 10)
    outer_lay.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    content = QWidget()
    main_lay = QVBoxLayout(content)
    main_lay.setContentsMargins(20, 15, 20, 15)
    main_lay.setSpacing(10)
    scroll.setWidget(content)
    outer_lay.addWidget(scroll, 1)

    swatches = {}
    opacity_sliders = {}
    size_sliders = {}

    def _save_color_if_changed(setter, key):
        """Persist a color only if it differs from its initial value,
        otherwise clear any stale override so the theme base takes over."""
        if colors[key].name() != initial_colors[key].name():
            setter(colors[key].name())
        else:
            setter(None)

    def _apply_live():
        """Persist current dialog state and refresh the app theme
        so color/transparency/theme edits apply in real time."""
        _save_color_if_changed(cfg.set_state_highlight_color, "state_highlight")
        _save_color_if_changed(cfg.set_point_highlight_color, "point_highlight")
        _save_color_if_changed(cfg.set_progress_bar_color, "progress_fill")
        _save_color_if_changed(cfg.set_waveform_color, "waveform_fill")
        _save_color_if_changed(cfg.set_floating_toggle_color, "floating_toggle")
        _save_color_if_changed(cfg.set_floating_controls_color, "floating_controls")
        _save_color_if_changed(cfg.set_state_button_color, "state_button")
        _save_color_if_changed(cfg.set_point_button_color, "point_button")
        _save_color_if_changed(cfg.set_subject_button_color, "subject_button")
        _save_color_if_changed(cfg.set_floating_header_color, "floating_header")
        _save_color_if_changed(cfg.set_stationary_button_color, "stationary_button")
        _save_color_if_changed(cfg.set_button_hover_color, "button_hover")
        _save_color_if_changed(cfg.set_ui_background_color, "ui_bg")
        _save_color_if_changed(cfg.set_tree_background_color, "tree_bg")
        if opacity_sliders:
            cfg.set_progress_bar_opacity(
                (100 - opacity_sliders["progress_bar_opacity"].value()) / 100.0)
            cfg.set_waveform_opacity(
                (100 - opacity_sliders["waveform_opacity"].value()) / 100.0)
            cfg.set_spectrogram_opacity(
                (100 - opacity_sliders["spectrogram_opacity"].value()) / 100.0)
            cfg.set_floating_toggle_opacity(
                (100 - opacity_sliders["floating_toggle_opacity"].value()) / 100.0)
            cfg.set_floating_controls_opacity(
                (100 - opacity_sliders["floating_controls_opacity"].value()) / 100.0)
            cfg.set_floating_buttons_opacity(
                (100 - opacity_sliders["floating_buttons_opacity"].value()) / 100.0)
            cfg.set_floating_header_opacity(
                (100 - opacity_sliders["floating_header_opacity"].value()) / 100.0)
        if "floating_button_size" in size_sliders:
            cfg.set_floating_button_size(
                size_sliders["floating_button_size"].value() / 100.0)
        if "annotation_tree_font_size" in size_sliders:
            cfg.set_annotation_tree_font_size(
                size_sliders["annotation_tree_font_size"].value())
        theme.apply_config_overrides(cfg)
        new_theme = selected_theme[0]
        theme.load_theme(new_theme)
        cfg.update_theme(new_theme)
        if on_accept:
            on_accept(new_theme, colors)

    def _update_swatch(btn, c):
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {c.name()};"
            f"  border: 1px solid grey; border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 2px solid white; }}")

    def _pick_color(key, btn):
        c = QColorDialog.getColor(colors[key], dlg, "Select Color")
        if c.isValid():
            colors[key] = c
            _update_swatch(btn, c)
            _apply_live()

    def _make_swatch(key):
        btn = QPushButton()
        btn.setFixedSize(60, 28)
        _update_swatch(btn, colors[key])
        btn.clicked.connect(lambda: _pick_color(key, btn))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        swatches[key] = btn
        return btn

    def _section(text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; padding-top: 4px;")
        return lbl

    # --- Theme section ---
    main_lay.addWidget(_section("Theme"))
    theme_row = QHBoxLayout()
    theme_row.setSpacing(12)
    theme_btns = []

    def _update_theme_btns():
        base = QColor(theme.color('button_bg'))
        selected_bg = base.darker(140).name()
        for b in theme_btns:
            if b.text().lower() == selected_theme[0]:
                b.setStyleSheet(
                    f"QPushButton {{ background-color: {selected_bg};"
                    f"  border: 1px solid grey; border-radius: 4px;"
                    f"  padding: 4px 12px; font-weight: bold; }}")
            else:
                b.setStyleSheet(
                    "QPushButton { border: 1px solid grey;"
                    "  border-radius: 4px; padding: 4px 12px; }")

    def _select_theme(name):
        selected_theme[0] = name
        _update_theme_btns()
        _apply_live()

    for name in ("system", "dark", "light"):
        btn = QPushButton(name.capitalize())
        btn.clicked.connect(
            lambda checked, n=name: _select_theme(n))
        theme_btns.append(btn)
        theme_row.addWidget(btn)
    theme_row.addStretch()
    main_lay.addLayout(theme_row)
    _update_theme_btns()

    # --- Colors section ---
    main_lay.addWidget(_section("Colors"))
    color_grid = QGridLayout()
    color_grid.setSpacing(8)
    color_grid.setColumnStretch(0, 1)

    _color_items = [
        ("State Annotation Highlight", "state_highlight"),
        ("Point Annotation Highlight", "point_highlight"),
        ("Progress Bar", "progress_fill"),
        ("Audio Track", "waveform_fill"),
        ("Floating Toggles", "floating_toggle"),
        ("Floating Controls", "floating_controls"),
        ("Floating State Buttons", "state_button"),
        ("Floating Point Buttons", "point_button"),
        ("Floating Subject Buttons", "subject_button"),
        ("Floating Headers", "floating_header"),
        ("Stationary Buttons", "stationary_button"),
        ("Button Hover", "button_hover"),
        ("UI Background", "ui_bg"),
        ("Annotations List Background", "tree_bg"),
    ]

    color_defaults = {
        "state_highlight": theme.base_qcolor("active_color"),
        "point_highlight": theme.base_qcolor("highlight_color"),
        "progress_fill": theme.base_qcolor("progress_fill"),
        "waveform_fill": QColor(0, 150, 255),
        "floating_toggle": theme.base_qcolor("float_toggle_bg"),
        "floating_controls": theme.base_qcolor("float_control_bg"),
        "state_button": theme.base_qcolor("float_state_bg"),
        "point_button": theme.base_qcolor("float_point_bg"),
        "subject_button": QColor("#008080"),
        "floating_header": QColor(50, 50, 50),
        "stationary_button": theme.base_qcolor("button_bg"),
        "button_hover": theme.base_qcolor("button_hover"),
        "ui_bg": theme.base_qcolor("window_bg"),
        "tree_bg": theme.base_qcolor("tree_bg"),
    }

    def _reset_color(key):
        c = QColor(color_defaults[key])
        colors[key] = c
        _update_swatch(swatches[key], c)
        _apply_live()

    for row, (label, key) in enumerate(_color_items):
        color_grid.addWidget(QLabel(label + ":"), row, 0)
        color_grid.addWidget(_make_swatch(key), row, 1)
        color_grid.addWidget(
            _make_reset_button(lambda _=False, k=key: _reset_color(k)),
            row, 2)

    main_lay.addLayout(color_grid)

    # --- Transparency section ---
    main_lay.addWidget(_section("Transparency"))
    trans_grid = QGridLayout()
    trans_grid.setSpacing(8)
    trans_grid.setColumnStretch(1, 1)

    _transparency_items = [
        ("Progress Bar", "progress_bar_opacity",
         cfg.get_progress_bar_opacity()),
        ("Audio Track", "waveform_opacity",
         cfg.get_waveform_opacity()),
        ("Spectrogram", "spectrogram_opacity",
         cfg.get_spectrogram_opacity()),
        ("Floating Toggles", "floating_toggle_opacity",
         cfg.get_floating_toggle_opacity()),
        ("Floating Controls", "floating_controls_opacity",
         cfg.get_floating_controls_opacity()),
        ("Floating Buttons", "floating_buttons_opacity",
         cfg.get_floating_buttons_opacity()),
        ("Floating Headers", "floating_header_opacity",
         cfg.get_floating_header_opacity()),
    ]

    # Slider values are inverted: 0 = fully opaque, 100 = fully transparent.
    transparency_defaults = {
        "progress_bar_opacity": 0,        # 0% transparent
        "waveform_opacity": 0,            # 0%
        "spectrogram_opacity": 0,         # 0%
        "floating_toggle_opacity": 20,    # 20% transparent
        "floating_controls_opacity": 20,  # 20%
        "floating_buttons_opacity": 20,   # 20%
        "floating_header_opacity": 20,    # 20%
    }

    for row, (label, key, current_val) in enumerate(_transparency_items):
        trans_grid.addWidget(QLabel(label + ":"), row, 0)
        slider = _NoScrollSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(100 - int(current_val * 100))
        slider.setMaximumWidth(160)
        trans_grid.addWidget(slider, row, 1)
        opacity_sliders[key] = slider
        trans_grid.addWidget(
            _make_reset_button(
                lambda _=False, k=key: opacity_sliders[k].setValue(
                    transparency_defaults[k])),
            row, 2)

    main_lay.addLayout(trans_grid)

    # --- Size section ---
    main_lay.addWidget(_section("Size"))
    size_grid = QGridLayout()
    size_grid.setSpacing(8)
    size_grid.setColumnStretch(1, 1)
    size_defaults = {
        "floating_button_size": 100,         # 1.0x
        "annotation_tree_font_size": 14,     # 14px
    }

    size_grid.addWidget(QLabel("Floating Buttons:"), 0, 0)
    size_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    size_slider.setRange(50, 200)  # 0.5x .. 2.0x
    size_slider.setValue(int(cfg.get_floating_button_size() * 100))
    size_slider.setMaximumWidth(160)
    size_grid.addWidget(size_slider, 0, 1)
    size_sliders["floating_button_size"] = size_slider
    size_grid.addWidget(
        _make_reset_button(
            lambda _=False: size_sliders["floating_button_size"].setValue(
                size_defaults["floating_button_size"])),
        0, 2)

    size_grid.addWidget(QLabel("Annotation Font:"), 1, 0)
    tree_font_slider = _NoScrollSlider(Qt.Orientation.Horizontal)
    tree_font_slider.setRange(8, 28)
    tree_font_slider.setValue(int(cfg.get_annotation_tree_font_size()))
    tree_font_slider.setMaximumWidth(160)
    size_grid.addWidget(tree_font_slider, 1, 1)
    size_sliders["annotation_tree_font_size"] = tree_font_slider
    size_grid.addWidget(
        _make_reset_button(
            lambda _=False: size_sliders["annotation_tree_font_size"].setValue(
                size_defaults["annotation_tree_font_size"])),
        1, 2)

    main_lay.addLayout(size_grid)

    main_lay.addStretch()

    # --- Reset + OK/Cancel ---
    def _reset():
        for key in color_defaults:
            _reset_color(key)
        for key, val in transparency_defaults.items():
            opacity_sliders[key].setValue(val)
        for key, val in size_defaults.items():
            size_sliders[key].setValue(val)
        _apply_live()

    btn_row = QHBoxLayout()
    btn_row.setContentsMargins(20, 0, 20, 0)
    reset_btn = QPushButton("Reset to Defaults")
    reset_btn.clicked.connect(_reset)
    btn_row.addWidget(reset_btn)
    btn_row.addStretch()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)
    btn_row.addSpacing(10)
    apply_btn = QPushButton("Apply")
    apply_btn.clicked.connect(_apply_live)
    btn_row.addWidget(apply_btn)
    btn_row.addSpacing(10)
    ok_btn = QPushButton("OK")
    def _on_ok():
        _apply_live()
        dlg.accept()
    ok_btn.clicked.connect(_on_ok)
    btn_row.addWidget(ok_btn)
    outer_lay.addLayout(btn_row)

    def _on_finished(result):
        dlg.deleteLater()
        if result == QDialog.DialogCode.Rejected:
            # Restore the cfg state captured when the dialog opened and
            # reapply the theme so visible state reverts to pre-dialog.
            cfg.set_state_highlight_color(
                initial_cfg_state["state_highlight_color"])
            cfg.set_point_highlight_color(
                initial_cfg_state["point_highlight_color"])
            cfg.set_progress_bar_color(
                initial_cfg_state["progress_bar_color"])
            cfg.set_waveform_color(initial_cfg_state["waveform_color"])
            cfg.set_floating_toggle_color(
                initial_cfg_state["floating_toggle_color"])
            cfg.set_floating_controls_color(
                initial_cfg_state["floating_controls_color"])
            cfg.set_state_button_color(
                initial_cfg_state["state_button_color"])
            cfg.set_point_button_color(
                initial_cfg_state["point_button_color"])
            cfg.set_subject_button_color(
                initial_cfg_state["subject_button_color"])
            cfg.set_stationary_button_color(
                initial_cfg_state["stationary_button_color"])
            cfg.set_button_hover_color(
                initial_cfg_state["button_hover_color"])
            cfg.set_ui_background_color(
                initial_cfg_state["ui_background_color"])
            cfg.set_tree_background_color(
                initial_cfg_state["tree_background_color"])
            cfg.set_progress_bar_opacity(
                initial_cfg_state["progress_bar_opacity"])
            cfg.set_waveform_opacity(
                initial_cfg_state["waveform_opacity"])
            cfg.set_spectrogram_opacity(
                initial_cfg_state["spectrogram_opacity"])
            cfg.set_floating_toggle_opacity(
                initial_cfg_state["floating_toggle_opacity"])
            cfg.set_floating_controls_opacity(
                initial_cfg_state["floating_controls_opacity"])
            cfg.set_floating_buttons_opacity(
                initial_cfg_state["floating_buttons_opacity"])
            cfg.set_floating_header_color(
                initial_cfg_state["floating_header_color"])
            cfg.set_floating_header_opacity(
                initial_cfg_state["floating_header_opacity"])
            cfg.set_floating_button_size(
                initial_cfg_state["floating_button_size"])
            cfg.set_annotation_tree_font_size(
                initial_cfg_state["annotation_tree_font_size"])
            theme.apply_config_overrides(cfg)
            theme.load_theme(initial_cfg_state["theme"])
            cfg.update_theme(initial_cfg_state["theme"])
            if on_accept:
                on_accept(initial_cfg_state["theme"], initial_colors)

    dlg.finished.connect(_on_finished)
    dlg.open()
    return dlg
