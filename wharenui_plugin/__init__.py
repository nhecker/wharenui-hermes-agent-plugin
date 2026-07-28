"""Wharenui Hermes plugin — seam-aware register() stub."""

import logging

log = logging.getLogger("wharenui_plugin")


def register(ctx):
    """Register Wharenui with Hermes Agent.

    Seam-aware: probes for register_control_tool; if absent (stock Hermes),
    emits a non-fatal AI-visible WARNING and loads journal-only in degraded
    mode. Control-tool wiring is later work (depends on WP2 core seam).
    """
    if hasattr(ctx, "register_control_tool"):
        log.info("Wharenui phase-control seam detected; full mode available.")
    else:
        log.warning(
            "Wharenui phase-control seam not found; "
            "loading journal-only in degraded/observed mode."
        )