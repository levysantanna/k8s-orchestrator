FROM python:3.11-slim

LABEL maintainer="Levy Santanna <https://github.com/levysantanna>"
LABEL description="Ingress Operator for k8s-orchestrator"
LABEL version="1.0.0"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy operator code
COPY operator.py .

# Run operator with kopf
CMD ["kopf", "run", "operator.py", "--verbose", "--all-namespaces"]
