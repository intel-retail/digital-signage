# Flask
from flask import Flask
# API
from server.apis import api
from database.mqtt_manager import MqttManager
from server.arules.association_rules import ARDiscoverer
# Logging
import logging
logger = logging.getLogger(__name__)

__version__ = "0.1.0"

class PcaServer:
    def __init__(self):
        logger.info(f"Starting PCA Server version {__version__}")
        self.app = Flask(__name__) # Defining 
        logger.info(f"Flask App initialized")
        self.mqttmanager = MqttManager() # Creating MQTT Manager
        logger.info(f"MQTT Manager initialized")
        self.ardiscoverer = ARDiscoverer() # Creating AR Discoverer
        logger.info(f"AR Discoverer initialized")
        api.init_app(self.app) # Initializing APIs in App
        logger.info(f"API initialized")

    def run(self, hostname:str, pport:int, pdebug:bool):
        return self.app.run(host= hostname, port=pport, debug=pdebug)
    