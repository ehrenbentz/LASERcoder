import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QGridLayout, QDialogButtonBox, QMessageBox, QWidget,
    QRadioButton, QSlider, QFrame,
)
from PySide6.QtCore import Qt, QTimer

from annotation_store import format_time_human, parse_time
from config_manager import get_config
from debug_logger import get_logger
import theme

logger = get_logger()


def _apply_dialog_theme(dialog):
    theme.apply_dialog_theme(dialog)


def _cleanup_dialog(dlg, annotator):
    """Clean up after a dialog closes."""
    logger.debug("Dialog cleanup: %s", dlg.windowTitle())
    dlg.deleteLater()





# ======================================================================
# Coding-start / duration dialog
# ======================================================================

def show_coding_start_dialog(annotator):
    """Present the "Set Coding Start and Duration" dialog.

    Modifies annotator.coding_start / coding_duration / coding_end
    directly when the user clicks Save.
    """
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
    clear_btn = QPushButton("Clear Coding Settings")

    def _clear():
        start_input.clear(); hours_in.clear(); mins_in.clear(); secs_in.clear()
        et_input.clear(); dur_end_value.setText("Not set"); et_dur_value.setText("Not set")
        annotator.coding_start = 0
        annotator.coding_duration = None
        annotator.coding_end = None
        annotator.update_coding_info_display()

    clear_btn.clicked.connect(_clear)
    grid.addWidget(clear_btn, 5, 0, 1, 3)

    layout.addWidget(coding_group)

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
    layout.addWidget(bbox)

    def _on_finished(_result):
        annotator.dialog_open = False
        dialog.deleteLater()
        if hasattr(annotator, "player") and annotator.player and was_playing:
            annotator.player.pause = False

    dialog.finished.connect(_on_finished)
    dialog.open()


# ======================================================================
# Add-note dialog
# ======================================================================

def show_note_dialog(annotator):
    """Show dialog to add/edit a note on the selected annotation."""
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


# ======================================================================
# View annotation details
# ======================================================================

def show_annotation_details(annotator):
    """Display a read-only details dialog for the selected annotation."""
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
    dlg.resize(500, 400)

    main_lay = QVBoxLayout(dlg)
    main_lay.setContentsMargins(15, 15, 15, 15)

    details_w = QWidget()
    grid = QGridLayout(details_w)
    grid.setColumnStretch(1, 1)
    main_lay.addWidget(details_w)

    pairs = [
        ("Event:", annotation["Event"]),
        ("Type:", atype),
        ("Video:", annotator.store.video_name),
    ]

    if atype == "State":
        st = format_time_human(annotation["start_time"])
        et = format_time_human(annotation["end_time"]) if annotation["end_time"] is not None else "NA"
        dur = (format_time_human(annotation["end_time"] - annotation["start_time"])
               if annotation["end_time"] is not None and annotation["start_time"] is not None
               else "NA")
        pairs += [
            ("Start Time:", st), ("End Time:", et), ("Duration:", dur),
            ("Mutually Exclusive:", annotation.get("Mutually_Exclusive", "False")),
        ]
    else:
        pairs.append(("Time:", annotation["time"]))

    if "Manual_Edit" in annotation:
        pairs.append(("Manually Edited:", str(annotation["Manual_Edit"])))

    for row, (lbl, val) in enumerate(pairs):
        l = QLabel(lbl); l.setStyleSheet("font-weight: bold;")
        grid.addWidget(l, row, 0)
        grid.addWidget(QLabel(val), row, 1)

    sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    main_lay.addWidget(sep)

    main_lay.addWidget(QLabel("Notes:"))
    notes_box = QTextEdit()
    notes_box.setMinimumHeight(100)
    notes_box.setText(annotation.get("Notes", "").replace(" . ", "\n"))
    notes_box.setReadOnly(True)
    main_lay.addWidget(notes_box)

    btn_f = QWidget()
    btn_l = QHBoxLayout(btn_f)
    btn_l.setContentsMargins(0, 10, 0, 0)
    edit_btn = QPushButton("Edit")
    edit_btn.clicked.connect(lambda: (
        setattr(dlg, '_open_edit', True), dlg.accept()))
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.reject)
    btn_l.addWidget(edit_btn); btn_l.addStretch(); btn_l.addWidget(close_btn)
    main_lay.addWidget(btn_f)

    def _on_finished(_result):
        open_edit = getattr(dlg, '_open_edit', False)
        annotator.dialog_open = False
        dlg.deleteLater()
        if open_edit:
            show_comprehensive_edit(annotator, annotation, atype)

    dlg.finished.connect(_on_finished)
    dlg.open()


# ======================================================================
# Comprehensive edit dialog
# ======================================================================

def show_comprehensive_edit(annotator, annotation, annotation_type):
    """Open a combined timing + notes edit dialog."""
    if not annotator.store.check_file_access():
        if hasattr(annotator, "player") and annotator.player:
            annotator.player.pause = True
        annotator.on_write_error()
        return

    annotator.dialog_open = True

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle(f"Edit {annotation_type} Annotation")

    _apply_dialog_theme(dlg)
    dlg.resize(400, 500)

    main_lay = QVBoxLayout(dlg)
    main_lay.setContentsMargins(15, 15, 15, 15)

    form = QFormLayout()
    entries = {}
    fields = ["Event"]
    if annotation_type == "State":
        fields += ["H_Start", "H_End"]
    else:
        fields.append("H_Start")

    for field in fields:
        entry = QLineEdit()
        if field == "Event":
            entry.setText(annotation["Event"])
        elif field == "H_Start":
            if annotation_type == "State":
                entry.setText(format_time_human(annotation["start_time"]))
            else:
                entry.setText(annotation["time"])
        elif field == "H_End" and annotation["end_time"] is not None:
            entry.setText(format_time_human(annotation["end_time"]))
        form.addRow(field.replace("H_", "") + ":", entry)
        entries[field] = entry

    main_lay.addLayout(form)

    main_lay.addWidget(QLabel("Notes:"))
    existing = annotation.get("Notes", "").replace(" . ", "\n")
    notes_text = QTextEdit()
    notes_text.setMinimumHeight(150)
    notes_text.setText(existing)
    main_lay.addWidget(notes_text)

    # Store originals for rollback
    originals = {"Event": annotation["Event"], "Notes": annotation.get("Notes", "")}
    if annotation_type == "State":
        originals["start_time"] = annotation["start_time"]
        originals["end_time"] = annotation["end_time"]
    else:
        originals["time"] = annotation["time"]

    btn_f = QWidget()
    btn_l = QHBoxLayout(btn_f)

    def _save():
        if not annotator.store.check_file_access():
            annotator.on_write_error()
            return
        vals = {f: e.text().strip() for f, e in entries.items()}
        new_note = notes_text.toPlainText().strip().replace("\n", " . ")

        if annotation_type == "State":
            try:
                new_start = parse_time(vals["H_Start"])
                new_end = parse_time(vals["H_End"])
            except ValueError:
                show_message(annotator.parent, "Invalid Time Format",
                                   "Could not parse time values.")
                return
            if annotation["Event"] != vals["Event"] or annotation["start_time"] != new_start or annotation["end_time"] != new_end:
                annotation["Manual_Edit"] = True
            annotation["Event"] = vals["Event"]
            annotation["start_time"] = new_start
            annotation["end_time"] = new_end
            annotation["Notes"] = new_note
        else:
            if annotation["Event"] != vals["Event"] or annotation["time"] != vals["H_Start"]:
                annotation["Manual_Edit"] = True
            annotation["Event"] = vals["Event"]
            annotation["time"] = vals["H_Start"]
            annotation["Notes"] = new_note

        if not annotator.store.save_sorted_annotations():
            annotation.update(originals)
            return

        annotator.update_annotations()
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


# ======================================================================
# Simple edit dialogs (point / state)
# ======================================================================

def show_edit_point_dialog(annotator):
    """Edit a point annotation's name and time."""
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


def show_video_settings_dialog(annotator):
    """Show a dialog to adjust MPV video display properties."""
    PROPS = ("brightness", "contrast", "gamma", "saturation", "hue")

    # Snapshot current player values for Cancel rollback
    originals = {}
    for prop in PROPS:
        try:
            originals[prop] = int(getattr(annotator.player, prop, 0) or 0)
        except Exception:
            originals[prop] = 0

    cfg = get_config()
    per_video = annotator.store.load_video_settings()
    global_settings = cfg.get_video_settings()

    dlg = QDialog(annotator.parent)
    dlg.setWindowTitle("Video Settings")

    _apply_dialog_theme(dlg)
    dlg.resize(480, 380)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(8)

    # --- Sliders for each property ---
    sliders = {}
    value_labels = {}

    sliders_group = QGroupBox("Display Adjustments")
    sliders_layout = QGridLayout(sliders_group)
    sliders_layout.setColumnStretch(1, 1)

    for row, prop in enumerate(PROPS):
        lbl = QLabel(prop.capitalize() + ":")
        sliders_layout.addWidget(lbl, row, 0, Qt.AlignmentFlag.AlignLeft)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(-100)
        slider.setMaximum(100)
        slider.setTickInterval(25)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        sliders[prop] = slider
        sliders_layout.addWidget(slider, row, 1)

        val_lbl = QLabel("0")
        val_lbl.setFixedWidth(30)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_labels[prop] = val_lbl
        sliders_layout.addWidget(val_lbl, row, 2)

        reset_btn = QPushButton("↺")
        reset_btn.clicked.connect(lambda _, p=prop: sliders[p].setValue(0))
        sliders_layout.addWidget(reset_btn, row, 3)

    layout.addWidget(sliders_group)

    # --- Scope selection ---
    scope_group = QGroupBox("Apply to:")
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

    def _load_scope_values(settings):
        """Load settings dict into sliders and update player preview."""
        for prop in PROPS:
            val = int(settings.get(prop, 0)) if settings else 0
            sliders[prop].blockSignals(True)
            sliders[prop].setValue(val)
            sliders[prop].blockSignals(False)
            value_labels[prop].setText(str(val))
            try:
                setattr(annotator.player, prop, val)
            except Exception:
                pass

    def _on_scope_changed():
        if all_radio.isChecked():
            _load_scope_values(global_settings)
        else:
            _load_scope_values(per_video or {})

    def _on_slider_changed(val, prop):
        value_labels[prop].setText(str(val))
        try:
            setattr(annotator.player, prop, val)
        except Exception:
            pass

    for prop in PROPS:
        sliders[prop].valueChanged.connect(
            lambda val, p=prop: _on_slider_changed(val, p))

    all_radio.toggled.connect(lambda _: _on_scope_changed())

    def _save():
        current = {prop: sliders[prop].value() for prop in PROPS}
        if all_radio.isChecked():
            cfg.update_video_settings(current)
        else:
            annotator.store.save_video_settings(current)
        dlg.accept()

    def _cancel():
        for prop in PROPS:
            try:
                setattr(annotator.player, prop, originals[prop])
            except Exception:
                pass
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
    """Edit a state annotation's name, start, and end time."""
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


# ======================================================================
# Themed message box and input dialog
# ======================================================================

def show_message(parent, title, text, icon="warning", callback=None):
    """Show a themed QMessageBox.

    If *callback* is provided, uses open() (window-modal, non-blocking).
    The callback receives the QMessageBox result as its argument.

    If *callback* is None, falls back to exec() (application-modal, blocking)
    for callsites not yet migrated.
    """
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
        # Sync fallback for callers that haven't migrated to callbacks
        result = dlg.exec()
        dlg.deleteLater()
        return result


def get_text(parent, title, label, text="", callback=None):
    """Show a themed input dialog.

    If *callback* is provided, uses open() and calls callback(text, ok).
    If *callback* is None, falls back to exec() and returns (text, ok).
    """
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
        # Sync fallback for callers that haven't migrated to callbacks
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        result = line.text()
        dlg.deleteLater()
        return result, ok
