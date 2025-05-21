from flask_restx import Namespace, Resource, fields
from datetime import datetime

api = Namespace('PCA - Version', description='Version related operations')

#Version schema
version_sch = api.model('pca_version', {
    'component': fields.String(required=True, default=None, description="Component Name", example="2.2.5"),
    'version': fields.String(required=True,  default=None, description="Component Version", example="0.1.0"),
    'observation': fields.String(required=False, default=None, description="Component Observation", example="0.1.0"),
    'lastverification': fields.String(required=True, default=None, description="Component Last Verification", example="2025-05-21 11:32"),
})

class Version_sch(object):
    component:str=None
    version:str=None
    observation:str=None
    lastverification:str=None

@api.route('/versions',
           doc={"description":"It returns the version of the PCA Server and associated libraries."})
class HStatus(Resource):
    @api.marshal_list_with(version_sch)
    def get(self):
        rdo=[]
        curr=Version_sch()
        curr.component="PCA Server"
        curr.version="0.0.1"
        curr.observation="Product Consumption Analyzer (PCA) Server"
        curr.lastverification=datetime.now().strftime("%Y-%m-%d %H:%M")
        rdo.append(curr)
        
        return rdo
