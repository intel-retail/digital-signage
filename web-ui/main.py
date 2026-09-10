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
AIG_INFERENCE_DEVICE = (os.getenv('AIG_INFERENCE_DEVICE', 'GPU')).upper()  # Default to GPU if not specified
# Context rules for select_dynamic_ad (MCP action); empty dict means the feature is unavailable
context_rules = {}
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

AIG_SERVER_ACTIVE = False

# Product Associations Dictionary
product_associations = {}
product_association_lookup = {}


def normalize_product_key(name):
    """Normalize labels so MQTT detections match CSV product names."""
    if not name:
        return ""
    return name.strip().lower().replace("-", " ").replace("_", " ")


def resolve_product_label(label):
    """Map an incoming label to a known CSV product key, if available."""
    normalized_label = normalize_product_key(label)
    return product_association_lookup.get(normalized_label)

def load_product_associations(csv_path):
    """Load product associations from CSV file into dictionary"""
    global product_associations, product_association_lookup
    try:
        product_associations = {}
        product_association_lookup = {}
        with open(csv_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                primary_product = row['primary_product']
                normalized_primary = normalize_product_key(primary_product)
                product_association_lookup[normalized_primary] = primary_product
                
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
                                timeout=15
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
        self.running = False
        self.http_session = requests.Session()
        self.last_generated_ad = None
        self.time_taken_last_generated_ad = 0
        logger.info("Ad_Generator thread initialized")
        self.last_known_height = 600 # Default height until received from browser
        self.last_known_width = 480 # Default width until received from browser
        self.list_of_clients = []
        self.last_generated_timestamp = None
        self.last_processed_item = []
        self.last_selected_item = None
        self.product_generation_count = {}
        self.last_association_index_by_label = {}
        self.time_to_display_ad = int(os.getenv('TIME_TO_DISPLAY_AD_SECONDS', 5))
        self.agent_override_ad = None
        self.agent_override_until = 0.0
        self.agent_override_item = None
        self.agent_override_generating = False  # True while background generation is in progress
        self.override_epoch = 0  # bumped by clear_agent_override to invalidate in-flight generations
        self._generation_lock = threading.Lock()  # prevents camera and agent from generating simultaneously
    def run(self):
        """Main thread loop to process messages from queue"""
        self.running = True
        logger.info("Ad_Generator thread started")
        
        while self.running:
            try:
                global message_queue
                if not message_queue.empty():
                    label_set = message_queue.get(timeout=1)
                    # Skip camera generation while agent is generating to prevent race condition
                    if self.agent_override_generating:
                        message_queue.task_done()
                        continue
                    if (self.last_generated_timestamp is None or (time.time() - self.last_generated_timestamp) > self.time_to_display_ad):
                        item = self.find_product_for_ad_generation(label_set)
                        if item is None:
                            message_queue.task_done()
                            continue
                        global product_associations
                        associations = product_associations.get(item, None)
                        # Prepare the API payload for AIG server
                        if not associations:
                            logger.warning(f"No associations found for product: {item}. Using default ad parameters.")
                        with self._generation_lock:
                            self.generate_advertisement(item, associations, check_predefined=True, dummy_ad=False)
                        self.last_generated_timestamp = time.time()
                    message_queue.task_done()
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in Ad_Generator thread: {str(e)}")
                time.sleep(1)

    def get_product_max_price(self, item):
        """Return the max configured price for a product, used for first-time prioritization."""
        global product_associations
        associations = product_associations.get(item, [])
        max_price = -1.0
        for assoc in associations:
            try:
                price = float(assoc.get('price', 0))
                if price > max_price:
                    max_price = price
            except (TypeError, ValueError):
                continue
        return max_price

    def find_high_priced_candidate(self, candidate_items):
        """Select highest-priced item from candidates."""
        if not candidate_items:
            return None
        max_price = -1.0
        best_items = []
        for item in candidate_items:
            price = self.get_product_max_price(item)
            if price > max_price:
                max_price = price
                best_items = [item]
            elif price == max_price:
                best_items.append(item)
        return random.choice(best_items) if best_items else None

    def find_rotating_candidate(self, candidate_items):
        """Rotate among candidates by preferring less-shown products and avoiding immediate repeats."""
        if not candidate_items:
            return None

        pool = list(candidate_items)
        if self.last_selected_item and len(pool) > 1:
            non_repeating = [item for item in pool if item != self.last_selected_item]
            if non_repeating:
                pool = non_repeating

        min_count = min(self.product_generation_count.get(item, 0) for item in pool)
        least_shown = [item for item in pool if self.product_generation_count.get(item, 0) == min_count]
        return random.choice(least_shown)

    def choose_association_index(self, label, associations):
        """Choose an association variant while avoiding repeating the previous variant for the same label."""
        if not associations:
            return 0

        if len(associations) == 1:
            self.last_association_index_by_label[label] = 0
            return 0

        last_index = self.last_association_index_by_label.get(label)
        candidate_indices = list(range(len(associations)))
        if last_index in candidate_indices:
            candidate_indices.remove(last_index)

        selected_index = random.choice(candidate_indices if candidate_indices else list(range(len(associations))))
        self.last_association_index_by_label[label] = selected_index
        return selected_index

    def find_product_for_ad_generation(self, processed_item):
        """Determine which product to generate ad for from label set"""
        global product_associations

        resolved_items = []
        logger.info(f"Processing detected labels for ad selection: {processed_item}")
        for item in processed_item:
            resolved = resolve_product_label(item)
            if not resolved:
                continue
            if resolved not in product_associations:
                continue
            if resolved not in resolved_items:
                resolved_items.append(resolved)

        if not resolved_items:
            logger.debug(f"No known products found in labels: {processed_item}")
            self.last_processed_item = []
            return None

        new_identified_items = [item for item in resolved_items if item not in self.last_processed_item]
        logger.info(f"Resolved labels for ad selection: {resolved_items}; newly identified: {new_identified_items}")

        selection_pool = new_identified_items if new_identified_items else resolved_items
        never_generated = [item for item in selection_pool if self.product_generation_count.get(item, 0) == 0]
        logger.info(f"Selection candidates: {selection_pool}; first-time candidates: {never_generated}")

        if never_generated:
            selected_item = self.find_high_priced_candidate(never_generated)
            logger.info(f"First-time selection mode (high price): {selected_item}")
        else:
            selected_item = self.find_rotating_candidate(selection_pool)
            logger.info(f"Rotation selection mode: {selected_item}")

        self.last_processed_item = resolved_items

        if selected_item:
            self.last_selected_item = selected_item
            self.product_generation_count[selected_item] = self.product_generation_count.get(selected_item, 0) + 1
            logger.info(f"Selected item for ad generation: {selected_item}")
            return selected_item

        logger.debug("No eligible item selected for ad generation")
        return None
                
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
            association_index = self.choose_association_index(label, associations)
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
                    "marperc_from_border": 2,
                    "font_size": 18,
                    "line_width": (len(associations[association_index]['price']) + 1) if associations else 5,

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
                    "marperc_from_border": 2,

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
            total_start_time = time.time()
            data_available_predefined = False
            recvd_img = False
            predefined_http_elapsed = 0.0
            dynamic_http_elapsed = 0.0
            response_copy_elapsed = 0.0
            response_size_kb = 0.0

            if check_predefined:
                logger.info(f"Checking for pre-defined advertisement for product: {label} {pre_defined_ad_description}")
                aig_payload["query"] = pre_defined_ad_description
                aig_payload["n_results"] = 1
                aig_payload["use_default_ad_onempty"] = False
                predefined_http_start = time.time()
                aig_response = self.http_session.post(
                    AIG_PREDEFINED_AD_QUERY_ENDPOINT,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    json=aig_payload,
                    timeout=15
                )
                predefined_http_elapsed = time.time() - predefined_http_start

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
                    logger.error(f"AIG pre-defined ad query server error: {aig_response.status_code} (roundtrip {predefined_http_elapsed:.2f} seconds)")
            
            if not data_available_predefined:
                logger.info(f"Pre-defined advertisement not found for product: {label}, Generating dynamic advertisement.")
                aig_payload["description"] = description
                aig_payload["device"] = AIG_INFERENCE_DEVICE
                dynamic_http_start = time.time()
                aig_response = self.http_session.post(
                    AIG_DYNAMIC_AD_ENDPOINT,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    json=aig_payload,
                    timeout=400
                )
                dynamic_http_elapsed = time.time() - dynamic_http_start
                if aig_response.status_code == 200:
                    copy_start = time.time()
                    self.last_generated_ad = aig_response.content
                    response_copy_elapsed = time.time() - copy_start
                    response_size_kb = len(aig_response.content) / 1024.0
                    recvd_img = True
            
            elapsed_time = time.time() - total_start_time
            
            if recvd_img and not dummy_ad:
                if data_available_predefined:
                    self.time_taken_last_generated_ad = (
                        f"Pre-defined ad fetched in {predefined_http_elapsed:.2f} seconds")
                else:
                    self.time_taken_last_generated_ad = (
                        f"Dynamic ad generated in {dynamic_http_elapsed:.2f} seconds ")
                self.list_of_clients = []  # Reset client list to force refresh
                logger.info(f"Advertisement generated successfully for product: {label} (took {elapsed_time:.2f} seconds)")
                logger.info(self.time_taken_last_generated_ad)
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

        # Agent-commanded override takes priority; served continuously until expiry
        if self.agent_override_ad and time.time() < self.agent_override_until:
            return self.agent_override_ad, f"Agent-commanded: {self.agent_override_item}"

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
        self.http_session.close()
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
        self.last_n_messages_labels = []  # Track labels from last N messages
        self.object_recency_count = int(os.getenv('OBJECT_RECENCY_FRAME_COUNT', 5))
        self.object_threshold_confidence = float(os.getenv('OBJECT_CONFIDENCE_THRESHOLD', 0.5))
        self.max_message_history = self.object_recency_count * 2  # Number of messages to track

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
                
                # Extract unique labels with confidence from current message
                current_message_labels = {}  # {label: [confidence1, confidence2, ...]}
                if 'metadata' in message_data and 'gva_meta' in message_data['metadata'] and len(message_data['metadata']['gva_meta']) > 0:
                    for i in range(len(message_data['metadata']['gva_meta'])):
                        if 'tensor' not in message_data['metadata']['gva_meta'][i]:
                            logger.info("No tensor data found in gva_meta")
                            continue
                        else:
                            tensors = message_data['metadata']['gva_meta'][i]['tensor']
                            for j in range(len(tensors)):
                                tensor = tensors[j]
                                confidence = tensor.get('confidence', None)
                                raw_label = tensor.get('label', 'unknown')
                                label = raw_label.strip().lower() if isinstance(raw_label, str) else 'unknown'
                                if confidence is not None and label != 'unknown':
                                    if label not in current_message_labels:
                                        current_message_labels[label] = []
                                    current_message_labels[label].append(confidence)
                    
                    # logger.info(f"Unique labels detected in current message: {current_message_labels.keys()}")
                    
                    # Update message history first - add current labels and maintain size
                    self.last_n_messages_labels.append(current_message_labels)
                    if len(self.last_n_messages_labels) > self.max_message_history:
                        self.last_n_messages_labels.pop(0)
                    
                    # Count occurrences and track confidence scores for each label in last N messages
                    label_data = {}  # {label: {'count': X, 'confidences': [...]}}
                    for labels_dict in self.last_n_messages_labels:
                        for label, confidences in labels_dict.items():
                            if label not in label_data:
                                label_data[label] = {'count': 0, 'confidences': []}
                            label_data[label]['count'] += 1
                            label_data[label]['confidences'].extend(confidences)
                    
                    # Process labels that appear in at least N of the last X messages
                    # and haven't been processed recently
                    label_to_process = []
                    for label, data in label_data.items():
                        if data['count'] >= self.object_recency_count:
                            avg_confidence = sum(data['confidences']) / len(data['confidences'])
                            # logger.info(f"Label '{label}' detected in {data['count']}/{len(self.last_n_messages_labels)} recent messages, avg confidence: {avg_confidence:.3f}")
                            if avg_confidence >= self.object_threshold_confidence:  # Confidence threshold
                                label_to_process.append(label)
                    if len(label_to_process) > 0:
                        logger.debug(f"Labels to process after recency check: {label_to_process}")
                        message_queue.put(label_to_process)
                    
                else:
                    logger.info("No tensor data found in gva_meta")
                    self.last_n_messages_labels.clear()  # Clear history if no data
                    self.list_of_processed_products.clear()  # Clear processed products list
                    self.last_processed_item = ""  # Reset last processed item

                
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

@app.route('/portrait')
def portrait():
    """Portrait mode page"""
    return render_template('portrait.html')

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


def normalize_display_seconds(value, default=60):
    """Coerce a display_seconds input to a positive int; falls back to default on non-numeric or non-positive values."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def trigger_ad_core(item, display_seconds=60, promo_text=None, slogan=None):
    """Resolve a raw item name and display its ad. Shared by the REST route and the MCP trigger_ad tool."""
    global ad_generator_Obj, product_associations

    resolved = resolve_product_label(item)
    if not resolved or resolved not in product_associations:
        return {'error': f'Unknown item: {item}', 'available_items': sorted(product_associations.keys())}

    display_seconds = normalize_display_seconds(display_seconds)
    associations = [dict(a) for a in product_associations[resolved]]
    # Applied to every variant, not just index 0, since generate_advertisement may pick any variant index
    if promo_text:
        for a in associations:
            a['promo_details'] = promo_text
    if slogan:
        for a in associations:
            a['slogan'] = slogan

    # Held across the acquire check and the background thread's generation so nothing can
    # steal the lock in between (acquire-then-release-then-reacquire would race the camera thread).
    if not ad_generator_Obj._generation_lock.acquire(blocking=False):
        return {'error': 'Another ad generation is already in progress; try again in a few seconds.'}

    def _generate_and_set(item_name, assocs, secs):
        ad_generator_Obj.agent_override_generating = True
        ad_generator_Obj.agent_override_item = item_name
        my_epoch = ad_generator_Obj.override_epoch
        try:
            ad_generator_Obj.generate_advertisement(item_name, assocs, check_predefined=True, dummy_ad=False)
            captured = ad_generator_Obj.last_generated_ad
            if ad_generator_Obj.override_epoch != my_epoch:
                logger.info(f"Agent ad for '{item_name}' discarded; override was cleared during generation")
            elif captured:
                ad_generator_Obj.agent_override_ad = captured
                ad_generator_Obj.agent_override_until = time.time() + secs
                logger.info(f"Agent ad ready for '{item_name}' ({secs}s)")
            else:
                logger.error(f"Agent ad generation produced no image for '{item_name}'")
                ad_generator_Obj.agent_override_item = None
        finally:
            ad_generator_Obj.agent_override_generating = False
            ad_generator_Obj._generation_lock.release()

    try:
        threading.Thread(target=_generate_and_set, args=(resolved, associations, display_seconds), daemon=True).start()
    except RuntimeError:
        ad_generator_Obj._generation_lock.release()
        return {'error': 'Failed to start ad generation; try again in a few seconds.'}
    logger.info(f"Agent ad generation started for '{resolved}' ({display_seconds}s), returning immediately")
    return {
        'status': 'generating',
        'item': resolved,
        'display_seconds': display_seconds,
        'message': f"Ad for '{resolved}' is being generated and will appear on the display shortly. Use get_active_ad to check when it is live."
    }


def clear_agent_override():
    """Clear the agent-commanded override and return to camera-driven ad flow. Used by the MCP clear_ad tool."""
    global ad_generator_Obj
    prev_item = ad_generator_Obj.agent_override_item
    ad_generator_Obj.agent_override_ad = None
    ad_generator_Obj.agent_override_until = 0.0
    ad_generator_Obj.agent_override_item = None
    ad_generator_Obj.override_epoch += 1  # invalidates any generation started before this clear
    logger.info(f"Agent cleared override ad (was: {prev_item})")
    return {'status': 'ok', 'cleared_item': prev_item}


def get_active_ad_info():
    """Build the current display status as a dict; used by the get_current_ad MCP tool."""
    global ad_generator_Obj
    now = time.time()
    if ad_generator_Obj.agent_override_generating:
        return {'mode': 'generating', 'item': ad_generator_Obj.agent_override_item, 'seconds_remaining': None}
    if ad_generator_Obj.agent_override_ad and now < ad_generator_Obj.agent_override_until:
        return {'mode': 'agent', 'item': ad_generator_Obj.agent_override_item,
                'seconds_remaining': round(ad_generator_Obj.agent_override_until - now, 1)}
    return {'mode': 'camera', 'item': ad_generator_Obj.last_selected_item, 'seconds_remaining': None}


def load_context_rules(path):
    """Load context-to-product resolution rules used by select_dynamic_ad. Missing/invalid file disables the feature."""
    global context_rules
    try:
        with open(path, 'r') as f:
            context_rules = json.load(f)
        logger.info(f"Loaded {len(context_rules.get('rules', []))} context rules from {path}")
    except Exception as e:
        logger.warning(f"Could not load context rules from {path}: {str(e)}. select_dynamic_ad will be unavailable.")
        context_rules = {}


def _normalize_context_value(value):
    """Trim and lowercase a context value so e.g. 'Rain' / ' rain ' match the rules file's 'rain'."""
    return str(value).strip().lower() if value is not None else None


def resolve_context_to_product(context):
    """Match a context dict against context_rules; the rule matching the most fields wins. Matching is
    case/whitespace-insensitive but still requires an exact value match otherwise (no fuzzy/synonym matching)."""
    normalized_context = {k: _normalize_context_value(v) for k, v in context.items()}
    best_rule, best_score = None, -1
    for rule in context_rules.get('rules', []):
        score, matched = 0, True
        for key in ('weather', 'demand', 'age_mix', 'daypart'):
            rule_val = rule.get(key)
            if rule_val is None:
                continue
            if normalized_context.get(key) != _normalize_context_value(rule_val):
                matched = False
                break
            score += 1
        if matched and score > best_score:
            best_rule, best_score = rule, score
    if best_rule:
        return best_rule.get('product'), best_rule
    default_product = context_rules.get('default_product')
    return (default_product, {'default': True}) if default_product else (None, None)


def select_dynamic_ad_core(context, display_seconds=60, benchmark=False):
    """Resolve a context dict to a product and display its ad. Shared by the REST route and the MCP tool."""
    global ad_generator_Obj, product_associations

    product, matched_rule = resolve_context_to_product(context)
    if not product:
        return {'error': 'no matching rule and no default_product configured'}

    resolved = resolve_product_label(product)
    if not resolved or resolved not in product_associations:
        return {'error': f"resolved product '{product}' is not in the catalog"}

    associations = [dict(a) for a in product_associations[resolved]]
    display_seconds = normalize_display_seconds(display_seconds)

    if benchmark:
        # Synchronous call: waiting its turn on the lock (rather than failing fast) is the expected behavior here.
        ad_generator_Obj.agent_override_generating = True
        ad_generator_Obj.agent_override_item = resolved
        try:
            start = time.time()
            with ad_generator_Obj._generation_lock:
                ad_generator_Obj.generate_advertisement(resolved, associations, check_predefined=True, dummy_ad=False)
                captured = ad_generator_Obj.last_generated_ad
            total_ms = round((time.time() - start) * 1000)
        finally:
            ad_generator_Obj.agent_override_generating = False
        if not captured:
            return {'error': f"ad generation failed for '{resolved}'"}
        ad_generator_Obj.agent_override_ad = captured
        ad_generator_Obj.agent_override_until = time.time() + display_seconds
        ad_generator_Obj.agent_override_item = resolved
        source = 'predefined' if 'Pre-defined' in (ad_generator_Obj.time_taken_last_generated_ad or '') else 'aig'
        return {
            'resolved_product': resolved, 'matched_rule': matched_rule, 'source': source,
            'timing_ms': {'total': total_ms}, 'status': 'ok'
        }

    # Held across the acquire check and the background thread's generation so nothing can
    # steal the lock in between (acquire-then-release-then-reacquire would race the camera thread).
    if not ad_generator_Obj._generation_lock.acquire(blocking=False):
        return {'error': 'Another ad generation is already in progress; try again in a few seconds.'}

    def _generate_and_set(item_name, assocs, secs):
        ad_generator_Obj.agent_override_generating = True
        ad_generator_Obj.agent_override_item = item_name
        my_epoch = ad_generator_Obj.override_epoch
        try:
            ad_generator_Obj.generate_advertisement(item_name, assocs, check_predefined=True, dummy_ad=False)
            captured = ad_generator_Obj.last_generated_ad
            if ad_generator_Obj.override_epoch != my_epoch:
                logger.info(f"Context-resolved ad for '{item_name}' discarded; override was cleared during generation")
            elif captured:
                ad_generator_Obj.agent_override_ad = captured
                ad_generator_Obj.agent_override_until = time.time() + secs
                logger.info(f"Context-resolved ad ready for '{item_name}' ({secs}s)")
            else:
                logger.error(f"Context-resolved ad generation produced no image for '{item_name}'")
                ad_generator_Obj.agent_override_item = None
        finally:
            ad_generator_Obj.agent_override_generating = False
            ad_generator_Obj._generation_lock.release()

    try:
        threading.Thread(target=_generate_and_set, args=(resolved, associations, display_seconds), daemon=True).start()
    except RuntimeError:
        ad_generator_Obj._generation_lock.release()
        return {'error': 'Failed to start ad generation; try again in a few seconds.'}
    return {'resolved_product': resolved, 'matched_rule': matched_rule, 'status': 'generating', 'display_seconds': display_seconds}


def get_catalog_summary(full=False):
    """Build a per-product catalog summary; used by the get_catalog MCP tool."""
    global product_associations
    summary = []
    for product, entries in product_associations.items():
        if not entries:
            continue
        base = entries[0]
        cross_sells = sorted({e['associated_cross_sell'] for e in entries if e.get('associated_cross_sell')})
        item = {'product': product, 'price': base.get('price'), 'unit': base.get('unit'), 'cross_sells': cross_sells}
        if full:
            item['variants'] = entries
        summary.append(item)
    return summary


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

    # Load context rules for select_dynamic_ad (MCP action); safe to be missing, feature just stays disabled
    context_rules_path = "/app/context_rules.json"
    if os.path.exists(context_rules_path):
        load_context_rules(context_rules_path)
    else:
        logger.warning(f"Context rules file not found at {context_rules_path}. select_dynamic_ad will be unavailable.")

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
        flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)) # nosec B104
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

        # Start MCP server (agent-facing tools) in its own daemon thread; failures here are isolated
        try:
            from mcp_server import run_mcp_server
            mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
            mcp_thread.start()
            logger.info("MCP server thread started")
        except Exception as e:
            logger.error(f"Failed to start MCP server thread: {str(e)}")

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