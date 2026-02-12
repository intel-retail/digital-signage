import io
import os
import gc
#Flask API
from flask import send_file
from flask_restx import Namespace, Resource, fields
# GenAI
import openvino_genai
from PIL import Image
#Logging
import time
import logging
import sys

# Configure logger to output to stdout (visible in container logs)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = True

#AIGServer Environment
from database.version import AigServerMetadata
from imgproc.img_frame import ImgDecorator


api = Namespace('AIG - Inference with Added-Value Services', description='Advertise Image Generation')

## Schemas
minf_request_sch_frame = api.model('ModelInference_BasicRequest_Frame', {
    'activate': fields.Boolean(required=True, default=False, description="It indicates whether the generated image will have a frame.", example="false"),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the frame and the picture limits", example="2.0")
})

class Minf_request_sch_frame(object):
    activate:bool=False
    marperc_from_border:float=2.0

minf_request_sch_price = api.model('ModelInference_BasicRequest_Price', {
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

minf_request_sch_promo = api.model('ModelInference_BasicRequest_Promo', {
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

minf_request_sch_logo = api.model('ModelInference_BasicRequest_Logo', {
    'align': fields.String(required=False, default="left", description="Logo horizontal alignment (left, center, or right)", example="left", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="top", description="Logo vertical alignment (top, middle, or bottom)", example="top", enum=["top", "middle", "bottom"]),
    'logo_percentage': fields.Float(required=False, default=25, description="Logo Scaling (%%) based on the generated image size ", example="25.0"),
    'margin_px': fields.Integer(required=False, default=10, description="The number of pixels between the logo and the figure borders", example="10")
})

minf_request_scg_slogan = api.model('ModelInference_BasicRequest_Slogan', {
    'slogan_text': fields.String(required=False, default="", description="The text of the slogan to be shown in the image.", example="The best price in town"),
    'text_color': fields.String(required=False, default="white", description="Slogan text color (Named color from PIL -ImageColor-)", example="white"),
    'align': fields.String(required=False, default="center", description="Slogan horizontal alignment (left, center, or right)", example="center", enum=["left", "center", "right"]),
    'valign': fields.String(required=False, default="bottom", description="Slogan vertical alignment (top, middle, or bottom)", example="bottom", enum=["top", "middle", "bottom"]),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the slogan and the picture limits", example="2.0"),
    'font_size': fields.Integer(required=False, default=20, description="Font Size", example="20"),
    'line_width': fields.Integer(required=False, default=20, description="Max line width before wrapping the text", example="20")
})

minf_request_scg_frame = api.model('ModelInference_BasicRequest_Frame', {
    'framed': fields.Boolean(required=False, default="false", description="It indicates whether the figure needs to be framed.", example="false"),
    'marperc_from_border': fields.Float(required=False, default=2, description="Percentage of separation between the frame and the picture borders", example="2.0")
})

minf_request_sch = api.model('ModelInference_BasicRequest', {
    'description': fields.String(required=True, default=None, description="The text description to generate the image.", example="A 35mm photo with bananas, 8k"),
    'device': fields.String(required=True, default='CPU', description="The device for inferencing [CPU|GPU|NPU].", example="CPU", enum=['CPU', 'GPU', 'NPU']),
    'price_details': fields.Nested(minf_request_sch_price, required=False, description="It contains the details of the price to be shown in the image.", example={
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
    'promo_details': fields.Nested(minf_request_sch_promo, required=False, description="It contains the details of the promo to be shown in the image.", example={
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
    'logo_details': fields.Nested(minf_request_sch_logo, required=False, description="It contains the details of the logo to be shown in the image.", example={
        'align': "left",
        'valign': "top",
        'logo_percentage': 25.0,
        'margin_px': 10
    }),
    'slogan_details': fields.Nested(minf_request_scg_slogan, required=False, description="It contains the details of the slogan to be shown in the image.", example={
        'slogan_text': "The best price in town",
        'text_color': "white",
        'align': "center",
        'valign': "bottom",
        'marperc_from_border': 2.0,
        'font_size': 20,
        'line_width': 20
    }),
    'framed_details': fields.Nested(minf_request_sch_frame, required=False, description="It contains the details of the frame to be shown in the image.", example={
        'activate': False,
        'marperc_from_border': 2.0
    })
})

class Minf_request_sch_price(object):
    price:str=""
    align:str="center"
    valign:str="bottom"
    marperc_from_border:float=2.0
    font_size:int=20
    line_width:int=20
    price_color:str="white"
    price_in_circle:bool=True
    price_circle_color:str="black"

class Minf_request_sch_promo(object):
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

class Minf_request_sch_logo(object):
    align:str="left"
    valign:str="top"
    logo_percentage:float=25.0
    margin_px:int=10

class Minf_request_scg_slogan(object):
    slogan_text:str=""
    text_color:str="white"
    align:str="center"
    valign:str="bottom"
    marperc_from_border:float=2.0
    font_size:int=20
    line_width:int=20

class Minf_request_scg_frame(object):
    activate:bool=False
    marperc_from_border:float=2.0

class Minf_request_sch(object):
    description:str=None # Text description to generate the image
    device:str='GPU'
    price_details:Minf_request_sch_price=None
    promo_details:Minf_request_sch_promo=None
    slogan_details:Minf_request_scg_slogan=None
    frame_details:Minf_request_sch_frame=None
    
@api.route('/minf/',
           doc={"description":"It returns an image based on a text description with the requested add-ons (when applicable).",
                "produces": ['image/jpeg']
                })
class ModelInference_Img(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')    
    @api.response(503, 'Accepted but server is busy with other requests')    
    @api.expect(minf_request_sch, validate=True, description="It expects the text description to generate the image and an optional offer to put over the message as a banner.")
    def post(self):
        list=[]
        data = api.payload # 
        errorMessage=None

        if data.get('device') not in ['CPU', 'GPU', 'NPU']:
            errorMessage="Device not supported. Only CPU, GPU and NPU are supported."
            logger.error(errorMessage)
            return errorMessage, 500
        
        try:
            start_time = time.time()
            # Model
            model = AigServerMetadata.get_t2i_model_path() # Model Path only
            description = data.get('description')
            device = data.get('device', 'GPU')

            pipe = None
            if str(device).upper() == AigServerMetadata.get_t2i_model_device():
                # Use the preloaded model if the device matches
                pipe = AigServerMetadata().get_preloaded_model()

            if pipe is None:
                pipe = openvino_genai.Text2ImagePipeline(model, device)
                       
            image_tensor = None
            max_retries = 3
            counter = 0
            while counter < max_retries:
                try:
                    # guidance_scale=0.0 intentionally disables classifier-free guidance for this turbo/OpenVINO-optimized model
                    image_tensor = pipe.generate(description, width=AigServerMetadata.get_img_width(), height=AigServerMetadata.get_img_height(), 
                                                    num_inference_steps=AigServerMetadata.get_model_inference_steps(), guidance_scale=0.0, num_images_per_prompt=1)
                    if image_tensor is not None and len(image_tensor.data) > 0:
                        counter = max_retries  # Exit loop if image generation is successful
                except Exception as e:
                    image_tensor = None
                    counter += 1

            if image_tensor is None:
                errorMessage=f"Image Generation. Service is busy."
                logger.error(errorMessage)
                return errorMessage, 503

            image = Image.fromarray(image_tensor.data[0])

            if image is None or not isinstance(image, Image.Image):
                errorMessage=f"Image Generation. The generated image is not valid."
                logger.error(errorMessage)
                return errorMessage, 500

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
                aig_server=AigServerMetadata()
                logo = aig_server.get_logo()
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
            img_io.seek(0)              
            end_time = time.time()
            
            # Clean up memory - unload model if configured to do so
            if not AigServerMetadata.should_keep_model_in_memory():
                if pipe == AigServerMetadata().get_preloaded_model():
                    # Only unload if using the singleton model
                    AigServerMetadata().unload_model()
                    logger.info(f"Image Generation. Processed in {end_time - start_time}s, model unloaded")
                else:
                    # Clean up temporary model instance
                    del pipe
                    gc.collect()
                    logger.info(f"Image Generation. Processed in {end_time - start_time}s, temp model cleaned")
            else:
                logger.info(f"Image Generation. Processed in {end_time - start_time}s, model kept in memory")
            
            # Clean up intermediate objects
            del image_tensor
            del image
            del img_postprice
            del img_postpromo
            del img_postframe
            del img_postlogo
            del img_postslogan
            gc.collect()
            
            #Do not incorporate ,200 at the end because it is understod as a JSON by default (and not an image stream)
            return send_file(img_io, mimetype='image/jpeg')
        except Exception as e:
            errorMessage=f"Image Generation. Exception: {str(e)}"
            logger.error(errorMessage)
            # Clean up on error
            if 'pipe' in locals() and pipe is not None:
                if not AigServerMetadata.should_keep_model_in_memory():
                    if pipe == AigServerMetadata().get_preloaded_model():
                        AigServerMetadata().unload_model()
                    else:
                        del pipe
                    gc.collect()
        
        if errorMessage is not None:           
            return errorMessage, 500
                        
        return "Nothing", 200
