# AIG Service

The Flask-RESTX server in `aig/` — REST layer, model loading (image and video), Qdrant, and
overlay drawing.

## Contents

- [Adding a REST endpoint](#adding-a-rest-endpoint)
- [Schema patterns](#schema-patterns)
- [The singletons](#the-singletons)
- [Model loading and generation](#model-loading-and-generation)
- [Video generation](#video-generation)
- [Qdrant layer](#qdrant-layer)
- [Overlay drawing](#overlay-drawing)
- [Known inconsistencies](#known-inconsistencies)

## Adding a REST endpoint

Endpoints live in `aig/src/server/apis/`, one module per namespace, registered centrally.

### 1. Create or extend a namespace module

Each module creates a `Namespace` at module level and attaches resources to it. `status.py` is
the minimal example, `predefinedads.py` the full one.

```python
from flask_restx import Namespace, Resource, fields

api = Namespace('ASE - Advertise Searcher',
                description='It provides functionalities to define and search predefined ads.')
```

The namespace name is what appears as a section heading in Swagger, so it is user-visible.

### 2. Define request and response models

```python
predef_ad_schema = api.model('PredefinedAd', {
    'id':          fields.Integer(readOnly=False, description='...', example=1),
    'description': fields.String(required=True,  description='...', example="..."),
    'imgb64':      fields.String(required=True,  description='Base64-encoded image'),
    'source':      fields.String(required=False, description='Source of the ad', example="Marketing Department"),
})
```

Every field carries a `description` and an `example` — those populate Swagger, which is the only
API documentation that stays current, so treat them as required even though the framework
doesn't.

### 3. Attach the resource

```python
@api.route('/predef/', doc={"description": "Add/update predefined ads."})
class PredefAdResource(Resource):
    @api.response(200, 'Success')
    @api.response(400, 'Invalid Parameters or not found')
    @api.response(500, 'Accepted but it could not be processed/recovered')
    @api.expect(predef_ad_schema, validate=True, description='...')
    def post(self):
        data = api.payload
        ...
```

Conventions the existing code follows consistently:

- `@api.expect(model, validate=True)` on anything with a body. `validate=True` rejects unknown
  fields and enforces required ones before the handler runs.
- `@api.response(...)` for every status code you return — these are the documented contract.
- `@api.marshal_with(model)` for a single object, `@api.marshal_list_with(model)` for a list.
  Omit both when returning a raw image via `send_file`.
- Path parameters are typed in the route (`<int:id>`, `<string:id>`) and documented with
  `@api.param`.
- Read the body with `api.payload`, not `request.get_json()`.

### 4. Register the namespace

Only if the module is new — `aig/src/server/apis/__init__.py`:

```python
from .predefinedads import api as predefined_ads_api

api.add_namespace(predefined_ads_api, path='/ase')
```

The `path` prefix is applied to every route in the namespace: `/aig` for AIG endpoints (status,
version, `minf`, `mvid`), `/ase` for ad-search endpoints. A route declared
`@api.route('/predef/')` in a namespace mounted at `/ase` serves `/ase/predef/`.

### 5. Check the two things outside the service

- **nginx** proxies `/aig-api/` to the AIG server with the prefix stripped (the trailing `/` on
  `proxy_pass`), so any new path under an existing namespace is reachable at
  `https://localhost:5000/aig-api/<path>` with no nginx change. nginx also rewrites
  `basePath` in `/swagger.json` to `/aig-api` so Swagger "Try it out" works through the proxy. A
  brand-new top-level prefix would need a new `location` — see `pipeline-and-config.md`.
- **web-ui** is the only caller. If the endpoint is meant to be used, wire it up there too (and
  expose it through an MCP tool if agents need it); if it's for operators, it's reachable via
  curl and Swagger already.

### 6. Verify

`aig/src` is bind-mounted, so `docker restart aig-server` picks up the change without a rebuild
(Flask runs with `debug=False`; the restart is what reloads code):

```bash
docker restart aig-server && sleep 5
curl -k https://localhost:5000/aig-api/ase/predef/query \
  -H 'Content-Type: application/json' -d '{"query":"oranges","n_results":1}'
```

Check `https://localhost:5000/swaggerui/` to confirm the endpoint documents itself correctly —
a malformed model shows up there before it shows up in behavior.

## Schema patterns

Returning a binary image bypasses marshalling entirely:

```python
img_io = io.BytesIO()
image.save(img_io, 'JPEG')
img_io.seek(0)
return send_file(img_io, mimetype='image/jpeg')
```

`/aig/minf/` and `/ase/predef/query/firstad` both do this (`/aig/mvid/` does the same with
`image/webp`); the list-returning variants base64-encode into the `imgb64` field instead.

The five overlay objects (`price_details`, `promo_details`, `logo_details`, `slogan_details`,
`framed_details`) are defined **twice** — once in `modelinf.py` with a `ModelInference_*` prefix
and once in `predefinedads.py` with a `Predef_*` prefix — with identical fields. There is no
shared definition between those two. `videoinf.py` imports the `modelinf.py` models rather than
defining its own, so it follows the image endpoint automatically. Adding a field to an overlay
means editing both `modelinf.py` and `predefinedads.py`, or the two paths diverge.

Field defaults are declared in the schema *and* re-specified in the handler's `.get()` calls,
and they don't always agree — `logo_percentage` is `25` in the schema but `15.0` in the
`modelinf.py` handler's `.get()` fallback. The handler value is what actually applies when the
client omits the field.

## The singletons

Both live in `aig/src/database/version.py` and use the same shape: `__new__` returns a cached
class attribute, `__init__` guards re-initialization with `hasattr`, and expensive work happens
lazily behind a `threading.Lock`.

```python
class AigServerMetadata:
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(AigServerMetadata, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        if not hasattr(self, 'logo'):          # guard: __init__ runs on every construction
            self.logo = ...
            self.preloadedModel = None
            self._model_lock = threading.Lock()
```

Construct them freely — `AigServerMetadata()` anywhere returns the same instance. The
`hasattr` guard matters: Python calls `__init__` on every `AigServerMetadata()`, so without it
the model would be dropped on each call.

`AigServerMetadata` holds two independent lazy models — the image pipeline and the video
pipeline — each with its own lock, device and unload method. `AseServerMetadata` follows the
same pattern for the Qdrant client, collection, and embedding model, initializing them on first
property access rather than at construction. That laziness is deliberate — it lets the AIG
server start before Qdrant is ready, which matters given `depends_on` doesn't wait for
readiness; a failed init leaves the client `None` and the next access retries it.

Environment access is centralized here as static accessors (`get_t2i_model_path()`,
`get_ase_distance_threshold()`, `get_video_num_frames()`, …). Add new variables as accessors here
rather than calling `os.getenv` from a handler — that's what keeps the defaults auditable. The
existing exceptions are `BENCHMARK_MODE` (read at module level in `server/aig_server.py` and
`modelinf.py`), `AIG_NPU_CACHE_DIR`, `ASE_MODEL_PATH` and `ASE_ENABLE_SAMPLEDATA_DIR`.

The `.env` names that drive device selection differ from what the container sees: compose maps
`AIG_INFERENCE_DEVICE` → `AIG_MODEL_DEVICE` and `AIG_VIDEO_INFERENCE_DEVICE` →
`AIG_VIDEO_MODEL_DEVICE` for aig-server (web-ui receives the original names).

## Model loading and generation

`get_preloaded_model()` holds `_model_lock` and reloads when the model is absent **or the
requested device changed**:

```python
if self.preloadedModel is None or self._model_device != requested_device:
    if AigServerMetadata.is_device_available(requested_device):
        self.preloadedModel = AigServerMetadata.create_text2image_pipeline(path, requested_device)
```

`is_device_available` treats CPU as always present and otherwise checks
`ov.Core().available_devices`. A load failure logs and leaves `preloadedModel = None` rather than
raising, so callers must handle `None`. A failed load on a device is not retried for
`MODEL_LOAD_RETRY_SECONDS` (300 s) — a failed NPU compile can take minutes, so repeating it per
request would stall everything.

**NPU** is accepted for the image model (`AIG_INFERENCE_DEVICE=NPU`, experimental).
`create_text2image_pipeline` reshapes the pipeline to the static `AIG_IMG_WIDTH_DEFAULT` ×
`AIG_IMG_HEIGHT_DEFAULT` with `guidance_scale=0.0` and compiles with `CACHE_DIR` set to
`AIG_NPU_CACHE_DIR` (`/opt/npu_cache`, a host bind from `AIG_NPU_CACHE_HOST_DIR`). First start
compiles for minutes and the cache is large and survives `make down`; changing the image size
invalidates it. Compose mounts `/dev/accel` into the container only when the host has it
(`ACCEL_MOUNT_PATH` in the Makefile).

In `/aig/minf/` the request's `device` field is compared against `AIG_MODEL_DEVICE`: equal means
reuse the singleton (and a failed load returns **503** rather than building another pipeline),
different means build a per-request pipeline. After generating, the model is unloaded unless
`AIG_KEEP_MODEL_IN_MEMORY` is true. Generation retries up to **3 times** before returning 503.
An optional `seed` request field is passed through as `rng_seed`.

```python
pipe.generate(description, width=..., height=...,
              num_inference_steps=..., guidance_scale=0.0, num_images_per_prompt=1)
```

`guidance_scale=0.0` is correct for SDXL-Turbo, which is distilled to work without classifier-free
guidance — raising it degrades output rather than improving it. Likewise `num_inference_steps`
belongs in the 1–4 range.

If you change device or memory handling, exercise both branches: a request whose `device` matches
`AIG_MODEL_DEVICE` and one that doesn't. They take completely different paths; web-ui only sends
its `AIG_INFERENCE_DEVICE`, which compose also feeds to `AIG_MODEL_DEVICE`, so only the first is
on the hot path.

With `BENCHMARK_MODE=true` and an `X-Benchmark-Timing: true` request header, responses carry a
`Server-Timing` header (`/aig/minf/`: model_load, inference, overlay, …; `/ase/predef/query/ad`:
query_build, vector_search, ranking_retrieval). Off by default.

## Video generation

`aig/src/server/apis/videoinf.py` serves `POST /aig/mvid/` (namespace "AIG - Video Inference"). It
takes the same body as `/aig/minf/` — `description`, `device`, optional `seed`, and the five
overlay objects — and returns an **animated WEBP** (`image/webp`, looped, quality 90). It is
called only by the web UI's MCP-triggered video ads.

- **Model:** `openvino_genai.Text2VideoPipeline` (LTX-Video) from `AIG_VIDEO_MODEL_PATH`, held in a
  separate lazy singleton (`get_preloaded_video_model`) with its own `video_model_lock`.
  `AIG_PRELOAD_VIDEO_MODEL=true` loads it in a background thread at server start; it is only
  useful with `AIG_KEEP_MODEL_IN_MEMORY=true`. The model is optional — if the directory is
  absent, only video requests fail.
- **Device:** `AIG_VIDEO_MODEL_DEVICE` is CPU or GPU; NPU is coerced to GPU. Precision comes from
  `AIG_VIDEO_PRECISION` (`f16` default, `f32` for full precision) via an inference-precision hint.
  A request whose `device` equals the configured one reuses the singleton; otherwise (or if the
  singleton failed to load) it builds a per-request pipeline — unlike the image endpoint, there is
  no 503 shortcut.
- **Generation knobs** (all `AIG_VIDEO_*`): `WIDTH_DEFAULT`/`HEIGHT_DEFAULT`, `NUM_FRAMES`
  (must be 8k+1), `NUM_INFERENCE_STEPS`, `GUIDANCE_SCALE` (real guidance, unlike SDXL-Turbo),
  `FRAME_RATE`, `NEGATIVE_PROMPT`. `AIG_VIDEO_LOOP_SECONDS` only sets the WEBP's per-frame
  duration (loop length), not generation cost.
- **Overlays:** each frame goes through `apply_ad_overlays()` (defined in `modelinf.py`), the same
  function the image endpoint uses.
- **Failure shape:** 3 retries then 503; unload-after-use follows `AIG_KEEP_MODEL_IN_MEMORY`.

`AIG_VIDEO_LOOP_SECONDS` must equal web-ui's `VIDEO_AD_DISPLAY_SECONDS` — see `web-ui-service.md`.

## Qdrant layer

`AseServerMetadata` wraps the client. Helpers: `qdrant_add`, `qdrant_remove`, `qdrant_update`,
`qdrant_get`, `qdrant_exists`, `qdrant_query`, `qdrant_querytxt`, `qdrant_heartbeat`.

```python
client = QdrantClient(host=ASE_QDRANT_HOST, port=ASE_QDRANT_PORT)   # ase-qdrant:6333
embedding_model = SentenceTransformer(os.getenv('ASE_MODEL_PATH'))  # encode(..., normalize_embeddings=True)
client.create_collection(ASE_COLLECTION_NAME,
        vectors_config=VectorParams(size=<model dim>, distance=Distance.COSINE))
```

Points are keyed by an **integer** ID (non-int-convertible IDs raise `ValueError`), the vector is
the embedding of `description`, and the payload carries `source`, `id`, `description`, `img_path`,
`img_height`, `img_width`. The image itself is written to disk at `ASE_IMG_PATH` as
`img_<id>.jpg`, not into Qdrant — so `qdrant_remove` must also remove the file, and any new
storage path needs the same pairing. `qdrant_update` swaps the image in via a temp file and
restores the previous vector if the upsert fails.

Behaviors that surprise people:

- **There is no embedding fallback.** If the `SentenceTransformer` fails to load, or an existing
  collection's vector size/distance doesn't match the model, init logs an error and leaves the
  client unset: every ASE call raises "Qdrant collection is not initialized" (HTTP 500) and
  retries init on the next call. Changing `ASE_MODEL_PATH` to a model with a different dimension
  needs a fresh collection — `make down` (which drops the Qdrant volume) or a new
  `ASE_COLLECTION_NAME`.
- **Scores, not distances.** The collection is cosine; `qdrant_query` returns Qdrant's similarity
  *scores* (higher = better) under the legacy key `distances`. `get_ase_distance_threshold()`
  reads `ASE_QDRANT_SCORE_MIN_THRESHOLD` (default 0.8), and `is_qdrant_match(score)` keeps
  `score >= threshold`. Raising the threshold makes matching stricter, even though the legacy
  names (`distances`, `get_ase_distance_threshold`) suggest a "max distance" where lower is
  stricter.
- **Threshold filtering happens in the endpoint, not the query.** `qdrant_query` returns up to
  `n_results` points regardless of score; `/ase/predef/query`, `/ase/predef/query/ad` and
  `/ase/predef/query/firstad` each call `is_qdrant_match` themselves. A new query endpoint must
  do the same or it will return matches the rest of the system considers too weak.
- **A miss is an empty list, not a 404**, on `/predef/query/ad` and `/firstad` when
  `use_default_ad_onempty` is false (web-ui always sends false, because `ASE_IMG_DEFAULT_AD`
  doesn't exist in the repo).

`process_sample_data()` loads paired `<name>.jpg` / `<name>.txt` files from
`ASE_ENABLE_SAMPLEDATA_DIR` using a hardcoded category→id map in `utils.py`
(`bread: 275859`, `oranges: 431937`, …). That directory doesn't exist in the repo, so this path
is dead today — don't take it as a working example. `aig/src/database/testqdrant.py` is a
standalone script that talks to Qdrant directly; `testASE.py` calls the REST endpoints.

## Overlay drawing

`aig/src/imgproc/img_frame.py` holds `ImgDecorator`, all static methods, each taking a PIL
`Image` and returning a new one:

| Method | Draws |
|---|---|
| `draw_frame_double_border(img, percentageFromBorder)` | Double border frame |
| `draw_price_raw(...)` | Price as plain text |
| `draw_price_circle(...)` | Price inside a filled circle |
| `draw_promo_rounded_rect(...)` | Promo text in a rounded rectangle |
| `draw_logo(img, logo_img, align, valign, logo_percentage, margin_px)` | Logo, scaled by percentage |
| `draw_slogan(...)` | Slogan text |
| `is_color_valid(name)` | Validates a PIL named color |

Handlers call these in a fixed order, threading the result through: **price → promo → frame →
logo → slogan**. Order is layering — later draws land on top. Positioning uses `align`
(`left|center|right`), `valign` (`top|middle|bottom`), and `marperc_from_border` as a *percentage
of image size*, which is what lets the same payload work across display resolutions.

Color handling is forgiving by design: `is_color_valid` gates each color and an invalid name
falls back to the default rather than erroring. Preserve that — the web UI builds these payloads
from CSV text that nobody validates.

The sequence lives in three places: `apply_ad_overlays()` in `modelinf.py` (used by both
`/aig/minf/` and, per frame, `/aig/mvid/`) and two inline copies in `predefinedads.py`
(`/predef/query/ad` and `/predef/query/firstad`). If you add an overlay, change all three, define
the schema in both `modelinf.py` and `predefinedads.py`, and pick its place in the draw order
deliberately.

## Known inconsistencies

Real asymmetries in the current code. Assume none of them are accidental enough to fix casually
in an unrelated change, but know they exist.

| What | Where | Effect |
|---|---|---|
| Slogan drawing is a no-op on generated images | `apply_ad_overlays()` in `modelinf.py` (`img_postslogan = img_postlogo`) | `/aig/minf/` and `/aig/mvid/` accept and validate `slogan_details` and then ignore it. `predefinedads.py` still draws it, so slogans appear on predefined ads but never on generated images or video. (Price drawing is active everywhere) |
| `framed_details` schema defined twice | `modelinf.py` and `predefinedads.py` both register `*_BasicRequest_Frame` twice — one with `activate`, one with `framed` | The second registration wins in Swagger; handlers read **`activate`**. Sending `framed` silently does nothing |
| Schema default ≠ handler default | e.g. `logo_percentage` 25 vs 15.0 | Omitting the field gives the handler value, not the documented one |
| `os.getenv` defaults diverge from `.env` | `AIG_KEEP_MODEL_IN_MEMORY` (`'false'` vs `true`), `AIG_MODEL_NUM_INFERENCE_STEPS` (5 vs 4), `AIG_IMG_WIDTH/HEIGHT_DEFAULT` (512 vs 448), `AIG_VIDEO_NUM_FRAMES` (41 vs 25), `AIG_VIDEO_LOOP_SECONDS` (5 vs 3) | Behavior changes silently if the `.env` entry is ever removed. `ASE_QDRANT_SCORE_MIN_THRESHOLD` now agrees (0.8 in both) |
| Image and video device handling differ | `/aig/minf/` vs `/aig/mvid/` | Image returns 503 if the matching singleton failed to load; video falls through to a per-request pipeline |
| No license headers | all of `aig/src/` except `server/apis/videoinf.py` | AGENTS.md requires them on new files; add to new files, don't bulk-retrofit |
| `database/version.py` name | ~1,000 lines of singletons, env accessors and Qdrant | Nothing to do with versions; expect to work here for most AIG changes |
