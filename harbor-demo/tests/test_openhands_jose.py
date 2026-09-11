from src.arms.adapters.agents.openhands_jose import patch_authlib_jose_to_joserfc


_SDK_21_SNIPPET = '''
from aiohttp import web
from authlib.common.security import generate_token
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from httpx import AsyncClient, Client

class _JWKSCache:
    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0
        self._lock = threading.Lock()

    def get_key_set(self) -> Any:
        with self._lock:
            now = time.time()
            if not self._keys or (now - self._fetched_at) > JWKS_CACHE_TTL_SECONDS:
                self._fetch_jwks()
            return JsonWebKey.import_key_set(self._keys)

    def clear(self) -> None:
        with self._lock:
            self._keys = {}
            self._fetched_at = 0

def _extract_chatgpt_account_id(access_token: str) -> str | None:
    try:
        key_set = _jwks_cache.get_key_set()
        claims = jwt.decode(access_token, key_set)

        # Validate standard claims (issuer)
        claims.validate()

        # Extract account ID from nested structure
        auth_info = claims.get("https://api.openai.com/auth", {})
        account_id = auth_info.get("chatgpt_account_id")
        return account_id
    except JoseError as e:
        return None
'''


def test_patch_replaces_authlib_jose_with_joserfc() -> None:
    patched = patch_authlib_jose_to_joserfc(_SDK_21_SNIPPET)
    assert "from authlib.jose import" not in patched
    assert "from joserfc import jwk, jwt" in patched
    assert "from joserfc.errors import JoseError" in patched
    assert "JsonWebKey" not in patched
    assert "jwk.KeySet.import_key_set" in patched
    assert "JWTClaimsRegistry" in patched
    assert "token.claims.get" in patched
    assert 'self._keys["keys"]' in patched


def test_install_joserfc_uses_uv_pip_when_import_missing(monkeypatch, tmp_path) -> None:
    from src.arms.adapters.agents import openhands_jose as jose

    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        if cmd[:3] == [str(python), "-c", "import joserfc"]:
            Result.returncode = 1
            return Result()
        return Result()

    monkeypatch.setattr(jose.subprocess, "run", fake_run)
    monkeypatch.setattr(jose.shutil, "which", lambda name: "/usr/bin/uv")
    assert jose._install_joserfc(python) is None
    assert calls[1][:4] == ["/usr/bin/uv", "pip", "install", "--python"]
    assert calls[1][4] == str(python)
    assert calls[1][5] == "joserfc>=1.0.0"

