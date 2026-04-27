# syntax=docker/dockerfile:1.6
#
# Tender Intelligence — production container
#
# Runs the app/main.py pipeline once per invocation. Designed for Azure
# Container Apps Jobs (schedule-triggered, ephemeral). The image bundles
# Python 3.12, Google Chrome, and undetected-chromedriver dependencies.
#
# CRITICAL gotchas verified 2026-04-23 on Azure B2s North Europe:
#   1. setuptools must be installed — undetected-chromedriver 3.5.5
#      imports distutils.version.LooseVersion, which Python 3.12 removed.
#      Without setuptools the import fails before main.py runs.
#   2. Pass --disable-dev-shm-usage as a Chrome option in app/main.py
#      (already in code). The default /dev/shm in containers is 64 MB and
#      crashes Chrome under load.
#   3. Container needs ≥ 2 GB RAM. B1s (1 GB) causes Chromedriver OOM
#      timeouts in headless mode. Container Apps Job profile must be
#      ≥ 2 vCPU / 4 GB.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install Chrome + system deps in one layer.
# Chrome from Google's apt repo (stable channel).
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates fonts-liberation \
        libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
        libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libxcomposite1 \
        libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/tender

# setuptools FIRST — required shim for undetected-chromedriver on Python 3.12
RUN pip install --upgrade pip setuptools

COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code — copy late so dep changes don't bust the layer cache.
COPY app/ ./app/
COPY config/ ./config/

# Runtime data dirs (gitignored in source — created here at image build time
# so the container starts with the directory layout app/paths.py expects).
RUN mkdir -p /opt/tender/data /opt/tender/data/downloads /opt/tender/data/previews

# Default mode is the combined Hilma + tarjouspalvelu nightly run. Override
# at job level via the args / env override mechanism in Bicep.
CMD ["python", "-m", "app.main", "--mode=combined"]
