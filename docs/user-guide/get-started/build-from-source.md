# Build from Source

This guide provides step-by-step instructions for cloning the Digital Signage repository, building container images from source, and downloading the required AI models with the shared model-download microservice.

> **Note:** Run all commands as a regular (non-root) user, without using `sudo`. Ensure [Docker is configured](../get-started.md#configure-docker) and you have internet access before proceeding.

## Step 1: Clone the Repository

```bash
git clone https://github.com/intel-retail/digital-signage -b main
cd digital-signage
```

## Step 2: Build Docker Images

```bash
make build
```

## Step 3: Download AI Models

```bash
make download_models
```

This command pulls the pinned published model-download microservice image, applies the startup configuration from `configs/model-download/startup-models.yaml`, and prepares the PID and AIG model directories expected by Docker Compose.

Continue with the remaining steps in the [Get Started guide](../get-started.md#step-4-configure-environment).
