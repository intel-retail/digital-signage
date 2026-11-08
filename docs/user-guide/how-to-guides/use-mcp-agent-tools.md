# Use MCP Agent Tools

The Web UI exposes an [MCP](https://modelcontextprotocol.io/) server so an LLM-based agent can read what is on the signage display and drive it directly, alongside the existing camera-driven ad flow.

## Endpoint

The MCP server runs inside the `web-ui` container on port `5100` (Streamable HTTP transport) and is reached through the `nginx` proxy at:

```text
https://<HOST_IP>:5000/mcp
```

Port `5100` is not published directly on the host; all access goes through the TLS-terminating nginx proxy.

The nginx certificate is self-signed and regenerated on every `nginx` container
restart (`configs/nginx/nginx-cert-gen.sh`). Its Subject Alternative Names cover
`localhost`, `127.0.0.1`, `host.docker.internal`, and `HOST_IP` (if set to a
real IP/hostname in `.env`) — connect using one of those, or add another SAN
entry for your case. An agent connecting from a container on the same host
(e.g. via `host.docker.internal`) can trust this certificate automatically at
its own startup using a trust-on-first-use fetch; see the qsr-agent project's
`docs/architecture.md` ("Remote MCP TLS trust") for an example of that pattern.

## Available Tools

| Tool | Description |
| --- | --- |
| `describe` | Describes what the agent can read and do. |
| `get_current_ad` | Returns a short description of the advertisement currently shown. |
| `get_catalog` | Lists available products and their cross-sell promos. |
| `select_dynamic_ad` | Resolves a shopping context (`weather`, `demand`, `age_mix`, `daypart`) to a product and displays its ad. |
| `trigger_ad` | Directly displays a specific catalog item's ad by name, bypassing context resolution. Like `select_dynamic_ad`, it generates a dynamic (AI-generated) ad when no predefined image exists for the item. |
| `trigger_video_ad` | Displays a looping video ad, live on screen for `VIDEO_AD_DISPLAY_SECONDS` (default 5s). Takes exactly one of `item` (a catalog product; uses its predefined video if provisioned, otherwise generates one with the catalog's price/promo/slogan/frame overlays) or `description` (free text describing the video's content directly, no overlays) — not both, since their overlays/content would be unrelated. MCP-triggered only — never produced by the camera-driven flow. |
| `clear_ad` | Clears any active agent-commanded override and returns to the camera-driven flow. |

> **Video ad generation time:** `trigger_video_ad` returns immediately and the video is generated in the background. On an Intel iGPU with the default `f16` precision this takes about 25-30 s per video; the first request also loads the video model (about 20 s) unless `AIG_PRELOAD_VIDEO_MODEL=true`. Running in `f32` takes about 3 minutes. See [Change Inference Device](change-inference-device.md#video-precision-and-preloading). A new `trigger_video_ad` call may be rejected until the current video finishes.

When `select_dynamic_ad`, `trigger_ad` or `trigger_video_ad` refuses a request (missing or invalid arguments, an ad already generating, an unknown item), the call fails as an MCP tool error (`isError` is set) instead of returning a normal text result. Agents can therefore tell a refused action from an executed one.

## Connect and Test

### MCP Inspector

Requires Node.js (install via [nvm](https://github.com/nvm-sh/nvm) if you don't already have it).

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 npx @modelcontextprotocol/inspector
```

In the Inspector UI:

- **Transport:** Streamable HTTP
- **URL:** `https://<HOST_IP>:5000/mcp`
- Allow insecure/self-signed certificates (the nginx proxy uses a self-signed certificate)

Use "List Tools" to see the tools above, then call them directly to verify responses.

### Python Client

```bash
pip install mcp==1.29.1 httpx==0.28.1
```

```python
import asyncio
import ssl
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def get_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def run_mcp_client(host_ip: str, port: int = 5000):
    uri = f"https://{host_ip}:{port}/mcp"
    ssl_context = get_ssl_context()

    print(f"Connecting to {uri}")

    # Build httpx client configured with our custom SSL context
    http_client = httpx.AsyncClient(
        verify=ssl_context,
        timeout=httpx.Timeout(30.0, read=300.0),
        follow_redirects=True,
    )

    try:
        async with http_client:
            async with streamable_http_client(uri, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    print("Initializing session...")
                    await session.initialize()

                    print("\nListing tools...")
                    tools_response = await session.list_tools()
                    print(tools_response)

                    print("\nCalling trigger_ad...")
                    result = await session.call_tool("trigger_ad", {"item": "banana"})
                    print("\nResult:")
                    print(result)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_mcp_client("localhost"))
```

## Events

The web UI records two named events. Each one is written to the `web-ui` container log as a single
`SIGNAGE_EVENT {json}` line (with an increasing `seq`) and can also be pushed to an agent.

| Event | `data` fields | When |
| --- | --- | --- |
| `product_detected` | `label`, `confidence` | A product passes the confidence and recency checks. It is reported when it appears, and again only after it was absent for `QSR_EVENT_DETECTION_COOLDOWN_SECONDS` (default 60). |
| `ad_displayed` | `product`, `variant` (`predefined` or `generated`), `media` (`image` or `video`), `trigger` (`camera` or `agent`) | An ad goes live, whether from the camera flow or an agent tool. Image ads fire when a display client is first served the image. |

Read the log with `docker logs web-ui 2>&1 | grep SIGNAGE_EVENT`.

To push events to an agent, set these in `.env`:

- `QSR_EVENTS_URL`: the agent endpoint, for example `http://<agent-host>:8600/autonomy/events`. Leave it empty to only log events.
- `QSR_STORE_ID`: the store identifier the agent expects. Defaults to `qsr-001`.

The `web-ui` container sends through the proxy settings from your environment, so add the agent host to `no_proxy`.
Delivery runs in the background and retries three times; a client error other than HTTP 429 is not retried. A failed or slow agent never delays ad rendering.

The log is not persisted and there is no replay: the delivery queue is in memory, so events queued while the agent is unreachable are lost when the `web-ui` container restarts.

## Notes

- If the `mcp` package fails to import or the server can't bind its port, the MCP server logs an error and stays disabled; the rest of the application (Flask, MQTT, AIG) keeps running unaffected.
- `select_dynamic_ad` requires `web-ui/context_rules.json` to be configured; if it is missing or invalid, the tool is unavailable.
