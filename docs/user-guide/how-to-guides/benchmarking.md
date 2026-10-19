# Benchmarking

This guide covers the full `make benchmark-all` workflow and explains the summary fields produced by the PID, AIG/ASe, Qdrant, Web UI, Docker-stats, host-metrics, and consolidated E2E outputs.

## Before You Run

Check the worktree, then update registered submodules:

```sh
git status --short
make update-submodules
```

Download model files if they are not already installed:

```sh
make download_models
```

The benchmark targets check required model artifacts and start the application stack themselves. Do not run a benchmark against changing input videos, models, device settings, or unrelated workloads if you need comparable runs.

## Run Benchmarks

Run the complete PID, Web-UIm AIG, Qdrant, and live E2E suite:

```sh
make benchmark-all
```

The suite configures devices, resets the application stack once with `make down` then `make up`, enables `BENCHMARK_MODE`, waits five minutes by default, and runs AIG, Qdrant, then E2E without further resets. E2E runs PID capture and Web UI trace capture concurrently. Each capture writes into the same `results/<timestamp>/` directory.

`make down` uses `docker compose down -v`; it removes named volumes, including Qdrant's existing ads and the pipeline cache. Predefined ads are reloaded from the Web UI product associations on startup. Manually added Qdrant ads are lost.

Run an individual benchmark when only one workload is needed:

```sh
make benchmark-pid
make benchmark-aig
make benchmark-web-ui
make benchmark-qdrant
make benchmark-e2e
make benchmark-metrics
```

Each individual target performs its own device configuration, stack reset, and warmup. `benchmark-metrics` only sleeps for its configured collection duration after the same reset and warmup. The normal application default is `BENCHMARK_MODE=false`; Make benchmark targets set it true when starting the stack.

## Make Parameters

Use Make variable assignments before or after the target, for example `make benchmark-all PID_DEVICE=NPU AIG_DEVICE=CPU`. Defaults below reflect the Makefile.

| Parameter | Default | Applies to | Meaning |
| --- | --- | --- | --- |
| `PID_DEVICE` | `CPU` | PID, E2E | PID inference device: `CPU`, `GPU`, or `NPU`; written into `configs/pid/config.json` before stack startup. |
| `AIG_DEVICE` | `GPU` | AIG, Web UI, E2E | AIG inference device: `CPU` or `GPU`; written to `AIG_INFERENCE_DEVICE` in `.env` before startup. `BENCHMARK_DEVICE` remains an alias for AIG. |
| `PID_CONFIG` | `configs/pid/config.json` | Device setup | PID config path to update before startup. |
| `AIG_ENV_FILE` | `.env` | Device setup | Environment file whose `AIG_INFERENCE_DEVICE` entry Make updates. |
| `BENCHMARK_DURATION` | `300` seconds | PID, AIG, Web UI, E2E | Capture duration. AIG schedules iterations across at least this duration; long requests can extend it. |
| `BENCHMARK_WARMUP_SECONDS` | `300` seconds | All benchmark targets | Delay after `up` and before capture; set to `0` to skip warmup. |
| `BENCHMARK_ITERATIONS` | `10` | AIG | Number of predefined-search/dynamic-generation pairs. |
| `BENCHMARK_COLD_START` | `false` | AIG | Restarts `aig-server` before the first measurement so the first model call can include cold-start cost. |
| `BENCHMARK_INSECURE` | `false` | AIG | Disable TLS verification for a custom AIG endpoint. The default local self-signed endpoint is handled by the script. |
| `QDRANT_SIZES` | `100 1000` | Qdrant | Cumulative temporary collection sizes used for vector-search tests. Must be unique and ascending. |
| `QDRANT_QUERIES` | `30` | Qdrant | Sequential query count at each collection size. |
| `GPU_METRICS` | unset | PID | Optional parsed qmassa JSON path used for `gpu_compute_percent`; this is device-wide, not PID-container GPU usage. |
| `COLLECT_METRICS` | `true` | All benchmark targets | Collect host CPU/GPU/NPU/memory/power series. Set false to skip the host collector; Docker service stats still run. |
| `METRICS_DURATION` | `BENCHMARK_DURATION`, otherwise `300` seconds | `benchmark-metrics` | Host-only metrics capture duration. |
| `METRICS_QMASSA_CYCLE` | `QMASSA_CYCLE_SECONDS`, otherwise metrics duration + `60` seconds | Host metrics | GPU collector rotation interval; increase for longer runs if needed. |
| `QMASSA_CYCLE_SECONDS` | unset | Host metrics | Environment-level override for the qmassa rotation interval. |
| `RESULTS_PATH` | `results` | All targets | Parent directory for the run folder. |
| `RUN_ID` | current timestamp | All targets | Name shared by all result files and child runs in `benchmark-all`. |

## Output Files

`benchmark-all` creates these main outputs under `results/<RUN_ID>/`:

| Files | Contents |
| --- | --- |
| `aig_benchmark_*.json/.csv` | One row per predefined search and dynamic generation call. |
| `aig_benchmark_*_summary.json/.csv` | AIG/ASe averages split by predefined and dynamic path. |
| `qdrant_benchmark_*.json/.csv` | Per-size search measurements plus temporary ad indexing. |
| `qdrant_benchmark_*_summary.json/.csv` | One flattened row with separate fields for each collection size. |
| `pid_benchmark_*.json/.csv` | PID run-level summary. |
| `pid_benchmark_*_frames.json/.csv` | Per-frame PID/MQTT samples. |
| `web_ui_benchmark_*.json/.csv` | Web UI frame and ad averages. |
| `web_ui_benchmark_*_frames.json/.csv` | Per-MQTT-frame Web UI timing fields, including queue/cooldown metrics. |
| `web_ui_benchmark_*_ads.json/.csv` | Per-generated-ad trace, served, and optional browser timings. |
| `e2e_consolidated_*.json/.csv` | Combined stage table across PID, Web UI, AIG, Qdrant, and resource metrics. |
| `<aig|qdrant|e2e>_docker_stats.json/.csv` | Per-container CPU/memory samples and averages. |
| `<aig|qdrant|e2e>_metrics.json` | Full-run host CPU/GPU/NPU/memory/power time series. |
| `<aig|qdrant|e2e>_platform_info.json` | Host processor, GPU, NPU, memory, and storage description. |
| `<aig|qdrant|e2e>_raw_metrics/` | Raw collector logs used to build the host metrics JSON. |

PID and Web UI run inside the E2E capture in `benchmark-all`, so they share `e2e_raw_metrics/`; they do not get duplicate PID/Web UI host-metrics folders. The collector runs once for each top-level AIG, Qdrant, and E2E capture.

## AIG Summary Fields

`aig_benchmark_*_summary.json/.csv` contains:

| Field or pattern | Meaning |
| --- | --- |
| `timestamp` | UTC time the summary was produced. |
| `device` | AIG device used, `CPU` or `GPU`. |
| `capture_elapsed_ms` | Actual benchmark capture duration in milliseconds. |
| `predefined_calls`, `dynamic_calls` | Number of ASe search and AIG generation calls. |
| `predefined_sla_met`, `dynamic_sla_met` | Count of calls that met the configured SLA, not a boolean. ASe target is under 5 s; dynamic AIG is under 15 s warm or 60 s for the first call when cold-start is enabled. |
| `avg_predefined_http_elapsed_ms`, `avg_dynamic_http_elapsed_ms` | Mean client-observed HTTP round-trip time, including transfer. |
| `avg_*_response_size_kb` | Mean encoded HTTP response size. |
| `avg_*_image_size_kb` | Mean decoded image byte size. |
| `avg_predefined_query_build_ms` | Mean query embedding/build time inside ASe. |
| `avg_predefined_vector_search_ms` | Mean Qdrant vector-search stage time inside ASe. |
| `avg_predefined_ranking_retrieval_ms` | Mean ASe score filtering and image retrieval time. |
| `avg_dynamic_model_load_ms` | Mean model acquisition/load stage time. |
| `avg_dynamic_inference_ms` | Mean model inference time, including model-lock wait/retries. |
| `avg_dynamic_overlay_ms` | Mean promo/logo overlay time. |
| `avg_dynamic_jpeg_encode_ms` | Mean JPEG encoding time. |
| `avg_dynamic_model_unload_ms` | Mean unload time; null when the model stays loaded. |
| `avg_dynamic_model_cleanup_ms` | Mean intermediate-object cleanup time. |
| `dynamic_first_call_http_elapsed_ms` | First dynamic call HTTP duration; only a true cold-start run measures a cold model. |
| `avg_dynamic_warm_http_elapsed_ms` | Mean dynamic HTTP time excluding call 1; preferred for warm-device comparison. |

`avg_*` values ignore missing stage values. ASe and AIG are separate requests, so their averages are not additive across individual rows; in the live Web UI path, a dynamic ad pays for both sequentially.

## Qdrant Summary Fields

`qdrant_benchmark_*_summary.json/.csv` contains:

| Field or pattern | Meaning |
| --- | --- |
| `timestamp` | UTC summary creation time. |
| `sizes` | Collection point counts tested, as a space-separated string. |
| `queries_per_size` | Sequential query count at each size. |
| `search_<size>_avg_query_ms` | Mean client-observed query latency for that collection size. |
| `search_<size>_p95_query_ms` | 95th-percentile query latency for that size. |
| `search_<size>_queries_per_sec` | Sequential query throughput for that size. |
| `search_<size>_upsert_ms` | Time to insert the new points for that size step. Sizes are cumulative; the 1000-point step inserts the points after the 100-point step. |
| `search_<size>_qdrant_memory_delta_mib` | Whole-Qdrant-container memory change measured around the size test; noisy, not per-collection RAM. |
| `predefined_ad_index_http_ms` | Full HTTP duration to add one temporary predefined ad through ASe. |
| `predefined_ad_index_image_kb` | JPEG image size used for that indexing test. |
| `predefined_ad_index_memory_delta_mib` | Whole-container memory change around indexing; can be negative due to noise. |

The search test uses synthetic random vectors in a temporary collection and returns top-1 with no payload. It measures raw vector-search scaling, not full live ASe query latency or semantic retrieval quality. The indexing test uses the predefined-ad API and removes its temporary record afterward.

## PID Summary Fields

`pid_benchmark_*.json/.csv` contains one run-level record:

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC result creation time. |
| `device` | PID inference device selected in `configs/pid/config.json`. |
| `duration_seconds` | Requested capture duration. |
| `frames` | MQTT frames received by the benchmark subscriber. |
| `fps_dlstreamer` | Mean `FpsCounter` throughput from pipeline logs. |
| `fps_mqtt_reported` | Mean FPS reported in MQTT pipeline status. |
| `detections_per_frame`, `detections_total` | Mean and total detection boxes in received frames. |
| `cpu_percent` | Mean `docker stats` CPU percent for the PID container; can exceed 100% across CPU cores. |
| `memory_mib` | Mean PID-container memory usage in MiB. |
| `pipeline_latency_reported` | Mean DLSPS `avg_pipeline_latency`; null if DLSPS does not report it. |
| `mqtt_arrival_delay_ms` | Mean DLSPS frame timestamp to host benchmark-subscriber receipt; includes publish, broker, pipe, and scheduling. |
| `startup_to_first_frame_ms` | Restart-to-first-frame duration; null for Make benchmarks because they warm up before capture and then sample without a second restart. |
| `gpu_compute_percent` | Mean qmassa CCS engine utilization from optional `GPU_METRICS`; null when not supplied. |

`*_frames.json/.csv` holds frame ID, DLSPS frame timestamp, subscriber arrival timestamp, detection count, FPS/latency status, and per-frame MQTT delay. `pipeline_latency_reported` and `gpu_compute_percent` are not interchangeable: the former is a DLSPS latency (often null), while the latter is device-wide GPU busy percentage.

## Web UI Summary Fields

`web_ui_benchmark_*.json/.csv` summarizes frames and generated ads:

| Field or pattern | Meaning |
| --- | --- |
| `timestamp`, `capture_seconds` | UTC summary time and actual Web UI log-capture duration. |
| `frames` | MQTT frame records captured. |
| `frames_selected` | Frames with a selector timing record. |
| `cooldown_suppressed_frames` | Candidate frames dropped because the ad-display cooldown had not expired. |
| `recency_frames`, `confidence_threshold` | Active selection configuration. |
| `avg_mqtt_to_web_ui_ms` | Mean DLSPS frame timestamp to Web UI MQTT callback; combines publishing and broker delivery. |
| `avg_label_normalization_ms` | Mean label extraction/normalization in the MQTT callback. |
| `avg_recency_filtering_ms` | Mean history maintenance and recency counting time. |
| `avg_confidence_gating_ms` | Mean confidence-threshold decision time. |
| `avg_callback_total_ms` | Mean callback processing time, including JSON parsing and queueing. |
| `avg_product_key_normalization_ms` | Mean detected-label normalization for product lookup. |
| `avg_csv_lookup_ms` | Mean in-memory product-association lookup time. |
| `avg_product_deduplication_ms` | Mean candidate deduplication time. |
| `avg_selector_total_ms` | Mean product-selection time. |
| `avg_queue_wait_ms` | Mean candidate enqueue-to-generator-dequeue time across candidate frames. |
| `avg_cooldown_remaining_ms` | Mean cooldown time left when candidates are dropped; they are not deferred for later. |
| `avg_total_selection_logic_ms` | Callback plus selector time where both are available; excludes queue wait, ad generation, and network requests. |
| `ads` | Total generated-ad traces. |
| `avg_ad_<metric>` | Mean ad metric across all paths; mixes predefined and dynamic ads. |
| `ads_predefined`, `ads_dynamic` | Ad counts for ASe hits and ASe misses respectively. |
| `avg_predefined_<metric>`, `avg_dynamic_<metric>` | Per-path means for each ad metric. Prefer these over combined averages when comparing paths. |

Ad metric suffixes include `queue_wait_ms`, `ase_query_ms`, `aig_generation_ms`, `ad_generation_total_ms`, `frame_to_ad_ready_ms`, `ready_to_served_ms`, `browser_fetch_ms`, `browser_render_ms`, and `frame_to_render_ms`. A predefined ad has no AIG generation, so its AIG field is null. `ready_to_served_ms` includes the browser polling interval. Browser fields require an open page during the capture; otherwise they are null. Browser render is a paint-opportunity estimate, not proof that pixels reached the display.

`*_frames.json/.csv` contains per-MQTT-frame timings, including cooldown state. `*_ads.json/.csv` contains one row per generated ad and browser events joined by `ad_id`. Empty values mean no event/sample exists, not zero milliseconds.

### Keep the Web UI Page Visible

`browser_render_ms` is sampled from a `requestAnimationFrame` callback. Browsers suspend animation frames in hidden, minimized, or background tabs, so the callback does not run until the page becomes visible again. Every pending ad then reports the wait for visibility instead of its render time, which makes `browser_render_ms`, `frame_to_render_ms`, and the consolidated browser rows meaningless.

Keep the Web UI page open, visible, and in the foreground for the whole capture. Do not minimize the window, lock the screen, or switch tabs.

Check `web_ui_benchmark_*_ads.json` before trusting browser numbers. Values that fall steadily with each newer ad and end with one small value indicate suspended frames; a valid run shows no such trend. In the sample below every ad resolved at the same instant, so only the final ad was measured correctly:

| `ad_id` | Trace time | `browser_render_ms` |
| --- | --- | --- |
| 82 | +0.0 s | 107959.9 |
| 89 | +50.9 s | 58204.9 |
| 96 | +100.9 s | 8200.7 |
| 97 | +108.5 s | 129.3 |

Only the 129.3 ms value is a real render measurement. Each other ad finishes 109.5 s into the capture, which is when the page regained visibility. `browser_fetch_ms` uses plain timestamps instead of animation frames, so it stays valid.

Browser fields are populated only for ads served while the page was open, so their sample count is usually lower than `ads`.

## E2E Consolidated Fields

`e2e_consolidated_*.json` has a top-level `timestamp` and a `stages` array. Each stage row has:

| Field | Meaning |
| --- | --- |
| `stage` | Human-readable pipeline stage or resource label. |
| `source` | Component that supplied the measurement. |
| `samples` | Number of numeric observations used for statistics. Zero means none were available. |
| `avg_ms` | Arithmetic mean in milliseconds. |
| `p50_ms` | Median in milliseconds. |
| `p95_ms` | 95th percentile in milliseconds. |
| `max_ms` | Maximum observed value in milliseconds. |
| `value` | A pre-aggregated scalar or count when raw samples are not present; these rows have no `samples` count. |
| `note` | Caveat or interpretation for the stage. |
| `file` | Source result file. |

Stage rows cover PID inference/throughput/MQTT arrival, Web UI receipt/filtering/queue/cooldown/selection, live ASe and AIG, ad serving/browser fetch/render, synthetic AIG and Qdrant, and host resource averages. `Server-Timing` stage rows are blank if the server image lacks instrumentation. DLSPS often reports inference latency as null, so throughput is shown separately. The `9. Browser render` and `E2E frame -> ad rendered` rows require an open page and inherit the animation-frame caveat in [Keep the Web UI Page Visible](#keep-the-web-ui-page-visible); verify those before quoting end-to-end latency.

## Docker and Host Metrics Fields

`<target>_docker_stats.json` contains `sample_interval_seconds`, a `services` map, and `host_metric_averages`. Each service entry contains:

| Field | Meaning |
| --- | --- |
| `samples` | Number of one-second-ish container samples for that service. |
| `containers` | Container names sampled for the service. |
| `average_cpu_percent` | Mean Docker CPU usage; can exceed 100% across cores. |
| `average_memory_percent` | Mean container memory as a percent of its limit. |
| `average_memory_usage_mib`, `average_memory_limit_mib` | Mean used memory and reported limit in MiB. |

`host_metric_averages` contains `cpu_utilization_percent`, `gpu_utilization_percent`, and `memory_utilization_percent`. GPU is host-wide because Docker stats does not attribute it to a container. The companion Docker stats CSV has `timestamp`, `service`, `container`, `cpu_percent`, `memory_percent`, `memory_usage_mib`, and `memory_limit_mib` per sample.

`<target>_metrics.json` keeps host time series: `cpu_utilization`, `gpu_utilization`, `npu_utilization`, `memory`, and `power`. CPU/GPU/NPU samples are `[timestamp, percent]`; memory samples are `[timestamp, total_gb, used_gb, free_gb, usage_percent]`; power samples are `[timestamp, package_0_watts, ...]`. `_platform_info.json` has `Processor`, `iGPU`, `NPU`, `Memory`, and `Storage` fields; `_raw_metrics/` retains the collector files.
