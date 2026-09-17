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
| `trigger_ad` | Directly displays a specific catalog item's ad by name, bypassing context resolution. Like `select_dynamic_ad`, it generates a dynamic (AI-generated) ad when no predefined image exists for the item. |
| `clear_ad` | Clears any active agent-commanded override and returns to the camera-driven flow. |

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

## Notes

- If the `mcp` package fails to import or the server can't bind its port, the MCP server logs an error and stays disabled; the rest of the application (Flask, MQTT, AIG) keeps running unaffected.
- `select_dynamic_ad` requires `web-ui/context_rules.json` to be configured; if it is missing or invalid, the tool is unavailable.
