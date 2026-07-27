# Web UI Service

`web-ui/main.py` — MQTT ingestion, product selection, ad generation, and the browser contract.
766 lines, three cooperating pieces: `MQTTSubscriber`, the `Ad_Generator` thread, and four Flask
routes.

Unlike `aig/src`, this file is **baked into the image** — changes need `make build && make up`,
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
- [ProductAssociations.csv](#productassociationscsv)
- [Startup](#startup)

## Threading model

Flask runs in a **daemon thread** on `0.0.0.0:5000` (`debug=False, threaded=True`) while the
main thread does setup. `Ad_Generator` is a third thread consuming a `Queue` that
`MQTTSubscriber` fills from the paho callback thread.

The queue is the only synchronization between detection and generation. `Ad_Generator` holds all
selection state as plain instance attributes (`product_generation_count`,
`last_association_index_by_label`, `last_selected_item`, …) touched only from its own thread —
if you add state read by a Flask route, it crosses a thread boundary and needs a lock.

## Detection ingestion

`MQTTSubscriber.on_message` parses:

```
metadata.gva_meta[i].tensor[j].label
metadata.gva_meta[i].tensor[j].confidence
```

It keeps a rolling window of the last `OBJECT_RECENCY_FRAME_COUNT * 2` messages and accepts a
label only when it appears in at least `OBJECT_RECENCY_FRAME_COUNT` of them with mean confidence
at least `OBJECT_CONFIDENCE_THRESHOLD`. Accepted labels go onto the queue as a set.

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

`generate_advertisement` composes the request. Fixed placement:

| Overlay | Position |
|---|---|
| price | bottom right, in a circle |
| promo | bottom center |
| logo | top left |
| slogan | top right |
| frame | active |

Two things drive the numbers:

**Prompt construction** appends a fixed background prompt to the CSV's `dynamic_ad_prompt`:

```python
background_prompt = ("perfectly dead-center, surrounded by vast white negative space, "
                     "minimalist composition with wide margins, isolated on a pure white "
                     "seamless background, high-key studio lighting, 8k, crisp detail, sharp focus")
```

That white-background framing is what makes generated ads composable with overlays — a prompt
change that loses it produces images where the text lands on busy pixels and becomes unreadable.

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
# POST /ase/predef/query/ad     timeout=5
#   ... if nothing came back:
# POST /aig/minf/  device="GPU" timeout=400
```

Three details that matter when changing this:

- **The 5-second timeout is tight.** Anything that slows the predefined path — a larger embedding
  model, more results, added post-processing — silently turns every ad into a generated one. The
  fallback is indistinguishable from a legitimate miss.
- **`use_default_ad_onempty=False`** because `ASE_IMG_DEFAULT_AD` doesn't exist in the repo.
  Setting it true without adding that file makes things worse, not better.
- **`device` is hardcoded `"GPU"`** regardless of `AIG_MODEL_DEVICE`. When the server is
  configured for CPU or NPU, every request mismatches and builds a fresh pipeline instead of
  reusing the preloaded one. Reading `AIG_MODEL_DEVICE` here would be a genuine improvement, but
  it means adding the variable to the web-ui environment in `docker-compose.yml` too.

A dummy warm-up ad is generated at startup so the first real detection doesn't pay model
compilation cost.

## The browser contract

| Route | Returns |
|---|---|
| `GET /` | `index.html` — landscape |
| `GET /portrait` | `portrait.html` |
| `GET /get_current_advertisement?width=&height=&client_id=` | JPEG + `X-Generation-Time`, or **204** |

The 204 is the whole protocol: the browser polls every **2000 ms**, and 204 means "you already
have the current ad". `client_id` is a fingerprint of user agent, resolution, timezone,
`performance.timeOrigin` and a `sessionStorage` tab id — so it's per-tab and survives reloads
but not a new tab.

`Ad_Generator.list_of_clients` tracks which clients have seen the current ad. Adding a client
type, or changing when the list is cleared, changes what every open browser sees — this is the
one piece of state that is genuinely shared across viewers.

`width`/`height` from the query string update `last_known_width`/`last_known_height`, which feed
the responsive scaling above. So the *first* client to poll after a new ad effectively sets the
sizing for that ad; mixed-resolution viewers see overlays scaled for someone else's screen.

Templates load the video by pointing an iframe at the nginx-proxied MediaMTX page
(`${window.location.origin}/samplestream/`) rather than negotiating WebRTC themselves — there is
no WebRTC code in this repo to change.

## ProductAssociations.csv

Mounted read-only at `/app/ProductAssociations.csv`. 94 rows.

| Column | Used for |
|---|---|
| `primary_product` | Match key against normalized detection labels |
| `price`, `unit` | Price overlay text, and first-time selection priority |
| `weight` | Quantity basis |
| `cross_sell_discount` | Discount text |
| `promo_details` | Promo banner text |
| `slogan` | Slogan text |
| `associated_cross_sell` | Second half of the predefined-ad query string |
| `dynamic_ad_prompt` | Base of the SDXL-Turbo prompt |
| `pre_defined_ad_image` | Filename in `pre-defined-ads/`; **empty forces dynamic generation** |

`price` is parsed with a `try/except` that skips unparseable values, so a malformed price
silently drops that row out of first-time prioritization rather than erroring.

Multiple rows per `primary_product` become variants. Adding variety is a CSV edit, not a code
change.

## Startup

`initialize_app()`, in order:

1. Load the CSV and build the lookup table.
2. For each row naming a `pre_defined_ad_image`, base64-encode the JPEG and POST it to
   `/ase/predef/` with a **5-second timeout**. Failures are logged and skipped — there is no
   retry, so ads silently go missing if aig-server isn't ready yet.
3. Start `Ad_Generator`.
4. Generate a dummy warm-up ad.
5. Connect `MQTTSubscriber`; `os._exit(1)` on failure.

Since `make down` removes the ChromaDB volume, this seeding runs fresh every start — the CSV plus
`pre-defined-ads/` is the real source of truth, and ChromaDB is a cache. If you add persistence,
step 2 becomes an upsert concern rather than a seed.
