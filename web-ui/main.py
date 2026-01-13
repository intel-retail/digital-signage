#!/usr/bin/env python3
"""
Flask Web UI for Digital Signage
Streams video frames from MediaMTX server and displays them in a web interface
"""

import os
import cv2
import time
import threading
import requests
from flask import Flask, render_template, Response, jsonify, request
import logging
from datetime import datetime
import paho.mqtt.client as mqtt
import json
from queue import Queue
import numpy as np
from io import BytesIO
import csv
import base64
import random

AIG_SERVER_URL = os.getenv('AIG_SERVER_URL', 'http://aig-server:5003')
AIG_DYNAMIC_AD_ENDPOINT = f"{AIG_SERVER_URL}/aig/minf/"
AIG_PREDEFINED_AD_STORE_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/"
AIG_PREDEFINED_AD_QUERY_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/query/ad"
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

AIG_SERVER_ACTIVE = False

# Product Associations Dictionary
product_associations = {}

def load_product_associations(csv_path):
    """Load product associations from CSV file into dictionary"""
    global product_associations
    try:
        with open(csv_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                primary_product = row['primary_product']
                
                # Initialize list if primary product not in dict
                if primary_product not in product_associations:
                    product_associations[primary_product] = []
                
                # Add association details
                product_associations[primary_product].append({
                    'price': row['price'],
                    'unit': row['unit'],
                    'weight': row['weight'],
                    'cross_sell_discount': row['cross_sell_discount'],
                    'promo_details': row['promo_details'],
                    'slogan': row['slogan'],
                    'associated_cross_sell': row['associated_cross_sell'],
                    'dynamic_ad_prompt': row['dynamic_ad_prompt']
                })
                pre_defined_ad = row.get('pre_defined_ad_image', None)
                if pre_defined_ad:
                    try:
                        logger.info(f"Saving pre-defined ad for {primary_product}: {pre_defined_ad}")
                        # Read the pre-defined ad image from file
                        pre_defined_ad_path = os.path.join('/app/pre-defined-ads', pre_defined_ad)
                        if os.path.exists(pre_defined_ad_path):
                            with open(pre_defined_ad_path, 'rb') as img_file:
                                pre_defined_ad_data = base64.b64encode(img_file.read()).decode('utf-8')
                        else:
                            logger.warning(f"Pre-defined ad file not found: {pre_defined_ad_path}")
                            continue
                        
                        aig_payload = {
                            "description": f"{primary_product} and {row['associated_cross_sell']}",
                            "imgb64": pre_defined_ad_data,
                            "source": "Provisioning Script"
                            }
                        aig_response = requests.post(
                                AIG_PREDEFINED_AD_STORE_ENDPOINT,
                                headers={
                                    'accept': 'application/json',
                                    'Content-Type': 'application/json'
                                },
                                json=aig_payload,
                                timeout=5
                            )
                        if aig_response.status_code == 200:
                            logger.info(f"Successfully stored pre-defined ad for {primary_product}")
                        else:
                            logger.warning(f"Failed to store pre-defined ad for {primary_product}: {aig_response.status_code}")
                    except Exception as e:
                        logger.error(f"Error storing pre-defined ad for {primary_product}: {str(e)}")
        return True
    except Exception as e:
        logger.error(f"Failed to load product associations: {str(e)}")
        return False

# MQTT Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'ia-mqtt-broker')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'yolo_od_results')

# Store latest MQTT messages
mqtt_messages = []
mqtt_messages_lock = threading.Lock()


# Queue for processing MQTT messages
message_queue = Queue()

class Ad_Generator(threading.Thread):
    """Process messages from queue in a separate thread"""
    
    def __init__(self):
        super().__init__()
        self.ad_generating_in_progress = False
        self.running = False
        self.last_generated_ad = None
        self.time_taken_last_generated_ad = 0
        logger.info("Ad_Generator thread initialized")
        self.last_known_height = 600 # Default height until received from browser
        self.last_known_width = 480 # Default width until received from browser
        self.list_of_clients = []
    def run(self):
        """Main thread loop to process messages from queue"""
        self.running = True
        logger.info("Ad_Generator thread started")
        
        while self.running:
            try:
                global message_queue
                if not message_queue.empty():
                    item = message_queue.get(timeout=1)
                    if not self.ad_generating_in_progress:
                        global product_associations
                        associations = product_associations.get(item, None)
                        # Prepare the API payload for AIG server
                        if not associations:
                            logger.warning(f"No associations found for product: {item}. Using default ad parameters.")
                        self.generate_advertisement(item, associations, check_predefined=True, dummy_ad=False)
                    message_queue.task_done()
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in Ad_Generator thread: {str(e)}")
                time.sleep(1)
                
    def scaled(self, val, scale, min_val=None, max_val=None):
        """
        Scale UI values based on resolution with safety clamps
        """
        v = int(val * scale)
        if min_val is not None:
            v = max(v, min_val)
        if max_val is not None:
            v = min(v, max_val)
        return v
                
    def generate_advertisement(self, label, associations, check_predefined=False, dummy_ad=False):
        """Process individual message from queue"""
        try:

            logger.info(f"Detected object: {label}, {len(associations) if associations else 0} associations found")
            association_index = random.randint(0, len(associations) - 1) if associations else 0
            background_prompt = "perfectly dead-center, surrounded by vast white negative space, minimalist composition with wide margins, " \
                                "isolated on a pure white seamless background, high-key studio lighting, 8k, crisp detail, sharp focus"
            description = associations[association_index]['dynamic_ad_prompt'] + background_prompt \
                if associations else f"A high-quality 35mm photo featuring {label}, 8k resolution with height {self.last_known_height} and width {self.last_known_width}"

            pre_defined_ad_description = f"{label} and {associations[association_index]['associated_cross_sell']}"  if associations else f"{label}"
            
            base_dim = min(self.last_known_width, self.last_known_height)
            scale = base_dim / 1080.0

            factor = {
                "small": 0.04,
                "normal": 0.05,
                "large": 0.06
            } 

            aig_payload = {
                "description": description,                
                # ---------------- PRICE (BOTTOM RIGHT)
                "price_details": {
                    "price": ("$" + associations[association_index]['price'] + associations[association_index]["unit"]) if associations else "0.5 $/lb",

                    "align": "right",
                    "valign": "bottom",

                    # same as working JSON → scaled
                    "marperc_from_border": 3,
                    "font_size": 20,
                    "line_width": 5,

                    "price_color": "white",
                    "price_in_circle": True,
                    "price_circle_color": "black"
                },
                # ---------------- PROMO (BOTTOM CENTER)
                "promo_details": {
                    "promo_text": associations[association_index]['promo_details'] if associations else "Special Offer - Check out our latest deals!",
                    "text_color": "white",
                    "rect_color": "black",
                    "rect_padding": max(10, min(30, len(associations[association_index]['promo_details']) // 4)) if associations else 20,
                    "rect_radius": 8,

                    "align": "center",
                    "valign": "bottom",

                    # 👇 PROMO must be ABOVE frame
                    "marperc_from_border": 3,

                    "font_size": self.scaled(factor["normal"] * base_dim, 1.0, min_val=12, max_val=18),
                    "line_width": self.scaled(factor["small"] * base_dim, 1.0, min_val=12, max_val=18)
                },

                # ---------------- LOGO (TOP LEFT)
                "logo_details": {
                    "align": "left",
                    "valign": "top",
                    "logo_percentage": self.scaled(25, scale, min_val=15, max_val=35),
                    "margin_px": self.scaled(10, scale, min_val=6, max_val=30)
                },

                # ---------------- SLOGAN (ABOVE PROMO)
                "slogan_details": {
                    "slogan_text": associations[association_index]['slogan']
                        if associations else "Freshness You Can Trust",

                    "text_color": "white",
                    "align": "right",
                    "valign": "top",

                    # 👇 MUST be higher than promo
                    "marperc_from_border": 1,

                    "font_size":  self.scaled(factor["normal"] * base_dim, 1.0, min_val=12, max_val=18),
                    "line_width": self.scaled(factor["small"] * base_dim, 1.0, min_val=12, max_val=18)
                },

                # ---------------- FRAME
                "framed_details": {
                    "activate": True,
                    "marperc_from_border": self.scaled(2, scale, min_val=1, max_val=4)
                }
            }
            logger.info(f"Generating advertisement for product: {label} ")
            
            # Make API call to AIG server
            aig_response = None
            start_time = time.time()
            data_available_predefined = False
            recvd_img = False

            if check_predefined:
                logger.info(f"Checking for pre-defined advertisement for product: {label} {pre_defined_ad_description}")
                aig_payload["query"] = pre_defined_ad_description
                aig_payload["n_results"] = 1
                aig_payload["use_default_ad_onempty"] = False
                aig_response = requests.post(
                    AIG_PREDEFINED_AD_QUERY_ENDPOINT,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    json=aig_payload,
                    timeout=5
                )

                if aig_response.status_code == 200:
                    logger.debug(f"Pre-defined advertisement query successful for product: {label}")
                    content = aig_response.json()
                    
                    if len(content) > 0:
                        content_b64 = content[0].get('imgb64', None)
                        if content_b64:
                            data_available_predefined = True
                            recvd_img = True
                            decoded_bytes = base64.b64decode(content_b64)
                            self.last_generated_ad  = decoded_bytes
                            logger.info(f"Pre-defined advertisement found for product: {label}")
                else:
                    logger.error(f"AIG pre-defined ad query server error: {aig_response.status_code} (took {time.time() - start_time:.2f} seconds)")
            
            if not data_available_predefined:
                logger.info(f"Pre-defined advertisement not found for product: {label}, Generating dynamic advertisement.")
                aig_payload["description"] = description
                aig_payload["device"] = "GPU"
                aig_response = requests.post(
                    AIG_DYNAMIC_AD_ENDPOINT,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    json=aig_payload,
                    timeout=400
                )
                if aig_response.status_code == 200:
                    self.last_generated_ad = aig_response.content
                    recvd_img = True
            
            elapsed_time = time.time() - start_time
            
            if recvd_img and not dummy_ad:
                if data_available_predefined:
                    self.time_taken_last_generated_ad = f"Pre-defined ad fetched in {elapsed_time:.2f} seconds"
                else:
                    self.time_taken_last_generated_ad = f"Dynamic ad generated in {elapsed_time:.2f} seconds"
                self.list_of_clients = []  # Reset client list to force refresh
                logger.info(f"Advertisement generated successfully for product: {label} (took {elapsed_time:.2f} seconds)")
            else:
                self.last_generated_ad = None
                if not dummy_ad: 
                    logger.error(f"AIG server error: {aig_response.status_code} (took {elapsed_time:.2f} seconds)")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
        
    def get_current_advertisement(self, height=None, width=None, client_id=None):
        """Return the current advertisement being displayed, optionally resized"""
        # Update last known dimensions
        if height:
            self.last_known_height = height
        if width:
            self.last_known_width = width
        
        # Return None if no ad has been generated yet
        if self.last_generated_ad is None or client_id is None:
            return None, 0
        if client_id and client_id not in self.list_of_clients:
            self.list_of_clients.append(client_id)
            return self.last_generated_ad, self.time_taken_last_generated_ad
        
        # Client already received this ad
        return None, 0
    
    def stop(self):
        """Stop the processor thread"""
        self.running = False
        logger.info("Ad_Generator thread stopping")

# Global message processor instance
ad_generator_Obj = Ad_Generator()

class MQTTSubscriber:
    """MQTT Subscriber Client for Digital Signage"""
    
    def __init__(self, broker, port, topic):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.connected = False
   
        
        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.list_of_processed_products = []
        self.last_processed_item = ""

        logger.info(f"MQTT Subscriber initialized for {broker}:{port} on topic {topic}")
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            # Subscribe to topic
            client.subscribe(self.topic)
            logger.info(f"Subscribed to topic: {self.topic}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Try to parse as JSON
            try:
                global message_queue
                message_data = json.loads(payload)
                # Put message in queue for processing
                
                if 'metadata' in message_data and 'gva_meta' in message_data['metadata'] and len(message_data['metadata']['gva_meta']) > 0  and 'tensor' in message_data['metadata']['gva_meta'][0]:
                    tensors = message_data['metadata']['gva_meta'][0]['tensor']
                    tensor = tensors[0]  # Assuming single tensor for simplicity
                    confidence = tensor.get('confidence', None)
                    label = tensor.get('label', 'unknown')  
                    if confidence is not None and confidence > 0.5:
                        # logger.debug(f"Detected object: {label} with confidence: {confidence}")
                        if label not in self.list_of_processed_products[-3:]:
                            message_queue.put(label)
                            self.last_processed_item = label
                            self.list_of_processed_products.append(label)
                    else:
                        logger.info("No tensor data found in gva_meta")
                
            except json.JSONDecodeError:
                message_data = {'raw': payload}                    
        except Exception as e:
            logger.error(f"Error processing MQTT message: {str(e)}")
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            logger.info(f"MQTT client loop started for {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting MQTT client: {str(e)}")

# Global MQTT subscriber instance
mqtt_subscriber = None

# Configuration
@app.route('/')
def index():
    """Main page with video stream displayed on the left"""
    return render_template('index.html')


@app.route('/get_current_advertisement', methods=['GET'])
def get_current_advertisement():
    """Get current advertisement with optional width and height parameters"""
    global ad_generator_Obj
    
    # Get width and height from query parameters
    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)
    client_id = request.args.get('client_id', type=str)    
    ad_data, time_taken = ad_generator_Obj.get_current_advertisement(height, width, client_id)
    if ad_data:
        return Response(
            ad_data,
            mimetype='image/jpeg',
            headers={
            'Content-Disposition': 'inline; filename="current_ad.jpg"',
            'X-Generation-Time': time_taken
            }
        )
    else:   
        return jsonify({'status': 'ok'}), 204


# Initialize the application
def initialize_app():
    """Initialize the video streaming application"""
    global mqtt_subscriber, ad_generator_Obj
    
    logger.info("Initializing Digital Signage Web UI...")
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Load product associations CSV
    csv_path = "/app/ProductAssociations.csv"
    if os.path.exists(csv_path):
        load_product_associations(csv_path)
    else:
        logger.warning(f"Product associations CSV not found at {csv_path}")
    
    # Start message processor thread
    try:
        ad_generator_Obj.start()
        logger.info("Message processor thread started successfully")
    except Exception as e:
        logger.error(f"Failed to start message processor thread: {str(e)}")
    
    #Generating test advertisement to warm up AIG server
    logger.info("Warming up AIG server by generating a test advertisement...")
    ad_generator_Obj.generate_advertisement("test_product", None, dummy_ad=True)

    # Initialize MQTT subscriber
    try:
        mqtt_subscriber = MQTTSubscriber(MQTT_BROKER, MQTT_PORT, MQTT_TOPIC)
        mqtt_subscriber.connect()
        logger.info(f"MQTT subscriber started successfully on {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.warning(f"Failed to initialize MQTT subscriber: {str(e)}")
        logger.warning("Continuing without MQTT functionality")
        os._exit(1)
    

if __name__ == '__main__':
    try:
        logger.info("Digital Signage Web UI initialized successfully")

        # Run the Flask app
        logger.info("Starting Flask server on http://0.0.0.0:5000")
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False))
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask server started in separate thread")
    
        # Check if AIG server is up
        logger.info(f"Checking AIG server availability at {AIG_SERVER_URL}")
        while True:
            try:
                response = requests.get(f"{AIG_SERVER_URL}", timeout=2)
                if response.status_code == 200:
                    logger.info("AIG server is up and running")
                    break
                else:
                    logger.warning(f"AIG server responded with status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to connect to AIG server: {str(e)}")
                logger.error("Waiting for AIG server to become available...")
        
            time.sleep(1)

        # Initialize the application
        initialize_app()
         
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        # Clean up message processor thread
        if ad_generator_Obj:
            try:
                ad_generator_Obj.stop()
                logger.info("Message processor thread stopped")
            except Exception as e:
                logger.error(f"Error stopping message processor: {str(e)}")
        
        # Clean up MQTT subscriber
        if mqtt_subscriber:
            try:
                mqtt_subscriber.disconnect()
                logger.info("MQTT subscriber disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT subscriber: {str(e)}")