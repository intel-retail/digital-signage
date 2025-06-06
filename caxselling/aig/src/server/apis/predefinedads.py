import io
import os
#Flask API
from flask import send_file, request
from flask_restx import Namespace, Resource, fields
# GenAI
import openvino_genai
from PIL import Image
#Logging
import math
import logging
logger = logging.getLogger(__name__)
#AseServer Environment
from database.version import AseServerMetadata
from imgproc.img_frame import ImgDecorator
import base64

api = Namespace('ASE - Advertise Searcher', description='It provides functionalities to define and search predefined ads.')

## Schemas
predef_ad_schema = api.model('PredefinedAd', {
    'id': fields.Integer(readOnly=False, description='The unique identifier of the ad. If not defined, the server proposes one ID in add operations.', example=1),
    'description': fields.String(required=True, description='The description of the ad. It is essential to determine when it is applicable.', example="It shows fruits such as oranges and bananas..."),
    'imgb64': fields.String(required=True, description='Base64-encoded image'), 
    'source': fields.String(required=False, description='Source of the ad', example="Marketing Department"),
})

predef_ad_query_schema = api.model('PredefinedAdQuery', {
    'query': fields.String(required=True, description='The query text to search for predefined ads', example="What is the ad most related to oranges?"),
    'n_results': fields.Integer(required=True, default=1, description='Number of results to return', example=1)
})

## Schemas
predef_request_sch_frame = api.model('Predef_BasicRequest_Frame', {
    'activate': fields.Boolean(required=True, default=False, description="It indicates whether the generated image will have a frame.", example="false"),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the frame and the picture limits", example="2.0")
})

class Predef_request_sch_frame(object):
    activate:bool=False
    marperc_from_border:float=2.0

predef_request_sch_price = api.model('Predef_BasicRequest_Price', {
    'price': fields.String(required=False, default="", description="Price text to be shown.", example="0.5 $/lb"),
    'align': fields.String(required=False, default="center", description="Price horizontal alignment (left, center, or right)", example="center", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="bottom", description="Price vertical alignment (top, middle, or bottom)", example="bottom", enum=["top", "middle", "bottom"]),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the price and the picture limits", example="2.0"),
    'font_size': fields.Integer(required=False, default=20, description="Font Size", example="20"),
    'line_width': fields.Integer(required=False, default=20, description="Max line width before wrapping the text", example="20"),
    'price_color': fields.String(required=False, default="white", description="Price font color (Named color from PIL -ImageColor-)", example="white"),
    'price_in_circle': fields.Boolean(required=False, default="true", description="It indicates whether the price is incorporated into a circle", example="false"),
    'price_circle_color': fields.String(required=False, default="black", description="Price Circle color (Named color from PIL -ImageColor-)", example="black")
})

predef_request_sch_promo = api.model('Predef_BasicRequest_Promo', {
    'promo_text': fields.String(required=False, default="", description="The promo text", example="Buy 1, Get 50%% in 2nd unit"),
    'text_color': fields.String(required=False, default="white", description="Promo text color (Named color from PIL -ImageColor-)", example="white"),
    'rect_color': fields.String(required=False, default="black", description="Rounded Rectangle color where the promo text is incorporated (Named color from PIL -ImageColor-)", example="black"),
    'rect_padding': fields.Integer(required=False, default="10", description="Padding around the text block", example="10"),    
    'rect_radius': fields.Integer(required=False, default="20", description="Corner radius for rounded rectangle", example="20"),     
    'align': fields.String(required=False, default="center", description="Rounded rectangle horizontal alignment (left, center, or right)", example="center", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="bottom", description="Rounded rectangle vertical alignment (top, middle, or bottom)", example="bottom", enum=["top", "middle", "bottom"]),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the rounded rectangle and the picture limits", example="2.0"),
    'font_size': fields.Integer(required=False, default=20, description="Font Size", example="20"),
    'line_width': fields.Integer(required=False, default=20, description="Max line width before wrapping the text", example="20")
})

predef_request_sch_logo = api.model('Predef_BasicRequest_Logo', {
    'align': fields.String(required=False, default="left", description="Logo horizontal alignment (left, center, or right)", example="left", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="top", description="Logo vertical alignment (top, middle, or bottom)", example="top", enum=["top", "middle", "bottom"]),
    'logo_percentage': fields.Float(required=False, default=25, description="Logo Scaling (%%) based on the generated image size ", example="25.0"),
    'margin_px': fields.Integer(required=False, default=10, description="The number of pixels between the logo and the figure borders", example="10")
})

predef_request_scg_slogan = api.model('Predef_BasicRequest_Slogan', {
    'slogan_text': fields.String(required=False, default="", description="The text of the slogan to be shown in the image.", example="The best price in town"),
    'text_color': fields.String(required=False, default="white", description="Slogan text color (Named color from PIL -ImageColor-)", example="white"),
    'align': fields.String(required=False, default="center", description="Slogan horizontal alignment (left, center, or right)", example="center", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="bottom", description="Slogan vertical alignment (top, middle, or bottom)", example="bottom", enum=["top", "middle", "bottom"]),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the slogan and the picture limits", example="2.0"),
    'font_size': fields.Integer(required=False, default=20, description="Font Size", example="20"),
    'line_width': fields.Integer(required=False, default=20, description="Max line width before wrapping the text", example="20")
})

predef_request_scg_frame = api.model('Predef_BasicRequest_Frame', {
    'framed': fields.Boolean(required=False, default="false", description="It indicates whether the figure needs to be framed.", example="false"),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the frame and the picture borders", example="2.0")
})


predef_request_sch = api.model('Predef_BasicRequest', {
    'query': fields.String(required=True, description='The query text to search for predefined ads', example="What is the ad most related to oranges?"),
    'n_results': fields.Integer(required=True, default=1, description='Number of results to return', example=1),
    'use_default_ad_onempty': fields.Boolean(required=True, default=True, description="It indicates whether the default ad should be returned when the query result is empty.", example="true"),
    'price_details': fields.Nested(predef_request_sch_price, required=False, description="It contains the details of the price to be shown in the image.", example={
        'price': "0.5 $/lb",
        'align': "center",
        'valign': "bottom",
        'marperc_from_border': 2.0,
        'font_size': 20,
        'line_width': 20,
        'price_color': "white",
        'price_in_circle': True,
        'price_circle_color': "black"
    }),
    'promo_details': fields.Nested(predef_request_sch_promo, required=False, description="It contains the details of the promo to be shown in the image.", example={
        'promo_text': "Buy 1, Get 50%% in 2nd unit",
        'text_color': "white",
        'rect_color': "black",
        'rect_padding': 10,
        'rect_radius': 20,
        'align': "center",
        'valign': "bottom",
        'marperc_from_border': 2.0,
        'font_size': 20,
        'line_width': 20
    }),
    'logo_details': fields.Nested(predef_request_sch_logo, required=False, description="It contains the details of the logo to be shown in the image.", example={
        'align': "left",
        'valign': "top",
        'logo_percentage': 25.0,
        'margin_px': 10
    }),
    'slogan_details': fields.Nested(predef_request_scg_slogan, required=False, description="It contains the details of the slogan to be shown in the image.", example={
        'slogan_text': "The best price in town",
        'text_color': "white",
        'align': "center",
        'valign': "bottom",
        'marperc_from_border': 2.0,
        'font_size': 20,
        'line_width': 20
    }),
    'framed_details': fields.Nested(predef_request_sch_frame, required=False, description="It contains the details of the frame to be shown in the image.", example={
        'activate': False,
        'marperc_from_border': 2.0
    })
})

## Classes
class Predef_ad_schema(object):
    id:int
    description:str
    imgb64:str
    source:str = None  # Optional field, can be None

class Predef_ad_query_schema(object):
    query:str
    n_results:int

class Predef_request_sch_price(object):
    price:str=""
    align:str="center"
    valign:str="bottom"
    marperc_from_border:float=2.0
    font_size:int=20
    line_width:int=20
    price_color:str="white"
    price_in_circle:bool=True
    price_circle_color:str="black"

class Predef_request_sch_promo(object):
    promo_text:str=""
    text_color:str="white"
    rect_color:str="black"
    rect_padding:int=10
    rect_radius:int=20
    align:str="center"
    valign:str="bottom"
    marperc_from_border:float=2.0
    font_size:int=20
    line_width:int=20

class Predef_request_sch_logo(object):
    align:str="left"
    valign:str="top"
    logo_percentage:float=25.0
    margin_px:int=10

class Predef_request_scg_slogan(object):
    slogan_text:str=""
    text_color:str="white"
    align:str="center"
    valign:str="bottom"
    marperc_from_border:float=2.0
    font_size:int=20
    line_width:int=20

class Predef_request_scg_frame(object):
    activate:bool=False
    marperc_from_border:float=2.0

class Predef_request_sch(object):
    query:str # The query text to search for predefined ads
    n_results:int=1 # Number of results to return
    use_default_ad_onempty:bool=True # It indicates whether the default ad should be returned when the query result is empty.
    price_details:Predef_request_sch_price=None
    promo_details:Predef_request_sch_promo=None
    slogan_details:Predef_request_scg_slogan=None
    frame_details:Predef_request_sch_frame=None


@api.route('/predef/',
           doc={'description':'Add or Update predefined ads. JPEG images are supported.'}
           )
class PredefAdResource(Resource):
    @api.response(200, 'Success')
    @api.response(400, 'Invalid Parameters or not found')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(predef_ad_schema, validate=True, description='Add/Update predefined ads or post new ones.')
    def post(self):
        data = api.payload
        server = AseServerMetadata()

        # process the image_file as needed
        image_id = data.get('id', None)
        if image_id is None:
            # If no ID is provided, generate a new one
            image_id = server.get_ase_img_id()

        image_description = data.get('description', None)
        img_b64 = data.get('imgb64',None)
        img_source = data.get('source', None)

        if not img_b64:
            return {"error": "imgb64 field is required"}, 400
        
        image=None
        try:
            img_bytes = base64.b64decode(img_b64)
            image = Image.open(io.BytesIO(img_bytes))
        except Exception as e:
            return {"error": f"Invalid base64 image: {e}"}, 400

        image_format = image.format  # This will be 'JPEG', 'PNG', etc.
        if image_format not in ['JPEG']:
            return {"error": "Unsupported image format. Only JPEG is allowed."}, 400
        

        try:
            if server.chromadb_exists(image_id):
                server.chromadb_update(image_id, image_description, image, img_source)
            else:
                server.chromadb_add(image_id,image_description, image, img_source)    
        except Exception as e:
            logger.error(f"Error while adding/updating predefined ad: {e}")
            return {"error": "Failed to add/update predefined ad"}, 500
        
        return {"message": "Success"}, 200

@api.route('/predef/<string:id>',
           doc={'description':'It gets or removes the predefined ad with the given ID.'}
           )
@api.param('id', 'The unique identifier of the predefined ad to be get or removed')
class PredefAdResourceDeleteGet(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'Not found')
    @api.response(500, 'Accepted but it could not be processed')    
    def delete(self,id):        
        try:
            server = AseServerMetadata()
            if not server.chromadb_exists(id):
                return {"error": "Predefined ad not found"}, 404
            server.chromadb_remove(id)

        except Exception as e:
            return {"error": f" {e}"}, 500
        
        return {"message": "Success"}, 200

    @api.response(200, 'Success')
    @api.response(404, 'Not found')
    @api.response(500, 'Accepted but it could not be recovered')    
    @api.marshal_with(predef_ad_schema, description='Predefined ad details (Base64-encoded image).')
    def get(self,id):                               
        server = AseServerMetadata()
        item = Predef_ad_schema()
        if not server.chromadb_exists(id):
            logger.error(f"[ASE-Chromadb] Predefined ad with ID {id} not found.")
            item.description = f"Predefined ad with ID {id} not found."
            return item, 404
        item = None
        try:        
            results=server.chromadb_get(id)
            if not results:
                item.description = f"Predefined ad with ID {id} not found."
                return item, 404
                
            if 'metadatas' not in results or 'ids' not in results :
                item.description=f"[ASE-Chromadb Result] 'metadatas' or 'ids' not found in results: {results}"
                logger.error(f"[ASE-Chromadb Result] 'metadatas' or 'ids' not found in results: {results}")
                return {"error": "Incomplete Response from the Vector DB"}, 500

            ids = results.get('ids',[])
            metadatas = results.get('metadatas',[])

            for query_index, (id_list, metadata_list) in enumerate (zip(ids, metadatas)):
                for doc_index, doc_id in enumerate(id_list):
                    id_int = None
                    try:
                        id_int = int(doc_id)
                    except Exception as e:
                        continue # when id is not int, discard from result and move to the next one
                    
                    logger.error("Step 7. ")
                    # Get the metadata for the document    
                    doc_metadata = metadata_list #metadata_list is the dictionary of metadata for the document
                    if doc_metadata is None:
                        logger.error(f"[ASE-Chromadb Result] Metadata for ID {id_int} is None.")
                        item.description = f"Metadata for ID {id_int} is None."
                        return item, 404
                    

                    description = doc_metadata.get('description',None)
                    img_path = doc_metadata.get('img_path',None)
                    source = doc_metadata.get('source', None)
                    # Get the image from the server

                    img = server.get_image_file_from_path(img_path)
                    img_b64 = None
                    if img is not None:
                        buffered = io.BytesIO()                        
                        img.save(buffered, format="JPEG")
                        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    # Check if all required fields are present
                    # and add to the records list
                    if img_b64 is not None and id_int is not None and description is not None:
                        item = Predef_ad_schema()
                        item.id = id_int
                        item.description = description
                        item.source = source if source else None
                        item.imgb64 = img_b64                        
                    else:
                        logger.error(f"[ASE-Chromadb Result] Incomplete Record. id: {id_int} description: {description} image_path: {img_path}")
                        item.description = f"Incomplete Record. id: {id_int} description: {description} image_path: {img_path}"
        except Exception as e:
            item = Predef_ad_schema()
            item.description=f"Error: {e}"
            return item, 500

        return item, 200


@api.route('/predef/query',
           doc={'description':'Query predefined ads. It returns the most similar predefined ads based on the query text.'}
           )
class PredefAdResourceQuery(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No content found for the query')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(predef_ad_query_schema, validate=True, description='Query the catalog and return the most similar .')
    @api.marshal_list_with(predef_ad_schema, description='List of predefined ads that match the query (Base64-encoded image).')
    def post(self):
        data = api.payload
        
        # process the image_file as needed
        query = data.get('query', None)
        n_results = data.get('n_results', 1)
        if not query:
            return {"error": "query field is required"}, 400

        records=[]                
        server = AseServerMetadata()
        try:
            results=server.chromadb_querytxt(query, n_results=n_results)
            if results is None or len(results) == 0:
                return {"error": "No results found"}, 404

            if 'metadatas' not in results or 'ids' not in results or 'distances' not in results:                    
                logger.error(f"[ASE-Chromadb Result] 'distances', 'metadatas' or 'ids' not found in results: {results}")
                return {"error": "Incomplete Response from the Vector DB"}, 500

            ids = results.get('ids',[])
            metadatas = results.get('metadatas',[])
            distances = results.get('distances',[])

            for query_index, (id_list, metadata_list, distance_list) in enumerate (zip(ids, metadatas,distances)):
                for doc_index, doc_id in enumerate(id_list):
                    doc_distance = distance_list[doc_index]                            

                    if doc_distance is not None and doc_distance <= AseServerMetadata.get_ase_distance_threshold():
                        id_int = None
                        try:
                            id_int = int(doc_id)
                        except Exception as e:
                            continue # when id is not int, discard from result and move to the next one

                        # Get the metadata for the document    
                        doc_metadata = metadata_list[doc_index]                    
                        description = doc_metadata.get('description',None)
                        img_path = doc_metadata.get('img_path',None)
                        img_source = doc_metadata.get('source', None)
                        # Get the image from the server
                        img = server.get_image_file_from_path(img_path)
                        img_b64 = None
                        if img is not None:
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG")
                            img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        # Check if all required fields are present
                        # and add to the records list
                        if img_b64 is not None and id_int is not None and description is not None:
                            item = Predef_ad_schema()
                            item.id = id_int
                            item.description = description
                            item.imgb64 = img_b64
                            item.source = img_source if img_source else None
                            records.append(item)
                        else:
                            logger.error(f"[ASE-Chromadb Result] Incomplete Record. id: {id_int} description: {description} image_path: {img_path}")

        except Exception as e:
            logger.error(f"Error while querying predefined ad: {e}")
            return {"error": "Failed to query predefined ad"}, 500
        
        return records, 200

@api.route('/predef/query/ad',
           doc={"description":"It looks for a similar ads based on text description and returns it (Base64-encoded) with the requested add-ons (when applicable) as a list."
                })
class Predefined_Adhocad_Img(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(predef_request_sch, validate=True, description="It expects the text description to generate the image and an optional offer to put over the message as a banner.")
    @api.marshal_list_with(predef_ad_schema, description='List of predefined ads with add-ons in the imgb64 field that match the query (Base64-encoded image).')
    def post(self):
        data = api.payload # 
        errorMessage=None
        
        predef_query= data.get('query', None)            
        if predef_query is None or len(predef_query) == 0:
            errorMessage="Empty query or not defined."
            logger.error(errorMessage)
            return errorMessage, 500
        predef_n_results = data.get('n_results', 1)
        try:
            predef_n_results = int(predef_n_results)
            if predef_n_results < 1:                
                predef_n_results = 1

        except Exception as e:
            errorMessage=f"Invalid n_results value: {predef_n_results}. It was setted in 1."
            predef_n_results = 1 # Default value
            logger.error(errorMessage)
        predef_use_default_ad_onempty = data.get('use_default_ad_onempty', True)
        if predef_use_default_ad_onempty is None:
            predef_use_default_ad_onempty = True
        
        server = None
        pipeline_imgs=[]
        pipeline_processed_imgs_b64=[]
        try:
            server = AseServerMetadata()
                        
            results=server.chromadb_querytxt(predef_query, n_results=predef_n_results)
            if results is None or len(results) == 0:
                if predef_use_default_ad_onempty:
                    pipeline_imgs.append(server.default_ad_image)
                else:
                    return [], 200
            else:
                if 'metadatas' not in results or 'ids' not in results or 'distances' not in results:                    
                    if predef_use_default_ad_onempty:
                        pipeline_imgs.append(server.default_ad_image)
                    else:
                        return [], 200
                else:
                    ids = results.get('ids',[])
                    metadatas = results.get('metadatas',[])
                    distances = results.get('distances',[])

                    for query_index, (id_list, metadata_list, distance_list) in enumerate (zip(ids, metadatas,distances)):
                        for doc_index, doc_id in enumerate(id_list):
                            doc_distance = distance_list[doc_index]

                            if doc_distance is not None and doc_distance <= AseServerMetadata.get_ase_distance_threshold():
                                # Get the metadata for the document    
                                doc_metadata = metadata_list[doc_index]                                                
                                img_path = doc_metadata.get('img_path',None)
                                # Get the image from the server
                                img = server.get_image_file_from_path(img_path)
                                pipeline_imgs.append(img)

            if len(pipeline_imgs) == 0:
                if predef_use_default_ad_onempty:
                    pipeline_imgs.append(server.default_ad_image)
                else:
                    return [], 200

            for image in pipeline_imgs:
                # Price details
                price_details = data.get('price_details')            
                img_postprice = None
                if price_details is not None:
                    price:str=price_details.get('price', "")
                    align:str=price_details.get('align',"center")
                    valign:str=price_details.get('valign',"bottom")
                    marperc_from_border:float=float(price_details.get('marperc_from_border',2.0))
                    font_size:int=int(price_details.get('font_size',20))
                    line_width:int=int(price_details.get('line_width',20))
                    price_color:str=price_details.get('price_color',"white")            
                    
                    if ImgDecorator.is_color_valid(price_color) is False:
                        price_color="white" # Default color if the provided one is not valid
                        
                    price_in_circle:bool=price_details.get('price_in_circle',False)
                    
                    price_circle_color:str=price_details.get('price_circle_color',"black")                
                    if ImgDecorator.is_color_valid(price_circle_color) is False:
                        price_circle_color="black"

                    if price_in_circle:
                        # Draw the price circle
                        img_postprice = ImgDecorator.draw_price_circle(image, 
                                price= price, price_color=price_color,
                                circle_color=price_circle_color,                             
                                align=align, valign=valign,                             
                                margin_percentage=marperc_from_border, 
                                font_size=font_size, line_width=line_width)
                    else:
                        img_postprice = ImgDecorator.draw_price_circle(image, 
                                    price= price, align=align, valign=valign, 
                                    margin_percentage=marperc_from_border, font_size=font_size,
                                    line_width=line_width, price_color=price_color)    
                else:
                    img_postprice = image

                # Promo details (Rounded Rectangle)
                promo_details = data.get('promo_details')
                img_postpromo = None
                if promo_details is not None:
                    promo_text:str=promo_details.get('promo_text', "")
                    text_color:str=promo_details.get('text_color',"white")
                    
                    if ImgDecorator.is_color_valid(text_color) is False:
                        text_color="white"

                    rect_color:str=promo_details.get('rect_color',"black")
                    if ImgDecorator.is_color_valid(rect_color) is False:
                        rect_color="black"

                    rect_padding:int=int(promo_details.get('rect_padding',10))
                    rect_radius:int=int(promo_details.get('rect_radius',20))
                    align:str=promo_details.get('align',"center")
                    valign:str=promo_details.get('valign',"bottom")
                    marperc_from_border:float=float(promo_details.get('marperc_from_border',2.0))
                    font_size:int=int(promo_details.get('font_size',20))
                    line_width:int=int(promo_details.get('line_width',20))

                    img_postpromo = ImgDecorator.draw_promo_rounded_rect(img_postprice, 
                                text=promo_text, text_color=text_color, rect_color=rect_color,
                                align=align, valign=valign,
                                margin_percentage=marperc_from_border, font_size=font_size, line_width=line_width,
                                rect_padding=rect_padding, rect_radius=rect_radius)
                else:
                    img_postpromo = img_postprice

                # Frame
                frame_details=data.get('framed_details')
                img_postframe = None
                if frame_details is not None:
                    framed:bool=bool(frame_details.get('activate',False))
                    marperc_from_border:float=float(frame_details.get('marperc_from_border',2.0))
                    
                    if framed:
                        img_postframe = ImgDecorator.draw_frame_double_border(img_postpromo,
                                                                            percentageFromBorder=marperc_from_border)
                    else:
                        img_postframe = img_postpromo
                else:
                    img_postframe = img_postpromo

                # Logo
                logo_details = data.get('logo_details')
                img_postlogo = None
                if logo_details is not None:
                    logo = server.get_logo()
                    if logo is not None:
                        align:str=logo_details.get('align',"left")
                        valign:str=logo_details.get('valign',"top")
                        logo_percentage:float=float(logo_details.get('logo_percentage',15.0))
                        margin_px:int=int(logo_details.get('margin_px',10))

                        img_postlogo = ImgDecorator.draw_logo(img_postframe, logo_img=logo,
                                    align=align, valign=valign, 
                                    logo_percentage=logo_percentage, margin_px=margin_px)
                    else:
                        img_postlogo = img_postframe
                else:
                    img_postlogo = img_postframe

                # Slogan
                slogan_details = data.get('slogan_details')
                img_postslogan = None
                if slogan_details is not None:
                    slogan_text:str=slogan_details.get('slogan_text', "")
                    text_color:str=slogan_details.get('text_color',"white")
                    if ImgDecorator.is_color_valid(text_color) is False:
                        text_color="white"

                    align:str=slogan_details.get('align',"center")
                    valign:str=slogan_details.get('valign',"bottom")
                    marperc_from_border:float=float(slogan_details.get('marperc_from_border',2.0))
                    font_size:int=int(slogan_details.get('font_size',20))
                    line_width:int=int(slogan_details.get('line_width',20))

                    img_postslogan = ImgDecorator.draw_slogan(img_postlogo, 
                                text=slogan_text, text_color=text_color,
                                align=align, valign=valign,
                                margin_percentage=marperc_from_border, font_size=font_size, line_width=line_width)
                else:
                    img_postslogan = img_postlogo

                # Save the updated image to a BytesIO object
                buffered = io.BytesIO()
                img_postslogan.save(buffered, format='JPEG')  # or 'PNG'
                im_b64= base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                if(im_b64 is not None):
                    item = Predef_ad_schema()
                    item.imgb64 = im_b64
                    pipeline_processed_imgs_b64.append(item)

        except Exception as e:
            errorMessage=f"Image Generation. Exception: {str(e)}"
            logger.error(errorMessage)
        
        if errorMessage is not None:           
            return errorMessage, 500
                        
        return pipeline_processed_imgs_b64, 200

@api.route('/predef/query/firstad',
           doc={"description":"It looks for a similar ads based on text description and returns one (Base64-encoded) with the requested add-ons (when applicable) as a JPEG.",
                "produces": ['image/jpeg']
                })
class Predefined_Adhocad_Img(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.expect(predef_request_sch, validate=True, description="It expects the text description to generate the image and an optional offer to put over the message as a banner.")
    def post(self):
        data = api.payload # 
        errorMessage=None
        
        predef_query= data.get('query', None)            
        if predef_query is None or len(predef_query) == 0:
            errorMessage="Empty query or not defined."
            logger.error(errorMessage)
            return errorMessage, 500
        predef_n_results = 1
        predef_use_default_ad_onempty = data.get('use_default_ad_onempty', True)
        if predef_use_default_ad_onempty is None:
            predef_use_default_ad_onempty = True
        
        server = None
        pipeline_imgs=[]
        try:
            server = AseServerMetadata()
                        
            results=server.chromadb_querytxt(predef_query, n_results=predef_n_results)
            if results is None or len(results) == 0:
                if predef_use_default_ad_onempty:
                    pipeline_imgs.append(server.default_ad_image)
                else:
                    return [], 200
            else:
                if 'metadatas' not in results or 'ids' not in results or 'distances' not in results:                    
                    if predef_use_default_ad_onempty:
                        pipeline_imgs.append(server.default_ad_image)
                    else:
                        return [], 200
                else:
                    ids = results.get('ids',[])
                    metadatas = results.get('metadatas',[])
                    distances = results.get('distances',[])                    

                    for query_index, (id_list, metadata_list, distance_list) in enumerate (zip(ids, metadatas,distances)):
                        for doc_index, doc_id in enumerate(id_list):
                            doc_distance = distance_list[doc_index]                            

                            if doc_distance is not None and doc_distance <= AseServerMetadata.get_ase_distance_threshold():
                                # Get the metadata for the document    
                                doc_metadata = metadata_list[doc_index]                    
                                img_path = doc_metadata.get('img_path',None)
                                # Get the image from the server
                                img = server.get_image_file_from_path(img_path)
                                pipeline_imgs.append(img)

            if len(pipeline_imgs) == 0:
                if predef_use_default_ad_onempty:
                    pipeline_imgs.append(server.default_ad_image)
                else:
                    return [], 200

            for image in pipeline_imgs:
                # Price details
                price_details = data.get('price_details')            
                img_postprice = None
                if price_details is not None:
                    price:str=price_details.get('price', "")
                    align:str=price_details.get('align',"center")
                    valign:str=price_details.get('valign',"bottom")
                    marperc_from_border:float=float(price_details.get('marperc_from_border',2.0))
                    font_size:int=int(price_details.get('font_size',20))
                    line_width:int=int(price_details.get('line_width',20))
                    price_color:str=price_details.get('price_color',"white")            
                    
                    if ImgDecorator.is_color_valid(price_color) is False:
                        price_color="white" # Default color if the provided one is not valid
                        
                    price_in_circle:bool=price_details.get('price_in_circle',False)
                    
                    price_circle_color:str=price_details.get('price_circle_color',"black")                
                    if ImgDecorator.is_color_valid(price_circle_color) is False:
                        price_circle_color="black"

                    if price_in_circle:
                        # Draw the price circle
                        img_postprice = ImgDecorator.draw_price_circle(image, 
                                price= price, price_color=price_color,
                                circle_color=price_circle_color,                             
                                align=align, valign=valign,                             
                                margin_percentage=marperc_from_border, 
                                font_size=font_size, line_width=line_width)
                    else:
                        img_postprice = ImgDecorator.draw_price_circle(image, 
                                    price= price, align=align, valign=valign, 
                                    margin_percentage=marperc_from_border, font_size=font_size,
                                    line_width=line_width, price_color=price_color)    
                else:
                    img_postprice = image

                # Promo details (Rounded Rectangle)
                promo_details = data.get('promo_details')
                img_postpromo = None
                if promo_details is not None:
                    promo_text:str=promo_details.get('promo_text', "")
                    text_color:str=promo_details.get('text_color',"white")
                    
                    if ImgDecorator.is_color_valid(text_color) is False:
                        text_color="white"

                    rect_color:str=promo_details.get('rect_color',"black")
                    if ImgDecorator.is_color_valid(rect_color) is False:
                        rect_color="black"

                    rect_padding:int=int(promo_details.get('rect_padding',10))
                    rect_radius:int=int(promo_details.get('rect_radius',20))
                    align:str=promo_details.get('align',"center")
                    valign:str=promo_details.get('valign',"bottom")
                    marperc_from_border:float=float(promo_details.get('marperc_from_border',2.0))
                    font_size:int=int(promo_details.get('font_size',20))
                    line_width:int=int(promo_details.get('line_width',20))

                    img_postpromo = ImgDecorator.draw_promo_rounded_rect(img_postprice, 
                                text=promo_text, text_color=text_color, rect_color=rect_color,
                                align=align, valign=valign,
                                margin_percentage=marperc_from_border, font_size=font_size, line_width=line_width,
                                rect_padding=rect_padding, rect_radius=rect_radius)
                else:
                    img_postpromo = img_postprice

                # Frame
                frame_details=data.get('framed_details')
                img_postframe = None
                if frame_details is not None:
                    framed:bool=bool(frame_details.get('activate',False))
                    marperc_from_border:float=float(frame_details.get('marperc_from_border',2.0))
                    
                    if framed:
                        img_postframe = ImgDecorator.draw_frame_double_border(img_postpromo,
                                                                            percentageFromBorder=marperc_from_border)
                    else:
                        img_postframe = img_postpromo
                else:
                    img_postframe = img_postpromo

                # Logo
                logo_details = data.get('logo_details')
                img_postlogo = None
                if logo_details is not None:
                    logo = server.get_logo()
                    if logo is not None:
                        align:str=logo_details.get('align',"left")
                        valign:str=logo_details.get('valign',"top")
                        logo_percentage:float=float(logo_details.get('logo_percentage',15.0))
                        margin_px:int=int(logo_details.get('margin_px',10))

                        img_postlogo = ImgDecorator.draw_logo(img_postframe, logo_img=logo,
                                    align=align, valign=valign, 
                                    logo_percentage=logo_percentage, margin_px=margin_px)
                    else:
                        img_postlogo = img_postframe
                else:
                    img_postlogo = img_postframe

                # Slogan
                slogan_details = data.get('slogan_details')
                img_postslogan = None
                if slogan_details is not None:
                    slogan_text:str=slogan_details.get('slogan_text', "")
                    text_color:str=slogan_details.get('text_color',"white")
                    if ImgDecorator.is_color_valid(text_color) is False:
                        text_color="white"

                    align:str=slogan_details.get('align',"center")
                    valign:str=slogan_details.get('valign',"bottom")
                    marperc_from_border:float=float(slogan_details.get('marperc_from_border',2.0))
                    font_size:int=int(slogan_details.get('font_size',20))
                    line_width:int=int(slogan_details.get('line_width',20))

                    img_postslogan = ImgDecorator.draw_slogan(img_postlogo, 
                                text=slogan_text, text_color=text_color,
                                align=align, valign=valign,
                                margin_percentage=marperc_from_border, font_size=font_size, line_width=line_width)
                else:
                    img_postslogan = img_postlogo

                # Save the updated image to a BytesIO object
                img_io = io.BytesIO()
                img_postslogan.save(img_io, format='JPEG')  # or 'PNG'                
                img_io.seek(0)  # Move to the beginning of the BytesIO object
                
                return send_file(img_io, mimetype='image/jpeg', download_name='ad_image.jpg')

        except Exception as e:
            errorMessage=f"Image Generation. Exception: {str(e)}"
            logger.error(errorMessage)
        
        if errorMessage is not None:           
            return errorMessage, 500
                        
        return None, 200
