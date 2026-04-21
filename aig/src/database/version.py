import importlib.metadata
from datetime import datetime
from PIL import Image
import os
import gc
import threading
# GenAI
import openvino_genai
import openvino as ov
# Logging
import logging
logger = logging.getLogger(__name__)
# ChromaDB
import chromadb
from chromadb.utils import embedding_functions
# numpy
import numpy as np
# Utils 
from database.utils import SharedUtils

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
    __version__ = "0.1.0"
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
        try:
            core = ov.Core()
            core.available_devices
            if device in core.available_devices:
                return True
        except Exception as e:
            logger.error(f"[OpenVINO] Error checking device availability: {e}")
            return False
        
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
        if not hasattr(self, 'chroma_client'):
            # Lazy initialization - client is None until first use
            self._chroma_client = None
            self._collection = None
            self._embedding_function = None
            self._chromadb_lock = threading.Lock()
            
            #Load the Default Ad image
            self.default_ad_image = None
            try:
                self.default_ad_image=Image.open(AseServerMetadata.get_ase_default_ad_img())
            except Exception as e:
                logger.error(f"[ASE] Error loading default ad image: {e}")
                self.default_ad_image = None

            self.logo = Image.open(AigServerMetadata.get_logo_path()) if AigServerMetadata.get_logo_path() else None
            
            logger.info("[ASE] ChromaDB will be loaded on-demand (lazy loading enabled)")
    
    @property
    def chroma_client(self):
        """Lazy-load ChromaDB client on first access"""
        if self._chroma_client is None:
            with self._chromadb_lock:
                if self._chroma_client is None:  # Double-check locking
                    self._initialize_chromadb()
        return self._chroma_client
    
    @property
    def collection(self):
        """Lazy-load collection on first access"""
        if self._collection is None:
            # Accessing chroma_client will trigger initialization
            _ = self.chroma_client
        return self._collection
    
    def _initialize_chromadb(self):
        """Initialize ChromaDB client and collection (called lazily)"""
        logger.info("[ASE] Initializing ChromaDB client with persistent storage...")
        try:
            self._chroma_client = chromadb.HttpClient(
                host=AseServerMetadata.get_ase_chromadb_host(), 
                port=AseServerMetadata.get_ase_chromadb_port()
            )
            logger.info(f"[ASE] ChromaDB client connected to {AseServerMetadata.get_ase_chromadb_host()}:{AseServerMetadata.get_ase_chromadb_port()}")
        except Exception as e:
            logger.error(f"[ASE] Error initializing ChromaDB client: {e}")
            self._chroma_client = None
            return

        if self._chroma_client is not None:
            local_path = os.getenv('ASE_MODEL_PATH')
            try:
                self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=local_path)
                logger.info(f"[ASE] Embedding function initialized with model: {local_path}")
            except Exception as e:
                logger.error(f"[ASE] Error initializing embedding function with model '{local_path}': {e}")
                logger.warning("[ASE] Falling back to default embedding function.")
                self._embedding_function = embedding_functions.DefaultEmbeddingFunction()
            
            try:
                self._collection = self._chroma_client.get_or_create_collection(
                    name=AseServerMetadata.get_ase_collection_name(), 
                    embedding_function=self._embedding_function
                )
                logger.info(f"[ASE] Collection '{AseServerMetadata.get_ase_collection_name()}' ready")
            except Exception as e:
                logger.error(f"[ASE] Failed to create collection: {e}")
                self._collection = None
            
            # Load sample data after collection is ready
            self.process_sample_data()
        else:
            logger.error("[ASE] Failed to initialize ChromaDB client.")
            self._collection = None
            
    
    def chromadb_heartbeat(self):
        """
        Check the Chromadb reachability.
        """
        if self.chroma_client is not None:
            return self.chroma_client.heartbeat()
        else:            
            return None
    
    def process_sample_data(self):
        """
        Load sample data into the ChromaDB collection if it is enabled.
        """
        if not AseServerMetadata.get_ase_enable_sampledata():
            return
        path_sample_data = os.getenv('ASE_ENABLE_SAMPLEDATA_DIR', '/opt/sharedata/sample')
        if path_sample_data is None or not os.path.exists(path_sample_data):
            logger.error(f"[ChromaDB] Sample data directory {path_sample_data} does not exist.")
            return
        
        results=SharedUtils.load_sampledata(self.collection, path_sample_data)  # Ensure the image path exists

        if results is None:
            logger.error("[ChromaDB] No sample data found or failed to load sample data.")
            return
        
        count = 0
        total = 0
        for result in results:
            try:
                id = result['id'] #int
                description = result['description']
                image = result['image']
                source = result.get('source', 'ase')  # Default source is 'ase'
                
                if not self.chromadb_exists(id):
                    self.chromadb_add(id, description, image, source)
                    count = count +1
                
                total = total + 1
            except Exception as e:
                logger.error(f"[ChromaDB] Error processing sample data: {e}")

        logger.warning(f"[ChromaDB] {count} of {total} Sample data loaded successfully.")
        

    @staticmethod
    def get_ase_enable_sampledata() ->  bool:
        """
        Get the ASE enable sample data flag.
        Default is 'False'.
        """
        val = None
        try:
            val=int(os.getenv('ASE_ENABLE_SAMPLEDATA', 0))
        except ValueError:
            return False
        
        return (not val == 0)
    
    @staticmethod
    def get_ase_distance_threshold() -> float:
        """
        Get the ASE distance threshold for image similarity.
        Default is '0.5'.
        """
        try:
            return float(os.getenv('ASE_DISTANCE_MAX_THRESHOLD', 1.5))  # Default distance threshold
        except ValueError:
            return 1.5
        
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
                continue #Look for a another ID            
        
    @staticmethod
    def get_ase_collection_name():
        return os.getenv('ASE_COLLECTION_NAME', 'ase-collection') # ASE collection name
    
    @staticmethod
    def get_ase_chromadb_port() ->int:
        """
        Get the ASE Chroma DB Port.
        Default is '8000'.
        """
        return int(os.getenv('ASE_CHROMADB_PORT', 8000)) # Default host for Chroma DB
    
    @staticmethod
    def get_ase_chromadb_host():
        """
        Get the ASE Chroma DB host.
        Default is 'ase-chromadb'.
        """
        return os.getenv('ASE_CHROMADB_HOST', 'ase-chromadb') # Default host for Chroma DB        
    
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
        Get the ASE img path.
        """
        return os.getenv('ASE_IMG_PATH', '/opt/sharedata/imgs')

    @staticmethod
    def save_image_to_dir(image: Image.Image, id: int):
        # Ensure the directory exists
        directory=AseServerMetadata.get_ase_img_path()
        filename = f"img_{str(id)}.jpg"
        os.makedirs(directory, exist_ok=True)
        # Build the full path
        filepath = os.path.join(directory, filename)
        # Save the image
        try:
            image.save(filepath)
        except Exception as e:
            logger.error(f"[ChromaDB] Error saving image to {filepath}: {e}")
            raise ValueError(f"Could not save image to {filepath}. Error: {e}")

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
        Get the image file from filepath 
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

    def chromadb_add(self,id:int, description:str,image:Image, source:str="ase"):
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        
        if id is None or description is None or image is None:
            raise ValueError("id, description and image must be provided.")

        filepath = None
        try:
            filepath=AseServerMetadata.save_image_to_dir(image, id)
        except Exception as e:
            logger.error(f"[ChromaDB] Error processing image: {e}")
            raise ValueError("Invalid image provided.") 

        img_height = image.height
        img_width = image.width

        try:
            self.collection.add(
                documents=[description],
                metadatas=[{"source": source, "id": id, "description": description, "img_path": filepath, "img_height": img_height, "img_width": img_width}],
                ids=[str(id)]
            )
            logger.info(f"[ChromaDB] Document with ID {id} added successfully.")
        except Exception as e:
            AseServerMetadata.remove_image_file(id)
            logger.error(f"[ChromaDB] Error adding document with ID {id}: {e}")
            raise ValueError(f"Could not add document with ID {id} to ChromaDB. Error: {e}")
        
        return True
    
    def chromadb_remove(self, id:str):
        """
        Remove a document from ChromaDB by its ID.
        """
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        
        if id is None:
            raise ValueError("id must be provided.")

        try:
            self.collection.delete(ids=[id])
            try:
                AseServerMetadata.remove_image_file(int(id))
            except ValueError as e:
                logger.info(f"{id}: Not image is associated with it.")

            logger.info(f"[ChromaDB] Document with ID {id} removed successfully.")
        except Exception as e:
            logger.error(f"[ChromaDB] Error removing document with ID {id}: {e}")
            raise ValueError(f"Could not remove document with ID {id} from ChromaDB. Error: {e}")
        
        return True
    
    def chromadb_querytxt(self, simpletext:str, n_results:int=3):
        return self.chromadb_query([simpletext], n_results)
    
    def chromadb_query(self, query_texts:list, n_results:int=3):
        """
        Query the ChromaDB collection with the given query texts.
        :param query_texts: List of query texts to search for.
        :param n_results: Number of results to return.
        :return: Query results.
        """
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        
        if not query_texts or not isinstance(query_texts, list):
            raise ValueError("query_texts must be a non-empty list.")

        try:
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results
            )
            logger.info(f"[ChromaDB] Query executed successfully with {len(results['documents'])} results.")
            return results
        except Exception as e:
            logger.error(f"[ChromaDB] Error executing query: {e}")
            raise ValueError(f"Could not execute query. Error: {e}")
    
    def chromadb_exists(self, id:int):
        """
        Check if a document with the given ID exists in the ChromaDB collection.
        """
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        if id is None:
            raise ValueError("id must be provided.")

        try:
            result = self.collection.get(ids=[str(id)])
            # If the id exists, result['ids'] will contain the id
            if result is None or 'ids' not in result or not result['ids']:
                logger.info(f"[ChromaDB] Document with ID {id} does not exist.")
                return False
            
            return str(id) in result.get('ids', [])[0]
        except Exception as e:
            logger.error(f"[ChromaDB] Error checking existence of document with ID {id}: {e}")
            return False
        
    def chromadb_update(self, id, description: str, image: Image.Image, source: str = "ase"):
        """
        Update a document in ChromaDB by its ID.
        """
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        if id is None or description is None or image is None:
            raise ValueError("id, description, and image must be provided.")

        # Remove the old document and image (if they exist)
        self.chromadb_remove(str(id))

        # Add the new/updated document and image
        return self.chromadb_add(id, description, image, source)    
    
    def chromadb_get(self, id:str):
        """
        Get a document with the given ID in the ChromaDB collection.
        """
        if self.collection is None:
            raise ValueError("ChromaDB collection is not initialized. Please check the connection settings.")
        if id is None:
            raise ValueError("id must be provided.")

        try:
            result = self.collection.get(ids=[str(id)])
            # If the id exists, result['ids'] will contain the id
            if result is None or 'ids' not in result:
                logger.warning(f"[ChromaDB] Document with ID {id} does not exist.")
                return None
            
            return result
        except Exception as e:
            logger.error(f"[ChromaDB] Error checking existence of document with ID {id}: {e}")
            return None
    