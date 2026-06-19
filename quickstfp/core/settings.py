import json
import logging
from pathlib import Path

from quickstfp.core.config import get_data_path

logger = logging.getLogger(__name__)

SETTINGS_FILE = get_data_path("settings.json", legacy_cwd_fallback=False)

def get_default_settings():
    return {
        "temp_download_dir": str(Path.home() / "Downloads" / "QuickSFTP"),
        "font_family": "Courier New",  # Default fallback
        "font_size": 14,
    }

class SettingsManager:
    _settings = None

    @classmethod
    def load(cls):
        if cls._settings is None:
            cls._settings = get_default_settings()
            try:
                if Path(SETTINGS_FILE).exists():
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cls._settings.update(data)
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
        return cls._settings

    @classmethod
    def save(cls, settings_dict):
        cls._settings.update(settings_dict)
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    @classmethod
    def get(cls, key, default=None):
        return cls.load().get(key, default)

    @classmethod
    def set(cls, key, value):
        cls.load()[key] = value
        cls.save({key: value})
