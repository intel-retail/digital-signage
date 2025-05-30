from flask_restx import Namespace, Resource, fields
from datetime import datetime

from database.version import ServerEnvironment

api = Namespace('AIG - Version', description='Version related operations')

#Version schema
version_sch = api.model('pca_version', {
    'component': fields.String(required=True, default=None, description="Component Name", example="2.2.5"),
    'version': fields.String(required=True,  default=None, description="Component Version", example="0.1.0"),
    'observation': fields.String(required=False, default=None, description="Component Observation", example="0.1.0"),
    'lastverification': fields.String(required=True, default=None, description="Component Last Verification", example="2025-05-21 11:32"),
})

@api.route('/versions',
           doc={"description":"It returns the version of the PCA Server and dependencies."})
class VersionsPcaDependencies(Resource):
    @api.marshal_list_with(version_sch)
    def get(self):        
        return ServerEnvironment.get_aig_with_dependencies()
