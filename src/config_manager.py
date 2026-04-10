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
        self.config_file = os.path.join(self.home_dir, '.lasertag.conf')
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

    def get_event_button_opacity(self):
        return self.config.get('event_button_opacity', 0.4)

    def set_event_button_opacity(self, value):
        self.config['event_button_opacity'] = max(0.1, min(1.0, float(value)))
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
        return self.config.get('waveform_opacity', 0.8)

    def set_waveform_opacity(self, value):
        self.config['waveform_opacity'] = max(0.1, min(1.0, float(value)))
        self.save_config()

    def get_splitter_sizes(self):
        return self.config.get('splitter_sizes', None)

    def set_splitter_sizes(self, sizes):
        self.config['splitter_sizes'] = sizes
        self.save_config()


_instance = None

def get_config():
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance
