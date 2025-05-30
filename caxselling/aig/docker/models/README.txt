Put your models under this folder. It is mounted in the docker container at /opt/models.

All models under this folder should be OpenVino format.

For example, if you download the dreamlike anime model (Text-2-Image) in ./dreamlike_anime_1_0_ov/FP16, you can reference it from the container as "/opt/models/dreamlike_anime_1_0_ov/FP16"