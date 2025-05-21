from flask_restx import Namespace, Resource, fields

api = Namespace('PCA - Status', description='Status related operations')

## Schemas
    ##Status
status_sch = api.model('status_test', {
    'status': fields.String(required=True, default=None, description="ok: the id was read. failure: the id has not been received.", example="ok"),
    'id': fields.Integer(required=True, default=7, description="An integer ID as an example to check the reading/response procedure.", example="7"),
})

class Status_sch(object):
    status:str=None
    id:int=None

@api.route('/hstatus/<int:id>', 
           doc={"description":"It replies with the indicated parameter to check the server status."})
@api.param('id','An integer ID as an example to check the reading/response procedure.')
class HStatus(Resource):
    @api.doc('Check the Health Status - Get')
    @api.marshal_with(status_sch)
    def get(self, id):
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
