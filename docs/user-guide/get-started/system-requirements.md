# System Requirements

This page provides detailed hardware, software, and platform requirements to help you set up and run the Digital Signage application efficiently.

## Minimum Hardware Requirements

| Component     | Specification                                                 |
| ------------- | ------------------------------------------------------------- |
| **Processor** | Intel® Core™ Ultra (Series 2) or above with at least 16 cores |
| **RAM**       | 16 GB minimum (32 GB recommended)                             |
| **Storage**   | 500 GB free space                                             |
| **GPU**       | Intel® integrated GPU (iGPU)                                  |

> **Video ad generation (`trigger_video_ad`):** the LTX-Video model needs about 8 GB of GPU/shared memory with the default `f16` precision (about 11 GB with `f32`) in addition to the image model, so 32 GB RAM is recommended if you use it. See [Change Inference Device](../how-to-guides/change-inference-device.md#video-precision-and-preloading).

## Software Requirements

| Component          | Version / Details                                       |
| ------------------ | ------------------------------------------------------- |
| **OS**             | Ubuntu 24.04 LTS (Ubuntu 26.04 LTS also validated)      |
| **Docker Engine**  | 24.x or higher                                          |
| **Docker Compose** | v2                                                      |
| **Browser**        | Google Chrome (recommended)                             |
| **Network**        | Internet access for model downloads and container pulls |

## Validation

Ensure all requirements above are met before proceeding to [Get Started](../get-started.md).
