import os
#Flask API
from flask_restx import Namespace, Resource, fields
# Rule definition
from database.arules import Arule_sch
# Association Rules
from server.arules.association_rules import ARDiscoverer
import daal4py as d4p
import numpy as np
#Logging
import logging
logger = logging.getLogger(__name__)

api = Namespace('PCA - Association Rules', description='Product Association Rules related operations based on transactions ')

@api.route('/prd/assocrules/<float:supp>/<float:conf>', 
           doc={"description": "Discover Association Rules subject to a given support and confidence."})
@api.param('supp', 'Minimum support for the association rules between (0, 1). Default is 0.001')
@api.param('conf', 'Minimum confidence for the association rules between (0,1). Default is 0.7')
class ARDiscover(Resource):
    @api.doc('It returns the number of detected rules.')
    @api.response(200, 'Success')
    @api.response(204, 'Wrong parameter values')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    def get(self,supp=0.001,conf=0.7):
        if supp <= 0  or supp >=1:
            return "Incorrect Support", 204
        if conf <= 0  or conf >=1:
            return "Incorrect Confidence", 204        

        ardiscoverer=ARDiscoverer() #Singleton
        ardiscoverer.min_support=supp
        ardiscoverer.min_confidence=conf
        ardiscoverer.algoDiscoverer =  d4p.association_rules(
                discoverRules=True,
                minSupport=ardiscoverer.min_support,
                minConfidence=ardiscoverer.min_confidence
            )

        errorMessage=None
        try:
            result1 = ardiscoverer.fitFromPostgres()

            if result1 is None:
                return 0, 200        

            ardiscoverer.lastResult = result1
            if result1 is not None:
                logger.info("Association rules discovered successfully.")
                if result1.antecedentItemsets is not None and len(result1.antecedentItemsets) > 0:
                    myRulesID = np.unique(result1.antecedentItemsets[:, 0])                
                else:
                    myRulesID = []
            else:
                logger.error("Failed to discover association rules.")            


        except Exception as e:
            errorMessage=f"Association Rules. Support ({supp}) & Confidence ({conf}). Exception: {str(e)}"
            logger.error(errorMessage)
        
        if errorMessage is not None:            
            return errorMessage, 500
                        
        return len(myRulesID), 200

@api.route('/prd/assocrules/get_antecedents_for/<int:consequentID>',
           doc={"description": "It returns the number of antecedent products ordered in a descendent way by frequency of rules."})
@api.param('consequentID', 'Look for the antecendets of the consequentID (A product ID)')
class ARDiscoverAntecedent(Resource):
    @api.response(200, 'Success')
    @api.response(204, 'Wrong parameter values')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    def get(self,consequentID):
        if consequentID is None or consequentID <= 0:
            return "Incorrect ConsequentID", 204

        ardiscoverer=ARDiscoverer() #Singleton
        if ardiscoverer.lastResult is None:
            return "No Association Rules", 204

        pants = ardiscoverer.lastResult.see_antecends(consequentID)                        
        presult=[]
        if pants is None or len(pants) == 0:
            return presult, 200
        
        #Warning: ProductIDs are uint64 and it needs to be converted to int for serialization
        return [int(x) for x in pants], 200

consequent_ids_model = api.model('IDs', {
    'IDs': fields.List(fields.Integer, required=True, description='List of Product IDs', example="[1,2,3]"),
})

@api.route('/prd/assocrules/get_consequents_for/',
           doc={"description": "It returns the number of consequents that contain a list products in the antecedent."})
class ARDiscoverConsequentFor(Resource):
    @api.expect(consequent_ids_model, validate=True, description="List of Product IDs", example="[1,2,3]")
    @api.response(200, 'Success')
    @api.response(204, 'Wrong parameter values')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    def post(self):
        data=api.payload
        IDs = data.get('IDs', [])

        if not IDs or not all(isinstance(i, int) for i in IDs):
            return "Incorrect Product IDs", 204

        ardiscoverer=ARDiscoverer() #Singleton
        if ardiscoverer.lastResult is None:
            return "No Association Rules", 204

        pcons = ardiscoverer.lastResult.see_consequents(IDs)
        presult=[]
        if pcons is None or len(pcons) == 0:
            return presult, 200
        
        #Warning: ProductIDs are uint64 and it needs to be converted to int for serialization
        return [int(x) for x in pcons], 200 


arule_sch = api.model('ruledefinition', {
    'antecedents': fields.List(fields.Integer, required=True, description='List of productIDs in the antecedent for the rule'),
    'consequents': fields.List(fields.Integer, required=True, description='List of productIDs in the consequent for the rule'),
    'support': fields.Float(required=True, 
                         readonly=True,
                         description="Rule support.", 
                         example="mytopic"),                         
    'confidence': fields.Float(required=False, 
                         readonly=True,
                         description="Rule confidence.", 
                         example="0.7"),
    'ntransactions': fields.Integer(required=False, 
                         readonly=True,
                         description="Number of transactions.", 
                         example="20000"),                       
})


@api.route('/prd/assocrules/filter_someof/',
           doc={"description": "It returns the rules (ordered by support desc) containing some of indicated productIDs in the antecedent or consequent. if at least one of the IDs is in the antecedent or consequent, the rule is returned."})
class ARDiscoverFilterSomeOf(Resource):
    @api.expect(consequent_ids_model, validate=True, description="List of Product IDs", example="[1,2,3]")
    @api.response(200, 'Success')
    @api.response(204, 'Wrong parameter values')
    @api.response(500, 'Accepted but it could not be processed/recovered')  
    @api.marshal_with(arule_sch)      
    def post(self):
        data=api.payload
        IDs = data.get('IDs', [])

        if not IDs or not all(isinstance(i, int) for i in IDs):
            return "Incorrect Product IDs", 204

        ardiscoverer=ARDiscoverer() #Singleton
        if ardiscoverer.lastResult is None:
            return "No Association Rules", 204

        prules = ardiscoverer.lastResult.see_rules_someof(IDs)
        presult=[]        
        if prules is None or len(prules) == 0:
            return presult, 200
        
        #Warning: ProductIDs are uint64 and it needs to be converted to int for serialization
        return prules, 200 

filter_ids_model = api.model('filter_ids_model', {
    'IDs': fields.List(fields.Integer, required=True, description='List of Product IDs', example="[1,2,3]"),
    'pantecedent': fields.Boolean(required=True, default=True, description='True if the IDs must be present in the antecedent. False if the IDs must be present in the consequent', example="true"),
})

@api.route('/prd/assocrules/filter_strict/',
           doc={"description": "It returns the rules (ordered by support desc) containing all indicated productIDs in the antecedent or consequent (based on pantecedent). The rule is returned when All IDs are present in the antecedent or consequent."})
class ARDiscoverFilterStrict(Resource):
    @api.expect(filter_ids_model, validate=True, description="List of Product IDs and section to be applied in the rule (antecent or consequent)")
    @api.response(200, 'Success')
    @api.response(204, 'Wrong parameter values')
    @api.response(500, 'Accepted but it could not be processed/recovered')  
    @api.marshal_with(arule_sch)      
    def post(self):
        data=api.payload
        IDs = data.get('IDs', [])
        pantecedent = data.get('pantecedent', True)

        if not IDs or not all(isinstance(i, int) for i in IDs):
            return "Incorrect Product IDs", 204

        ardiscoverer=ARDiscoverer() #Singleton
        if ardiscoverer.lastResult is None:
            return "No Association Rules", 204

        prules = ardiscoverer.lastResult.see_rules_strict(IDs,pantecedent)
        presult=[]        
        if prules is None or len(prules) == 0:
            return presult, 200
        
        #Warning: ProductIDs are uint64 and it needs to be converted to int for serialization
        return prules, 200 