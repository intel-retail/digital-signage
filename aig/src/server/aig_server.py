# Flask
from flask import Flask, g, request
# API
from server.apis import api
from database.version import Version_sch
# Dependencies
from database.version import AigServerMetadata
# Logging
from datetime import datetime
import logging
import os
import threading
logger = logging.getLogger(__name__)

# Keeps stage timing out of the normal serving path
BENCHMARK_MODE = os.getenv('BENCHMARK_MODE', 'false').strip().lower() == 'true'

class AigServer:

    def __init__(self):
        logger.info(f"Starting AIG Server version {AigServerMetadata.version()}")
        self.app = Flask(__name__) # Defining 
        logger.info(f"Flask App initialized")
        api.init_app(self.app) # Initializing APIs in App
        logger.info(f"API initialized")
        @self.app.after_request
        def add_search_timings(response):
            if BENCHMARK_MODE and request.headers.get('X-Benchmark-Timing', '').lower() == 'true':
                timings = getattr(g, 'benchmark_timings', None)
                if timings:
                    response.headers['Server-Timing'] = ', '.join(
                        f'{name};dur={duration:.3f}' for name, duration in timings.items()
                    )
            return response

    @staticmethod
    def _preload_video_model():
        if not AigServerMetadata.should_keep_model_in_memory():
            logger.warning("[AIG] AIG_PRELOAD_VIDEO_MODEL=true but AIG_KEEP_MODEL_IN_MEMORY is not true; "
                           "the preloaded model will be unloaded after the first video request")
        start = datetime.now()
        if AigServerMetadata().get_preloaded_video_model() is not None:
            logger.info(f"[AIG] Video model preloaded in {(datetime.now() - start).total_seconds():.1f}s")
        else:
            logger.warning("[AIG] Video model preload failed; it will be retried on the first video request")

    def run(self, hostname : str = "0.0.0.0", pport : int = AigServerMetadata.get_rest_server_port()): # nosec B104
        if AigServerMetadata.should_preload_video_model():
            # Background thread so the REST server (images, ASe) is available while the model loads
            threading.Thread(target=AigServer._preload_video_model, name="video-preload", daemon=True).start()
        # threaded=True so ASe (Qdrant) requests aren't blocked behind slow AIG image generation
        # Debug mode is never enabled from this runtime path.
        return self.app.run(host= hostname, port=pport, debug=False, threaded=True)
    