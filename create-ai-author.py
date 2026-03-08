#!/usr/bin/env python3
"""Create the 'Meridian' KI author directly in Ghost's MySQL database.

Bypasses the email invite flow entirely — works without a mail server.
Requires Docker to be running with the Ghost + MySQL containers up.

Usage (from project root):
    python create-ai-author.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Author identity ───────────────────────────────────────────────────────────

AI_NAME     = "Meridian"
AI_SLUG     = "meridian"
AI_EMAIL    = "meridian@bit-transfer.local"
AI_BIO      = (
    "KI-gestützter Wissenschaftsredakteur. "
    "Analysiert aktuelle Forschungspublikationen und überträgt sie "
    "in praxisnahe Erkenntnisse für das Handwerk."
)
AI_PASSWORD = "Meridian_BitTransfer_2026!"   # stored in DB; never used for login

# ── Load .env ─────────────────────────────────────────────────────────────────

def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


env_path = Path(__file__).parent / ".env"
env = load_env(env_path)

API_KEY   = env.get("GHOST_ADMIN_API_KEY", "")
GHOST_URL = env.get("GHOST_URL", "http://localhost:2368").rstrip("/")
DB_PASS   = env.get("MYSQL_ROOT_PASSWORD", "ghostpass")

if not API_KEY:
    sys.exit("✗  GHOST_ADMIN_API_KEY not set in .env")
if ":" not in API_KEY:
    sys.exit("✗  GHOST_ADMIN_API_KEY must be in format <id>:<hex-secret>")

key_id, secret_hex = API_KEY.split(":", 1)

# ── Ghost JWT (stdlib only) ───────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def make_token(ttl: int = 300) -> str:
    now = int(time.time())
    hdr = _b64url(json.dumps({"alg": "HS256", "kid": key_id, "typ": "JWT"}).encode())
    pay = _b64url(json.dumps({"iat": now, "exp": now + ttl, "aud": "/admin/"}).encode())
    sig = hmac.new(bytes.fromhex(secret_hex), f"{hdr}.{pay}".encode(), hashlib.sha256).digest()
    return f"{hdr}.{pay}.{_b64url(sig)}"

def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Ghost {make_token()}", "Accept": "application/json"}

# ── Ghost Admin API ───────────────────────────────────────────────────────────

def api_get(path: str, params: dict | None = None) -> dict:
    url = f"{GHOST_URL}/ghost/api/admin{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers=auth_headers())
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def api_put(path: str, body: dict) -> dict:
    url  = f"{GHOST_URL}/ghost/api/admin{path}"
    hdrs = {**auth_headers(), "Content-Type": "application/json"}
    req  = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdrs, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"PUT {path} → HTTP {e.code}: {e.read().decode(errors='replace')}") from e

# ── Docker helpers ────────────────────────────────────────────────────────────

def docker_containers() -> list[str]:
    """Return names of all running containers."""
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=10,
    )
    return out.stdout.strip().splitlines()


def find_container(keyword: str) -> str | None:
    """Find a running container whose name contains *keyword*."""
    for name in docker_containers():
        if keyword in name:
            return name
    return None


def docker_exec(container: str, *cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", container, *cmd],
        capture_output=True, text=True, timeout=30,
    )


def mysql(container: str, sql: str) -> str:
    """Run a SQL statement in the Ghost MySQL container."""
    result = docker_exec(
        container,
        "mysql", "-u", "root", f"-p{DB_PASS}", "ghost",
        "--batch", "--silent", "--skip-column-names",
        "-e", sql,
    )
    if result.returncode != 0:
        err = result.stderr.strip()
        # Ignore password-on-CLI warning
        if "Using a password on the command line" not in err and err:
            raise RuntimeError(f"MySQL error: {err}")
    return result.stdout.strip()


def bcrypt_hash(ghost_container: str, password: str) -> str:
    """Generate a bcrypt hash via Node.js inside the Ghost container.

    bcryptjs lives in Ghost's own node_modules, not in the system PATH.
    We locate it first, then require() it from there.
    """
    script = (
        "const b=require('bcryptjs');"
        f"b.hash({json.dumps(password)},10)"
        ".then(h=>process.stdout.write(h))"
        ".catch(e=>{process.stderr.write(e.message);process.exit(1)});"
    )

    # Try candidate directories where Ghost's node_modules might live
    candidates = [
        "/var/lib/ghost/current",
        "/var/lib/ghost",
        "/home/node/app",
    ]

    for cwd in candidates:
        sh_cmd = f"cd {cwd} && node -e {json.dumps(script)}"
        result = docker_exec(ghost_container, "sh", "-c", sh_cmd)
        if result.returncode == 0 and result.stdout.startswith("$2"):
            return result.stdout.strip()

    # Last resort: locate bcryptjs directory and require() by absolute path
    find = docker_exec(ghost_container, "find", "/var/lib/ghost", "-name", "bcryptjs",
                       "-type", "d", "-maxdepth", "6")
    bcrypt_dir = next(
        (ln.strip() for ln in find.stdout.splitlines() if "node_modules/bcryptjs" in ln),
        None,
    )
    if bcrypt_dir:
        script_abs = (
            f"const b=require({json.dumps(bcrypt_dir)});"
            f"b.hash({json.dumps(password)},10)"
            ".then(h=>process.stdout.write(h))"
            ".catch(e=>{process.stderr.write(e.message);process.exit(1)});"
        )
        result = docker_exec(ghost_container, "node", "-e", script_abs)
        if result.returncode == 0 and result.stdout.startswith("$2"):
            return result.stdout.strip()

    raise RuntimeError(
        "Could not generate bcrypt hash in Ghost container.\n"
        f"  Last stderr: {result.stderr.strip()}\n"
        f"  Last stdout: {result.stdout.strip()}"
    )


def ghost_object_id() -> str:
    """Generate a 24-char hex Ghost ObjectID."""
    return secrets.token_hex(12)

# ── .env persistence ──────────────────────────────────────────────────────────

def save_user_id(user_id: str) -> None:
    if not env_path.exists():
        env_path.write_text(f"GHOST_AI_AUTHOR_ID={user_id}\n", encoding="utf-8")
        return
    text = env_path.read_text(encoding="utf-8")
    if "GHOST_AI_AUTHOR_ID" in text:
        lines = [
            f"GHOST_AI_AUTHOR_ID={user_id}" if ln.startswith("GHOST_AI_AUTHOR_ID=") else ln
            for ln in text.splitlines()
        ]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        with env_path.open("a", encoding="utf-8") as f:
            f.write(f"\nGHOST_AI_AUTHOR_ID={user_id}\n")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Verify Ghost is reachable ──────────────────────────────────────────
    print(f"Connecting to Ghost at {GHOST_URL} …")
    try:
        data = api_get("/users/", {"limit": "all", "fields": "id,name,email"})
    except Exception as exc:
        sys.exit(f"✗  Ghost Admin API not reachable: {exc}\n"
                 "   Start containers:  docker compose up -d")

    # ── 2. Check if already exists ────────────────────────────────────────────
    for user in data.get("users", []):
        if user.get("email") == AI_EMAIL:
            uid = user["id"]
            print(f"✓  '{AI_NAME}' already exists (id: {uid})")
            save_user_id(uid)
            print(f"✓  GHOST_AI_AUTHOR_ID={uid}  →  .env updated")
            return

    # ── 3. Locate Docker containers ───────────────────────────────────────────
    print("Locating Docker containers …")
    ghost_c = find_container("ghost")
    db_c    = find_container("db") or find_container("mysql")

    if not ghost_c:
        sys.exit("✗  Ghost container not found. Run:  docker compose up -d")
    if not db_c:
        sys.exit("✗  MySQL container not found. Run:  docker compose up -d")

    print(f"  Ghost : {ghost_c}")
    print(f"  MySQL : {db_c}")

    # ── 4. Generate bcrypt password hash via Node.js in Ghost container ───────
    print("Generating bcrypt hash …")
    pw_hash = bcrypt_hash(ghost_c, AI_PASSWORD)
    print(f"  Hash  : {pw_hash[:29]}…")

    # ── 5. Get Author role ID from MySQL ──────────────────────────────────────
    role_id = mysql(db_c, "SELECT id FROM roles WHERE name='Author' LIMIT 1;")
    if not role_id:
        role_id = mysql(db_c, "SELECT id FROM roles LIMIT 1;")
    if not role_id:
        sys.exit("✗  No roles found in Ghost database.")
    print(f"  Author role id: {role_id}")

    # ── 6. Get first admin user ID (for created_by / updated_by) ─────────────
    admin_id = mysql(db_c, "SELECT id FROM users LIMIT 1;")
    if not admin_id:
        admin_id = "1"

    # ── 7. Delete any leftover pending invite for this email ──────────────────
    mysql(db_c, f"DELETE FROM invites WHERE email='{AI_EMAIL}';")

    # ── 8. Insert user directly into MySQL ───────────────────────────────────
    user_id     = ghost_object_id()
    roles_us_id = ghost_object_id()
    now_sql     = "NOW(3)"   # millisecond precision matches Ghost's schema

    # Escape apostrophes in bio
    bio_escaped = AI_BIO.replace("'", "\\'")

    insert_user = f"""
    INSERT INTO users
        (id, name, slug, email, password, status, bio,
         created_at, created_by, updated_at, updated_by, visibility, locale)
    VALUES
        ('{user_id}', '{AI_NAME}', '{AI_SLUG}', '{AI_EMAIL}',
         '{pw_hash}', 'active', '{bio_escaped}',
         {now_sql}, '{admin_id}', {now_sql}, '{admin_id}',
         'public', 'de');
    """.strip()

    print(f"Inserting user '{AI_NAME}' …")
    mysql(db_c, insert_user)

    insert_role = f"""
    INSERT INTO roles_users (id, role_id, user_id)
    VALUES ('{roles_us_id}', '{role_id}', '{user_id}');
    """.strip()

    print("Assigning Author role …")
    mysql(db_c, insert_role)

    # ── 9. Verify via Ghost Admin API ─────────────────────────────────────────
    print("Verifying via Ghost Admin API …")
    data = api_get("/users/", {"limit": "all", "fields": "id,name,email"})
    verified = next((u for u in data.get("users", []) if u.get("email") == AI_EMAIL), None)

    if not verified:
        sys.exit("✗  Inserted in MySQL but Ghost API doesn't return the user yet.\n"
                 "   Try:  docker compose restart ghost  and run again.")

    uid = verified["id"]

    # ── 10. Set bio via Ghost API (handles any encoding cleanly) ──────────────
    try:
        api_put(f"/users/{uid}/", {"users": [{"id": uid, "bio": AI_BIO}]})
    except Exception:
        pass   # bio is cosmetic

    # ── 11. Save to .env ──────────────────────────────────────────────────────
    save_user_id(uid)

    print(f"\n✓  Author created successfully!")
    print(f"   Name  : {AI_NAME}")
    print(f"   Email : {AI_EMAIL}")
    print(f"   ID    : {uid}")
    print(f"\n✓  GHOST_AI_AUTHOR_ID={uid}  →  saved to .env")
    print("\nRestart backend to apply:  docker compose restart backend")


if __name__ == "__main__":
    main()
