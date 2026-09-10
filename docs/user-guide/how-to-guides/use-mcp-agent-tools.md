# Use MCP Agent Tools

The Web UI exposes an [MCP](https://modelcontextprotocol.io/) server so an LLM-based agent can read what is on the signage display and drive it directly, alongside the existing camera-driven ad flow.

## Endpoint

The MCP server runs inside the `web-ui` container on port `5100` (Streamable HTTP transport) and is reached through the `nginx` proxy at:

```text
https://<HOST_IP>:5000/mcp
```

Port `5100` is not published directly on the host; all access goes through the TLS-terminating nginx proxy.

## Available Tools

| Tool | Description |
| --- | --- |
| `describe` | Describes what the agent can read and do. |
| `get_current_ad` | Returns a short description of the advertisement currently shown. |
| `get_catalog` | Lists available products and their cross-sell promos. |
| `select_dynamic_ad` | Resolves a shopping context (`weather`, `demand`, `age_mix`, `daypart`) to a product and displays its ad. |
| `trigger_ad` | Directly displays a specific catalog item's ad by name, bypassing context resolution. |
| `clear_ad` | Clears any active agent-commanded override and returns to the camera-driven flow. |

## Connect and Test

### MCP Inspector

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 npx @modelcontextprotocol/inspector
```

In the Inspector UI:

- **Transport:** Streamable HTTP
- **URL:** `https://<HOST_IP>:5000/mcp`
- Allow insecure/self-signed certificates (the nginx proxy uses a self-signed certificate)

Use "List Tools" to see the tools above, then call them directly to verify responses.

### Python Client

```python
import asyncio, ssl
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

async def main():
    async with streamablehttp_client("https://<HOST_IP>:5000/mcp", ssl=ssl_ctx) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            print(await session.list_tools())
            print(await session.call_tool("trigger_ad", {"item": "banana"}))

asyncio.run(main())
```

## Notes

- If the `mcp` package fails to import or the server can't bind its port, the MCP server logs an error and stays disabled; the rest of the application (Flask, MQTT, AIG) keeps running unaffected.
- `select_dynamic_ad` requires `web-ui/context_rules.json` to be configured; if it is missing or invalid, the tool is unavailable.
