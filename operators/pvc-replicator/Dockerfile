FROM python:3.11-slim

LABEL maintainer="Levy Santanna <https://github.com/levysantanna>"
LABEL description="PVC Replicator Operator for Kubernetes"
LABEL license="GPL-3.0"

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    rsync \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    kopf==1.37.0 \
    kubernetes==29.0.0 \
    pyyaml==6.0.1

# Copy operator code
COPY operator.py /app/

# Run as non-root
RUN groupadd -r operator && useradd -r -g operator operator
USER operator

# Run operator
CMD ["kopf", "run", "/app/operator.py", "--standalone"]
