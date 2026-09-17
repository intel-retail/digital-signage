"""
MCP server exposing Digital Signage as an agent-facing sensor+actuator.

Runs in-process alongside the Flask app (same container, separate port) so
tools call the shared in-memory state directly instead of hitting REST over
HTTP. Tool results are short natural-language strings, not raw payloads, so
an LLM client doesn't spend tokens stitching structured data together.

Any failure here is isolated: if the mcp package is missing or the server
can't bind its port, this logs an error and the rest of the application
(Flask, MQTT, AIG) keeps running unaffected.
"""
import sys
import logging

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    FastMCP = None
    logger.error(f"mcp package not available, MCP server will not start: {e}")

MCP_PORT = 5100


def _app():
    # main.py is launched as `python3 main.py` (runs as __main__), so "import main" here would
    # re-import it as a second, disconnected, never-initialized module instead of reusing it.
    return sys.modules['__main__']


def _format_price(value):
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def build_mcp_app():
    if FastMCP is None:
        raise RuntimeError("mcp package is not installed")

    mcp = FastMCP("digital-signage", host="0.0.0.0", port=MCP_PORT)

    @mcp.tool()
    def describe() -> str:
        """Describe what this digital signage agent can read and do."""
        return (
            "Digital Signage sensor+actuator. "
            "Reads: get_current_ad() describes what's on screen now; "
            "get_catalog() lists available products and their cross-sell promos. "
            "Actions: select_dynamic_ad(weather, demand, age_mix, daypart, display_seconds, benchmark) "
            "resolves a shopping context to a product and displays its ad (a predefined image if one "
            "exists, otherwise an AI-generated image); trigger_ad(item, display_seconds, promo_text, "
            "slogan) directly displays a specific catalog item's ad by name, bypassing context resolution; "
            "clear_ad() clears any active override and returns to the camera-driven flow. "
            "Note: a detection/display event history is not available yet."
        )

    @mcp.tool()
    def get_current_ad() -> str:
        """Return a short description of the advertisement currently shown on the signage display."""
        main = _app()
        info = main.get_active_ad_info()
        if info['mode'] == 'generating':
            return f"An ad for '{info['item']}' is currently being generated and will appear shortly."
        if info['mode'] == 'agent':
            return (f"Currently showing an agent-commanded ad for '{info['item']}', "
                    f"{info['seconds_remaining']}s remaining.")
        if info['item']:
            return f"Currently showing a camera-driven ad for '{info['item']}'."
        return "No advertisement is currently being displayed."

    @mcp.tool()
    def get_catalog() -> str:
        """Return a short summary of products available for advertising and their cross-sell promos."""
        main = _app()
        entries = main.get_catalog_summary()
        if not entries:
            return "No products are currently configured."
        parts = []
        for entry in entries:
            cross_sells = ", ".join(entry['cross_sells']) if entry['cross_sells'] else "no cross-sell offers"
            parts.append(f"{entry['product']} ({_format_price(entry['price'])}{entry['unit']}, cross-sells with {cross_sells})")
        return f"{len(entries)} products available: " + "; ".join(parts) + "."

    @mcp.tool()
    def select_dynamic_ad(weather: str = "", demand: str = "", age_mix: str = "",
                           daypart: str = "", display_seconds: int = 60, benchmark: bool = False) -> str:
        """Resolve a shopping context (weather, demand, age_mix, daypart) to a product and display its ad."""
        main = _app()
        context = {k: v for k, v in {
            "weather": weather, "demand": demand, "age_mix": age_mix, "daypart": daypart
        }.items() if v}
        if not context:
            return "No context provided (need at least one of weather, demand, age_mix, daypart)."
        result = main.select_dynamic_ad_core(context, display_seconds=display_seconds, benchmark=benchmark)
        if result.get('error'):
            return f"Could not resolve context {context}: {result['error']}"
        product = result['resolved_product']
        if benchmark:
            timing = result.get('timing_ms', {})
            return (f"Context {context} resolved to '{product}'. Ad generated via {result.get('source')} "
                    f"in {timing.get('total', '?')}ms and is now live for {display_seconds}s.")
        return (f"Context {context} resolved to '{product}'. Ad is generating now and will appear on the "
                f"display within a few seconds, live for {display_seconds}s.")

    @mcp.tool()
    def trigger_ad(item: str, display_seconds: int = 60, promo_text: str = "", slogan: str = "") -> str:
        """Directly display a specific catalog item's ad by name, bypassing context resolution."""
        main = _app()
        if not item.strip():
            return "item is required."
        result = main.trigger_ad_core(item, display_seconds=display_seconds,
                                       promo_text=promo_text or None, slogan=slogan or None)
        if result.get('error'):
            return f"{result['error']}"
        return (f"Ad for '{result['item']}' is generating now and will appear on the display within a "
                f"few seconds, live for {result['display_seconds']}s.")

    @mcp.tool()
    def clear_ad() -> str:
        """Clear any agent-commanded override ad and return the display to the camera-driven flow."""
        main = _app()
        result = main.clear_agent_override()
        if result.get('cleared_item'):
            return f"Cleared the agent-commanded ad for '{result['cleared_item']}'; display returned to camera-driven flow."
        return "No agent-commanded ad was active; display is already camera-driven."

    return mcp


def run_mcp_server():
    """Start the MCP server (blocking). Intended to run in its own daemon thread."""
    try:
        mcp = build_mcp_app()
    except Exception as e:
        logger.error(f"MCP server disabled: {e}")
        return
    try:
        logger.info(f"Starting MCP server (Streamable HTTP) on port {MCP_PORT}")
        mcp.run(transport="streamable-http")
    except Exception as e:
        logger.error(f"MCP server stopped unexpectedly: {e}")
