import importlib.metadata
from datetime import datetime
from PIL import Image
import os
import gc
import tempfile
import threading
# GenAI
import openvino_genai
import openvino as ov
# Logging
import logging
# Embeddings / Vector DB
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models
# numpy
import numpy as np
# Utils 
from database.utils import SharedUtils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Version_sch(object):
    """
    Version schema to describe a component's version information."""
    component:str=None
    version:str=None
    observation:str=None
    lastverification:str=None

class AigServerMetadata:
    def __new__(cls):
        """Singleton pattern to ensure only one instance of AigServerMetadata exists."""
        if not hasattr(cls, 'instance'):
            cls.instance = super(AigServerMetadata, cls).__new__(cls)
        return cls.instance
    
    def __init__(self):
        # It avoids re-initialization of the instance for the singleton pattern
        if not hasattr(self, 'logo'):
            self.logo = Image.open(AigServerMetadata.get_logo_path()) if AigServerMetadata.get_logo_path() else None
            
            # Model is NOT preloaded - lazy loading instead
            self.preloadedModel = None
            self._model_device = None
            self._model_lock = threading.Lock()
            logger.info("[AIG] Model will be loaded on-demand (lazy loading enabled)")
            

    def get_logo(self):
        """
        Returns the logo image for the AIG server.
        If the logo path is not set, it returns None.
        """
        return self.logo
    
    def get_preloaded_model(self):
        """
        Returns the preloaded Text2Image model with lazy loading.
        If the model is not available, it loads it on-demand.
        """
        with self._model_lock:
            requested_device = AigServerMetadata.get_t2i_model_device()
            
            # Load model if not loaded or device changed
            if self.preloadedModel is None or self._model_device != requested_device:
                if AigServerMetadata.is_device_available(requested_device):
                    logger.info(f"[AIG] Loading Text2Image model on device: {requested_device}")
                    try:
                        self.preloadedModel = openvino_genai.Text2ImagePipeline(
                            AigServerMetadata.get_t2i_model_path(), 
                            requested_device
                        )
                        self._model_device = requested_device
                        logger.info(f"[AIG] Model loaded successfully on {requested_device}")
                    except Exception as e:
                        logger.error(f"[AIG] Failed to load model on {requested_device}: {e}")
                        self.preloadedModel = None
                        self._model_device = None
                else:
                    logger.error(f"[AIG] Device {requested_device} is not available")
                    self.preloadedModel = None
            
            return self.preloadedModel
    
    def unload_model(self):
        """
        Unload the Text2Image model from memory to free up resources.
        """
        with self._model_lock:
            if self.preloadedModel is not None:
                logger.info("[AIG] Unloading Text2Image model from memory")
                del self.preloadedModel
                self.preloadedModel = None
                self._model_device = None
                gc.collect()
                logger.info("[AIG] Model unloaded successfully")
            
    
    """
    Metadata for AIG Server.
    """
    __version__ = os.getenv("AIG_VERSION")
    __name_short = "AIG Server"
    __name_extended = "Advertise Image Generator (AIG) Server"
    __description_short = "It creates advertise image dyncamically based on a text description."

    @staticmethod
    def is_device_available(device: str) -> bool:
        """
        Check if the specified device is available.
        :param device: Device type (e.g., 'GPU', 'CPU').
        :return: True if the device is available, False otherwise.
        """
        if device.upper() == 'CPU':
            return True  # CPU is always present; skip ov.Core() which probes GPU and crashes without hardware
        try:
            core = ov.Core()
            return device in core.available_devices
        except Exception as e:
            logger.error(f"[OpenVINO] Error checking device availability: {e}")
            return False
        
    @staticmethod
    def version():
        return AigServerMetadata.__version__
    
    @staticmethod
    def name_short():
        return AigServerMetadata.__name_short

    @staticmethod
    def name_extended():
        return AigServerMetadata.__name_extended

    @staticmethod
    def description_short():
        return AigServerMetadata.__description_short

    @staticmethod
    def get_aig_versioninfo() -> Version_sch:
        aigversion = Version_sch()
        aigversion.component = AigServerMetadata.name_short()
        aigversion.version = AigServerMetadata.version()
        aigversion.observation = AigServerMetadata.description_short()
        aigversion.lastverification = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        return aigversion

    @staticmethod
    def get_logo_path():
        return os.getenv('AIG_LOGO_PATH')
    
    @staticmethod
    def get_font_path():
        return os.getenv('AIG_FONT_PATH')
    
    @staticmethod
    def get_t2i_model_path():
        return os.getenv('AIG_MODEL_PATH')

    @staticmethod
    def get_t2i_model_device():
        device = os.getenv('AIG_MODEL_DEVICE', 'GPU')  # Default to GPU if not specified

        if device not in ['GPU', 'CPU', 'NPU']:
             device = 'CPU'
        
        return device

    @staticmethod
    def get_rest_server_port():
        return int(os.getenv('AIG_PORT',5003))

    @staticmethod
    def get_model_inference_steps():
        return int(os.getenv('AIG_MODEL_NUM_INFERENCE_STEPS', 5))    

    @staticmethod
    def get_img_width():
        return int(os.getenv('AIG_IMG_WIDTH_DEFAULT', 512)) # Default image width for the model
    
    @staticmethod
    def get_img_height():
        return int(os.getenv('AIG_IMG_HEIGHT_DEFAULT', 512)) # Default image height for the model   
    
    @staticmethod
    def should_keep_model_in_memory():
        """
        Check if the model should be kept in memory after first use.
        Returns True if model should stay loaded, False to unload after each use.
        """
        return os.getenv('AIG_KEEP_MODEL_IN_MEMORY', 'false').lower() == 'true'
    
class ServerEnvironment:
    @staticmethod
    def get_dependencies() -> list[Version_sch]:
        """
        Get the AIG dependencies and their versions.
        """
        dependencies = []
        for dist in importlib.metadata.distributions():
                dep = Version_sch()
                dep.component = dist.metadata['Name']
                dep.version = dist.version
                dep.observation = dist.metadata['Summary']
                dep.lastverification = datetime.now().strftime("%Y-%m-%d %H:%M")
                dependencies.append(dep)        
        return dependencies

        
    
    @staticmethod
    def get_aig_with_dependencies() -> list[Version_sch]:
        """
        Get the AIG version and dependencies.
        """
        aig = AigServerMetadata.get_aig_versioninfo()
        dependencies = ServerEnvironment.get_dependencies()
        return [aig] + dependencies

class AseServerMetadata:
    def __new__(cls):
        """Singleton pattern to ensure only one instance of AigServerMetadata exists."""
        if not hasattr(cls, 'instance'):
            cls.instance = super(AseServerMetadata, cls).__new__(cls)
        return cls.instance
    
    def __init__(self):
        # It avoids re-initialization of the instance for the singleton pattern
        if not hasattr(self, '_qdrant_client'):
            # Lazy initialization - client is None until first use
            self._qdrant_client = None
            self._collection = None
            self._embedding_model = None
            self._embedding_dimensions = None
            self._qdrant_lock = threading.Lock()
            self._record_locks = {}
            self._record_locks_lock = threading.Lock()
            
            # Load the Default Ad image
            self.default_ad_image = None
            try:
                self.default_ad_image = Image.open(AseServerMetadata.get_ase_default_ad_img())
            except Exception as e:
                logger.error(f"[ASE] Error loading default ad image: {e}")
                self.default_ad_image = None

            self.logo = Image.open(AigServerMetadata.get_logo_path()) if AigServerMetadata.get_logo_path() else None
            
            logger.info("[ASE] Qdrant will be loaded on-demand (lazy loading enabled)")
    
    @property
    def qdrant_client(self):
        """Lazy-load Qdrant client on first access."""
        if self._qdrant_client is None:
            with self._qdrant_lock:
                if self._qdrant_client is None:  # Double-check locking
                    self._initialize_qdrant()
        return self._qdrant_client
    
    @property
    def collection(self):
        """Lazy-load collection on first access."""
        if self._collection is None:
            # Accessing qdrant_client will trigger initialization
            _ = self.qdrant_client
        return self._collection
    
    @staticmethod
    def _normalize_point_id(id):
        if id is None:
            raise ValueError("id must be provided.")
        try:
            return int(id)
        except (TypeError, ValueError) as e:
            raise ValueError(f"id must be convertible to int for Qdrant storage. Got: {id}") from e

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._embedding_model is None:
            raise ValueError("Qdrant embedding model is not initialized. Please check the connection settings.")
        embeddings = self._embedding_model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

    def _get_record_lock(self, point_id: int):
        with self._record_locks_lock:
            if point_id not in self._record_locks:
                self._record_locks[point_id] = threading.Lock()
            return self._record_locks[point_id]
    
    def _initialize_qdrant(self):
        """Initialize Qdrant client, embedding model and collection (called lazily)."""
        logger.info("[ASE] Initializing Qdrant client with persistent storage...")
        try:
            self._qdrant_client = QdrantClient(
                host=AseServerMetadata.get_ase_qdrant_host(),
                port=AseServerMetadata.get_ase_qdrant_port()
            )
            logger.info(
                f"[ASE] Qdrant client connected to "
                f"{AseServerMetadata.get_ase_qdrant_host()}:{AseServerMetadata.get_ase_qdrant_port()}"
            )
        except Exception as e:
            logger.error(f"[ASE] Error initializing Qdrant client: {e}")
            self._qdrant_client = None
            return

        local_path = os.getenv('ASE_MODEL_PATH')
        try:
            self._embedding_model = SentenceTransformer(local_path)
            self._embedding_dimensions = self._embedding_model.get_sentence_embedding_dimension()
            logger.info(f"[ASE] Embedding model initialized with: {local_path}")
        except Exception as e:
            logger.error(f"[ASE] Error initializing embedding model with '{local_path}': {e}")
            self._embedding_model = None
            self._embedding_dimensions = None
            self._qdrant_client = None
            return

        collection_name = AseServerMetadata.get_ase_collection_name()
        try:
            if not self._qdrant_client.collection_exists(collection_name=collection_name):
                self._qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self._embedding_dimensions,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"[ASE] Collection '{collection_name}' created")
            else:
                collection_info = self._qdrant_client.get_collection(collection_name=collection_name)
                vectors_config = collection_info.config.params.vectors
                vector_params = next(iter(vectors_config.values())) if isinstance(vectors_config, dict) else vectors_config
                configured_size = getattr(vector_params, "size", None)
                configured_distance = getattr(vector_params, "distance", None)
                if configured_size != self._embedding_dimensions or configured_distance != models.Distance.COSINE:
                    raise ValueError(
                        f"Collection '{collection_name}' expects vectors of size {configured_size} "
                        f"with distance {configured_distance}, but model '{local_path}' produces "
                        f"size {self._embedding_dimensions} for cosine search."
                    )
                logger.info(f"[ASE] Collection '{collection_name}' already exists")
            self._collection = collection_name
        except Exception as e:
            logger.error(f"[ASE] Failed to create collection '{collection_name}': {e}")
            self._collection = None
            self._qdrant_client = None
            return
        
        # Load sample data after collection is ready
        self.process_sample_data()
    
    def qdrant_heartbeat(self):
        """
        Check Qdrant reachability.
        """
        if self.qdrant_client is not None:
            return self.qdrant_client.get_collections()
        else:
            return None
    
    def process_sample_data(self):
        """
        Load sample data into the Qdrant collection if it is enabled.
        """
        if not AseServerMetadata.get_ase_enable_sampledata():
            return
        path_sample_data = os.getenv('ASE_ENABLE_SAMPLEDATA_DIR', '/opt/sharedata/sample')
        if path_sample_data is None or not os.path.exists(path_sample_data):
            logger.error(f"[Qdrant] Sample data directory {path_sample_data} does not exist.")
            return
        
        results = SharedUtils.load_sampledata(self.collection, path_sample_data)

        if results is None:
            logger.error("[Qdrant] No sample data found or failed to load sample data.")
            return
        
        count = 0
        total = 0
        for result in results:
            try:
                id = result['id']
                description = result['description']
                image = result['image']
                source = result.get('source', 'ase')
                
                if not self.qdrant_exists(id):
                    self.qdrant_add(id, description, image, source)
                    count = count + 1
                
                total = total + 1
            except Exception as e:
                logger.error(f"[Qdrant] Error processing sample data: {e}")

        logger.warning(f"[Qdrant] {count} of {total} sample data items loaded successfully.")
    
    @staticmethod
    def get_ase_enable_sampledata() -> bool:
        """
        Get the ASE enable sample data flag.
        Default is 'False'.
        """
        val = None
        try:
            val = int(os.getenv('ASE_ENABLE_SAMPLEDATA', 0))
        except ValueError:
            return False
        
        return (not val == 0)
    
    @staticmethod
    def get_ase_distance_threshold() -> float:
        """
        Get the ASE similarity threshold for predefined ad matching.
        Prefer ASE_QDRANT_SCORE_MIN_THRESHOLD for Qdrant deployments.
        For backward compatibility, when only the legacy ASE_DISTANCE_MAX_THRESHOLD
        is set, it is translated from a maximum distance into an equivalent minimum
        cosine similarity score by using (1.0 - distance).
        """
        try:
            explicit_score = os.getenv('ASE_QDRANT_SCORE_MIN_THRESHOLD')
            if explicit_score is not None:
                return float(explicit_score)

            legacy_distance = float(os.getenv('ASE_DISTANCE_MAX_THRESHOLD', 0.2))
            translated_score = 1.0 - legacy_distance
            return min(1.0, max(0.0, translated_score))
        except ValueError:
            return 0.8

    @staticmethod
    def is_qdrant_match(score: float) -> bool:
        """
        Return True when the Qdrant cosine similarity score passes the configured threshold.
        """
        return score is not None and score >= AseServerMetadata.get_ase_distance_threshold()
    
    @staticmethod
    def get_ase_img_id():
        """
        Get the ASE image ID between 0 and 1x10^6.
        It tries 10 times to get an ID not associated with an image.
        Default is 'ase-img'.
        """
        for i in range(10):
            proposal = int(np.random.randint(0, 1000000))

            directory = AseServerMetadata.get_ase_img_path()
            filename = f"img_{str(proposal)}.jpg"
            filepath = os.path.join(directory, filename)
            
            if not os.path.exists(filepath):
                return proposal
            else:
                continue
    
    @staticmethod
    def get_ase_collection_name():
        """
        Get the ASE Qdrant collection name.
        """
        return os.getenv('ASE_COLLECTION_NAME', 'ase-collection')
    
    @staticmethod
    def get_ase_qdrant_port() -> int:
        """
        Get the ASE Qdrant port.
        Default is '6333'.
        """
        return int(os.getenv('ASE_QDRANT_PORT', 6333))
    
    @staticmethod
    def get_ase_qdrant_host():
        """
        Get the ASE Qdrant host.
        Default is 'ase-qdrant'.
        """
        return os.getenv('ASE_QDRANT_HOST', 'ase-qdrant')
    
    @staticmethod
    def get_ase_default_ad_img():
        """
        Get the default ad image path.
        Default is '/opt/sharedata/imgs/ase_default_ad.jpg'.
        """
        return os.getenv('ASE_IMG_DEFAULT_AD', '/opt/sharedata/default_ad.jpg')
    
    @staticmethod
    def get_ase_img_path():
        """
        Get the ASE image path.
        """
        return os.getenv('ASE_IMG_PATH', '/opt/sharedata/imgs')

    @staticmethod
    def _build_payload(id: int, description: str, filepath: str, image: Image.Image, source: str):
        return {
            "source": source,
            "id": id,
            "description": description,
            "img_path": filepath,
            "img_height": image.height,
            "img_width": image.width
        }

    @staticmethod
    def save_image_to_path(image: Image.Image, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        try:
            image.save(filepath)
        except Exception as e:
            logger.error(f"[Qdrant] Error saving image to {filepath}: {e}")
            raise ValueError(f"Could not save image to {filepath}. Error: {e}")

    @staticmethod
    def save_image_to_dir(image: Image.Image, id: int):
        directory = AseServerMetadata.get_ase_img_path()
        filename = f"img_{str(id)}.jpg"
        filepath = os.path.join(directory, filename)
        AseServerMetadata.save_image_to_path(image, filepath)
        return filepath

    @staticmethod
    def get_image_file(id: int) -> Image.Image:
        """
        Get the image file path for the given ID.
        :param id: The ID of the image.
        :return: The full path to the image file.
        """
        directory = AseServerMetadata.get_ase_img_path()
        filename = f"img_{str(id)}.jpg"
        filepath = os.path.join(directory, filename)
        
        if not os.path.exists(filepath):
            logger.warning(f"Image file not found: {filepath}")
            return None
        
        return Image.open(filepath)

    @staticmethod
    def get_image_file_from_path(filepath: str) -> Image.Image:
        """
        Get the image file from filepath.
        :param filepath: The path of the image.
        :return: The image file.
        """
        if filepath is None:
            return None
        
        if not os.path.exists(filepath):
            logger.warning(f"Image file not found: {filepath}")
            return None
        
        return Image.open(filepath)

    @staticmethod
    def remove_image_file(id: int):
        directory = AseServerMetadata.get_ase_img_path()
        filename = f"img_{str(id)}.jpg"
        filepath = os.path.join(directory, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Removed image file: {filepath}")
            else:
                logger.warning(f"File not found: {filepath}")
        except Exception as e:
            logger.error(f"Error removing image file {filepath}: {e}")
            return False
        
        return True

    def get_logo(self):
        """
        Returns the logo image for the ASE server.
        If the logo path is not set, it returns None.
        """
        return self.logo

    def qdrant_add(self, id: int, description: str, image: Image.Image, source: str = "ase"):
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")
        
        if id is None or description is None or image is None:
            raise ValueError("id, description and image must be provided.")

        filepath = None
        try:
            filepath = AseServerMetadata.save_image_to_dir(image, id)
        except Exception as e:
            logger.error(f"[Qdrant] Error processing image: {e}")
            raise ValueError("Invalid image provided.")

        payload = AseServerMetadata._build_payload(id, description, filepath, image, source)

        try:
            vector = self._embed_texts([description])[0]
            self.qdrant_client.upsert(
                collection_name=self.collection,
                wait=True,
                points=[
                    models.PointStruct(
                        id=AseServerMetadata._normalize_point_id(id),
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            logger.info(f"[Qdrant] Document with ID {id} added successfully.")
        except Exception as e:
            AseServerMetadata.remove_image_file(id)
            logger.error(f"[Qdrant] Error adding document with ID {id}: {e}")
            raise ValueError(f"Could not add document with ID {id} to Qdrant. Error: {e}")
        
        return True
    
    def qdrant_remove(self, id: str):
        """
        Remove a document from Qdrant by its ID.
        """
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")

        point_id = AseServerMetadata._normalize_point_id(id)
        try:
            self.qdrant_client.delete(
                collection_name=self.collection,
                points_selector=models.PointIdsList(points=[point_id]),
                wait=True
            )
            try:
                AseServerMetadata.remove_image_file(point_id)
            except ValueError:
                logger.info(f"{id}: No image is associated with it.")

            logger.info(f"[Qdrant] Document with ID {id} removed successfully.")
        except Exception as e:
            logger.error(f"[Qdrant] Error removing document with ID {id}: {e}")
            raise ValueError(f"Could not remove document with ID {id} from Qdrant. Error: {e}")
        
        return True
    
    def qdrant_querytxt(self, simpletext: str, n_results: int = 3):
        return self.qdrant_query([simpletext], n_results)
    
    def qdrant_query(self, query_texts: list, n_results: int = 3):
        """
        Query the Qdrant collection with the given query texts.
        For backward compatibility the returned dictionary still exposes the key
        `distances`, but the stored values are Qdrant cosine similarity scores.
        Callers must therefore keep results whose score is greater than or equal
        to `get_ase_distance_threshold()`.
        """
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")
        
        if not query_texts or not isinstance(query_texts, list):
            raise ValueError("query_texts must be a non-empty list.")

        try:
            query_vectors = self._embed_texts(query_texts)
            result_ids = []
            result_metadatas = []
            result_distances = []
            result_documents = []

            for query_vector in query_vectors:
                response = self.qdrant_client.query_points(
                    collection_name=self.collection,
                    query=query_vector,
                    limit=n_results,
                    with_payload=True,
                    with_vectors=False
                )
                points = response.points if hasattr(response, "points") else response

                ids = []
                metadatas = []
                distances = []
                documents = []
                for point in points:
                    payload = point.payload or {}
                    ids.append(str(point.id))
                    metadatas.append(payload)
                    distances.append(point.score)
                    documents.append(payload.get("description"))

                result_ids.append(ids)
                result_metadatas.append(metadatas)
                result_distances.append(distances)
                result_documents.append(documents)

            results = {
                "ids": result_ids,
                "metadatas": result_metadatas,
                "distances": result_distances,
                "documents": result_documents
            }
            logger.info(
                f"[Qdrant] Query executed successfully with "
                f"{sum(len(documents) for documents in result_documents)} results."
            )
            return results
        except Exception as e:
            logger.error(f"[Qdrant] Error executing query: {e}")
            raise ValueError(f"Could not execute query. Error: {e}")
    
    def qdrant_exists(self, id: int):
        """
        Check if a document with the given ID exists in the Qdrant collection.
        """
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")

        point_id = AseServerMetadata._normalize_point_id(id)
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False
            )
            if not result:
                logger.info(f"[Qdrant] Document with ID {id} does not exist.")
                return False
            
            return True
        except Exception as e:
            logger.error(f"[Qdrant] Error checking existence of document with ID {id}: {e}")
            return False
    
    def qdrant_update(self, id, description: str, image: Image.Image, source: str = "ase"):
        """
        Update a document in Qdrant by its ID.
        """
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")
        if id is None or description is None or image is None:
            raise ValueError("id, description, and image must be provided.")
        
        point_id = AseServerMetadata._normalize_point_id(id)
        with self._get_record_lock(point_id):
            existing_records = self.qdrant_client.retrieve(
                collection_name=self.collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False
            )
            if not existing_records:
                return self.qdrant_add(id, description, image, source)

            current_payload = existing_records[0].payload or {}
            current_img_path = current_payload.get("img_path", os.path.join(AseServerMetadata.get_ase_img_path(), f"img_{id}.jpg"))
            previous_description = current_payload.get("description")
            new_payload = AseServerMetadata._build_payload(id, description, current_img_path, image, source)
            os.makedirs(os.path.dirname(current_img_path), exist_ok=True)
            temp_fd, temp_img_path = tempfile.mkstemp(
                prefix=f"img_{id}_",
                suffix=".jpg",
                dir=os.path.dirname(current_img_path)
            )
            os.close(temp_fd)

            try:
                AseServerMetadata.save_image_to_path(image, temp_img_path)
                vector = self._embed_texts([description])[0]
                self.qdrant_client.upsert(
                    collection_name=self.collection,
                    wait=True,
                    points=[
                        models.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=new_payload
                        )
                    ]
                )
                os.replace(temp_img_path, current_img_path)
                logger.info(f"[Qdrant] Document with ID {id} updated successfully.")
                return True
            except Exception as e:
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)

                if previous_description is not None:
                    try:
                        previous_vector = self._embed_texts([previous_description])[0]
                        self.qdrant_client.upsert(
                            collection_name=self.collection,
                            wait=True,
                            points=[
                                models.PointStruct(
                                    id=point_id,
                                    vector=previous_vector,
                                    payload=current_payload
                                )
                            ]
                        )
                    except Exception as restore_error:
                        logger.error(f"[Qdrant] Failed to restore previous payload for ID {id}: {restore_error}")

                logger.error(f"[Qdrant] Error updating document with ID {id}: {e}")
                raise ValueError(f"Could not update document with ID {id} in Qdrant. Error: {e}")
    
    def qdrant_get(self, id: str):
        """
        Get a document with the given ID in the Qdrant collection.
        """
        if self.collection is None:
            raise ValueError("Qdrant collection is not initialized. Please check the connection settings.")

        point_id = AseServerMetadata._normalize_point_id(id)
        try:
            result = self.qdrant_client.retrieve(
                collection_name=self.collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False
            )
            if not result:
                logger.warning(f"[Qdrant] Document with ID {id} does not exist.")
                return None
            
            payload = result[0].payload or {}
            return {
                "ids": [[str(result[0].id)]],
                "metadatas": [[payload]],
                "documents": [[payload.get("description")]]
            }
        except Exception as e:
            logger.error(f"[Qdrant] Error checking existence of document with ID {id}: {e}")
            return None
    