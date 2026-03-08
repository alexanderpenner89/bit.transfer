.PHONY: up down logs ghost-up ghost-down langfuse-up langfuse-down apply-theme restart-ghost author

# ── Start/Stop all ────────────────────────────────────────────────────────────

up:
	docker compose --profile ghost --profile langfuse up -d

down:
	docker compose --profile ghost --profile langfuse down

logs:
	docker compose logs -f $(s)

# ── Ghost ─────────────────────────────────────────────────────────────────────

ghost-up:
	docker compose --profile ghost up -d

ghost-down:
	docker compose --profile ghost down

apply-theme:
	@echo "→ Recreating Ghost container (new theme volume)..."
	docker compose --profile ghost up -d --force-recreate ghost
	@echo "✓ Theme mounted. Activate in Ghost Admin → Settings → Design → bit-transfer"

restart-ghost:
	docker compose restart ghost

author:
	python create-ai-author.py

# ── Langfuse ──────────────────────────────────────────────────────────────────

langfuse-up:
	docker compose --profile langfuse up -d

langfuse-down:
	docker compose --profile langfuse down
