"""
NonRoot Configuration & Settings Manager.
Persists configuration locally in ~/.nonroot/config.json or ./nonroot_config.json.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG = {
    "api_base_url": "http://127.0.0.1:3000/v1",
    "api_key": "sk-nonroot-free",
    "model": "deepseek-chat",
    "auto_accept_tools": True,
    "max_steps": 30,
    "workspace": str(Path.cwd().resolve()),
    "temperature": 0.2,
    "theme": "dark",
    "port": 8765,
    "system_prompt": ""
}

def get_config_dir() -> Path:
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent.parent.resolve()
    
    local_cfg_dir = app_dir / ".nonroot"
    try:
        local_cfg_dir.mkdir(parents=True, exist_ok=True)
        return local_cfg_dir
    except Exception:
        pass
    
    home_dir = Path.home() / ".nonroot"
    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir

CONFIG_FILE = get_config_dir() / "config.json"

class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        cfg = DEFAULT_CONFIG.copy()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    cfg.update(loaded)
            except Exception:
                pass
        return cfg

    def save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[!] Warning: Failed to save config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self.save()

    def update(self, updates: Dict[str, Any]):
        self.config.update(updates)
        self.save()

# Global instance
config_manager = ConfigManager()
