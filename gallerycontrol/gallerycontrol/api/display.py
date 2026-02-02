# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Display API endpoints for visitor-facing kiosk displays.

Provides HTML template rendering and JSON status endpoints for museum kiosk
systems showing artwork protection status (budget remaining, cooldown, etc.).

These endpoints are intended to be unprotected and accessed via IP whitelist
configured in the reverse proxy (Traefik).
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from gallerycontrol.display.config_loader import (
    DisplayConfig,
    get_display_config_loader,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/steuerung", tags=["display"])

# Path to templates directory
TEMPLATES_PATH = Path(__file__).parent.parent / "steuerung" / "templates"


class DisplayStatusResponse(BaseModel):
    """JSON response for display status polling."""

    available: bool
    budget_remaining: int
    budget_max: int
    budget_percent: int
    resets_in: int
    cooldown_active: bool
    cooldown_remaining: int
    is_running: bool


def get_protection_service():
    """Dependency to get protection service instance."""
    from gallerycontrol.main import app

    return app.state.protection_service


def _load_template(template_name: str) -> str | None:
    """Load HTML template content.

    Args:
        template_name: Name of the template directory (e.g., "mack-style").

    Returns:
        Template HTML content or None if not found.
    """
    template_path = TEMPLATES_PATH / template_name / "index.html"
    if not template_path.exists():
        logger.warning(f"Template not found: {template_path}")
        return None

    try:
        return template_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.error(f"Error reading template {template_path}: {e}")
        return None


def _load_base_assets() -> tuple[str, str]:
    """Load base CSS and shared JS content.

    Returns:
        Tuple of (base_css, shared_js).
    """
    base_css_path = TEMPLATES_PATH / "base.css"
    shared_js_path = TEMPLATES_PATH / "shared.js"
    charts_js_path = TEMPLATES_PATH / "charts.js"

    base_css = ""
    shared_js = ""

    if base_css_path.exists():
        try:
            base_css = base_css_path.read_text(encoding="utf-8")
        except OSError:
            pass

    if shared_js_path.exists():
        try:
            shared_js = shared_js_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Append charts.js to shared.js
    if charts_js_path.exists():
        try:
            charts_js = charts_js_path.read_text(encoding="utf-8")
            shared_js = shared_js + "\n\n" + charts_js
        except OSError:
            pass

    return base_css, shared_js


def _render_template(
    template_html: str,
    config: DisplayConfig,
    base_css: str,
    shared_js: str,
    slug: str,
    custom_css: str = "",
) -> str:
    """Render template with config values.

    Uses simple string replacement for Jinja2-style placeholders.
    """
    # Build CSS variables from config colors
    css_vars = f"""
    :root {{
        --bg-color: {config.colors['background']};
        --available-color: {config.colors['available']};
        --used-color: {config.colors['used']};
        --warning-color: {config.colors['warning']};
        --text-color: {config.colors['text']};
        --font-family: '{config.font['family']}', sans-serif;
        --font-size-budget: {config.font['size_budget']};
        --font-size-info: {config.font['size_info']};
        --scale: {config.scale};
    }}
    """

    # Build data attributes for JS
    data_attrs = f'data-slug="{slug}" data-chart-type="{config.chart_type}"'

    # Replace placeholders in template
    html = template_html

    # Inject CSS variables and base styles
    html = html.replace("<!-- CSS_VARIABLES -->", f"<style>{css_vars}</style>")
    html = html.replace("<!-- BASE_CSS -->", f"<style>{base_css}</style>")
    html = html.replace("<!-- CUSTOM_CSS -->", f"<style>{custom_css}</style>" if custom_css else "")

    # Inject JS
    html = html.replace("<!-- SHARED_JS -->", f"<script>{shared_js}</script>")

    # Inject data attributes on body
    html = html.replace("<body>", f"<body {data_attrs}>")

    # Replace text placeholders
    html = html.replace("{{ artwork_name }}", config.texts.get("artwork_name", ""))
    html = html.replace("{{ info_de }}", config.texts.get("info_de", ""))
    html = html.replace("{{ info_en }}", config.texts.get("info_en", ""))
    html = html.replace("{{ warning_de }}", config.texts.get("warning_de", ""))
    html = html.replace("{{ warning_en }}", config.texts.get("warning_en", ""))

    # Inject status endpoint URL
    html = html.replace("{{ status_url }}", f"/steuerung/{slug}/status")

    return html


@router.get("/{slug}", response_class=HTMLResponse)
async def display_page(slug: str, request: Request) -> HTMLResponse:
    """Render the visitor display page for an artwork.

    Args:
        slug: Artwork slug (directory name in steuerung/artworks/).

    Returns:
        Rendered HTML page for the kiosk display.
    """
    config_loader = get_display_config_loader()
    config = config_loader.get_config(slug)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Display configuration not found for '{slug}'",
        )

    # Load template
    template_html = _load_template(config.template)
    if not template_html:
        raise HTTPException(
            status_code=500,
            detail=f"Template '{config.template}' not found",
        )

    # Load base assets
    base_css, shared_js = _load_base_assets()

    # Load custom CSS if exists
    custom_css = ""
    custom_css_path = config_loader.get_custom_css_path(slug)
    if custom_css_path:
        try:
            custom_css = custom_css_path.read_text(encoding="utf-8")
        except OSError:
            pass

    # Render template
    html = _render_template(
        template_html=template_html,
        config=config,
        base_css=base_css,
        shared_js=shared_js,
        slug=slug,
        custom_css=custom_css,
    )

    return HTMLResponse(content=html)


@router.get("/{slug}/status", response_model=DisplayStatusResponse)
async def display_status(slug: str) -> DisplayStatusResponse:
    """Get current protection status for JS polling.

    Args:
        slug: Artwork slug (directory name in steuerung/artworks/).

    Returns:
        JSON status response for the display.
    """
    config_loader = get_display_config_loader()
    config = config_loader.get_config(slug)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Display configuration not found for '{slug}'",
        )

    if not config.artwork_uuid:
        raise HTTPException(
            status_code=400,
            detail="Display configuration missing artwork_uuid",
        )

    # Get protection service
    protection_service = get_protection_service()

    # Get protection status from service
    try:
        artwork_uuid = UUID(config.artwork_uuid)
        status = await protection_service.get_protection_status(artwork_uuid)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid artwork_uuid: {config.artwork_uuid}",
        )

    # If not protected, return default values
    if not status.get("protected"):
        return DisplayStatusResponse(
            available=True,
            budget_remaining=0,
            budget_max=0,
            budget_percent=100,
            resets_in=0,
            cooldown_active=False,
            cooldown_remaining=0,
            is_running=False,
        )

    state = status.get("state", {})
    time_slice = state.get("time_slice", {})

    budget_remaining = time_slice.get("remaining", 0)
    budget_max = time_slice.get("max", 0)
    budget_percent = int((budget_remaining / budget_max * 100) if budget_max > 0 else 100)

    cooldown_active = state.get("cooldown_active", False)
    cooldown_remaining = state.get("cooldown_remaining", 0)

    # Determine availability: can start AND not in cooldown
    available = state.get("can_start", True) and not cooldown_active

    return DisplayStatusResponse(
        available=available,
        budget_remaining=budget_remaining,
        budget_max=budget_max,
        budget_percent=budget_percent,
        resets_in=time_slice.get("resets_in", 0),
        cooldown_active=cooldown_active,
        cooldown_remaining=cooldown_remaining,
        is_running=state.get("is_running", False),
    )


@router.get("/", response_class=JSONResponse)
async def list_displays() -> JSONResponse:
    """List all available display configurations.

    Returns:
        JSON list of available artwork slugs with their configurations.
    """
    config_loader = get_display_config_loader()
    slugs = config_loader.list_artworks()

    displays = []
    for slug in slugs:
        config = config_loader.get_config(slug)
        if config:
            displays.append({
                "slug": slug,
                "artwork_uuid": config.artwork_uuid,
                "artwork_name": config.texts.get("artwork_name", slug),
                "template": config.template,
                "display_url": f"/steuerung/{slug}",
                "status_url": f"/steuerung/{slug}/status",
            })

    return JSONResponse(content={"displays": displays})
