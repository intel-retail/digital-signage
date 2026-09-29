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

Run `make download_models` to fetch the required model artifacts, then follow the remaining setup and deployment steps in the [Get Started guide](https://github.com/intel-retail/digital-signage/blob/main/docs/user-guide/get-started.md#step-3-download-ai-models).
