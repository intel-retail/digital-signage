"""
MCP server exposing Digital Signage as an agent-facing sensor+actuator.

Runs in-process alongside the Flask app (same container, separate port) so
tools call the shared in-memory state directly instead of hitting REST over
HTTP. Read tools return structured results (the agent reads `source` and
`product` as fields, not from wording) plus a short `summary` for chat; action
tools return a short natural-language confirmation.

Any failure here is isolated: if the mcp package is missing or the server
can't bind its port, this logs an error and the rest of the application
(Flask, MQTT, AIG) keeps running unaffected.
"""
import sys
import logging
from typing import Any

import events

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
except ImportError as e:
    FastMCP = None
    ToolAnnotations = None
    logger.error(f"mcp package not available, MCP server will not start: {e}")

MCP_PORT = 5100
# Bounds for an agent-requested image ad; the camera flow is not limited by these.
MIN_DISPLAY_SECONDS = 1
MAX_DISPLAY_SECONDS = 600
CONTEXT_KEYS = ('weather', 'demand', 'age_mix', 'daypart')
READ_TOOLS = ('describe', 'get_current_ad', 'get_catalog')
ACT_TOOLS = ('select_dynamic_ad', 'trigger_ad', 'trigger_video_ad', 'clear_ad')


def _app():
    # main.py is launched as `python3 main.py` (runs as __main__), so "import main" here would
    # re-import it as a second, disconnected, never-initialized module instead of reusing it.
    return sys.modules['__main__']


def _format_price(value):
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _known_context_values(rules):
    """Values the rules file accepts per context key, so an unknown value is refused instead of
    silently falling through to the default product."""
    known = {key: set() for key in CONTEXT_KEYS}
    for rule in rules.get('rules', []):
        for key in CONTEXT_KEYS:
            if rule.get(key) is not None:
                known[key].add(str(rule[key]).strip().lower())
    return known


def _validate_context(context, rules):
    known = _known_context_values(rules)
    for key, value in context.items():
        if str(value).strip().lower() not in known[key]:
            allowed = ', '.join(sorted(known[key])) or 'none configured'
            raise ValueError(f"unknown {key} '{value}'; the signage accepts: {allowed}.")


def _validate_display_seconds(value):
    if not isinstance(value, int) or isinstance(value, bool) \
            or not MIN_DISPLAY_SECONDS <= value <= MAX_DISPLAY_SECONDS:
        raise ValueError(f"display_seconds must be an integer from {MIN_DISPLAY_SECONDS} to {MAX_DISPLAY_SECONDS}.")


def _current_ad_summary(info):
    item, remaining = info['item'], info['seconds_remaining']
    return {
        'video_cancelling': f"The video ad for '{item}' was cancelled, but its request is still finishing in the "
                            "background; a new trigger_video_ad call may be briefly rejected until then.",
        'video_generating': f"A video ad for '{item}' is currently being generated and will appear shortly.",
        'video': f"Currently showing an agent-commanded video ad for '{item}', {remaining}s remaining.",
        'agent_cancelling': f"The ad for '{item}' was cancelled, but its request is still finishing in the "
                            "background; a new trigger_ad call may be briefly rejected until then.",
        'generating': f"An ad for '{item}' is currently being generated and will appear shortly.",
        'agent': f"Currently showing an agent-commanded ad for '{item}', {remaining}s remaining.",
    }.get(info['mode'], f"Currently showing a camera-driven ad for '{item}'." if item
          else "No advertisement is currently being displayed.")


def _current_ad(info):
    """Structured view of get_active_ad_info(): who put the ad up, which product, what state it is in."""
    mode = info['mode']
    source = 'camera' if mode == 'camera' and info['item'] else 'none' if mode == 'camera' else 'agent'
    state = ('cancelling' if mode.endswith('cancelling') else 'generating' if mode.endswith('generating')
             else 'showing' if source != 'none' else 'none')
    return {
        'source': source,
        'product': info['item'],
        'media': 'video' if mode.startswith('video') else 'image' if source != 'none' else None,
        'state': state,
        'seconds_remaining': info['seconds_remaining'],
        'summary': _current_ad_summary(info),
    }


def build_mcp_app():
    if FastMCP is None:
        raise RuntimeError("mcp package is not installed")

    # This container is not host-published; nginx reaches it over the private Docker network.
    mcp = FastMCP("digital-signage", host="0.0.0.0", port=MCP_PORT)  # nosec B104
    read_only = ToolAnnotations(readOnlyHint=True)

    @mcp.tool(annotations=read_only)
    def describe() -> dict[str, Any]:
        """Describe this service's contract: store, event types, read tools and action tools."""
        main = _app()
        return {
            'service': 'digital-signage',
            'store_id': events.STORE_ID,
            'event_types': {name: sorted(fields) for name, fields in events.EVENT_FIELDS.items()},
            'event_delivery': ('one-way push of ' + ', '.join(sorted(events.FORWARDED_TYPES))
                               if events.EVENTS_URL and events.FORWARDED_TYPES else 'not configured'),
            'read_tools': list(READ_TOOLS),
            'act_tools': list(ACT_TOOLS),
            'context_values': {key: sorted(values) for key, values in
                               _known_context_values(main.context_rules).items()},
            'video_ad_display_seconds': main.VIDEO_AD_DISPLAY_SECONDS,
            'summary': (
                "Digital Signage sensor+actuator. "
                "Reads: get_current_ad() reports the ad on screen (source camera|agent|none, product, media, state); "
                "get_catalog() lists available products and their cross-sell promos. "
                "Actions: select_dynamic_ad(weather, demand, age_mix, daypart, display_seconds, benchmark) "
                "resolves a shopping context to a product and displays its ad (a predefined image if one "
                "exists, otherwise an AI-generated image); trigger_ad(item, display_seconds, promo_text, "
                "slogan) directly displays a specific catalog item's ad by name, bypassing context resolution; "
                "trigger_video_ad(item, description) displays a looping video ad, live on screen for "
                f"{main.VIDEO_AD_DISPLAY_SECONDS} seconds - item for a catalog product (predefined video if "
                "provisioned, else AI-generated with catalog overlays), or description for free text describing "
                "the video's content directly; exactly one of the two is required, not both; "
                "clear_ad() clears any active override and returns to the camera-driven flow. "
                "Events: product_detected {label, confidence} and ad_displayed {product, variant, media, trigger} "
                "are recorded in the service log; the types listed in QSR_EVENT_TYPES are pushed to the QSR agent "
                "when QSR_EVENTS_URL is set."
            ),
        }

    @mcp.tool(annotations=read_only)
    def get_current_ad() -> dict[str, Any]:
        """Report the advertisement currently on the signage display: source (camera, agent or none),
        product, media (image or video), state (showing, generating, cancelling or none), seconds_remaining
        and a one-sentence summary."""
        return _current_ad(_app().get_active_ad_info())

    @mcp.tool(annotations=read_only)
    def get_catalog() -> dict[str, Any]:
        """List the products available for advertising with price, unit and cross-sell promos."""
        main = _app()
        entries = main.get_catalog_summary()
        products = [{'product': entry['product'], 'price': entry['price'], 'unit': entry['unit'],
                     'cross_sells': list(entry['cross_sells'])} for entry in entries]
        if not entries:
            summary = "No products are currently configured."
        else:
            parts = [f"{entry['product']} ({_format_price(entry['price'])}{entry['unit']}, cross-sells with "
                     f"{', '.join(entry['cross_sells']) if entry['cross_sells'] else 'no cross-sell offers'})"
                     for entry in entries]
            summary = f"{len(entries)} products available: " + "; ".join(parts) + "."
        return {'products': products, 'summary': summary}

    @mcp.tool()
    def select_dynamic_ad(weather: str = "", demand: str = "", age_mix: str = "",
                           daypart: str = "", display_seconds: int = 60, benchmark: bool = False) -> str:
        """Resolve a shopping context (weather, demand, age_mix, daypart) to a product and display its ad.
        Each given value must be one the signage's rules know (see describe().context_values)."""
        main = _app()
        context = {k: v for k, v in {
            "weather": weather, "demand": demand, "age_mix": age_mix, "daypart": daypart
        }.items() if v}
        if not context:
            raise ValueError("No context provided (need at least one of weather, demand, age_mix, daypart).")
        _validate_context(context, main.context_rules)
        _validate_display_seconds(display_seconds)
        result = main.select_dynamic_ad_core(context, display_seconds=display_seconds, benchmark=benchmark)
        if result.get('error'):
            raise ValueError(f"Could not resolve context {context}: {result['error']}")
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
            raise ValueError("item is required.")
        _validate_display_seconds(display_seconds)
        result = main.trigger_ad_core(item, display_seconds=display_seconds,
                                       promo_text=promo_text or None, slogan=slogan or None)
        if result.get('error'):
            raise ValueError(result['error'])
        return (f"Ad for '{result['item']}' is generating now and will appear on the display within a "
                f"few seconds, live for {result['display_seconds']}s.")

    @mcp.tool()
    def trigger_video_ad(item: str = "", description: str = "") -> str:
        """Display a looping video ad, live on screen for VIDEO_AD_DISPLAY_SECONDS. Provide exactly one
        of `item` or `description` (not both, since their overlays/content would be unrelated):
        - item only: a catalog product by name; uses its predefined video if provisioned, otherwise
          generates one with the catalog's price/promo/slogan/frame overlays.
        - description only: free text describing exactly what the video should show (e.g. "a cup of
          coffee with steam rising, commercial product video, subtle natural motion"); generated fresh,
          no overlays, no predefined-video lookup.
        Rejected if a video ad is already generating or still actively displaying - retry once it
        finishes rather than expecting this call to preempt it.
        MCP-triggered only."""
        main = _app()
        item = item.strip()
        description = description.strip()
        if main._is_blank(item) and main._is_blank(description):
            raise ValueError("Provide either item or description.")
        if not main._is_blank(item) and not main._is_blank(description):
            raise ValueError("Provide only one of item or description, not both.")
        result = main.trigger_video_ad_core(item=item or None, description=description or None)
        if result.get('error'):
            raise ValueError(result['error'])
        return (f"Video ad for '{result['item']}' is generating now (this can take a few minutes) and will "
                f"appear on the display once ready, playing for {result['display_seconds']}s.")

    @mcp.tool()
    def clear_ad() -> str:
        """Clear any agent-commanded override ad (image or video, including one still generating) and
        return the display to the camera-driven flow."""
        main = _app()
        result = main.clear_agent_override()
        cleared = [item for item in (result.get('cleared_item'), result.get('cleared_video_item')) if item]
        if cleared:
            return f"Cleared the agent-commanded ad(s) for {', '.join(repr(item) for item in cleared)}; display returned to camera-driven flow."
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
