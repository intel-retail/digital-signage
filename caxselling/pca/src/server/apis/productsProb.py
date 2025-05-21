import os
#Flask API
from flask_restx import Namespace, Resource, fields
#PostgresSQL & MQTT
from database.db_manager import DatabaseConnection
from database.mqtt_manager import MqttManager
#Logging
import logging
logger = logging.getLogger(__name__)

api = Namespace('PCA - MQTT: Object-Detection-based Probabilities', description='Product Probabilities related operations based on MQTT messages (Last 6 months)')

## Schemas
productProbability_sch = api.model('productProbability', {
    'host': fields.String(required=True, default=None, description="The MQTT Broker Host.", example="http://192.168.1.2"),
    'port': fields.Integer(required=True, default=1883, description="The port number in the MQTT Broker Host.", example="1883"),
    'topic': fields.String(required=True, default=None,  description="Topic to listen in the MQTT Broker.",  example="mytopic"),                         
    'dow': fields.Integer(required=True, default=None, description="Day of Week. From monday (1) to Sunday (7).", example="1"),
    'hh24': fields.Integer(required=False, default=None, description="Hour in the day. From 0 to 23.", example="13"),                        
    'label_class': fields.String(required=False, default=None, description="Product name",  example="banana"),                        
    'label_id': fields.String(required=False, default=None, description="Product ID",  example="46"),                        
    'probability': fields.Float(required=False, default=None, description="Probability [0, 1] for the product in a given day of week (and hour when correspond).",   example="0.69"),                        
})

class ProductProbability_sch(object):
    host:str=None
    port:int=None
    topic:str=None
    dow:int=None
    hh24:int=None
    label_class:str=None    
    label_id:str=None
    probability:float=None

@api.route('/mqtt/probweek/',
           doc={"description":"It returns the Top Ten Product Probability for the indicated day in localhost:port/topic based on detected items."})
class Top10WeeklyProb(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(productProbability_sch, validate=True, description="It expects the localhost:port/topic and day of week (dow) to filter the product probabilities based on detection.")
    @api.marshal_list_with(productProbability_sch)
    def post(self):
        #To Do
        list=[]
        data = api.payload # 
        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                ret=ProductProbability_sch()     
                return ret, 500        
            
            with conn.cursor() as curs:
                query="""
                    Select label_class,label_id,probability
                    from MQTTLabelDayProb
                    where hostname=%s and port=%s and topic=%s and
                        dow=%s 
                    order by probability desc
                    limit 10;
                    """
                values=(data.get('host'),
                        data.get('port'),
                        data.get('topic'),
                        data.get('dow'))
                curs.execute(query, values)
                results = curs.fetchall()

                while results:
                    row = results.pop(0)
                    dataprob=ProductProbability_sch()
                    dataprob.host = data.get('host')
                    dataprob.port = data.get('port')
                    dataprob.topic = data.get('topic')
                    dataprob.dow = data.get('dow')
                    dataprob.hh24 = None
                    dataprob.label_class = str(row[0])
                    dataprob.label_id = str(row[1])
                    dataprob.probability = float(row[2])
                                        
                    list.append(dataprob)

        except Exception as e:
            errorMessage=f"Query Probabilities for host: ({data.get('host')}), port ({data.get('port')}), topic: ({data.get('topic')}), Day-of-Week: ({data.get('dow')}). Exception: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()
        
        if errorMessage is not None:
            ret=ProductProbability_sch()   
            return ret, 500
                        
        return list, 200

@api.route('/mqtt/probweekhh24/', 
           doc={"description":"It returns the Top Ten Product Probability for the indicated day and hour in localhost:port/topic based on detected items."})
class Top10WeeklyHHProb(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(productProbability_sch, validate=True, description="It expects the localhost:port/topic, day of week (dow) and hour (24-hours format) to filter the product probabilities based on detection.")
    @api.marshal_list_with(productProbability_sch)
    def post(self):
        #To Do
        list=[]
        data = api.payload # 
        conn = None

        if data.get('hh24') is None:
            message=f"Hour of the day (hh24) is required."
            logger.error(message)
            ret=ProductProbability_sch()     
            return ret, 404
        
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                ret=ProductProbability_sch()     
                return ret, 500
                        
            with conn.cursor() as curs:
                query="""
                    Select label_class,label_id,probability
                    from MQTTLabelDayhourProb
                    where hostname=%s and port=%s and topic=%s and
                        dow=%s and hh24=%s
                    order by probability desc
                    limit 10;
                    """
                values=(data.get('host'),
                        data.get('port'),
                        data.get('topic'),
                        data.get('dow'),
                        data.get('hh24') if data.get('hh24') is not None else -1)
                curs.execute(query, values)
                results = curs.fetchall()

                while results:
                    row = results.pop(0)
                    dataprob=ProductProbability_sch()
                    dataprob.host = data.get('host')
                    dataprob.port = data.get('port')
                    dataprob.topic = data.get('topic')
                    dataprob.dow = data.get('dow')
                    dataprob.hh24 = data.get('hh24')
                    dataprob.label_class = str(row[0])
                    dataprob.label_id = str(row[1])
                    dataprob.probability = float(row[2])
                                        
                    list.append(dataprob)

        except Exception as e:
            errorMessage=f"Query Probabilities for host: ({data.get('host')}), port ({data.get('port')}), topic: ({data.get('topic')}), Day-of-Week: ({data.get('dow')}), HH24: ({data.get('hh24')}). Exception: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            ret=ProductProbability_sch()   
            return ret, 500
                        
        return list, 200

@api.route('/mqtt/prob/',
           doc={"description":"It updates all probabilities based on the detected objects."})
class ProductWeeklyProb(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    def get(self):
        conn = None
        errorMessage=None
        week=None
        weekhh24=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                return message, 500        
            
            with conn.cursor() as curs:
                query="""
                    Select WEEKPROB_MATRIX(), WEEKHH24PROB_MATRIX()
                    """
                curs.execute(query)
                results = curs.fetchall()

                while results:
                    row = results.pop(0)           
                    week = bool(row[0])
                    weekhh24 = bool(row[1])                                        

        except Exception as e:
            errorMessage=f"WeeklyProb Processing. Exception: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:            
            return errorMessage, 500
        
        if week is None or weekhh24 is None or week is False or weekhh24 is False:
            message=f"WeeklyProb Processing. Week Prob: {week} Week-Hour Prob: {weekhh24}."
            return message, 500
                
        return 'Success', 200
