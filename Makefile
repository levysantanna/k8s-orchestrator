# Makefile for K8s Orchestrator
# Copyright (C) 2026 K8s Orchestrator Contributors
# Licensed under GPL-3.0

.PHONY: help build run stop clean test lint

# Variables
IMAGE_NAME = k8s-orchestrator
IMAGE_TAG = latest
CONTAINER_NAME = k8s-orchestrator
PODMAN = $(shell command -v podman 2> /dev/null || echo docker)

help: ## Show this help message
	@echo "K8s Orchestrator - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Container runtime: $(PODMAN)"

build: ## Build container image with Podman/Docker
	$(PODMAN) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

build-no-cache: ## Build container image without cache
	$(PODMAN) build --no-cache -t $(IMAGE_NAME):$(IMAGE_TAG) .

run: ## Run container with Podman/Docker
	$(PODMAN) run -d \
		--name $(CONTAINER_NAME) \
		-p 5000:5000 \
		-e SECRET_KEY=change-me-in-production \
		-v k8s-orchestrator-data:/app/data \
		-v k8s-orchestrator-logs:/app/logs \
		$(IMAGE_NAME):$(IMAGE_TAG)

run-dev: ## Run container in development mode (interactive)
	$(PODMAN) run -it --rm \
		--name $(CONTAINER_NAME)-dev \
		-p 5000:5000 \
		-e FLASK_ENV=development \
		-v $(PWD):/app \
		-v k8s-orchestrator-data:/app/data \
		$(IMAGE_NAME):$(IMAGE_TAG)

compose-up: ## Start all services with docker-compose/podman-compose
	$(PODMAN)-compose up -d

compose-down: ## Stop all services
	$(PODMAN)-compose down

compose-logs: ## View logs from all services
	$(PODMAN)-compose logs -f

stop: ## Stop running container
	$(PODMAN) stop $(CONTAINER_NAME) || true
	$(PODMAN) rm $(CONTAINER_NAME) || true

clean: ## Remove container, image, and volumes
	$(PODMAN) stop $(CONTAINER_NAME) || true
	$(PODMAN) rm $(CONTAINER_NAME) || true
	$(PODMAN) rmi $(IMAGE_NAME):$(IMAGE_TAG) || true
	$(PODMAN) volume rm k8s-orchestrator-data k8s-orchestrator-logs || true

logs: ## Show container logs
	$(PODMAN) logs -f $(CONTAINER_NAME)

shell: ## Open shell in running container
	$(PODMAN) exec -it $(CONTAINER_NAME) /bin/bash

ps: ## Show running containers
	$(PODMAN) ps -a | grep $(IMAGE_NAME) || echo "No containers found"

init-db: ## Initialize database in container
	$(PODMAN) exec $(CONTAINER_NAME) python scripts/init-db.py

test: ## Run tests
	python -m pytest tests/ -v

lint: ## Run code linting
	python -m pylint app.py controllers/ services/ models/ functions/

format: ## Format code with black
	python -m black app.py controllers/ services/ models/ functions/

install: ## Install Python dependencies locally
	pip install -r requirements.txt

dev-run: ## Run application locally (without container)
	python app.py

push: ## Push image to registry (set REGISTRY variable)
	$(PODMAN) tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	$(PODMAN) push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

# Git shortcuts
git-status: ## Show git status
	git status

git-commit: ## Commit changes (use MSG="commit message")
	git add -A
	git commit -m "$(MSG)"

git-push: ## Push to GitHub
	git push origin main

# Quick deployment
deploy: build run ## Build and run container
	@echo "Orchestrator deployed! Access at http://localhost:5000"

redeploy: stop clean deploy ## Stop, clean, and redeploy

# Info
info: ## Show system information
	@echo "Container Runtime: $(PODMAN)"
	@echo "Image: $(IMAGE_NAME):$(IMAGE_TAG)"
	@echo "Container: $(CONTAINER_NAME)"
	@$(PODMAN) version

version: ## Show application version
	@echo "K8s Orchestrator v1.0.0"
	@echo "License: GPL-3.0"
