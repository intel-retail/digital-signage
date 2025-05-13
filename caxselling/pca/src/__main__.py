#Arguments
import argparse
# Flask 
from flask import Flask
from flask_restx import Resource, Api, fields
#OneDAL
import daal4py as d4p 

#Module

# Server
app = Flask(__name__)

#API DOC
api = Api(app, version="0.1", title="PCA Server", description="Product Consumption Analyzer Server") #Doc API Header

ns = api.namespace('pca-server', description = 'API PCA Server operations') #Section title

## Schemas
    ##Status
status_sch = api.model('status', {
    'status': fields.String(required=True, 
                            readonly=True,
                            description="ok: the id was read. failure: the id has not been received.",
                            example="ok"),
    'id': fields.Integer(required=True, 
                         readonly=True,
                         description="An integer ID as an example to check the reading/response procedure.", 
                         example="7"),
})

class Status_sch(object):
    status:str=None
    id:int=None

@ns.route('/hstatus/<int:id>')
@ns.param('id','An integer ID as an example to check the reading/response procedure.')
class HStatus(Resource):
    @ns.doc('Check the Health Status - Get')
    @ns.marshal_with(status_sch)
    def get(self, id):
        return self.common(id)

    @ns.doc('Check the Health Status - Put')
    @ns.marshal_with(status_sch)
    def put(self, id):
        return self.common(id)
    
    def common(self,id):        
        curr=Status_sch()

        if id is None or not isinstance(id,int):
            curr.id=id
            curr.status="failure"
        else:
            curr.id=id
            curr.status="ok"

        return curr

#Version schema
version_sch = api.model('version', {
    'flask': fields.String(required=True, 
                            readonly=True,
                            description="Flask library Version",
                            example="2.2.5"),
    'flask_restx': fields.String(required=True, 
                            readonly=True,
                            description="Flask-Restx library Version",
                            example="1.3.0"),
    'oneDAL': fields.String(required=True, 
                            readonly=True,
                            description="oneDAL library Version",
                            example="2024.7.0"),
    'PCAServer': fields.String(required=True, 
                               readonly=True,
                               description="PCA Server Version",
                               example="0.1.0"),
})

class Version_sch(object):
    flask:str=None
    flask_restx:str=None
    oneDAL:str=None
    PCAServer:str=None

@ns.route('/versions')
class HStatus(Resource):
    @ns.doc('Return the version of the PCA Server and associated libraries')
    @ns.marshal_with(version_sch)
    def get(self):
        curr=Version_sch()
        curr.flask="2.2.5x"
        curr.flask_restx="xx"
        curr.oneDAL=""
        curr.PCAServer=""##self.__version__

        return curr


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5002)
    args = parser.parse_args()

    #Registering the clean up function    
    app.run(host="0.0.0.0", debug=True, port=args.port)