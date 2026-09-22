.PHONY: setup test eval run ingest docker clean

PY ?= python3
VENV ?= .venv

setup: ## Create venv and install dependencies
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

ingest: ## Build the policy index (runs automatically on first use; kept for parity)
	$(VENV)/bin/python -c "from src.runner import get_index; i=get_index(); print(f'indexed {len(i.chunks)} chunks from {len(i.list_documents())} policy docs')"

test: ## Run the pytest suite
	$(VENV)/bin/python -m pytest -q

eval: ## Run the sample-application evaluation
	$(VENV)/bin/python scripts/eval.py

run: ## Serve the API + UI
	$(VENV)/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

docker: ## Build and run the container
	docker build -t underwriting-copilot .
	docker run --rm -p 8000:8000 --env-file .env underwriting-copilot

clean: ## Remove caches
	rm -rf .pytest_cache eval/__pycache__
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
