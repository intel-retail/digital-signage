# Build from Source

This guide provides step-by-step instructions for cloning the Digital Signage repository, downloading required AI models, and building container images from source.

> **Note:** Run all commands as a regular (non-root) user, without using `sudo`. Ensure [Docker is configured](../get-started.md#configure-docker) and you have internet access before proceeding.

## Step 1: Clone the Repository

```bash
git clone https://github.com/intel-retail/digital-signage -b release-2026.2.0
cd digital-signage
```

## Step 2: Build Docker Images

```bash
make build
```

Once the build completes, return to the Get Started guide and follow the remaining steps from [Step 3: Download AI Models](../get-started.md#step-3-download-ai-models) onwards.
