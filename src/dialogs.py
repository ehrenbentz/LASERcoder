import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QGridLayout, QDialogButtonBox, QMessageBox, QWidget,
    QRadioButton, QSlider, QFrame, QColorDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from annotation_store import format_time_human, parse_time
from config_manager import get_config
from debug_logger import get_logger
import theme

logger = get_logger()


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
        "When checked, the progress bar and waveform show only the\n"
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

    # Read-only info section
    info_w = QWidget()
    grid = QGridLayout(info_w)
    grid.setColumnStretch(1, 1)
    pairs = [
        ("Event:", annotation["Event"]),
        ("Type:", atype),
        ("Video:", annotator.store.video_name),
    ]
    if atype == "State":
        pairs.append(("Mutually Exclusive:",
                       annotation.get("Mutually_Exclusive", "False")))
    for row, (lbl, val) in enumerate(pairs):
        l = QLabel(lbl); l.setStyleSheet("font-weight: bold;")
        grid.addWidget(l, row, 0)
        grid.addWidget(QLabel(val), row, 1)
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

        if atype == "State":
            try:
                new_start = parse_time(vals["H_Start"])
                new_end = parse_time(vals["H_End"])
            except ValueError:
                show_message(annotator.parent, "Invalid Time Format",
                             "Could not parse time values.")
                return
            if (annotation["Event"] != vals.get("Event", annotation["Event"])
                    or annotation["start_time"] != new_start
                    or annotation["end_time"] != new_end):
                annotation["Manual_Edit"] = True
            annotation["start_time"] = new_start
            annotation["end_time"] = new_end
            annotation["Notes"] = new_note
        else:
            if annotation["time"] != vals["H_Start"]:
                annotation["Manual_Edit"] = True
            annotation["time"] = vals["H_Start"]
            annotation["Notes"] = new_note

        if not annotator.store.save_sorted_annotations():
            annotation.update(originals)
            return

        annotator._update_annotations()
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
    VIDEO_PROPS = ("brightness", "contrast", "gamma", "saturation", "hue")

    # Snapshot current values for Cancel rollback
    vid_originals = {}
    for prop in VIDEO_PROPS:
        try:
            vid_originals[prop] = int(getattr(annotator.player, prop, 0) or 0)
        except Exception:
            vid_originals[prop] = 0

    aud_originals = {
        "volume": int(annotator.player.volume or 100),
        "audio_delay": float(annotator.player.audio_delay or 0),
        "audio_pitch_correction": bool(
            getattr(annotator.player, "audio_pitch_correction", True)),
        "af": str(annotator.player.af or ""),
    }

    cfg = get_config()
    per_video = annotator.store.load_video_settings()
    global_settings = cfg.get_video_settings()

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Audio && Video Settings")
    _apply_dialog_theme(dlg)
    dlg.resize(500, 520)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(8)

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

        slider = QSlider(Qt.Orientation.Horizontal)
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

        reset_btn = QPushButton("\u21BA")
        reset_btn.clicked.connect(
            lambda _, p=prop: vid_sliders[p].setValue(0))
        vid_layout.addWidget(reset_btn, row, 3)

    layout.addWidget(vid_group)

    # --- Audio controls ---
    aud_group = QGroupBox("Audio")
    aud_layout = QGridLayout(aud_group)
    aud_layout.setColumnStretch(1, 1)

    # Volume (0-200)
    aud_layout.addWidget(QLabel("Volume:"), 0, 0)
    vol_slider = QSlider(Qt.Orientation.Horizontal)
    vol_slider.setMinimum(0)
    vol_slider.setMaximum(200)
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
    vol_reset = QPushButton("\u21BA")
    vol_reset.clicked.connect(lambda: vol_slider.setValue(100))
    aud_layout.addWidget(vol_reset, 0, 3)

    # Audio delay (-2.0 to +2.0 seconds, stored as int ms in slider)
    aud_layout.addWidget(QLabel("A/V Sync (s):"), 1, 0)
    delay_slider = QSlider(Qt.Orientation.Horizontal)
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
    delay_reset = QPushButton("\u21BA")
    delay_reset.clicked.connect(lambda: delay_slider.setValue(0))
    aud_layout.addWidget(delay_reset, 1, 3)

    # Pitch shift (-12 to +12 semitones)
    import math
    aud_layout.addWidget(QLabel("Pitch (semitones):"), 2, 0)
    pitch_slider = QSlider(Qt.Orientation.Horizontal)
    pitch_slider.setMinimum(-12)
    pitch_slider.setMaximum(12)
    pitch_slider.setTickInterval(1)
    pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    pitch_slider.setStyleSheet(_slider_style)
    pitch_slider.setValue(0)
    aud_layout.addWidget(pitch_slider, 2, 1)
    pitch_lbl = QLabel("0")
    pitch_lbl.setFixedWidth(30)
    pitch_lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    aud_layout.addWidget(pitch_lbl, 2, 2)
    pitch_reset = QPushButton("\u21BA")
    pitch_reset.clicked.connect(lambda: pitch_slider.setValue(0))
    aud_layout.addWidget(pitch_reset, 2, 3)

    # Pitch correction checkbox
    from PySide6.QtWidgets import QCheckBox
    pitch_cb = QCheckBox("Maintain pitch when speed changes")
    pitch_cb.setChecked(aud_originals["audio_pitch_correction"])
    aud_layout.addWidget(pitch_cb, 3, 0, 1, 4)

    layout.addWidget(aud_group)

    # --- Video scope selection ---
    scope_group = QGroupBox("Video settings apply to:")
    scope_layout = QHBoxLayout(scope_group)
    all_radio = QRadioButton("All Videos")
    video_radio = QRadioButton("This Video Only")
    scope_layout.addWidget(all_radio)
    scope_layout.addWidget(video_radio)
    layout.addWidget(scope_group)

    # --- Buttons ---
    btn_frame = QWidget()
    btn_lay = QHBoxLayout(btn_frame)
    save_btn = QPushButton("Save")
    cancel_btn = QPushButton("Cancel")
    btn_lay.addStretch()
    btn_lay.addWidget(save_btn)
    btn_lay.addWidget(cancel_btn)
    layout.addWidget(btn_frame)

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

    def _on_scope_changed():
        if all_radio.isChecked():
            _load_scope_values(global_settings)
        else:
            _load_scope_values(per_video or {})

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
    all_radio.toggled.connect(lambda _: _on_scope_changed())

    def _save():
        # Video
        current = {prop: vid_sliders[prop].value() for prop in VIDEO_PROPS}
        if all_radio.isChecked():
            cfg.update_video_settings(current)
        else:
            annotator.store.save_video_settings(current)
        # Audio
        cfg.set_volume(vol_slider.value())
        # Update the panel slider to match
        if hasattr(annotator, '_volume_slider'):
            annotator._volume_slider.blockSignals(True)
            annotator._volume_slider.setValue(
                min(vol_slider.value(), annotator._volume_slider.maximum()))
            annotator._volume_slider.blockSignals(False)
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
        annotator.player.af = aud_originals.get("af", "")
        dlg.reject()

    save_btn.clicked.connect(_save)
    cancel_btn.clicked.connect(_cancel)

    # Set initial scope and load values
    if per_video:
        video_radio.setChecked(True)
        _load_scope_values(per_video)
    else:
        all_radio.setChecked(True)
        _load_scope_values(global_settings)

    dlg.finished.connect(lambda _result: dlg.deleteLater())
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

    annotator.dialog_open = True
    sel = annotator.store.state_events[annotator.selected_index]

    if sel["end_time"] is None:
        show_message(annotator, "Edit Error",
                           "Please end the state event before editing.")
        return

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
    cfg = get_config()

    colors = {
        "state_highlight": (QColor(h) if (h := cfg.get_state_highlight_color())
                            else theme.qcolor("active_color")),
        "point_highlight": (QColor(h) if (h := cfg.get_point_highlight_color())
                            else theme.qcolor("highlight_color")),
        "point_button": (QColor(h) if (h := cfg.get_point_button_color())
                         else theme.qcolor("float_point_bg")),
        "state_button": (QColor(h) if (h := cfg.get_state_button_color())
                         else theme.qcolor("float_state_bg")),
        "progress_fill": (QColor(h) if (h := cfg.get_progress_bar_color())
                          else theme.qcolor("progress_fill")),
        "button_hover": (QColor(h) if (h := cfg.get_button_hover_color())
                         else theme.qcolor("button_hover")),
        "waveform_fill": (QColor(h) if (h := cfg.get_waveform_color())
                          else QColor(0, 150, 255)),
    }
    selected_theme = [theme.current_theme()]

    dlg = QDialog(parent)
    dlg.setWindowTitle("Appearance")
    _apply_dialog_theme(dlg)
    dlg.resize(380, 560)

    main_lay = QVBoxLayout(dlg)
    main_lay.setContentsMargins(20, 15, 20, 15)
    main_lay.setSpacing(10)

    swatches = {}

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

    # Theme section
    main_lay.addWidget(_section("Theme"))
    theme_row = QHBoxLayout()
    theme_row.setSpacing(12)
    theme_btns = []

    checked_style = (
        "QPushButton { font-weight: bold; border: 2px solid white;"
        "  border-radius: 4px; padding: 4px 12px; }"
    )
    unchecked_style = (
        "QPushButton { border: 1px solid grey; border-radius: 4px;"
        "  padding: 4px 12px; }"
    )

    def _update_theme_btns():
        for b in theme_btns:
            b.setStyleSheet(
                checked_style if b.text().lower() == selected_theme[0]
                else unchecked_style)

    for name in ("system", "dark", "light"):
        btn = QPushButton(name.capitalize())
        btn.clicked.connect(
            lambda checked, n=name: _select_theme(n))
        theme_btns.append(btn)
        theme_row.addWidget(btn)
    theme_row.addStretch()
    main_lay.addLayout(theme_row)
    _update_theme_btns()

    def _select_theme(name):
        selected_theme[0] = name
        _update_theme_btns()

    # Color grid
    grid = QGridLayout()
    grid.setSpacing(8)

    row = 0
    grid.addWidget(_section("Annotation Highlights"), row, 0, 1, 2)
    row += 1
    grid.addWidget(QLabel("State Event:"), row, 0)
    grid.addWidget(_make_swatch("state_highlight"), row, 1)
    row += 1
    grid.addWidget(QLabel("Point Event:"), row, 0)
    grid.addWidget(_make_swatch("point_highlight"), row, 1)

    row += 1
    grid.addWidget(_section("Event Buttons"), row, 0, 1, 2)
    row += 1
    grid.addWidget(QLabel("Point Buttons:"), row, 0)
    grid.addWidget(_make_swatch("point_button"), row, 1)
    row += 1
    grid.addWidget(QLabel("State Buttons:"), row, 0)
    grid.addWidget(_make_swatch("state_button"), row, 1)
    row += 1
    grid.addWidget(QLabel("Button Opacity:"), row, 0)
    event_opacity_slider = QSlider(Qt.Orientation.Horizontal)
    event_opacity_slider.setRange(10, 100)
    event_opacity_slider.setValue(int(cfg.get_event_button_opacity() * 100))
    event_opacity_slider.setMaximumWidth(120)
    grid.addWidget(event_opacity_slider, row, 1)

    row += 1
    grid.addWidget(_section("Interface"), row, 0, 1, 2)
    row += 1
    grid.addWidget(QLabel("Progress Bar:"), row, 0)
    grid.addWidget(_make_swatch("progress_fill"), row, 1)
    row += 1
    grid.addWidget(QLabel("Button Hover:"), row, 0)
    grid.addWidget(_make_swatch("button_hover"), row, 1)

    row += 1
    grid.addWidget(_section("Waveform"), row, 0, 1, 2)
    row += 1
    grid.addWidget(QLabel("Waveform Color:"), row, 0)
    grid.addWidget(_make_swatch("waveform_fill"), row, 1)
    row += 1
    grid.addWidget(QLabel("Waveform Opacity:"), row, 0)
    waveform_opacity_slider = QSlider(Qt.Orientation.Horizontal)
    waveform_opacity_slider.setRange(10, 100)
    waveform_opacity_slider.setValue(int(cfg.get_waveform_opacity() * 100))
    waveform_opacity_slider.setMaximumWidth(120)
    grid.addWidget(waveform_opacity_slider, row, 1)
    row += 1
    grid.addWidget(QLabel("Waveform Height:"), row, 0)
    waveform_height_slider = QSlider(Qt.Orientation.Horizontal)
    waveform_height_slider.setRange(10, 30)
    waveform_height_slider.setValue(int(cfg.get_waveform_height_multiplier() * 10))
    waveform_height_slider.setMaximumWidth(120)
    grid.addWidget(waveform_height_slider, row, 1)

    grid.setColumnStretch(0, 1)
    main_lay.addLayout(grid)

    # Reset + OK/Cancel
    def _reset():
        defaults = {
            "state_highlight": theme.base_qcolor("active_color"),
            "point_highlight": theme.base_qcolor("highlight_color"),
            "point_button": theme.base_qcolor("float_point_bg"),
            "state_button": theme.base_qcolor("float_state_bg"),
            "progress_fill": theme.base_qcolor("progress_fill"),
            "button_hover": theme.base_qcolor("button_hover"),
            "waveform_fill": QColor(0, 150, 255),
        }
        for key, c in defaults.items():
            colors[key] = c
            _update_swatch(swatches[key], c)
        event_opacity_slider.setValue(40)
        waveform_opacity_slider.setValue(80)
        waveform_height_slider.setValue(20)

    main_lay.addStretch()
    btn_row = QHBoxLayout()
    reset_btn = QPushButton("Reset to Defaults")
    reset_btn.clicked.connect(_reset)
    btn_row.addWidget(reset_btn)
    btn_row.addStretch()
    ok_btn = QPushButton("OK")
    ok_btn.clicked.connect(dlg.accept)
    btn_row.addWidget(ok_btn)
    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)
    main_lay.addLayout(btn_row)

    def _on_finished(result):
        dlg.deleteLater()
        if result == QDialog.DialogCode.Accepted:
            # Save all settings
            cfg.set_state_highlight_color(colors["state_highlight"].name())
            cfg.set_point_highlight_color(colors["point_highlight"].name())
            cfg.set_point_button_color(colors["point_button"].name())
            cfg.set_state_button_color(colors["state_button"].name())
            cfg.set_progress_bar_color(colors["progress_fill"].name())
            cfg.set_button_hover_color(colors["button_hover"].name())
            cfg.set_waveform_color(colors["waveform_fill"].name())
            cfg.set_event_button_opacity(event_opacity_slider.value() / 100.0)
            cfg.set_waveform_opacity(waveform_opacity_slider.value() / 100.0)
            cfg.set_waveform_height_multiplier(waveform_height_slider.value() / 10.0)
            theme.set_override("button_hover", colors["button_hover"].name())

            # Apply theme (always, so overrides take effect)
            new_theme = selected_theme[0]
            theme.load_theme(new_theme)
            cfg.update_theme(new_theme)

            if on_accept:
                on_accept(new_theme, colors)

    dlg.finished.connect(_on_finished)
    dlg.open()
    return dlg
