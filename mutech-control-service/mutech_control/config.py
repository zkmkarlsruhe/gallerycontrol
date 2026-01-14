"""Configuration management with hot-reload support."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Load .env file at module import time
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and manage YAML configuration with environment variable substitution."""

    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self._config: Dict[str, Any] = {}
        self._observer: Observer | None = None
        self.load()

    def load(self) -> None:
        """Load configuration from YAML files with environment variable substitution."""
        # Load default config
        default_path = self.config_dir / "default.yaml"
        if not default_path.exists():
            raise FileNotFoundError(f"Default configuration not found: {default_path}")

        with open(default_path) as f:
            self._config = yaml.safe_load(f)

        # Load environment-specific overrides
        env = os.getenv("ENVIRONMENT", "development")
        env_path = self.config_dir / f"{env}.yaml"
        if env_path.exists():
            with open(env_path) as f:
                env_config = yaml.safe_load(f)
                self._deep_merge(self._config, env_config)

        # Substitute environment variables
        self._config = self._substitute_env_vars(self._config)

    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Deep merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _substitute_env_vars(self, obj: Any) -> Any:
        """Recursively substitute ${VAR_NAME} with environment variables."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Match ${VAR_NAME} pattern
            pattern = r"\$\{([^}]+)\}"
            matches = re.findall(pattern, obj)
            for var_name in matches:
                env_value = os.getenv(var_name, "")
                obj = obj.replace(f"${{{var_name}}}", env_value)
            return obj
        else:
            return obj

    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated path."""
        keys = path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration."""
        return self._config.copy()

    def start_watching(self, callback: callable = None) -> None:
        """Start watching config files for changes."""
        if self._observer is not None:
            return  # Already watching

        class ConfigChangeHandler(FileSystemEventHandler):
            def __init__(self, loader: ConfigLoader, cb: callable = None):
                self.loader = loader
                self.callback = cb

            def on_modified(self, event):
                if event.src_path.endswith(".yaml"):
                    try:
                        logger.info("Config file changed, reloading", path=event.src_path)
                        self.loader.load()
                        logger.info("Configuration reloaded successfully")
                        if self.callback:
                            self.callback(self.loader)
                    except Exception as e:
                        logger.error("Error reloading configuration", error=str(e))

        self._observer = Observer()
        handler = ConfigChangeHandler(self, callback)
        self._observer.schedule(handler, str(self.config_dir), recursive=False)
        self._observer.start()
        logger.info("Started watching configuration directory", path=str(self.config_dir))

    def stop_watching(self) -> None:
        """Stop watching config files."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Stopped watching configuration directory")


# Global config instance
_config_instance: ConfigLoader | None = None


def get_config() -> ConfigLoader:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance


def reload_config() -> None:
    """Reload global configuration."""
    global _config_instance
    if _config_instance:
        _config_instance.load()
