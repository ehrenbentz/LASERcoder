# config_manager.py

import os
import json
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QDir
from debug_logger import get_logger

logger = get_logger()

DEFAULT_VIDEO_SETTINGS = {
    "brightness": 0, "contrast": 0, "gamma": 0,
    "saturation": 0, "hue": 0
}

class ConfigManager:
    """
    Manages configuration settings.

    """
    
    def __init__(self):
        """Initialize the configuration manager with default settings"""
        self.home_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        self.config_file = os.path.join(self.home_dir, '.lasercoder.conf')
        old_config = os.path.join(self.home_dir, '.lasertag.conf')
        if not os.path.exists(self.config_file) and os.path.exists(old_config):
            os.rename(old_config, self.config_file)
        self.config = None
        self.load_config()
        
    def load_config(self):
        """Load configuration from file or create with defaults"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info("Config loaded from %s", self.config_file)
            else:
                self.config = self.create_default_config()
                logger.info("Created default config")
        except Exception:
            self.config = self.create_default_config()
            logger.warning("Config load failed, using defaults")
            
        self._validate_and_update_config()
        return self.config

    def _validate_and_update_config(self):
        """Validate configuration"""
        if not self.config.get('output_dir') or not os.path.exists(self.config['output_dir']):
            self.config['output_dir'] = self.home_dir
            
        if not self.config.get('video_dir') or not os.path.exists(self.config['video_dir']):
            self.config['video_dir'] = self.home_dir
            
        if 'last_event_key' not in self.config:
            self.config['last_event_key'] = None

        if self.config.get('theme') not in ('dark', 'light', 'system'):
            self.config['theme'] = 'system'

        if 'video_settings' not in self.config:
            self.config['video_settings'] = DEFAULT_VIDEO_SETTINGS.copy()

        if 'wasd_navigation' not in self.config:
            self.config['wasd_navigation'] = True

        self.save_config()

    def create_default_config(self):
        """Create default configuration settings"""
        return {
            'output_dir': self.home_dir,
            'video_dir': self.home_dir,
            'last_event_key': None,
            'theme': 'system',
            'video_settings': DEFAULT_VIDEO_SETTINGS.copy(),
        }

    def save_config(self):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as exc:
            logger.warning("Config save failed: %s", exc)

    def get_output_dir(self):
        """Get the current output directory"""
        return self.config.get('output_dir', self.home_dir)

    def get_video_dir(self):
        """Get the current video directory"""
        return self.config.get('video_dir', self.home_dir)

    def get_last_event_key(self):
        """Get the last used event key file"""
        return self.config.get('last_event_key')

    def update_output_dir(self, new_dir):
        """Update the output directory if it exists"""
        if os.path.exists(new_dir):
            self.config['output_dir'] = new_dir
            self.save_config()

    def update_video_dir(self, video_path):
        """Update the video directory based on the selected video file"""
        video_dir = os.path.dirname(video_path)
        if os.path.exists(video_dir):
            self.config['video_dir'] = video_dir
            self.save_config()

    def update_last_event_key(self, event_key):
        """Update the last used event key file"""
        if event_key and isinstance(event_key, str):
            self.config['last_event_key'] = event_key
            self.save_config()

    def get_theme(self):
        """Get the current theme preference"""
        return self.config.get('theme', 'system')

    def update_theme(self, name):
        """Update the theme preference"""
        if name in ('dark', 'light', 'system'):
            self.config['theme'] = name
            self.save_config()

    def get_video_settings(self):
        """Get the global video display settings"""
        return self.config.get('video_settings', DEFAULT_VIDEO_SETTINGS.copy())

    def update_video_settings(self, settings):
        """Update and persist global video display settings"""
        self.config['video_settings'] = settings
        self.save_config()

    def get_show_floating_controls(self):
        return self.config.get('show_floating_controls', True)

    def set_show_floating_controls(self, visible):
        self.config['show_floating_controls'] = bool(visible)
        self.save_config()

    def get_show_events_toggle(self):
        return self.config.get('show_events_toggle', True)

    def set_show_events_toggle(self, visible):
        self.config['show_events_toggle'] = bool(visible)
        self.save_config()

    def get_events_list_expanded(self):
        return self.config.get('events_list_expanded', False)

    def set_events_list_expanded(self, expanded):
        self.config['events_list_expanded'] = bool(expanded)
        self.save_config()

    def get_show_zoom_button(self):
        return self.config.get('show_zoom_button', True)

    def set_show_zoom_button(self, visible):
        self.config['show_zoom_button'] = bool(visible)
        self.save_config()

    def get_backup_dirs(self):
        return self.config.get('backup_dirs', [])

    def add_backup_dir(self, path):
        dirs = self.config.get('backup_dirs', [])
        norm = os.path.normpath(path)
        if norm not in dirs:
            dirs.append(norm)
            self.config['backup_dirs'] = dirs
            self.save_config()

    def is_backup_dir(self, path):
        norm = os.path.normpath(path)
        return norm in self.config.get('backup_dirs', [])

    def get_state_highlight_color(self):
        return self.config.get('state_highlight_color', None)

    def set_state_highlight_color(self, hex_color):
        self.config['state_highlight_color'] = hex_color
        self.save_config()

    def get_point_highlight_color(self):
        return self.config.get('point_highlight_color', None)

    def set_point_highlight_color(self, hex_color):
        self.config['point_highlight_color'] = hex_color
        self.save_config()

    def get_point_button_color(self):
        return self.config.get('point_button_color', None)

    def set_point_button_color(self, hex_color):
        self.config['point_button_color'] = hex_color
        self.save_config()

    def get_state_button_color(self):
        return self.config.get('state_button_color', None)

    def set_state_button_color(self, hex_color):
        self.config['state_button_color'] = hex_color
        self.save_config()

    def get_button_hover_color(self):
        return self.config.get('button_hover_color', None)

    def set_button_hover_color(self, hex_color):
        self.config['button_hover_color'] = hex_color
        self.save_config()

    def get_progress_bar_color(self):
        return self.config.get('progress_bar_color', None)

    def set_progress_bar_color(self, hex_color):
        self.config['progress_bar_color'] = hex_color
        self.save_config()

    def get_volume(self):
        return self.config.get('volume', 100)

    def set_volume(self, value):
        self.config['volume'] = int(value)
        self.save_config()

    def get_audio_delay(self):
        return float(self.config.get('audio_delay', 0.0))

    def set_audio_delay(self, value):
        self.config['audio_delay'] = float(value)
        self.save_config()

    def get_pitch_semitones(self):
        return int(self.config.get('pitch_semitones', 0))

    def set_pitch_semitones(self, value):
        self.config['pitch_semitones'] = int(value)
        self.save_config()

    def get_audio_pitch_correction(self):
        return bool(self.config.get('audio_pitch_correction', True))

    def set_audio_pitch_correction(self, value):
        self.config['audio_pitch_correction'] = bool(value)
        self.save_config()

    def get_muted(self):
        return self.config.get('muted', False)

    def set_muted(self, muted):
        self.config['muted'] = bool(muted)
        self.save_config()

    def get_wasd_navigation(self):
        return self.config.get('wasd_navigation', True)

    def set_wasd_navigation(self, enabled):
        self.config['wasd_navigation'] = bool(enabled)
        self.save_config()

    def get_waveform_visible(self):
        return self.config.get('waveform_visible', False)

    def set_waveform_visible(self, visible):
        self.config['waveform_visible'] = bool(visible)
        self.save_config()

    def get_waveform_height_multiplier(self):
        return self.config.get('waveform_height_multiplier', 2.0)

    def set_waveform_height_multiplier(self, value):
        self.config['waveform_height_multiplier'] = max(1.0, min(3.0, float(value)))
        self.save_config()

    def get_waveform_color(self):
        return self.config.get('waveform_color', None)

    def set_waveform_color(self, hex_color):
        self.config['waveform_color'] = hex_color
        self.save_config()

    def get_waveform_opacity(self):
        return self.config.get('waveform_opacity', 1.0)

    def set_waveform_opacity(self, value):
        self.config['waveform_opacity'] = max(0.1, min(1.0, float(value)))
        self.save_config()

    def get_splitter_sizes(self):
        return self.config.get('splitter_sizes', None)

    def set_splitter_sizes(self, sizes):
        self.config['splitter_sizes'] = sizes
        self.save_config()

    def get_show_subject_list(self):
        return self.config.get('show_subject_list', False)

    def set_show_subject_list(self, visible):
        self.config['show_subject_list'] = bool(visible)
        self.save_config()

    def get_subject_list_expanded(self):
        return self.config.get('subject_list_expanded', False)

    def set_subject_list_expanded(self, expanded):
        self.config['subject_list_expanded'] = bool(expanded)
        self.save_config()

    def get_subject_button_color(self):
        return self.config.get('subject_button_color', None)

    def set_subject_button_color(self, hex_color):
        self.config['subject_button_color'] = hex_color
        self.save_config()

    def get_last_subject_file(self):
        return self.config.get('last_subject_file', None)

    def set_last_subject_file(self, filename):
        self.config['last_subject_file'] = filename
        self.save_config()

    def get_annotation_panel_width(self):
        return self.config.get('annotation_panel_width', None)

    def set_annotation_panel_width(self, width):
        self.config['annotation_panel_width'] = int(width)
        self.save_config()

    def get_annotation_panel_collapsed(self):
        return self.config.get('annotation_panel_collapsed', False)

    def set_annotation_panel_collapsed(self, collapsed):
        self.config['annotation_panel_collapsed'] = bool(collapsed)
        self.save_config()

    def get_all_subjects_mutually_exclusive(self):
        return self.config.get('all_subjects_mutually_exclusive', False)

    def set_all_subjects_mutually_exclusive(self, enabled):
        self.config['all_subjects_mutually_exclusive'] = bool(enabled)
        self.save_config()

    def get_show_floating_headers(self):
        return self.config.get('show_floating_headers', True)

    def set_show_floating_headers(self, visible):
        self.config['show_floating_headers'] = bool(visible)
        self.save_config()

    def get_allow_25x_speed(self):
        return self.config.get('allow_25x_speed', False)

    def set_allow_25x_speed(self, enabled):
        self.config['allow_25x_speed'] = bool(enabled)
        self.save_config()

    def get_waveform_dynamic_range(self):
        return self.config.get('waveform_dynamic_range', 1.0)

    def set_waveform_dynamic_range(self, value):
        self.config['waveform_dynamic_range'] = max(0.1, min(1.0, float(value)))
        self.save_config()

    # Spectrogram settings

    def get_spectrogram_visible(self):
        return self.config.get('spectrogram_visible', False)

    def set_spectrogram_visible(self, visible):
        self.config['spectrogram_visible'] = bool(visible)
        self.save_config()

    def get_spectrogram_colormap(self):
        return self.config.get('spectrogram_colormap', 'viridis')

    def set_spectrogram_colormap(self, name):
        self.config['spectrogram_colormap'] = name
        self.save_config()

    def get_spectrogram_opacity(self):
        return self.config.get('spectrogram_opacity', 1.0)

    def set_spectrogram_opacity(self, value):
        self.config['spectrogram_opacity'] = max(0.1, min(1.0, float(value)))
        self.save_config()

    def get_spectrogram_freq_low(self):
        return self.config.get('spectrogram_freq_low', 0)

    def set_spectrogram_freq_low(self, value):
        self.config['spectrogram_freq_low'] = max(0, int(value))
        self.save_config()

    def get_spectrogram_freq_high(self):
        return self.config.get('spectrogram_freq_high', 15000)

    def set_spectrogram_freq_high(self, value):
        self.config['spectrogram_freq_high'] = max(100, min(22050, int(value)))
        self.save_config()

    def get_spectrogram_window(self):
        return self.config.get('spectrogram_window', 10.0)

    def set_spectrogram_window(self, value):
        self.config['spectrogram_window'] = max(2.0, min(30.0, float(value)))
        self.save_config()

    def get_spectrogram_height_multiplier(self):
        return self.config.get('spectrogram_height_multiplier', 4.0)

    def set_spectrogram_height_multiplier(self, value):
        self.config['spectrogram_height_multiplier'] = max(2.0, min(8.0, float(value)))
        self.save_config()

    def get_floating_toggle_color(self):
        return self.config.get('floating_toggle_color', None)

    def set_floating_toggle_color(self, hex_color):
        self.config['floating_toggle_color'] = hex_color
        self.save_config()

    def get_floating_controls_color(self):
        return self.config.get('floating_controls_color', None)

    def set_floating_controls_color(self, hex_color):
        self.config['floating_controls_color'] = hex_color
        self.save_config()

    def get_stationary_button_color(self):
        return self.config.get('stationary_button_color', None)

    def set_stationary_button_color(self, hex_color):
        self.config['stationary_button_color'] = hex_color
        self.save_config()

    def get_ui_background_color(self):
        return self.config.get('ui_background_color', None)

    def set_ui_background_color(self, hex_color):
        self.config['ui_background_color'] = hex_color
        self.save_config()

    def get_tree_background_color(self):
        return self.config.get('tree_background_color', None)

    def set_tree_background_color(self, hex_color):
        self.config['tree_background_color'] = hex_color
        self.save_config()

    def get_progress_bar_opacity(self):
        return self.config.get('progress_bar_opacity', 1.0)

    def set_progress_bar_opacity(self, value):
        self.config['progress_bar_opacity'] = max(0.0, min(1.0, float(value)))
        self.save_config()

    def get_floating_controls_opacity(self):
        return self.config.get('floating_controls_opacity', 0.8)

    def set_floating_controls_opacity(self, value):
        self.config['floating_controls_opacity'] = max(0.0, min(1.0, float(value)))
        self.save_config()

    def get_floating_toggle_opacity(self):
        return self.config.get('floating_toggle_opacity', 0.8)

    def set_floating_toggle_opacity(self, value):
        self.config['floating_toggle_opacity'] = max(0.0, min(1.0, float(value)))
        self.save_config()

    def get_floating_header_color(self):
        return self.config.get('floating_header_color', None)

    def set_floating_header_color(self, hex_color):
        self.config['floating_header_color'] = hex_color
        self.save_config()

    def get_floating_header_opacity(self):
        return self.config.get('floating_header_opacity', 0.8)

    def set_floating_header_opacity(self, value):
        self.config['floating_header_opacity'] = max(0.0, min(1.0, float(value)))
        self.save_config()

    def get_floating_button_size(self):
        return self.config.get('floating_button_size', 1.0)

    def set_floating_button_size(self, value):
        self.config['floating_button_size'] = max(0.5, min(2.0, float(value)))
        self.save_config()

    def get_annotation_tree_font_size(self):
        return self.config.get('annotation_tree_font_size', 14)

    def set_annotation_tree_font_size(self, value):
        self.config['annotation_tree_font_size'] = max(8, min(28, int(value)))
        self.save_config()

    def get_floating_buttons_opacity(self):
        return self.config.get('floating_buttons_opacity', 0.8)

    def set_floating_buttons_opacity(self, value):
        self.config['floating_buttons_opacity'] = max(0.0, min(1.0, float(value)))
        self.save_config()

    def get_small_skip_seconds(self):
        return self.config.get('small_skip_seconds', 1.0)

    def set_small_skip_seconds(self, value):
        self.config['small_skip_seconds'] = max(0.1, min(60.0, float(value)))
        self.save_config()

    def get_large_skip_seconds(self):
        return self.config.get('large_skip_seconds', 5.0)

    def set_large_skip_seconds(self, value):
        self.config['large_skip_seconds'] = max(0.1, min(60.0, float(value)))
        self.save_config()


_instance = None

def get_config():
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance
