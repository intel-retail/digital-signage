import importlib.metadata
from datetime import datetime
from PIL import Image
import os
# GenAI
import openvino_genai
import openvino as ov
# Logging
import logging
logger = logging.getLogger(__name__)

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

            # Initialize the model for CPU            
            if AigServerMetadata.is_device_available(AigServerMetadata.get_t2i_model_device()):
                self.preloadedModel = openvino_genai.Text2ImagePipeline(AigServerMetadata.get_t2i_model_path(), AigServerMetadata.get_t2i_model_device())
            else:
                self.preloadedModel = None
            

    def get_logo(self):
        """
        Returns the logo image for the AIG server.
        If the logo path is not set, it returns None.
        """
        return self.logo
    
    def get_preloaded_model(self):
        """
        Returns the preloaded Text2Image model.
        If the model is not available, it returns None.
        """
        return self.preloadedModel
    
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
        return os.getenv('AIG_PORT',5003)

    @staticmethod
    def get_model_inference_steps():
        return int(os.getenv('AIG_MODEL_NUM_INFERENCE_STEPS', 20))    

    @staticmethod
    def get_img_width():
        return int(os.getenv('AIG_IMG_WIDTH_DEFAULT', 512)) # Default image width for the model
    
    @staticmethod
    def get_img_height():
        return int(os.getenv('AIG_IMG_HEIGHT_DEFAULT', 512)) # Default image height for the model   
    
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
