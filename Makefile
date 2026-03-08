.PHONY: up down logs apply-theme restart-ghost restart-backend author

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f $(s)

apply-theme:
	@echo "→ Recreating Ghost container (new theme volume)..."
	docker compose up -d --force-recreate ghost
	@echo "✓ Theme mounted. Activate in Ghost Admin → Settings → Design → bit-transfer"

restart-ghost:
	docker compose restart ghost

author:
	python create-ai-author.py
