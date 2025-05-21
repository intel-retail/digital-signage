from flask_restx import Api

from .status import api as pca_status
from .version import api as pca_version
from .mqttlistener import api as pca_mqttlistener
from .products import api as pca_products
from .productsProb import api as pca_productsProb
from .association_rules import api as pca_productsARU

#API DOC
api = Api(
    title='PCA Server',
    version='0.1',
    description='Product Consumption Analyzer Server',
    # All API metadatas
)

# Add Namespaces into the API with URL prefixes
api.add_namespace(pca_status, path='/pca') 
api.add_namespace(pca_version, path='/pca')
api.add_namespace(pca_mqttlistener, path='/pca')
api.add_namespace(pca_products, path='/pca')
api.add_namespace(pca_productsProb, path='/pca')
api.add_namespace(pca_productsARU, path='/pca')