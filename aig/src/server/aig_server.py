# Flask
from flask import Flask
# API
from server.apis import api
from database.version import Version_sch
# Dependencies
from database.version import AigServerMetadata
# Logging
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

class AigServer:

    def __init__(self):
        logger.info(f"Starting AIG Server version {AigServerMetadata.version()}")
        self.app = Flask(__name__) # Defining 
        logger.info(f"Flask App initialized")
        api.init_app(self.app) # Initializing APIs in App
        logger.info(f"API initialized")

    def run(self, hostname : str = "0.0.0.0", pport : int = AigServerMetadata.get_rest_server_port(), pdebug : bool = False):
        return self.app.run(host= hostname, port=pport, debug=pdebug)
    