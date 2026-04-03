# ──────────────────────────────────────────────
# CompliAGL — Development Makefile
# ──────────────────────────────────────────────

.PHONY: help install-backend install-frontend install run-backend run-frontend run

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────

install-backend: ## Install backend dependencies
	cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

install: install-backend install-frontend ## Install all dependencies

# ── Run ──────────────────────────────────────

run-backend: ## Start backend on http://localhost:8000
	cd backend && . venv/bin/activate && uvicorn app.main:app --reload --port 8000

run-frontend: ## Start frontend on http://localhost:5173
	cd frontend && npm run dev

run: ## Start both backend and frontend (backend in background)
	@echo "Starting backend on http://localhost:8000 …"
	@$(MAKE) run-backend &
	@echo "Starting frontend on http://localhost:5173 …"
	@$(MAKE) run-frontend
