# MCP Server Architecture

Technical reference for how the Digital Signage MCP server is implemented, how a client
discovers and calls its tools, and how each tool relates to existing application code.
See [use-mcp-agent-tools.md](use-mcp-agent-tools.md) for end-user connection instructions.

## Overview

The MCP server ([web-ui/mcp_server.py](https://github.com/intel-retail/digital-signage/blob/main/web-ui/mcp_server.py)) runs in-process
alongside the Flask app in the `web-ui` container, on port `5100`, using the `FastMCP`
Streamable HTTP transport. It is started as a daemon thread from
[web-ui/main.py](https://github.com/intel-retail/digital-signage/blob/main/web-ui/main.py) after `initialize_app()` completes, so a
failure to import `mcp` or bind the port only disables the MCP thread — Flask, MQTT,
and AIG keep running.

Because it runs in the same process as `main.py`, tool implementations call shared
in-memory state directly (via `sys.modules['__main__']`) instead of making HTTP
requests to the REST API.

Externally, the server is reached through the nginx proxy at `/mcp`
(`configs/nginx/nginx.conf`), which forwards to `http://web-ui:5100` and terminates TLS.

## How a client discovers and calls tools

This follows the standard MCP protocol handshake — no custom discovery code:

1. **Registration**: each Python function decorated with `@mcp.tool()` in
   `mcp_server.py` is auto-registered by the `FastMCP` SDK. The tool name is the
   function name; the input schema is derived from the function's type-annotated
   parameters; the description shown to clients is the function's docstring.
2. **`initialize`**: client opens a Streamable HTTP connection to `/mcp` and sends
   `initialize`.
3. **`tools/list`**: client requests the tool catalog; the server returns all
   registered tools with their descriptions and JSON-schema parameters.
4. **`tools/call`**: client invokes a tool by name with arguments; FastMCP dispatches
   to the corresponding Python function and returns its string return value as the
   result.

The `describe` tool exists as a convenience for agents that prefer reading a single
natural-language capability summary instead of parsing the schema.

## Tools added

| Tool | Signature | Purpose |
| --- | --- | --- |
| `describe()` | → str | Static capability summary for the agent |
| `get_current_ad()` | → str | What's currently on screen (camera / agent / generating) |
| `get_catalog()` | → str | Lists products and their cross-sell promos |
| `select_dynamic_ad()` | `(weather, demand, age_mix, daypart, display_seconds, benchmark)` → str | Resolves a shopping context to a product and displays its ad |
| `trigger_ad()` | `(item, display_seconds, promo_text, slogan)` → str | Directly displays a named catalog item's ad |
| `trigger_video_ad()` | `(item, description)` → str | Displays a looping video ad, live on screen for `VIDEO_AD_DISPLAY_SECONDS` (configured default 3s); exactly one of `item` (a catalog product; predefined video if provisioned, else AI-generated with catalog overlays) or `description` (free text describing the video directly) is required — not both, since their overlays/content would be unrelated; MCP-triggered only; generation runs in the background (about 25-30 s on GPU with the default `f16` precision, see [Change Inference Device](change-inference-device.md#video-precision-and-preloading)) |
| `clear_ad()` | → str | Clears the agent override, returns to camera-driven flow |

## New implementation vs. reuse of existing code

| Tool | Underlying code | New vs. reused |
| --- | --- | --- |
| `describe` | Inline string, no backing function | Fully new, MCP-only |
| `get_current_ad` | `get_active_ad_info()` | New function, but reads the existing `agent_override_*` / `last_selected_item` state — the same state `Ad_Generator.get_current_advertisement()` (used by the existing `/get_current_advertisement` REST route) already checks. Also reports the new `video_override_*` state (see `trigger_video_ad`) |
| `get_catalog` | `get_catalog_summary()` | New function built entirely on the existing `product_associations` dict, already populated from `ProductAssociations.csv` for the camera-driven flow |
| `trigger_ad` | `trigger_ad_core()` | New orchestration function; calls the pre-existing `resolve_product_label()` and the pre-existing core engine `Ad_Generator.generate_advertisement()` (same method the MQTT/camera pipeline uses). Introduces new state: `agent_override_ad/_until/_item/_generating`, `override_epoch` |
| `select_dynamic_ad` | `select_dynamic_ad_core()` + `resolve_context_to_product()` + `load_context_rules()` | New feature end-to-end (new `context_rules.json` config, new matching logic), but delegates final ad rendering to the same existing `generate_advertisement()` engine |
| `trigger_video_ad` | `trigger_video_ad_core()` + `Ad_Generator.generate_video_ad()` | Fully new, MCP-only video path with its own isolated state (`video_override_media/_until/_item/_generating`, `_video_generation_lock`). Predefined videos are looked up directly by product name (new `product_video_paths` dict from a new `pre_defined_ad_video` CSV column, mimetype detected from file extension) with no ChromaDB/AIG involvement. When no predefined video exists it calls a new AIG endpoint, `/aig/mvid/` (`Text2VideoPipeline`/LTX-Video model, separate from the existing image model), which generates genuinely temporally-related frames in a single call and returns an already-encoded looping animated WEBP (`image/webp`). AIG-side: new `videoinf.py` resource, new `AigServerMetadata` video-model config/singleton, and the promo/frame/logo overlay logic was extracted into a shared `apply_ad_overlays()` helper reused by both the image and video endpoints |
| `clear_ad` | `clear_agent_override()` | Fully new; manipulates the new override state fields |

**Notes:**

- Despite docstrings stating some core functions are "shared by the REST route and the
  MCP tool," there is currently no REST route calling `trigger_ad_core` or
  `select_dynamic_ad_core` — only `/`, `/portrait`, and `/get_current_advertisement`
  exist as Flask routes today.
- The genuine reuse point across the camera-driven flow and the new MCP action tools
  is `Ad_Generator.generate_advertisement()` — the image-generation engine that calls
  the AIG server's `/ase/predef/query/ad` and `/aig/minf/` endpoints is unchanged in
  interface and shared by both paths.
- On the AIG server side, the same change hardened (but did not add new endpoints to)
  the existing `/aig/minf/` inference API: a `model_lock` was added for thread-safety
  and the Flask app was switched to `threaded=True`, since MCP tools can now trigger
  concurrent generation requests that didn't previously occur.
- `trigger_video_ad` reads its own `AIG_VIDEO_INFERENCE_DEVICE` env var (web-ui) to
  pick the `device` sent to `/aig/mvid/`, kept deliberately separate from the image
  path's `AIG_INFERENCE_DEVICE`. It must match the AIG server's `AIG_VIDEO_MODEL_DEVICE`
  (same `.env` source variable) or the server can't reuse its preloaded video
  pipeline and rebuilds it from disk on every call.

## Error reporting

The action tools (`select_dynamic_ad`, `trigger_ad`, `trigger_video_ad`) raise `ValueError` when the
core function returns an `error`, so FastMCP reports the call as a tool error (`isError`). Clients such
as the QSR agent rely on this to avoid recording a refused action as executed.

## Events

[web-ui/events.py](https://github.com/intel-retail/digital-signage/blob/main/web-ui/events.py) builds the
`product_detected` and `ad_displayed` events, logs each as a `SIGNAGE_EVENT {json}` line and, when
`QSR_EVENTS_URL` is set, delivers it from a background thread. `main.py` emits `product_detected` from the
MQTT detection path (with a per-label cooldown) and `ad_displayed` when an ad goes live, from both the camera
flow and the agent tools. An image ad is announced when a display client is first served it, so an image
hidden behind a video override, superseded, or cleared before it is served produces no event. Event fields and settings are described in
[use-mcp-agent-tools.md](use-mcp-agent-tools.md#events).

## Control flow — client connecting and calling a tool

The full interaction is shown in four steps; each diagram continues from the one before it.

### 1. Session setup and tool discovery

```mermaid
---
config: {"theme":"base","themeVariables":{"actorBkg":"#E3F2FD","actorBorder":"#1E88E5","actorTextColor":"#0D47A1","signalColor":"#37474F","signalTextColor":"#263238","activationBkgColor":"#E8F5E9","activationBorderColor":"#43A047"},"sequence":{"mirrorActors":false,"messageAlign":"center"}}
---
sequenceDiagram
    autonumber
    participant Client as MCP Client<br/>(Inspector / LLM agent)
    participant Nginx as nginx proxy<br/>(TLS, :5000)
    participant MCP as MCP server thread<br/>(FastMCP, :5100)
    Client->>+Nginx: HTTPS POST /mcp (initialize)
    Nginx->>+MCP: proxy_pass http://web-ui:5100/mcp
    MCP-->>-Client: initialize result (capabilities)
    deactivate Nginx
    Client->>+Nginx: tools/list
    Nginx->>+MCP: forward
    MCP-->>-Client: [describe, get_current_ad, get_catalog,<br/>select_dynamic_ad, trigger_ad, trigger_video_ad, clear_ad] + schemas
    deactivate Nginx
```

### 2. `tools/call "trigger_ad"` — returns immediately

```mermaid
---
config: {"theme":"base","themeVariables":{"actorBkg":"#E3F2FD","actorBorder":"#1E88E5","actorTextColor":"#0D47A1","signalColor":"#37474F","signalTextColor":"#263238","activationBkgColor":"#E8F5E9","activationBorderColor":"#43A047"},"sequence":{"mirrorActors":false,"messageAlign":"center"}}
---
sequenceDiagram
    autonumber
    participant Client as MCP Client<br/>(Inspector / LLM agent)
    participant Nginx as nginx proxy<br/>(TLS, :5000)
    participant MCP as MCP server thread<br/>(FastMCP, :5100)
    participant Main as main.py<br/>(__main__ / Flask app)
    Client->>+Nginx: tools/call "trigger_ad" {item, display_seconds}
    Nginx->>+MCP: forward (proxy_buffering off, streamable-http)
    MCP->>+Main: _app() -> sys.modules['__main__']
    MCP->>Main: trigger_ad_core(item, display_seconds, ...)
    Main->>Main: resolve_product_label(item)
    Main->>Main: acquire _generation_lock (non-blocking)
    Main-->>-MCP: {'status': 'generating', 'item': resolved, ...}
    MCP-->>-Client: "Ad for '<item>' is generating now..." (immediate)
    deactivate Nginx
```

### 3. Background daemon thread (async, after the response is sent)

```mermaid
---
config: {"theme":"base","themeVariables":{"actorBkg":"#E3F2FD","actorBorder":"#1E88E5","actorTextColor":"#0D47A1","signalColor":"#37474F","signalTextColor":"#263238","activationBkgColor":"#E8F5E9","activationBorderColor":"#43A047"},"sequence":{"mirrorActors":false,"messageAlign":"center"}}
---
sequenceDiagram
    autonumber
    participant Main as main.py<br/>(__main__ / Flask app)
    participant AdGen as Ad_Generator<br/>(generate_advertisement)
    participant AIG as AIG server<br/>(:5003)
    activate Main
    Main->>+AdGen: generate_advertisement(item, associations)
    AdGen->>+AIG: POST /ase/predef/query/ad (check predefined)
    AIG-->>-AdGen: predefined image (if found)
    alt no predefined match
        AdGen->>+AIG: POST /aig/minf/ (dynamic generation)
        AIG-->>-AdGen: generated image bytes
    end
    AdGen->>-Main: last_generated_ad captured
    Main->>Main: agent_override_ad = captured<br/>agent_override_until = now + secs
    Main->>Main: release _generation_lock
    deactivate Main
```

### 4. `tools/call "get_current_ad"` — reads the override state

```mermaid
---
config: {"theme":"base","themeVariables":{"actorBkg":"#E3F2FD","actorBorder":"#1E88E5","actorTextColor":"#0D47A1","signalColor":"#37474F","signalTextColor":"#263238","activationBkgColor":"#E8F5E9","activationBorderColor":"#43A047"},"sequence":{"mirrorActors":false,"messageAlign":"center"}}
---
sequenceDiagram
    autonumber
    participant Client as MCP Client<br/>(Inspector / LLM agent)
    participant Nginx as nginx proxy<br/>(TLS, :5000)
    participant MCP as MCP server thread<br/>(FastMCP, :5100)
    participant Main as main.py<br/>(__main__ / Flask app)
    Client->>+Nginx: tools/call "get_current_ad"
    Nginx->>+MCP: forward
    MCP->>+Main: get_active_ad_info()
    Main-->>-MCP: {'mode': 'agent', 'item': ..., 'seconds_remaining': ...}
    MCP-->>-Client: "Currently showing an agent-commanded ad for '<item>'..."
    deactivate Nginx
```

## Data flow — state and payloads across components

The data flow is shown in four views that share the same components: how requests reach the tools, which tools read and write the shared state, the image-ad generation path, and the video-ad path.

### Request path — client to MCP tools and REST routes

```mermaid
---
config: {"theme":"base","themeVariables":{"fontSize":"18px","primaryColor":"#FFFFFF","primaryBorderColor":"#607D8B","primaryTextColor":"#263238","lineColor":"#546E7A","clusterBkg":"#FAFAFA","clusterBorder":"#B0BEC5"},"flowchart":{"curve":"linear","nodeSpacing":30,"rankSpacing":60,"padding":16}}
---
flowchart TB
    classDef client fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#0D47A1
    classDef proxy  fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#E65100
    classDef tool   fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#1B5E20
    classDef flask  fill:#E0F7FA,stroke:#00ACC1,stroke-width:2px,color:#006064
    subgraph Client["MCP Client"]
        C1["LLM agent / Inspector"]
    end
    subgraph Proxy["nginx (TLS termination)"]
        N1["/mcp location<br/>proxy_pass web-ui:5100"]
    end
    subgraph WebUI["web-ui container"]
        subgraph MCPThread["MCP server thread (:5100)"]
            direction LR
            T1["describe"]
            T2["get_current_ad"]
            T3["get_catalog"]
            T4["select_dynamic_ad"]
            T5["trigger_ad"]
            T6["clear_ad"]
            T7["trigger_video_ad"]
        end
        F1["Flask routes<br/>/, /portrait,<br/>/get_current_advertisement"]
    end
    C1 <==>|"HTTPS: initialize / tools-list / tools-call"| N1
    N1 <==>|"HTTP proxy"| MCPThread
    C1 -.->|"REST (unrelated path)"| F1
    class C1 client
    class N1 proxy
    class T1,T2,T3,T4,T5,T6,T7 tool
    class F1 flask
```

### Image ad state — which tools read and write the shared state

```mermaid
---
config: {"theme":"base","themeVariables":{"fontSize":"18px","primaryColor":"#FFFFFF","primaryBorderColor":"#607D8B","primaryTextColor":"#263238","lineColor":"#546E7A","clusterBkg":"#FAFAFA","clusterBorder":"#B0BEC5"},"flowchart":{"curve":"linear","nodeSpacing":24,"rankSpacing":140,"padding":16}}
---
flowchart LR
    classDef tool   fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#1B5E20
    classDef state  fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#4A148C
    classDef lock   fill:#FCE4EC,stroke:#D81B60,stroke-width:2px,stroke-dasharray:5 3,color:#880E4F
    classDef flask  fill:#E0F7FA,stroke:#00ACC1,stroke-width:2px,color:#006064
    subgraph WebUI["web-ui container"]
        direction LR
        subgraph MCPThread["MCP server thread (:5100)"]
            direction TB
            T2["get_current_ad"]
            T3["get_catalog"]
            T4["select_dynamic_ad"]
            T5["trigger_ad"]
            T6["clear_ad"]
        end
        F1["Flask routes<br/>/, /portrait,<br/>/get_current_advertisement"]
        MQ["MQTT subscriber<br/>(camera detections)"]

        subgraph SharedState["Shared in-memory state (Ad_Generator instance)"]
            direction TB
            S1[("product_associations<br/>from ProductAssociations.csv")]
            S2[("context_rules<br/>from context_rules.json")]
            S3[("agent_override_ad /<br/>_until / _item / _generating<br/>override_epoch")]
            S4[("last_generated_ad<br/>last_selected_item")]
            S5[("_generation_lock")]
        end
    end
    T2 --> S3
    T2 --> S4
    T3 --> S1
    T4 --> S2
    T4 --> S1
    T4 -->|"acquire/release"| S5
    T5 --> S1
    T5 -->|"acquire/release"| S5
    T6 --> S3
    MQ -->|"camera-detected item"| S1
    F1 -->|"reads"| S3
    F1 -->|"reads"| S4
    class T2,T3,T4,T5,T6 tool
    class S1,S2,S3,S4 state
    class S5 lock
    class F1,MQ flask
```

### Image ad generation — from the tools through AIG into the override state

```mermaid
---
config: {"theme":"base","themeVariables":{"fontSize":"18px","primaryColor":"#FFFFFF","primaryBorderColor":"#607D8B","primaryTextColor":"#263238","lineColor":"#546E7A","clusterBkg":"#FAFAFA","clusterBorder":"#B0BEC5"},"flowchart":{"curve":"linear","nodeSpacing":30,"rankSpacing":60,"padding":16}}
---
flowchart TB
    classDef tool   fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#1B5E20
    classDef state  fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#4A148C
    classDef flask  fill:#E0F7FA,stroke:#00ACC1,stroke-width:2px,color:#006064
    classDef aig    fill:#FFFDE7,stroke:#F9A825,stroke-width:2px,color:#F57F17
    subgraph Callers["web-ui container — callers of generate_advertisement"]
        direction LR
        T4["select_dynamic_ad"]
        T5["trigger_ad"]
        MQ["MQTT subscriber<br/>(camera detections)"]
    end
    subgraph AIGServer["aig-server container (:5003)"]
        direction LR
        A1["/ase/predef/query/ad<br/>(predefined lookup)"]
        A2["/aig/minf/<br/>(dynamic image generation, model_lock)"]
    end
    subgraph SharedState["Shared in-memory state (Ad_Generator instance)"]
        direction LR
        S3[("agent_override_ad /<br/>_until / _item / _generating<br/>override_epoch")]
        S4[("last_generated_ad<br/>last_selected_item")]
    end
    T4 & T5 -->|"generate_advertisement"| A1
    MQ -->|"generate_advertisement when no override"| A1
    A1 -->|"miss"| A2
    A1 & A2 -->|"image bytes"| S3
    S3 -->|"captured ad, expiry timestamp"| S4
    class T4,T5 tool
    class S3,S4 state
    class MQ flask
    class A1,A2 aig
```

### Video ad path — `trigger_video_ad`, isolated video state and the AIG video endpoint

```mermaid
---
config: {"theme":"base","themeVariables":{"fontSize":"18px","primaryColor":"#FFFFFF","primaryBorderColor":"#607D8B","primaryTextColor":"#263238","lineColor":"#546E7A","clusterBkg":"#FAFAFA","clusterBorder":"#B0BEC5"},"flowchart":{"curve":"linear","nodeSpacing":30,"rankSpacing":60,"padding":16}}
---
flowchart TB
    classDef tool   fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#1B5E20
    classDef state  fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#4A148C
    classDef lock   fill:#FCE4EC,stroke:#D81B60,stroke-width:2px,stroke-dasharray:5 3,color:#880E4F
    classDef aig    fill:#FFFDE7,stroke:#F9A825,stroke-width:2px,color:#F57F17
    subgraph WebUI["web-ui container"]
        subgraph MCPThread["MCP server thread (:5100)"]
            direction LR
            T2["get_current_ad"]
            T6["clear_ad"]
            T7["trigger_video_ad"]
        end
        subgraph SharedState["Shared in-memory state (Ad_Generator instance)"]
            S1[("product_associations<br/>from ProductAssociations.csv")]
            S6[("video_override_media /<br/>_until / _item / _generating<br/>product_video_paths")]
            S7[("_video_generation_lock")]
        end
    end
    subgraph AIGServer["aig-server container (:5003)"]
        A3["/aig/mvid/<br/>(video generation, LTX-Video)"]
    end
    T2 --> S6
    T6 --> S6
    T7 --> S1
    T7 -->|"acquire/release"| S7
    T7 -->|"predefined video miss"| A3
    A3 -->|"animated WEBP"| S6
    class T2,T6,T7 tool
    class S1,S6 state
    class S7 lock
    class A3 aig
```

**Key control-flow points:**

- All 7 tools are dispatched through the single FastMCP thread; each calls back into
  `main.py`'s module-level functions via `_app()` (same process, no HTTP hop internally).
- `trigger_ad` / `select_dynamic_ad` return immediately (status `generating`) while the
  actual image generation runs in a separate daemon thread — the MCP call never blocks
  on the AIG round-trip (except when `benchmark=True`).
- `_generation_lock` + `override_epoch` prevent two concurrent generations (agent vs.
  camera-driven, or agent vs. a `clear_ad` mid-flight) from corrupting shared state.

**Key data-flow points:**

- `agent_override_*` fields are the single hand-off point between MCP tools and the
  display: both the REST `/get_current_advertisement` route and MCP's `get_current_ad`
  read the same override state.
- `product_associations` (CSV) and `context_rules` (JSON) are load-once, read-many
  configuration feeding both the camera-driven MQTT path and the new MCP tools.
