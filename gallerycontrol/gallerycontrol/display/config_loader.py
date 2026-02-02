# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Config loader for visitor display configurations.

Loads YAML configs from steuerung/artworks/{slug}/config.yaml with TTL caching
for hot-reload support without excessive file I/O.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default TTL for config cache (seconds)
DEFAULT_CACHE_TTL = 5.0


@dataclass
class DisplayConfig:
    """Configuration for a single artwork display."""

    # Core identification
    artwork_uuid: str = ""
    slug: str = ""

    # Template settings
    template: str = "mack-style"
    chart_type: str = "donut"  # pie, donut, bar-horizontal, bar-vertical, gauge, digits-only

    # Colors
    colors: dict = field(default_factory=lambda: {
        "background": "#000000",
        "available": "#4CAF50",
        "used": "#FFC107",
        "warning": "#f44336",
        "text": "#FFFFFF",
    })

    # Font settings
    font: dict = field(default_factory=lambda: {
        "family": "Hero New",
        "size_budget": "4rem",
        "size_info": "1.5rem",
    })

    # Scale factor
    scale: float = 1.0

    # Text content
    texts: dict = field(default_factory=lambda: {
        "artwork_name": "",
        "info_de": "",
        "info_en": "",
        "warning_de": "",
        "warning_en": "",
    })

    # Optional custom CSS file
    custom_css: str | None = None

    # Raw config dict (for template access)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict, slug: str = "") -> "DisplayConfig":
        """Create DisplayConfig from a dictionary (parsed YAML).

        Performs defensive type checking to handle malformed YAML gracefully.
        """
        # Helper to safely get nested dict values
        def safe_dict(value: Any, default: dict) -> dict:
            return value if isinstance(value, dict) else default

        # Helper to safely convert to float
        def safe_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        # Helper to safely convert to string
        def safe_str(value: Any, default: str = "") -> str:
            if value is None:
                return default
            return str(value)

        colors_data = safe_dict(data.get("colors"), {})
        font_data = safe_dict(data.get("font"), {})
        texts_data = safe_dict(data.get("texts"), {})

        return cls(
            artwork_uuid=safe_str(data.get("artwork_uuid")),
            slug=slug,
            template=safe_str(data.get("template"), "mack-style"),
            chart_type=safe_str(data.get("chart_type"), "donut"),
            colors={
                "background": safe_str(colors_data.get("background"), "#000000"),
                "available": safe_str(colors_data.get("available"), "#4CAF50"),
                "used": safe_str(colors_data.get("used"), "#FFC107"),
                "warning": safe_str(colors_data.get("warning"), "#f44336"),
                "text": safe_str(colors_data.get("text"), "#FFFFFF"),
            },
            font={
                "family": safe_str(font_data.get("family"), "Hero New"),
                "size_budget": safe_str(font_data.get("size_budget"), "4rem"),
                "size_info": safe_str(font_data.get("size_info"), "1.5rem"),
            },
            scale=safe_float(data.get("scale"), 1.0),
            texts={
                "artwork_name": safe_str(texts_data.get("artwork_name")),
                "info_de": safe_str(texts_data.get("info_de")),
                "info_en": safe_str(texts_data.get("info_en")),
                "warning_de": safe_str(texts_data.get("warning_de")),
                "warning_en": safe_str(texts_data.get("warning_en")),
            },
            custom_css=data.get("custom_css") if isinstance(data.get("custom_css"), str) else None,
            raw=data,
        )


@dataclass
class CacheEntry:
    """Cache entry with TTL tracking."""

    config: DisplayConfig
    loaded_at: float
    file_mtime: float


class DisplayConfigLoader:
    """Loads and caches display configurations from YAML files.

    Configs are loaded from steuerung/artworks/{slug}/config.yaml with a TTL cache
    to balance hot-reload capability with file I/O efficiency.
    """

    def __init__(
        self,
        base_path: Path | str | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ):
        """Initialize the config loader.

        Args:
            base_path: Base path to steuerung/artworks directory.
                      Defaults to gallerycontrol/steuerung/artworks.
            cache_ttl: Cache time-to-live in seconds.
        """
        if base_path is None:
            # Default to gallerycontrol/steuerung/artworks relative to this file
            base_path = Path(__file__).parent.parent / "steuerung" / "artworks"
        elif isinstance(base_path, str):
            base_path = Path(base_path)

        self.base_path = base_path
        self.cache_ttl = cache_ttl
        self._cache: dict[str, CacheEntry] = {}

    def get_config(self, slug: str) -> DisplayConfig | None:
        """Get display config for an artwork by slug.

        Args:
            slug: The artwork slug (directory name).

        Returns:
            DisplayConfig if found, None if not found or invalid.
        """
        now = time.time()

        # Check cache first
        if slug in self._cache:
            entry = self._cache[slug]
            if now - entry.loaded_at < self.cache_ttl:
                # Cache hit and still valid
                return entry.config

            # Cache expired - check if file changed
            config_path = self._get_config_path(slug)
            if config_path.exists():
                try:
                    current_mtime = config_path.stat().st_mtime
                    if current_mtime == entry.file_mtime:
                        # File unchanged, refresh cache TTL
                        entry.loaded_at = now
                        return entry.config
                except OSError:
                    pass  # File access error, reload

        # Load from file
        return self._load_config(slug)

    def _get_config_path(self, slug: str) -> Path:
        """Get the config.yaml path for a slug."""
        return self.base_path / slug / "config.yaml"

    def _load_config(self, slug: str) -> DisplayConfig | None:
        """Load config from YAML file.

        Args:
            slug: The artwork slug.

        Returns:
            DisplayConfig if successful, None if file not found or invalid.
        """
        config_path = self._get_config_path(slug)

        if not config_path.exists():
            logger.warning(f"Display config not found: {config_path}")
            # Remove from cache if it was there
            self._cache.pop(slug, None)
            return None

        try:
            file_mtime = config_path.stat().st_mtime
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            config = DisplayConfig.from_dict(data, slug=slug)

            # Cache the result
            self._cache[slug] = CacheEntry(
                config=config,
                loaded_at=time.time(),
                file_mtime=file_mtime,
            )

            logger.debug(f"Loaded display config for {slug}")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in display config {config_path}: {e}")
            self._cache.pop(slug, None)
            return None
        except OSError as e:
            logger.error(f"Error reading display config {config_path}: {e}")
            self._cache.pop(slug, None)
            return None

    def get_custom_css_path(self, slug: str) -> Path | None:
        """Get the path to custom CSS file if it exists.

        Args:
            slug: The artwork slug.

        Returns:
            Path to custom.css if it exists, None otherwise.
        """
        config = self.get_config(slug)
        if not config:
            return None

        # Check for custom CSS specified in config
        css_filename = config.custom_css or "custom.css"
        css_path = self.base_path / slug / css_filename

        if css_path.exists():
            return css_path
        return None

    def list_artworks(self) -> list[str]:
        """List all available artwork slugs.

        Returns:
            List of slug names that have config.yaml files.
        """
        if not self.base_path.exists():
            return []

        slugs = []
        for item in self.base_path.iterdir():
            if item.is_dir():
                config_path = item / "config.yaml"
                if config_path.exists():
                    slugs.append(item.name)

        return sorted(slugs)

    def clear_cache(self, slug: str | None = None) -> None:
        """Clear the config cache.

        Args:
            slug: If provided, clear only this slug's cache.
                 If None, clear entire cache.
        """
        if slug is None:
            self._cache.clear()
            logger.debug("Cleared entire display config cache")
        else:
            if slug in self._cache:
                del self._cache[slug]
                logger.debug(f"Cleared display config cache for {slug}")


# Module-level singleton
_config_loader: DisplayConfigLoader | None = None


def get_display_config_loader() -> DisplayConfigLoader:
    """Get the global display config loader instance.

    On first call, reads settings from app config if available.
    """
    global _config_loader
    if _config_loader is None:
        # Try to get settings from app config
        cache_ttl = DEFAULT_CACHE_TTL
        try:
            from gallerycontrol.config import get_config
            config = get_config()
            cache_ttl = config.get("display.config_cache_ttl", DEFAULT_CACHE_TTL)
        except Exception:
            pass  # Use defaults if config not available

        _config_loader = DisplayConfigLoader(cache_ttl=cache_ttl)
    return _config_loader


def reset_display_config_loader() -> None:
    """Reset the singleton for testing or reconfiguration."""
    global _config_loader
    _config_loader = None
