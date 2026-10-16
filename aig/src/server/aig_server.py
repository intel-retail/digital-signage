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

    def run(self, hostname : str = "0.0.0.0", pport : int = AigServerMetadata.get_rest_server_port()): # nosec B104
        # threaded=True so ASe (Qdrant) requests aren't blocked behind slow AIG image generation
        # Debug mode is never enabled from this runtime path.
        return self.app.run(host= hostname, port=pport, debug=False, threaded=True)
    