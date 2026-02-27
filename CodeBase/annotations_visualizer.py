# annotations_visualizer.py

import os
import colorsys
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                            QComboBox, QLabel, QSpinBox, QFileDialog, QFrame,
                            QMessageBox, QGroupBox, QCheckBox, QScrollArea,
                            QWidget, QSizePolicy, QColorDialog)
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint, QSize
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                        QLinearGradient, QPainterPath, QImage, QFontMetrics,
                        QPixmap, QIcon)

import theme

# ---------------------------------------------------------------------------
# Color palette: golden-angle spacing for distinct per-event hues
# ---------------------------------------------------------------------------
_HUE_ANGLE = 30
_HUE_OFFSET   = 30.0

def _generate_default_colors(event_names):
    cmap = {}
    for i, name in enumerate(sorted(event_names)):
        hue = (_HUE_OFFSET + i * _HUE_ANGLE) % 360
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.55, 0.65)
        cmap[name] = QColor(int(r * 255), int(g * 255), int(b * 255))
    return cmap

def _state_fill(base_color):
    c = QColor(base_color)
    c.setAlpha(225)
    return c.lighter(100)

def _state_border(base_color):
    return QColor(base_color).darker(140)

def _point_marker(base_color):
    return QColor(base_color).darker(110)

def _legend_swatch(base_color):
    return QColor(base_color)

def _make_color_icon(color, size=16):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color).darker(150), 1))
    p.setBrush(QBrush(color))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
    p.end()
    return QIcon(pm)


class AnnotationsVisualizer(QFrame):
    """Timeline visualization widget for annotations."""

    def __init__(self, parent, video_name, state_events, point_events,
                 video_duration, parse_time_func, bounds=None):
        super().__init__(parent)
        self.video_name = video_name
        self.parse_time_func = parse_time_func
        self._full_video_duration = video_duration

        # Bounds info
        self.bounds = bounds or {"has_bounds": False, "whole_video": True}
        self.has_bounds = self.bounds.get("has_bounds", False)
        self.start_bound = self.bounds.get("start", 0) if self.has_bounds else 0
        self.end_bound = self.bounds.get("end") if self.has_bounds else None

        # Display options
        self.zero_base_time = False
        self.show_section_headers = True
        self.show_title = True
        self.show_legend = True

        # Always store the complete unfiltered events
        self._all_state_events = list(state_events)
        self._all_point_events = list(point_events)

        # Start in whole-video mode
        self.whole_video = True
        self._apply_range()

        # Active (visible) events — start with all
        self.state_events = list(self._raw_state_events)
        self.point_events = list(self._raw_point_events)

        # Visual constants
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setStyleSheet(f"background-color: {theme.color('viz_bg')};")

        self.title_height = 44
        self.axis_height = 36
        self.track_height = 32
        self.track_spacing = 6
        self.margin_left = 160
        self.margin_right = 50
        self.margin_top = 10
        self.margin_bottom = 50
        self.section_header_height = 28
        self.section_spacing = 14
        self.legend_row_height = 22

        # Build color map from ALL events {name: QColor}
        all_events = set()
        for e in self._all_state_events:
            if e['Event']:
                all_events.add(e['Event'])
        for e in self._all_point_events:
            if e['Event']:
                all_events.add(e['Event'])
        self._color_map = _generate_default_colors(all_events)

        # Canonical order lists — all known events in each type
        self._state_order = sorted(
            {e['Event'] for e in self._all_state_events if e['Event']})
        self._point_order = sorted(
            {e['Event'] for e in self._all_point_events if e['Event']})

        # Compute visible event name lists and height
        self.state_event_names, self.point_event_names = self._unique_events()
        self._recalc_height()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def update_data(self, state_events, point_events):
        """Re-set visible events and repaint."""
        self.state_events = list(state_events)
        self.point_events = list(point_events)
        self.state_event_names, self.point_event_names = self._unique_events()
        self._recalc_height()
        self.update()

    def set_event_color(self, name, color):
        self._color_map[name] = QColor(color)
        self.update()

    def set_segment_mode(self, coded_segment_only):
        self.whole_video = not coded_segment_only
        self._apply_range()
        self.state_events = list(self._raw_state_events)
        self.point_events = list(self._raw_point_events)
        self.state_event_names, self.point_event_names = self._unique_events()
        self._recalc_height()
        self.update()

    def set_event_order(self, state_order, point_order):
        """Set custom display order for events and repaint."""
        self._state_order = list(state_order)
        self._point_order = list(point_order)
        self.state_event_names, self.point_event_names = self._unique_events()
        self._recalc_height()
        self.update()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_range(self):
        if self.has_bounds and not self.whole_video:
            self.effective_start = self.start_bound
            self.effective_end = self.end_bound
            self._raw_state_events = self._filter_state_events(self._all_state_events)
            self._raw_point_events = self._filter_point_events(self._all_point_events)
            if self.effective_end is not None:
                self.effective_duration = self.effective_end - self.effective_start
            else:
                self.effective_duration = self._full_video_duration - self.effective_start
        else:
            self.effective_start = 0
            self.effective_end = None
            self.effective_duration = self._full_video_duration
            self._raw_state_events = list(self._all_state_events)
            self._raw_point_events = list(self._all_point_events)
        self.video_duration = self.effective_duration

    def _unique_events(self):
        """Return visible events in custom order."""
        visible_state = {e['Event'] for e in self.state_events if e['Event']}
        visible_point = {e['Event'] for e in self.point_events if e['Event']}
        state = [n for n in self._state_order if n in visible_state]
        point = [n for n in self._point_order if n in visible_point]
        return state, point

    def _recalc_height(self):
        title_h = self.title_height if self.show_title else 0
        total = len(self.state_event_names) + len(self.point_event_names)
        if total == 0:
            h = title_h + self.axis_height + self.margin_top + self.margin_bottom
        else:
            sections = (1 if self.state_event_names else 0) + (1 if self.point_event_names else 0)
            tracks_h = total * (self.track_height + self.track_spacing)
            if self.show_section_headers:
                headers_h = sections * self.section_header_height
            else:
                headers_h = 0
            gap = self.section_spacing if sections > 1 else 0
            legend_h = self._legend_height()
            h = (title_h + self.axis_height + tracks_h +
                 headers_h + gap + self.margin_top + self.margin_bottom + legend_h)
        self.setMinimumHeight(max(h, 200))

    def _legend_height(self):
        if not self.show_legend:
            return 0
        all_names = self.state_event_names + self.point_event_names
        unique = list(dict.fromkeys(all_names))  # preserve order, deduplicate
        if not unique:
            return 0
        items_per_row = max(1, (max(self.width(), 800) - self.margin_left - self.margin_right) // 160)
        rows = (len(unique) + items_per_row - 1) // items_per_row
        return 10 + rows * self.legend_row_height

    def _filter_state_events(self, events):
        if not (self.has_bounds and not self.whole_video):
            return events
        filtered = []
        for event in events:
            st = event.get('start_time')
            et = event.get('end_time')
            if et is not None and et < self.effective_start:
                continue
            if self.effective_end is not None and st > self.effective_end:
                continue
            adj = event.copy()
            if st < self.effective_start:
                adj['start_time'] = self.effective_start
            if et is not None and self.effective_end is not None and et > self.effective_end:
                adj['end_time'] = self.effective_end
            adj['start_time'] -= self.effective_start
            if adj['end_time'] is not None:
                adj['end_time'] -= self.effective_start
            filtered.append(adj)
        return filtered

    def _filter_point_events(self, events):
        if not (self.has_bounds and not self.whole_video):
            return events
        filtered = []
        for event in events:
            if 'raw_time' in event and event['raw_time'] is not None:
                tv = event['raw_time']
            else:
                tv = self.parse_time_func(event['time'])
            if tv < self.effective_start:
                continue
            if self.effective_end is not None and tv > self.effective_end:
                continue
            adj = event.copy()
            adj['raw_time'] = tv - self.effective_start
            filtered.append(adj)
        return filtered

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint(painter, self.width(), self.height(), for_export=False)
        painter.end()

    def _paint(self, painter, w, h, for_export=False):
        bg = QColor("#ffffff") if for_export else theme.qcolor("viz_bg")
        text_color = QColor("#282828") if for_export else theme.qcolor("viz_text")
        grid_color = QColor("#c8c8c8") if for_export else theme.qcolor("viz_grid")
        track_bg = QColor("#f0f0f0") if for_export else theme.qcolor("viz_track")
        track_bg_alt = QColor("#e8e8e8") if for_export else QColor(
            theme.qcolor("viz_track").darker(105))
        header_bg = QColor("#e6e6e6") if for_export else theme.qcolor("viz_header_bg")
        header_text_c = QColor("#464646") if for_export else theme.qcolor("viz_header_text")
        axis_color = QColor("#404040") if for_export else text_color

        painter.fillRect(QRectF(0, 0, w, h), bg)

        axis_width = w - self.margin_left - self.margin_right
        tick_count = max(4, min(12, int(axis_width / 100)))

        # ---- Title ----
        if self.show_title:
            painter.setPen(text_color)
            title_font = QFont("Arial", 16, QFont.Weight.Bold)
            painter.setFont(title_font)
            painter.drawText(
                QRectF(0, self.margin_top, w, self.title_height - 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                self.video_name,
            )

        # ---- Tracks ----
        title_h = self.title_height if self.show_title else 0
        y = self.margin_top + title_h
        track_font = QFont("Arial", 10)
        track_font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        section_font = QFont("Arial", 11, QFont.Weight.Bold)
        track_idx = 0

        def draw_grid_lines(y_start, y_end):
            painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DotLine))
            for i in range(tick_count + 1):
                gx = self.margin_left + (axis_width * i / tick_count)
                painter.drawLine(int(gx), int(y_start), int(gx), int(y_end))

        # State events section
        if self.state_event_names:
            if self.show_section_headers:
                hdr_rect = QRectF(self.margin_left - 10, y, axis_width + 20,
                                  self.section_header_height)
                grad = QLinearGradient(hdr_rect.topLeft(), hdr_rect.bottomLeft())
                grad.setColorAt(0, header_bg)
                grad.setColorAt(1, header_bg.darker(108))
                painter.fillRect(hdr_rect, grad)
                painter.setPen(header_text_c)
                painter.setFont(section_font)
                painter.drawText(hdr_rect, Qt.AlignmentFlag.AlignCenter,
                                 "State Events")
                y += self.section_header_height + 4

            painter.setFont(track_font)
            for event in self.state_event_names:
                row_bg = track_bg_alt if track_idx % 2 else track_bg
                track_idx += 1

                track_rect = QRectF(self.margin_left, y, axis_width,
                                    self.track_height)
                painter.fillRect(track_rect, row_bg)
                draw_grid_lines(y, y + self.track_height)

                painter.setPen(text_color)
                painter.setFont(track_font_bold)
                text_rect = QRectF(4, y, self.margin_left - 14, self.track_height)
                painter.drawText(text_rect,
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 event)
                painter.setFont(track_font)

                base = self._color_map.get(event, QColor("#6496dc"))
                fill = _state_fill(base)
                border_c = _state_border(base)

                for ev in self.state_events:
                    if ev['Event'] != event or ev['start_time'] is None:
                        continue
                    sx = self._time_to_x(ev['start_time'], axis_width)
                    if ev['end_time'] is None:
                        ex = self.margin_left + axis_width
                    else:
                        ex = self._time_to_x(ev['end_time'], axis_width)

                    bar = QRectF(sx, y + 3, max(ex - sx, 2), self.track_height - 6)
                    path = QPainterPath()
                    path.addRoundedRect(bar, 2, 2)
                    painter.fillPath(path, fill)
                    painter.setPen(QPen(border_c, 1))
                    painter.drawPath(path)

                painter.setPen(QPen(grid_color, 0.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(track_rect)

                y += self.track_height + self.track_spacing

            if self.point_event_names:
                y += self.section_spacing - self.track_spacing

        # Point events section
        if self.point_event_names:
            if self.show_section_headers:
                hdr_rect = QRectF(self.margin_left - 10, y, axis_width + 20,
                                  self.section_header_height)
                grad = QLinearGradient(hdr_rect.topLeft(), hdr_rect.bottomLeft())
                grad.setColorAt(0, header_bg)
                grad.setColorAt(1, header_bg.darker(108))
                painter.fillRect(hdr_rect, grad)
                painter.setPen(header_text_c)
                painter.setFont(section_font)
                painter.drawText(hdr_rect, Qt.AlignmentFlag.AlignCenter,
                                 "Point Events")
                y += self.section_header_height + 4

            painter.setFont(track_font)
            for event in self.point_event_names:
                row_bg = track_bg_alt if track_idx % 2 else track_bg
                track_idx += 1

                track_rect = QRectF(self.margin_left, y, axis_width,
                                    self.track_height)
                painter.fillRect(track_rect, row_bg)
                draw_grid_lines(y, y + self.track_height)

                painter.setPen(text_color)
                painter.setFont(track_font_bold)
                text_rect = QRectF(4, y, self.margin_left - 14, self.track_height)
                painter.drawText(text_rect,
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 event)
                painter.setFont(track_font)

                base = self._color_map.get(event, QColor("#dc5050"))
                pc = _point_marker(base)

                for ev in self.point_events:
                    if ev['Event'] != event:
                        continue
                    if 'raw_time' in ev and ev['raw_time'] is not None:
                        tv = ev['raw_time']
                    else:
                        tv = self.parse_time_func(ev['time'])
                    cx = self._time_to_x(tv, axis_width)

                    painter.setPen(QPen(pc, 2.5))
                    painter.drawLine(int(cx), int(y + 2),
                                     int(cx), int(y + self.track_height - 2))

                painter.setPen(QPen(grid_color, 0.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(track_rect)

                y += self.track_height + self.track_spacing

        # ---- Time axis (X axis) at bottom of tracks ----
        axis_y = y + 2
        tick_font = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(tick_font)

        painter.setPen(QPen(axis_color, 2.5))
        painter.drawLine(int(self.margin_left), int(axis_y),
                         int(self.margin_left + axis_width), int(axis_y))

        for i in range(tick_count + 1):
            x = self.margin_left + (axis_width * i / tick_count)
            tv = self.video_duration * i / tick_count

            if self.has_bounds and not self.whole_video and not self.zero_base_time:
                display_time = tv + self.effective_start
            else:
                display_time = tv

            painter.setPen(QPen(axis_color, 2))
            painter.drawLine(int(x), int(axis_y), int(x), int(axis_y + 6))

            painter.setPen(text_color)
            painter.drawText(
                QRectF(x - 50, axis_y + 7, 100, 18),
                Qt.AlignmentFlag.AlignCenter,
                self._fmt(display_time),
            )

        # ---- Legend ----
        if self.show_legend:
            legend_y = axis_y + self.axis_height
            self._draw_legend(painter, legend_y, w, text_color)

    def _draw_legend(self, painter, y, w, text_color):
        all_visible = list(dict.fromkeys(
            self.state_event_names + self.point_event_names))
        if not all_visible:
            return

        legend_font = QFont("Arial", 9)
        painter.setFont(legend_font)
        fm = QFontMetrics(legend_font)

        swatch_size = 12
        item_padding = 20
        x = self.margin_left
        max_x = w - self.margin_right

        for name in all_visible:
            base = self._color_map.get(name, QColor("#888888"))
            label_w = fm.horizontalAdvance(name)
            item_w = swatch_size + 6 + label_w + item_padding

            if x + item_w > max_x and x > self.margin_left:
                x = self.margin_left
                y += self.legend_row_height

            swatch_color = _legend_swatch(base)
            painter.fillRect(QRectF(x, y + 2, swatch_size, swatch_size), swatch_color)
            painter.setPen(QPen(swatch_color.darker(140), 1))
            painter.drawRect(QRectF(x, y + 2, swatch_size, swatch_size))

            painter.setPen(text_color)
            painter.drawText(QRectF(x + swatch_size + 4, y,
                                    label_w + 4, self.legend_row_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             name)
            x += item_w

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _time_to_x(self, time_value, axis_width):
        if self.video_duration <= 0:
            ratio = 0
        else:
            ratio = max(0.0, min(1.0, time_value / self.video_duration))
        return self.margin_left + ratio * axis_width

    def _fmt(self, seconds):
        s = int(round(seconds))
        if s >= 3600:
            return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
        return f"{s // 60}:{s % 60:02d}"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def render_to_image(self, image_format="PNG", dpi=300):
        scale = dpi / 96.0
        pw = int(self.width() * scale)
        ph = int(self.height() * scale)

        image = QImage(pw, ph, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)
        self._paint(painter, self.width(), self.height(), for_export=True)
        painter.end()
        return image, None


# ======================================================================
# Dialog
# ======================================================================

def show_visualization_dialog(parent, video_name, state_events, point_events,
                              video_duration, parse_time_func, center_window_func,
                              output_dir, bounds=None, store=None):
    """Create and show the visualization dialog with event selection panel."""
    try:
        viz_dialog = QDialog(parent)
        viz_dialog.setStyleSheet(theme.dialog_stylesheet())

        viz_dialog.setWindowTitle(f"Annotation Visualization - {video_name}")
        viz_dialog.setModal(True)

        screen = parent.screen()
        viz_width = int(screen.availableGeometry().width() * 0.9)
        viz_height = int(screen.availableGeometry().height() * 0.9)
        center_window_func(viz_dialog, viz_width, viz_height)

        outer = QVBoxLayout(viz_dialog)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        # ---- Selection panel ----
        select_group = QGroupBox("Select Annotations")
        select_group.setFixedWidth(270)
        select_layout = QVBoxLayout(select_group)
        select_layout.setContentsMargins(6, 10, 6, 6)
        select_layout.setSpacing(4)

        # Toggle all button
        toggle_btn = QPushButton("Deselect All")
        select_layout.addWidget(toggle_btn)

        # Build the timeline widget first so we can reference its order/colors
        timeline_widget = AnnotationsVisualizer(
            None, video_name, state_events, point_events,
            video_duration, parse_time_func, bounds=bounds,
        )

        # Load any previously saved event colors
        if store is not None:
            saved_colors = store.load_viz_colors()
            for bname, hex_color in saved_colors.items():
                if bname in timeline_widget._color_map:
                    timeline_widget._color_map[bname] = QColor(hex_color)

        # Canonical order from the visualizer
        state_order = list(timeline_widget._state_order)
        point_order = list(timeline_widget._point_order)

        # ---- Scrollable event rows ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # We'll store per-event widgets and rebuild the layout on reorder
        checkboxes = {}      # name -> QCheckBox
        color_buttons = {}   # name -> QPushButton

        arrow_btn_style = (
            "QPushButton { border: none; padding: 0px;"
            " min-width: 18px; max-width: 18px;"
            " min-height: 14px; max-height: 14px;"
            " font-size: 10px; }"
            "QPushButton:hover { background-color: rgba(128,128,128,80); }"
        )
        color_btn_style = (
            "QPushButton { border: 1px solid grey; border-radius: 2px;"
            " padding: 0px; min-width: 20px; max-width: 20px;"
            " min-height: 20px; max-height: 20px; }"
            "QPushButton:hover { border: 1px solid white; }"
        )

        # Load saved unchecked events
        saved_unchecked = set()
        if store is not None:
            saved_unchecked = set(store.load_viz_unchecked())

        # Create widgets for all events (state + point)
        all_names = state_order + point_order
        for name in all_names:
            cb = QCheckBox(name)
            cb.setChecked(name not in saved_unchecked)
            checkboxes[name] = cb

            color_btn = QPushButton()
            color_btn.setFixedSize(20, 20)
            color_btn.setStyleSheet(color_btn_style)
            base = timeline_widget._color_map.get(name, QColor("#888888"))
            color_btn.setIcon(_make_color_icon(base))
            color_btn.setIconSize(QSize(16, 16))
            color_btn.setToolTip(f"Change color for {name}")
            color_buttons[name] = color_btn

        # Container widget that gets rebuilt on reorder
        cb_container = [None]  # mutable ref

        def build_event_list():
            """(Re)build the scroll area contents from current order lists."""
            old = cb_container[0]
            if old is not None:
                old.setParent(None)
                old.deleteLater()

            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)

            # State section label
            if state_order:
                lbl = QLabel("State")
                lbl.setStyleSheet(
                    f"color: {theme.color('text_secondary')};"
                    " font-size: 9px; font-weight: bold;"
                    " background: transparent; padding-left: 2px;")
                layout.addWidget(lbl)
                for i, name in enumerate(state_order):
                    layout.addWidget(
                        _make_row(name, i, state_order, "state"))

            # Point section label
            if point_order:
                if state_order:
                    layout.addSpacing(6)
                lbl = QLabel("Point")
                lbl.setStyleSheet(
                    f"color: {theme.color('text_secondary')};"
                    " font-size: 9px; font-weight: bold;"
                    " background: transparent; padding-left: 2px;")
                layout.addWidget(lbl)
                for i, name in enumerate(point_order):
                    layout.addWidget(
                        _make_row(name, i, point_order, "point"))

            layout.addStretch(1)
            scroll.setWidget(container)
            cb_container[0] = container

        def _make_row(name, idx, order_list, section):
            """Build a single event row: [up][down] [checkbox] [color]."""
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            # Arrow column
            arrow_col = QVBoxLayout()
            arrow_col.setContentsMargins(0, 0, 0, 0)
            arrow_col.setSpacing(0)

            up_btn = QPushButton("\u25B2")
            up_btn.setStyleSheet(arrow_btn_style)
            up_btn.setEnabled(idx > 0)
            up_btn.setToolTip("Move up")
            up_btn.clicked.connect(
                lambda _, n=name, s=section: _move(n, s, -1))

            down_btn = QPushButton("\u25BC")
            down_btn.setStyleSheet(arrow_btn_style)
            down_btn.setEnabled(idx < len(order_list) - 1)
            down_btn.setToolTip("Move down")
            down_btn.clicked.connect(
                lambda _, n=name, s=section: _move(n, s, 1))

            arrow_col.addWidget(up_btn)
            arrow_col.addWidget(down_btn)

            row_layout.addLayout(arrow_col)
            row_layout.addWidget(checkboxes[name], 1)
            row_layout.addWidget(color_buttons[name], 0)

            return row_widget

        def _move(name, section, direction):
            """Move a event up or down within its section."""
            lst = state_order if section == "state" else point_order
            idx = lst.index(name)
            new_idx = idx + direction
            if new_idx < 0 or new_idx >= len(lst):
                return
            lst[idx], lst[new_idx] = lst[new_idx], lst[idx]
            # Update visualizer order
            timeline_widget.set_event_order(state_order, point_order)
            # Rebuild the sidebar to reflect new order
            build_event_list()

        build_event_list()
        select_layout.addWidget(scroll, 1)

        # ---- Options below the event list ----
        saved_options = {}
        if store is not None:
            saved_options = store.load_viz_options()

        show_title_cb = QCheckBox("Show title")
        show_title_cb.setChecked(saved_options.get("show_title", True))
        select_layout.addWidget(show_title_cb)
        timeline_widget.show_title = show_title_cb.isChecked()

        show_headers_cb = QCheckBox("Show section headers")
        show_headers_cb.setChecked(saved_options.get("show_headers", True))
        select_layout.addWidget(show_headers_cb)
        timeline_widget.show_section_headers = show_headers_cb.isChecked()

        show_legend_cb = QCheckBox("Show color legend")
        show_legend_cb.setChecked(saved_options.get("show_legend", True))
        select_layout.addWidget(show_legend_cb)
        timeline_widget.show_legend = show_legend_cb.isChecked()

        has_coding_bounds = bounds and bounds.get("has_bounds", False)
        segment_cb = None
        zero_base_cb = None
        if has_coding_bounds:
            segment_cb = QCheckBox("Coded segment only")
            segment_cb.setToolTip("Show only the coded segment instead of the whole video")
            segment_cb.setChecked(saved_options.get("coded_segment", False))
            select_layout.addWidget(segment_cb)

            zero_base_cb = QCheckBox("Start time at 0:00")
            zero_base_cb.setToolTip(
                "Subtract coding start so 0:00 aligns with the beginning of the coded segment")
            saved_zero = saved_options.get("zero_base", False)
            zero_base_cb.setChecked(saved_zero and segment_cb.isChecked())
            zero_base_cb.setEnabled(segment_cb.isChecked())
            select_layout.addWidget(zero_base_cb)

            # Apply saved segment mode to timeline
            if segment_cb.isChecked():
                timeline_widget.set_segment_mode(True)
            if zero_base_cb.isChecked():
                timeline_widget.zero_base_time = True

        timeline_widget._recalc_height()
        timeline_widget.update()

        content_layout.addWidget(select_group)

        # ---- Timeline (in a scroll area) ----
        timeline_scroll = QScrollArea()
        timeline_scroll.setWidgetResizable(True)
        timeline_scroll.setWidget(timeline_widget)
        content_layout.addWidget(timeline_scroll, 1)

        outer.addLayout(content_layout, 1)

        # ---- Interaction logic ----
        all_checked = [True]
        dialog_alive = [True]

        def on_checkbox_changed():
            if not dialog_alive[0]:
                return
            checked = {n for n, cb in checkboxes.items() if cb.isChecked()}
            filt_state = [e for e in timeline_widget._raw_state_events
                          if e.get('Event') in checked]
            filt_point = [e for e in timeline_widget._raw_point_events
                          if e.get('Event') in checked]
            timeline_widget.update_data(filt_state, filt_point)
            # Persist unchecked selections
            if store is not None:
                unchecked = [n for n, cb in checkboxes.items()
                             if not cb.isChecked()]
                store.save_viz_unchecked(unchecked)

        def toggle_all():
            if all_checked[0]:
                for cb in checkboxes.values():
                    cb.setChecked(False)
                toggle_btn.setText("Select All")
                all_checked[0] = False
            else:
                for cb in checkboxes.values():
                    cb.setChecked(True)
                toggle_btn.setText("Deselect All")
                all_checked[0] = True
            # on_checkbox_changed fires via stateChanged, but update toggle state
            if store is not None:
                unchecked = [n for n, cb in checkboxes.items()
                             if not cb.isChecked()]
                store.save_viz_unchecked(unchecked)

        def _save_options():
            if not dialog_alive[0] or store is None:
                return
            opts = {
                "show_title": show_title_cb.isChecked(),
                "show_headers": show_headers_cb.isChecked(),
                "show_legend": show_legend_cb.isChecked(),
            }
            if segment_cb is not None:
                opts["coded_segment"] = segment_cb.isChecked()
            if zero_base_cb is not None:
                opts["zero_base"] = zero_base_cb.isChecked()
            store.save_viz_options(opts)

        def on_segment_changed(state):
            coded_only = bool(state)
            timeline_widget.set_segment_mode(coded_only)
            on_checkbox_changed()
            if zero_base_cb is not None:
                zero_base_cb.setEnabled(coded_only)
                if not coded_only:
                    zero_base_cb.setChecked(False)
            _save_options()

        def on_zero_base_changed(state):
            timeline_widget.zero_base_time = bool(state)
            timeline_widget.update()
            _save_options()

        def on_show_title_changed(state):
            timeline_widget.show_title = bool(state)
            timeline_widget._recalc_height()
            timeline_widget.update()
            _save_options()

        def on_show_headers_changed(state):
            timeline_widget.show_section_headers = bool(state)
            timeline_widget._recalc_height()
            timeline_widget.update()
            _save_options()

        def on_show_legend_changed(state):
            timeline_widget.show_legend = bool(state)
            timeline_widget._recalc_height()
            timeline_widget.update()
            _save_options()

        def make_color_callback(event_name):
            def pick_color():
                current = timeline_widget._color_map.get(
                    event_name, QColor("#888888"))
                chosen = QColorDialog.getColor(
                    current, viz_dialog, f"Color for {event_name}")
                if chosen.isValid():
                    timeline_widget.set_event_color(event_name, chosen)
                    color_buttons[event_name].setIcon(
                        _make_color_icon(chosen))
                    # Persist custom colors to session state
                    if store is not None:
                        custom = {}
                        for n, c in timeline_widget._color_map.items():
                            custom[n] = c.name()
                        store.save_viz_colors(custom)
            return pick_color

        for cb in checkboxes.values():
            cb.stateChanged.connect(on_checkbox_changed)
        toggle_btn.clicked.connect(toggle_all)
        if segment_cb is not None:
            segment_cb.stateChanged.connect(on_segment_changed)
        if zero_base_cb is not None:
            zero_base_cb.stateChanged.connect(on_zero_base_changed)
        show_title_cb.stateChanged.connect(on_show_title_changed)
        show_headers_cb.stateChanged.connect(on_show_headers_changed)
        show_legend_cb.stateChanged.connect(on_show_legend_changed)

        for name, btn in color_buttons.items():
            btn.clicked.connect(make_color_callback(name))

        # Apply initial checkbox filter if any were saved as unchecked
        if saved_unchecked:
            on_checkbox_changed()
            # Update toggle button text if not all are checked
            if any(not cb.isChecked() for cb in checkboxes.values()):
                toggle_btn.setText("Select All")
                all_checked[0] = False

        # ---- Export bar ----
        export_frame = QFrame()
        export_layout = QHBoxLayout(export_frame)

        format_label = QLabel("Export Format:")
        export_layout.addWidget(format_label)
        format_combo = QComboBox()
        format_combo.addItems(["PNG", "JPEG"])
        export_layout.addWidget(format_combo)

        dpi_label = QLabel("Resolution (DPI):")
        export_layout.addWidget(dpi_label)
        dpi_spinner = QSpinBox()
        dpi_spinner.setRange(100, 900)
        dpi_spinner.setValue(300)
        dpi_spinner.setSingleStep(100)
        export_layout.addWidget(dpi_spinner)

        export_layout.addStretch(1)

        export_button = QPushButton("Export")
        export_layout.addWidget(export_button)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(viz_dialog.accept)
        export_layout.addWidget(ok_button)

        outer.addWidget(export_frame)

        def export_visualization():
            fmt = format_combo.currentText().upper()
            dpi = dpi_spinner.value()
            ext = ".jpg" if fmt == "JPEG" else ".png"
            filt = ("JPEG Images (*.jpg *.jpeg)" if fmt == "JPEG"
                    else "PNG Images (*.png)")

            suffix = ""
            if bounds and bounds.get("has_bounds") and not bounds.get("whole_video"):
                st = bounds.get("start", 0)
                et = bounds.get("end")
                if st > 0 and et is not None:
                    suffix = f"_segment_{int(st)}-{int(et)}"
                elif st > 0:
                    suffix = f"_from_{int(st)}"
                elif et is not None:
                    suffix = f"_until_{int(et)}"

            default_name = f"{video_name}_annotations{suffix}{ext}"
            file_path, _ = QFileDialog.getSaveFileName(
                viz_dialog, "Save Visualization",
                os.path.join(output_dir, default_name), filt)

            if not file_path:
                return
            try:
                image, _ = timeline_widget.render_to_image(fmt, dpi)
                image.save(file_path)
                QMessageBox.information(viz_dialog, "Export Successful",
                                        "Visualization exported successfully")
            except Exception as e:
                QMessageBox.critical(viz_dialog, "Export Error",
                                     f"Failed to export visualization: {e}")

        export_button.clicked.connect(export_visualization)

        viz_dialog.finished.connect(lambda: dialog_alive.__setitem__(0, False))
        viz_dialog.exec()
        return True

    except Exception as e:
        print(f"Error in visualization: {e}")
        QMessageBox.critical(parent, "Visualization Error",
                             f"Failed to create visualization: {e}")
        return False
