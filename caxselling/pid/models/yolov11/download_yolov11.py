from ultralytics import YOLO
import openvino
import sys
import shutil
import os

model_name = 'yolo11s'
model_type = 'yolo_v11'
weights = model_name + '.pt'
model = YOLO(weights)
model.info()

converted_path = model.export(format='openvino')
converted_model = converted_path + '/' + model_name + '.xml'

core = openvino.Core()

ov_model = core.read_model(model=converted_model)
if model_type in ["YOLOv8-SEG", "yolo_v11_seg"]:
    ov_model.output(0).set_names({"boxes"})
    ov_model.output(1).set_names({"masks"})
ov_model.set_rt_info(model_type, ['model_info', 'model_type'])

openvino.save_model(ov_model, './FP32/' + model_name +
                    '.xml', compress_to_fp16=False)
openvino.save_model(ov_model, './FP16/' + model_name +
                    '.xml', compress_to_fp16=True)

shutil.rmtree(converted_path)
os.remove(f"{model_name}.pt")
