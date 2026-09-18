import io
import gc
import threading
#Flask API
from flask import send_file
from flask_restx import Namespace, Resource, fields
from PIL import Image
#Logging
import time
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = True

#AIGServer Environment
from database.version import AigServerMetadata
from server.apis.modelinf import (
    apply_ad_overlays,
    minf_request_sch_price,
    minf_request_sch_promo,
    minf_request_sch_logo,
    minf_request_scg_slogan,
    minf_request_sch_frame,
)

# Text2VideoPipeline.generate() is not thread-safe; serialize access across concurrent requests.
# Separate from modelinf's model_lock since the image and video models are distinct pipelines.
video_model_lock = threading.Lock()

api = Namespace('AIG - Video Inference', description='Advertise Video Generation')

minf_video_request_sch = api.model('ModelVideoInference_BasicRequest', {
    'description': fields.String(required=True, default=None, description="The text description to generate the video.", example="A 35mm photo with bananas, 8k"),
    'device': fields.String(required=True, default='CPU', description="The device for inferencing [CPU|GPU|NPU].", example="CPU", enum=['CPU', 'GPU', 'NPU']),
    'seed': fields.Integer(required=False, default=None, description="Optional RNG seed for reproducible generation.", example=12345),
    'price_details': fields.Nested(minf_request_sch_price, required=False, description="It contains the details of the price to be shown in each frame."),
    'promo_details': fields.Nested(minf_request_sch_promo, required=False, description="It contains the details of the promo to be shown in each frame."),
    'logo_details': fields.Nested(minf_request_sch_logo, required=False, description="It contains the details of the logo to be shown in each frame."),
    'slogan_details': fields.Nested(minf_request_scg_slogan, required=False, description="It contains the details of the slogan to be shown in each frame."),
    'framed_details': fields.Nested(minf_request_sch_frame, required=False, description="It contains the details of the frame to be shown in each frame.")
})


@api.route('/mvid/',
           doc={"description": "It returns an animated WEBP video based on a text description with the requested add-ons (when applicable).",
                "produces": ['image/webp']
                })
class ModelInference_Video(Resource):
    @api.response(200, 'Success')
    @api.response(500, 'Accepted but it could not be processed/recovered')
    @api.response(503, 'Accepted but server is busy with other requests')
    @api.expect(minf_video_request_sch, validate=True, description="It expects the text description to generate the video and optional add-ons.")
    def post(self):
        data = api.payload
        errorMessage = None

        if data.get('device') not in ['CPU', 'GPU', 'NPU']:
            errorMessage = "Device not supported. Only CPU, GPU and NPU are supported."
            logger.error(errorMessage)
            return errorMessage, 500

        try:
            model = AigServerMetadata.get_t2v_model_path()
            if not model:
                errorMessage = "Video Generation. AIG_VIDEO_MODEL_PATH is not configured."
                logger.error(errorMessage)
                return errorMessage, 500

            description = data.get('description')
            device = data.get('device', 'GPU')
            seed = data.get('seed', None)

            pipe = None
            if str(device).upper() == AigServerMetadata.get_t2v_model_device():
                pipe = AigServerMetadata().get_preloaded_video_model()

            if pipe is None:
                try:
                    pipe = AigServerMetadata.create_text2video_pipeline(model, device)
                except Exception as e:
                    logger.error(f"Video Generation. Failed to create pipeline for device {device}: {e}")
                    return f"Device {device} unavailable: {str(e)[:200]}", 500

            start_time = time.time()
            video_result = None
            max_retries = 3
            counter = 0
            while counter < max_retries:
                try:
                    generate_kwargs = {}
                    if seed is not None:
                        generate_kwargs['rng_seed'] = seed
                    with video_model_lock:
                        video_result = pipe.generate(
                            description,
                            negative_prompt=AigServerMetadata.get_video_negative_prompt(),
                            # LTX-Video enables TaylorSeer caching (approximates some transformer steps)
                            # by default, trading quality for speed; disabled here since it visibly
                            # blurs motion between frames.
                            taylorseer_config=None,
                            width=AigServerMetadata.get_video_width(),
                            height=AigServerMetadata.get_video_height(),
                            num_frames=AigServerMetadata.get_video_num_frames(),
                            num_inference_steps=AigServerMetadata.get_video_inference_steps(),
                            frame_rate=AigServerMetadata.get_video_frame_rate(),
                            guidance_scale=AigServerMetadata.get_video_guidance_scale(),
                            **generate_kwargs
                        )
                    if video_result is not None and video_result.video is not None:
                        counter = max_retries
                except Exception as e:
                    logger.error(f"Video Generation. Attempt {counter + 1} failed with error: {str(e)}")
                    video_result = None
                    counter += 1

            if video_result is None:
                errorMessage = "Video Generation. Service is busy."
                logger.error(errorMessage)
                return errorMessage, 503

            end_time = time.time()

            video_tensor = video_result.video.data  # shape: (batch, num_frames, height, width, channels)
            frames = []
            for frame_index in range(video_tensor.shape[1]):
                frame_img = Image.fromarray(video_tensor[0, frame_index])
                frames.append(apply_ad_overlays(frame_img, data))

            if not frames:
                errorMessage = "Video Generation. The generated video has no frames."
                logger.error(errorMessage)
                return errorMessage, 500

            frame_duration_ms = int((AigServerMetadata.get_video_loop_seconds() * 1000) / len(frames))
            video_io = io.BytesIO()
            frames[0].save(
                video_io, format='WEBP', save_all=True, append_images=frames[1:],
                duration=frame_duration_ms, loop=0, quality=90
            )
            video_io.seek(0)

            if not AigServerMetadata.should_keep_model_in_memory():
                if pipe == AigServerMetadata().get_preloaded_video_model():
                    AigServerMetadata().unload_video_model()
                    logger.info(f"Video Generation. Processed in {end_time - start_time}s, model unloaded")
                else:
                    del pipe
                    gc.collect()
                    logger.info(f"Video Generation. Processed in {end_time - start_time}s, temp model cleaned")
            else:
                logger.info(f"Video Generation. Processed in {end_time - start_time}s, model kept in memory")

            del video_result
            del video_tensor
            del frames
            gc.collect()

            return send_file(video_io, mimetype='image/webp')
        except Exception as e:
            errorMessage = f"Video Generation. Exception: {str(e)}"
            logger.error(errorMessage)
            if 'pipe' in locals() and pipe is not None:
                if not AigServerMetadata.should_keep_model_in_memory():
                    if pipe == AigServerMetadata().get_preloaded_video_model():
                        AigServerMetadata().unload_video_model()
                    else:
                        del pipe
                    gc.collect()

        if errorMessage is not None:
            return errorMessage, 500

        return "Nothing", 200
