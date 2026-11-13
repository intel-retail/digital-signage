# Web UI Service

`web-ui/main.py` — MQTT ingestion, product selection, ad generation, the browser contract, and the
core functions behind the MCP tools in `web-ui/mcp_server.py`. ~1,550 lines, three cooperating
pieces: `MQTTSubscriber`, the `Ad_Generator` thread, and four Flask routes.

Unlike `aig/src`, these files are **baked into the image** — changes need `make build && make up`,
not a restart. Budget for that; it's the slowest loop in the repo.

## Contents

- [Threading model](#threading-model)
- [Detection ingestion](#detection-ingestion)
- [Label normalization](#label-normalization)
- [Product selection](#product-selection)
- [Variant selection](#variant-selection)
- [Building the AIG payload](#building-the-aig-payload)
- [Predefined first, dynamic fallback](#predefined-first-dynamic-fallback)
- [The browser contract](#the-browser-contract)
- [MCP server and agent-driven ads](#mcp-server-and-agent-driven-ads)
- [Context rules](#context-rules)
- [Benchmark mode](#benchmark-mode)
- [ProductAssociations.csv](#productassociationscsv)
- [Startup](#startup)

## Threading model

Flask runs in a **daemon thread** on `0.0.0.0:5000` (`debug=False, threaded=True`) while the
main thread does setup. `Ad_Generator` is a third thread consuming a `Queue` that
`MQTTSubscriber` fills from the paho callback thread. The MCP server is a fourth daemon thread
(port 5100), started last, and each MCP tool call that generates an ad spawns a short-lived
background thread.

The queue is the only synchronization between detection and generation. `Ad_Generator` holds all
selection state as plain instance attributes (`product_generation_count`,
`last_association_index_by_label`, `last_selected_item`, …) touched only from its own thread —
if you add state read by a Flask route, it crosses a thread boundary and needs a lock. The agent
override fields (`agent_override_*`, `video_override_*`) are the exception: they are written by
MCP/background threads and read by Flask and the camera loop, guarded only by the generation
locks and the epoch counters described below.

The camera loop drops queued label sets that arrive within `TIME_TO_DISPLAY_AD_SECONDS` of the
last generation, and also while an agent call is generating or waiting for the image lock.

## Detection ingestion

`MQTTSubscriber.on_message` parses:

```
metadata.gva_meta[i].tensor[j].label
metadata.gva_meta[i].tensor[j].confidence
```

(`metadata.frame_id` and `metadata.time` are also read, but only for benchmark tracing.) Labels
are stripped and lower-cased on the way in. It keeps a rolling window of the last
`OBJECT_RECENCY_FRAME_COUNT * 2` messages and accepts a label only when it appears in at least
`OBJECT_RECENCY_FRAME_COUNT` of them with mean confidence at least `OBJECT_CONFIDENCE_THRESHOLD`.
Accepted labels go onto the queue as a set. A message with no `gva_meta` at all clears the window.

The doubled window is the part people misread: with the default of 5, a label must appear in 5 of
the last 10 messages. Raising the count makes detection both stricter *and* slower to react,
because the window grows too.

Connection failure calls `os._exit(1)` rather than retrying — MQTT problems surface as a restart
loop. Don't copy that pattern into new code.

## Label normalization

```python
def normalize_product_key(name):
    return name.strip().lower().replace("-", " ").replace("_", " ")
```

A lookup table built at CSV load maps normalized labels to CSV product keys; `resolve_product_label`
returns `None` for anything unknown, and unknown labels are dropped silently.

This is the seam where a swapped detection model most often fails: a model emitting
`Orange_Fruit` normalizes to `orange fruit`, which doesn't match a CSV row for `orange`.
Detections appear in the video overlay and no ad ever fires. If you extend normalization,
extend it here — it is the single point where model vocabulary meets CSV vocabulary.

## Product selection

`find_product_for_ad_generation(processed_item)` runs a small cascade:

1. Resolve each detected label to a CSV product; drop unresolvable ones. If none resolve, reset
   `last_processed_item` and return `None`.
2. Compute `new_identified_items` — resolved products **not** in `last_processed_item`. The
   selection pool is the new ones if any exist, otherwise everything resolved. This biases toward
   things that just came into view.
3. Split the pool by whether `product_generation_count` is zero:
   - **Any never-shown products** → `find_high_priced_candidate`: the highest `price` across that
     product's CSV rows, ties broken randomly. First impressions go to the most valuable item.
   - **Otherwise** → `find_rotating_candidate`: drop `last_selected_item` if alternatives exist,
     then choose randomly among the least-shown, using `product_generation_count`.
4. Record `last_selected_item`, increment the count, return.

Two distinct anti-repeat mechanisms operate here — excluding the immediately previous item, and
preferring least-shown — and a third at the variant level below. With only one detected product
none of them can do anything, so "the same ad repeats" is usually a detection-coverage problem.

`product_generation_count` is unbounded and never decays, so over a long run the rotation
increasingly favors whatever has been seen least across the entire process lifetime rather than
recently. That's worth knowing before adding a fourth mechanism.

## Variant selection

`choose_association_index(label, associations)` picks among CSV rows sharing a `primary_product`,
excluding the previous index for that label (tracked per label in
`last_association_index_by_label`) and choosing randomly among the rest. With one row it returns
0. This is how multiple CSV rows for the same product become ad variants.

## Building the AIG payload

`generate_advertisement` composes the request via `_build_aig_payload`, which the video path
also uses. Fixed placement:

| Overlay | Position |
|---|---|
| price | bottom right, in a circle (font size fixed at 18) |
| promo | bottom center |
| logo | top left |
| slogan | top right |
| frame | active |

Two things drive the numbers:

**Prompt construction** appends a style suffix to the CSV's `dynamic_ad_prompt`. The default
suffix:

```python
style_suffix = ("perfectly dead-center, surrounded by vast white negative space, "
                "minimalist composition with wide margins, isolated on a pure white "
                "seamless background, high-key studio lighting, 8k, crisp detail, sharp focus")
```

That white-background framing is what makes generated ads composable with overlays — a prompt
change that loses it produces images where the text lands on busy pixels and becomes unreadable.
The video path passes a different, motion-oriented `VIDEO_AD_STYLE_SUFFIX` because a video model
reads "isolated, dead-center, still" literally and produces blank-looking clips.

**Responsive scaling** uses `base_dim = min(width, height)` reported by the browser, `scale =
base_dim / 1080.0`, and a `scaled(val, scale, min_val, max_val)` helper with clamps:

```python
"font_size":       self.scaled(0.05 * base_dim, 1.0, min_val=12, max_val=18),
"logo_percentage": self.scaled(25, scale, min_val=15, max_val=35),
```

The clamps are why text stays legible from a phone to a 4K panel. Preserve them if you change
sizing — the AIG server treats `marperc_from_border` as a percentage but `font_size` as absolute
pixels, so an unclamped font size breaks at the extremes.

The predefined query text is built separately, as `"{label} and {cross_sell}"` — a short phrase
tuned for embedding similarity, deliberately not the long generation prompt. Changing it changes
retrieval quality directly.

Dimensions default to 480×600 until a browser reports its actual size.

## Predefined first, dynamic fallback

```python
aig_payload["query"] = pre_defined_ad_description
aig_payload["n_results"] = 1
aig_payload["use_default_ad_onempty"] = False
# POST /ase/predef/query/ad     timeout=15
#   ... if nothing came back:
# POST /aig/minf/  device=AIG_INFERENCE_DEVICE  timeout=400
```

Three details that matter when changing this:

- **A timeout is not a miss.** An empty list or a non-200 from the predefined query falls through
  to generation, but a request *exception* (including the 15-second timeout) propagates to the
  outer `try`, which logs "Error processing message" and abandons the attempt — no fallback, and
  the displayed ad simply stops updating. If you make the predefined path slower — a bigger
  embedding model, more results, a cold Qdrant/embedding init — watch for that, not for a
  silent switch to generated ads. What changes the hit rate is `ASE_QDRANT_SCORE_MIN_THRESHOLD`
  (a cosine score; see `aig-service.md`).
- **`use_default_ad_onempty=False`** because `ASE_IMG_DEFAULT_AD` doesn't exist in the repo.
  Setting it true without adding that file makes things worse, not better.
- **`device` comes from `AIG_INFERENCE_DEVICE`** (CPU/GPU/NPU, else GPU), set on web-ui by
  compose from the same `.env` key that becomes aig-server's `AIG_MODEL_DEVICE`, so requests reuse
  the preloaded pipeline. Video uses `AIG_VIDEO_INFERENCE_DEVICE` (CPU/GPU, NPU falls back to GPU)
  the same way; keep it equal to aig-server's `AIG_VIDEO_MODEL_DEVICE`.

The whole overlay payload is also sent to the predefined query, so predefined ads get price,
promo, logo, slogan and frame drawn on them — including the slogan that generated images skip
(see `aig-service.md`, "Known inconsistencies").

A dummy warm-up ad is generated at startup (dynamic path, no predefined check) so the first real
detection doesn't pay model compilation cost.

## The browser contract

| Route | Returns |
|---|---|
| `GET /` | `index.html` — landscape |
| `GET /portrait` | `portrait.html` |
| `GET /get_current_advertisement?width=&height=&client_id=` | JPEG (or a video ad) + `X-Generation-Time`, or **204** |
| `POST /ad_rendered` | Benchmark timing sink; **404** unless `BENCHMARK_MODE` is true |

`/get_current_advertisement` resolves in priority order:

1. **Video override** — served once per `client_id`, then **204** for the rest of the window (so
   the browser never swaps to an image mid-clip). While a video is merely *generating*, this
   step is skipped and the image flow continues.
2. **Agent image override** — the `trigger_ad`/`select_dynamic_ad` result, returned as **200 on
   every poll** until it expires (an exception to the 204 rule), with `X-Generation-Time:
   Agent-commanded: <item>`.
3. **Camera-driven ad** — once per `client_id`, else **204**.

Mime types: JPEG for images; animated `image/webp` for generated video, or `video/mp4`,
`image/webp`, `image/gif` for predefined clips. The templates use a `<video>` element for
`video/*` and an `<img>` for everything else.

For the camera-driven path, 204 means "you already have the current ad": the browser polls every
**2000 ms**. `client_id` is a fingerprint of user agent, resolution, timezone,
`performance.timeOrigin` and a `sessionStorage` tab id — so it is per tab, and changes on a
reload (a reloaded tab receives the current ad again).

`Ad_Generator.list_of_clients` (and `video_list_of_clients`) track which clients have seen the
current ad. Adding a client type, or changing when the list is cleared, changes what every open
browser sees — this is the one piece of state that is genuinely shared across viewers.

`width`/`height` from the query string update `last_known_width`/`last_known_height` on every
poll, and those feed the responsive scaling above. So whichever client polled most recently
before generation starts effectively sets the sizing for that ad; mixed-resolution viewers see
overlays scaled for someone else's screen. Video ads are generated at the fixed `AIG_VIDEO_*`
resolution, but item-based ones still size their overlays from these same values.

Templates load the video by pointing an iframe at the nginx-proxied MediaMTX page
(`${window.location.origin}/samplestream/`) rather than negotiating WebRTC themselves — there is
no WebRTC code in this repo to change.

## MCP server and agent-driven ads

`web-ui/mcp_server.py` builds a FastMCP server (`mcp==1.30.0`, pinned <2 because it uses the v1
`mcp.server.fastmcp` API) that listens on `0.0.0.0:5100` inside the container, Streamable HTTP at
`/mcp`. nginx proxies `https://<HOST_IP>:5000/mcp` to it with a 400 s read timeout. Tools return
short natural-language strings and call into `main.py` through `sys.modules['__main__']`, so
they act on the live `Ad_Generator`. A missing `mcp` package or a bind failure is logged and
isolated — Flask, MQTT and AIG keep running. No authentication is configured.

| Tool | Does |
|---|---|
| `describe()` | Structured contract: store, event types, read/act tools, accepted context values, plus a prose `summary` |
| `get_current_ad()` | Structured: `source` (camera/agent/none), `product`, `media`, `state` (showing/generating/cancelling/none), `seconds_remaining`, `summary` |
| `get_catalog()` | `products` (name, price, unit, cross-sells) from the CSV, plus a prose `summary` |
| `select_dynamic_ad(weather, demand, age_mix, daypart, display_seconds=60, benchmark=False)` | Resolve context → product via `context_rules.json`, then generate and show its image ad |
| `trigger_ad(item, display_seconds=60, promo_text="", slogan="")` | Show a named catalog item's image ad; optionally override promo/slogan text on every variant |
| `trigger_video_ad(item="", description="")` | Show a looping video ad for `VIDEO_AD_DISPLAY_SECONDS`; **exactly one** of `item` or `description` |
| `clear_ad()` | Drop any agent override (image and video, including in-flight) and return to camera flow |

Behavior worth knowing before touching `*_core` functions:

- **Image ads** (`trigger_ad_core`, `select_dynamic_ad_core`) reuse `generate_advertisement`
  (predefined first, else SDXL-Turbo), under `_generation_lock`, which the camera loop also takes.
  The call waits up to `AGENT_LOCK_WAIT_SECONDS` (6 s) while telling the camera loop to yield,
  then generates in a background thread and returns immediately ("generating"). The result
  becomes `agent_override_ad` for `display_seconds` (non-positive/non-numeric → 60).
- **Video ads** (`trigger_video_ad_core`) use a separate non-blocking `_video_generation_lock`
  and are **rejected, not queued**, if a video is still playing or still generating.
  `item` → a provisioned predefined clip if the CSV has one, else `/aig/mvid/` with the item's
  prompt (motion suffix) and catalog overlays. `description` → `/aig/mvid/` with that text
  verbatim, no overlays, no predefined lookup. Generation can take minutes (900 s timeout).
  Exactly-one is enforced in both the tool and the core function, with `_is_blank` treating
  zero-width/format characters as empty.
- **`clear_ad`** bumps `override_epoch` / `video_override_epoch` so an in-flight generation's
  result is discarded; the underlying AIG call can't be aborted, so the lock stays held and a new
  trigger may be rejected as busy until that call finishes (`get_current_ad` reports
  "cancelling").
- Camera-driven ads keep being generated underneath an override; they reappear when it expires.
- The docstrings in `main.py` mention REST routes for these actions; none exist — MCP is the only
  entry point.

## Context rules

`web-ui/context_rules.json` (mounted read-only at `/app/context_rules.json`) drives
`select_dynamic_ad`:

```json
{ "rules": [ { "weather": "rain", "product": "coffee" }, { "daypart": "lunch", "product": "sandwich" }, … ],
  "default_product": "banana" }
```

A rule matches when **every** key it names (`weather`, `demand`, `age_mix`, `daypart`) equals the
caller's value — compared after trim + lowercase, otherwise exact, no synonyms. The matching rule
with the most keys wins; ties go to the earlier rule. No match → `default_product`. The product is
then resolved through `normalize_product_key` against the CSV, so it must exist there (`iced_coffee`
↔ `iced coffee`). A missing or invalid file just disables the feature (empty rules → the tool
reports an error). Today every rule names a single key, so contexts with several fields resolve to
the first matching rule in file order.

## Benchmark mode

`BENCHMARK_MODE=true` (compose passes it to both web-ui and aig-server; `make up` sets it from the
Makefile, and `make benchmark-*` sets it to true) switches on instrumentation that is otherwise
off: structured `WEB_UI_SELECTION`, `WEB_UI_PRODUCT_SELECTION`, `WEB_UI_AD_TRACE`,
`WEB_UI_AD_COOLDOWN`, `WEB_UI_AD_SERVED` and `WEB_UI_AD_RENDERED` JSON log lines; `X-Delivery-Id`
on served ads; the `/ad_rendered` route and the template's `benchmarkMode` reporting;
`select_dynamic_ad(benchmark=True)`, which generates synchronously and returns timings. These log
lines feed the `make benchmark-*` tooling (the `performance-tools` submodule), so treat their field
names as an interface. Keep any new timing code behind `BENCHMARK_MODE` so the normal serving path
stays clean.

## ProductAssociations.csv

Mounted read-only at `/app/ProductAssociations.csv`. 106 rows covering 50 distinct products.

| Column | Used for |
|---|---|
| `primary_product` | Match key against normalized detection labels |
| `price`, `unit` | Price overlay text, and first-time selection priority |
| `weight`, `cross_sell_discount` | Loaded into the association dict but not read anywhere |
| `promo_details` | Promo banner text |
| `slogan` | Slogan text |
| `associated_cross_sell` | Second half of the predefined-ad query string |
| `dynamic_ad_prompt` | Base of the SDXL-Turbo / LTX-Video prompt |
| `pre_defined_ad_image` | Filename in `pre-defined-ads/`; **empty forces dynamic generation** (7 rows set it today) |
| `pre_defined_ad_video` | Optional clip in `pre-defined-ads/` for `trigger_video_ad`; none set today |

Predefined clips must be `.mp4`, `.webp` or `.gif` and no longer than `VIDEO_AD_DISPLAY_SECONDS`
+ 0.5 s; anything else is skipped with a warning at load. Clips are registered per product (the
last row naming one wins).

`price` is parsed with a `try/except` that skips unparseable values, so a malformed price
silently drops that row out of first-time prioritization rather than erroring.

Multiple rows per `primary_product` become variants. Adding variety is a CSV edit, not a code
change.

## Startup

Before `initialize_app()`, the main thread starts Flask, then polls `AIG_SERVER_URL` every second
(no cap) until it returns 200 — so web-ui never initializes against a dead aig-server, but a
slow Qdrant/embedding init inside aig-server can still bite step 2.

`initialize_app()`, in order:

1. Load the CSV and build the lookup table. In the same pass:
   - for each row naming a `pre_defined_ad_image`, base64-encode the JPEG and POST it to
     `/ase/predef/` with a **15-second timeout** (description `"{product} and {cross_sell}"`,
     no `id`). Failures are logged and skipped — there is no retry, so ads silently go missing;
   - for each row naming a `pre_defined_ad_video`, validate and register the clip.
2. Load `context_rules.json`.
3. Start `Ad_Generator`.
4. Generate a dummy warm-up ad.
5. Connect `MQTTSubscriber`; `os._exit(1)` on failure.

Then the MCP thread starts (`run_mcp_server`), and the main thread idles.

Since `make down` removes the Qdrant volume, this seeding runs fresh every start — the CSV plus
`pre-defined-ads/` is the real source of truth, and Qdrant is a cache. Seeding sends no `id`, so
aig-server picks a random one: restarting only `web-ui` while Qdrant stays up duplicates every
predefined ad. If you add persistence, step 1 becomes an upsert concern rather than a seed
(send a stable `id`).
