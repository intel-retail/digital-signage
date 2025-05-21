import os
#Flask API
from flask_restx import Namespace, Resource, fields
#PostgresSQL & MQTT
from database.db_manager import DatabaseConnection
from database.mqtt_manager import MqttManager
#Logging
import logging
logger = logging.getLogger(__name__)

api = Namespace('PCA - MQTT', description='Listener definition related operations')

## Schemas
    ##Status
mqtttopic_sch = api.model('mqttdefinitions', {
    'host': fields.String(required=True, default=None, description="The MQTT Broker Host.",example="http://192.168.1.2"),
    'port': fields.Integer(required=True, default=1883, description="The port number in the MQTT Broker Host.", example="1883"),
    'topic': fields.String(required=True, default=None, description="Topic to listen in the MQTT Broker.", example="mytopic"),                         
    'status': fields.String(required=False, default=None, description="Last Known Status for the Topic in the MQTT Broker.", example="[YYYY-MM-DD HH:MM:SS] - Active {#Elements/min}"),                        
})

class Mqtttopic_sch(object):
    host:str=None
    port:int=None
    topic:str=None
    status:str=None

@api.route('/mqtt/',
           doc={"description": "Manage topics to listen given a MQTT broker."})
class Mqtttopic(Resource):
    @api.response(200, 'Success')
    @api.response(202, 'Accepted request but existent')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(mqtttopic_sch, validate=True, description="Host:port and topic to listen in the MQTT Broker.")
    @api.marshal_with(mqtttopic_sch)
    def post(self):
        data = api.payload
        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:                
                message=f"PG Connection Error"
                logger.error(message)
                ret=Mqtttopic_sch()
                ret.status=message                
                return ret, 500
                        
            with conn.cursor() as curs:
                phost=data["host"]
                pport=data["port"]
                ptopic=data["topic"]

                curs.execute(f"SELECT hostname, port, topic from mqtt_topics where hostname like '{phost}' and port={pport} and topic like '{ptopic}' limit 1;")
                results = curs.fetchall()
                
                if len(results)>0:
                    conn.close()
                    message=f"Topic {ptopic} already defined for the MQTT Broker: {phost}:{pport}"
                    logger.info(message)
                    ret=Mqtttopic_sch()
                    ret.status=message                    
                    return ret, 202
                
                curs.execute(f"INSERT INTO mqtt_topics(hostname, port, topic, message) VALUES('{phost}','{pport}','{ptopic}','');")

                # Incorporating the MQTT Client
                mqtt_manager = MqttManager()
                if mqtt_manager.add_client(phost, pport, ptopic):
                    conn.commit() # Confirm the deletion
                else:
                    conn.rollback() # Rollback
                    ret=Mqtttopic_sch()
                    ret.status=f"[MQTT Add] Topic {ptopic} in the MQTT Broker: {phost}:{pport}. It was not possible to add the MQTT Client."      
                    logger.error(ret.status)
                    return ret, 500
                
        except Exception as e:
            logger.error(f"Putting topic {data} for the MQTT Broker")            
            errorMessage=f"PG Exception: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            ret=Mqtttopic_sch()   
            ret.status=errorMessage
            return ret, 500
                
        return data, 200
    
    @api.doc('It removes the mentioned topic for the host:port MQTT Broker. PCA will not listen to it anymore')
    @api.response(200, 'Success')
    @api.response(404, 'No Topics for the mentioned MQTT broker:port and topic')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(mqtttopic_sch, validate=True, description="Host:port and topic to delete from the listening list in the MQTT Broker.")
    @api.marshal_with(mqtttopic_sch)
    def delete(self):
        data = api.payload

        conn = None
        errorMessage=None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                ret=Mqtttopic_sch()
                ret.status=message
                return ret, 500
            
            with conn.cursor() as curs:
                phost=data["host"]
                pport=data["port"]
                ptopic=data["topic"]

                curs.execute(f"SELECT hostname, port, topic from mqtt_topics where hostname like '{phost}' and port={pport} and topic like '{ptopic}' limit 1;")
                results = curs.fetchall()
                
                if len(results)==0:
                    conn.close()
                    message=f"Topic {ptopic} does not exist in the MQTT Broker: {phost}:{pport}"
                    ret=Mqtttopic_sch()
                    ret.status=message
                    return ret, 404
                
                curs.execute(f"DELETE FROM mqtt_topics where hostname like '{phost}' and port={pport} and topic like '{ptopic}';")                

                # Removing the MQTT Client
                mqtt_manager = MqttManager()
                if mqtt_manager.remove_client(phost, pport, ptopic):
                    conn.commit() # Confirm the deletion
                else:
                    conn.rollback() # Rollback
                    ret=Mqtttopic_sch()
                    ret.status=f"[MQTT Delete] Topic {ptopic} in the MQTT Broker: {phost}:{pport}. It was not possible to remove the MQTT Client."      
                    logger.error(ret.status)
                    return ret, 500

        except Exception as e:
            logger.error(f"Deleting topic {data} for the MQTT Broker")
            errorMessage=f"PG Exception: {str(e)}"
            logger.error(errorMessage) 
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            ret=Mqtttopic_sch()   
            ret.status=errorMessage
            return ret, 500
                
        return data, 200
    
    @api.doc('Update and Regenerate the In-memory MQTT client (Hard restart). Database is not affected.') 
    @api.response(200, 'Success')
    @api.response(404, 'Inexistent MQTT client for the mentioned MQTT broker:port and topic')
    @api.response(500, 'Accepted but it could not be processed/stored')
    @api.expect(mqtttopic_sch, validate=True, description="Host:port and topic to update and regenerate the In-memory MQTT client (hard restart) from the listening list in the MQTT Broker.")
    @api.marshal_with(mqtttopic_sch)
    def put(self):
        data = api.payload 
        conn = None
        errorMessage = None
        try:
            phost=data["host"]
            pport=data["port"]
            ptopic=data["topic"]

            mqtt_manager = MqttManager()
            if not mqtt_manager.exist_client(phost, pport, ptopic):
                message=f"MQTT Client {phost}:{pport} - {ptopic} does not exist"
                ret=Mqtttopic_sch()
                ret.status=message
                logger.error(ret.status)
                return ret, 404
            
            if mqtt_manager.regenerate_client(phost, pport, ptopic):
                message=f"MQTT Client {phost}:{pport} - {ptopic} was regenerated"
                ret=Mqtttopic_sch()
                ret.status=message
                return ret, 200
            else:
                message=f"MQTT Client {phost}:{pport} - {ptopic} was not regenerated"   
                ret=Mqtttopic_sch()
                ret.status=message
                logger.error(ret.status)
                return ret, 500
                
        except Exception as e:
            errorMessage=f"MQTT Client {phost}:{pport} - {ptopic} was not regenerated. Error: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            ret=Mqtttopic_sch()   
            ret.status=errorMessage
            return ret, 500
                            
        return data, 200

    
@api.route('/mqtt/<string:host>', 
           doc={"description": "It returns the list of all topics to listen for the mentioned MQTT broker (Host). Hard limit to 50 topics."})
@api.param('host','MQTT Broker Host to filter the topics')
class MqtttopicQuery(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No Topics for the mentioned MQTT broker')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.marshal_list_with(mqtttopic_sch)
    def get(self,host):
        #To Do
        list=[]
        conn = None
        errorMessage = None
        try:
            conn = DatabaseConnection.connect()            
            if conn is None:
                message=f"PG Connection Error"
                logger.error(message)
                ret=Mqtttopic_sch()
                ret.status=message                
                return ret, 500
            
            mqttmanager=MqttManager()
            
            with conn.cursor() as curs:
                curs.execute(f"SELECT hostname, port, topic from mqtt_topics where hostname like '{host}' order by hostname, port, topic limit 50;")
                results = curs.fetchall()

                while results:
                    row = results.pop(0)
                    data=Mqtttopic_sch()
                    data.host=str(row[0])
                    data.port=int(row[1])
                    data.topic=str(row[2])

                    if mqttmanager.exist_client(data.host, data.port, data.topic):
                        #Get the status from the MQTT Client
                        client= mqttmanager.get_client(data.host, data.port, data.topic)
                        data.status=client.get_status()
                    else:
                        data.status=f"MQTT Client not found ({data.host}:{data.port} - {data.topic})"
                    
                    
                    list.append(data)

        except Exception as e:
            logger.error(f"Query topics based on the host ({host}) for the MQTT Broker")            
            errorMessage=f"PG Exception: {str(e)}"
            logger.error(errorMessage)
        finally:
            if conn is not None:
                conn.close()

        if errorMessage is not None:
            ret=Mqtttopic_sch()
            ret.status=errorMessage            
            return ret, 500

        if len(list)==0:
            ret=Mqtttopic_sch()
            ret.status=f"No topics for the mentioned MQTT broker: {host}"
            return ret, 404
                
        return list, 200
