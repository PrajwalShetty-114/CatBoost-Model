# --- STAGE 1: LFS Fetcher ---
# We use a base image with git installed to pull the LFS files
FROM alpine/git:latest AS lfs-fetcher

# Set these args so we can clone the correct repo
# REPLACE THIS with your actual CatBoost repo URL
ARG REPO_URL="https://github.com/PrajwalShetty-114/CatBoost-Model.git"
ARG BRANCH="master"

WORKDIR /repo

# Clone the repo and pull LFS files
RUN git clone --branch ${BRANCH} ${REPO_URL} .
RUN git lfs install
RUN git lfs pull

# --- STAGE 2: Application ---
# Use Python 3.11 slim image for the final app
FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies needed for CatBoost/numpy/pandas
# (libgomp1 is often required for CatBoost)
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy application code and LFS files from Stage 1
# Copy the .cbm model file
COPY --from=lfs-fetcher /repo/data/ /app/data/
# Copy the application code
COPY --from=lfs-fetcher /repo/app.py .

# 4. Run the application
# Render provides the PORT environment variable
CMD gunicorn -w 4 -b 0.0.0.0:$PORT app:app