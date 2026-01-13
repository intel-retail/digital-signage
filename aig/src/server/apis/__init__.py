from flask_restx import Api

from .status import api as aig_status
from .version import api as aig_version
from .modelinf import api as aig_modelinf
from .predefinedads import api as predefined_ads_api

#API DOC
api = Api(
    title='AIG Server',
    version='0.1',
    description='Advertise Image Generator Server',
    # All API metadatas
)

# Add Namespaces into the API with URL prefixes
api.add_namespace(aig_status, path='/aig') 
api.add_namespace(aig_version, path='/aig')
api.add_namespace(aig_modelinf, path='/aig') 
api.add_namespace(predefined_ads_api, path='/ase') 
