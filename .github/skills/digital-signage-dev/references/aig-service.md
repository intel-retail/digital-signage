# AIG Service

The Flask-RESTX server in `aig/` — REST layer, model loading, ChromaDB, and overlay drawing.

## Contents

- [Adding a REST endpoint](#adding-a-rest-endpoint)
- [Schema patterns](#schema-patterns)
- [The singletons](#the-singletons)
- [Model loading and generation](#model-loading-and-generation)
- [ChromaDB layer](#chromadb-layer)
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

The `path` prefix is applied to every route in the namespace: `/aig` for AIG endpoints, `/ase`
for ad-search endpoints. A route declared `@api.route('/predef/')` in a namespace mounted at
`/ase` serves `/ase/predef/`.

### 5. Check the two things outside the service

- **nginx** proxies `/aig-api/` to the AIG server with the prefix stripped, so any new path under
  an existing namespace is reachable at `https://localhost:5000/aig-api/<path>` with no nginx
  change. A brand-new top-level prefix would need one — see `pipeline-and-config.md`.
- **web-ui** is the only caller. If the endpoint is meant to be used, wire it up there too; if
  it's for operators, it's reachable via curl and Swagger already.

### 6. Verify

`aig/src` is bind-mounted and Flask runs in debug mode, so `docker restart aig-server` picks up
the change without a rebuild:

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

`/aig/minf/` and `/ase/predef/query/firstad` both do this; the list-returning variants
base64-encode into the `imgb64` field instead.

The five overlay objects (`price_details`, `promo_details`, `logo_details`, `slogan_details`,
`framed_details`) are defined **twice** — once in `modelinf.py` with a `ModelInference_*` prefix
and once in `predefinedads.py` with a `Predef_*` prefix — with identical fields. There is no
shared definition. Adding a field to an overlay means editing both files, or the two paths
diverge.

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

`AseServerMetadata` follows the same pattern for the ChromaDB client, collection, and embedding
function, initializing them on first property access rather than at construction. That laziness
is deliberate — it lets the AIG server start before ChromaDB is ready, which matters given
`depends_on` doesn't wait for readiness.

All environment access is centralized here as static accessors (`get_t2i_model_path()`,
`get_ase_distance_threshold()`, …). Add new variables as accessors here rather than calling
`os.getenv` from a handler — that's what keeps the defaults auditable.

## Model loading and generation

`get_preloaded_model()` holds `_model_lock` and reloads when the model is absent **or the
requested device changed**:

```python
if self.preloadedModel is None or self._model_device != requested_device:
    if AigServerMetadata.is_device_available(requested_device):
        self.preloadedModel = openvino_genai.Text2ImagePipeline(path, requested_device)
```

`is_device_available` checks `ov.Core().available_devices`. Failure logs and leaves
`preloadedModel = None` rather than raising, so callers must handle `None`.

In `/aig/minf/` the request's `device` field is compared against `AIG_MODEL_DEVICE`: equal means
reuse the singleton, different means build a per-request pipeline. After generating, the model
is unloaded unless `AIG_KEEP_MODEL_IN_MEMORY` is true. Generation retries up to **3 times** before
returning 503.

```python
pipe.generate(description, width=..., height=...,
              num_inference_steps=..., guidance_scale=0.0, num_images_per_prompt=1)
```

`guidance_scale=0.0` is correct for SDXL-Turbo, which is distilled to work without classifier-free
guidance — raising it degrades output rather than improving it. Likewise `num_inference_steps`
belongs in the 1–4 range.

If you change device or memory handling, exercise both branches: a request whose `device` matches
`AIG_MODEL_DEVICE` and one that doesn't. They take completely different paths and only the first
is on the web UI's hot path.

## ChromaDB layer

`AseServerMetadata` wraps the client. Helpers: `chromadb_add`, `chromadb_remove`,
`chromadb_update`, `chromadb_get`, `chromadb_exists`, `chromadb_query`, `chromadb_querytxt`,
`chromadb_heartbeat`.

```python
client = chromadb.HttpClient(host=ASE_CHROMADB_HOST, port=ASE_CHROMADB_PORT)
embedding_function = SentenceTransformerEmbeddingFunction(model_name=os.getenv('ASE_MODEL_PATH'))
collection = client.get_or_create_collection(name=ASE_COLLECTION_NAME, ...)
```

Documents store this metadata: `source`, `id`, `description`, `img_path`, `img_height`,
`img_width`. The image itself is written to disk at `ASE_IMG_PATH` as `img_<id>.jpg`, not into
ChromaDB — so `chromadb_remove` must also remove the file, and any new storage path needs the
same pairing.

Two behaviors that surprise people:

- **Embedding fallback is silent.** If `SentenceTransformerEmbeddingFunction` fails to load, the
  code falls back to `DefaultEmbeddingFunction()` and logs, but keeps serving. Distances change
  scale completely, so a tuned `ASE_DISTANCE_MAX_THRESHOLD` stops meaning what it meant. If you
  are debugging retrieval quality, confirm which function is live before tuning anything.
- **Distance filtering happens in the endpoint, not the query.** `chromadb_query` returns
  everything ChromaDB gives back; `/ase/predef/query` and `/ase/predef/query/ad` then drop
  results with `distance > ASE_DISTANCE_MAX_THRESHOLD`. A new query endpoint must apply that
  filter itself or it will return matches the rest of the system considers too weak.

`process_sample_data()` loads paired `<name>.jpg` / `<name>.txt` files from
`ASE_ENABLE_SAMPLEDATA_DIR` using a hardcoded category→id map in `utils.py`
(`bread: 275859`, `oranges: 431937`, …). That directory doesn't exist in the repo, so this path
is dead today — don't take it as a working example.

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

If you add an overlay, add it in **both** `modelinf.py` and `predefinedads.py`, define the schema
in both, and pick its place in the draw order deliberately.

## Known inconsistencies

Real asymmetries in the current code. Assume none of them are accidental enough to fix casually
in an unrelated change, but know they exist.

| What | Where | Effect |
|---|---|---|
| Price and slogan drawing commented out | `modelinf.py` ~lines 253–290, 357–375 | `/aig/minf/` accepts and validates `price_details` and `slogan_details` and then ignores them. `predefinedads.py` applies both |
| `framed_details` schema defined twice | `modelinf.py` and `predefinedads.py` both register `*_BasicRequest_Frame` twice — one with `activate`, one with `framed` | The second registration wins in Swagger; handlers read **`activate`**. Sending `framed` silently does nothing |
| Schema default ≠ handler default | e.g. `logo_percentage` 25 vs 15.0 | Omitting the field gives the handler value, not the documented one |
| Flask debug in production | `__main__.py` passes `pdebug=True` | Convenient for iteration (code reloads on the bind mount), inappropriate beyond a lab network |
| `os.getenv` defaults diverge from `.env` | `AIG_KEEP_MODEL_IN_MEMORY` (`'false'` vs `true`), `ASE_DISTANCE_MAX_THRESHOLD` (`1.5` vs `0.2`) | Behavior changes silently if the `.env` entry is ever removed |
| No license headers | most files under `aig/src/` | AGENTS.md requires them on new files; add to new files, don't bulk-retrofit |
| `database/version.py` name | 646 lines of singletons, env accessors and ChromaDB | Nothing to do with versions; expect to work here for most AIG changes |
