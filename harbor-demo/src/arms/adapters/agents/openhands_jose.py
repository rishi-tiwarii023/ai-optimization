"""
The CLI package still pins openhands-sdk==1.21.0, which imports authlib.jose and
emits AuthlibDeprecationWarning (and can fail the process). Upstream SDK 1.22
already switched that JWT code to joserfc; this applies the same change in the
installed uv-tool environment.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def ensure_joserfc_in_openhands(cli_path: Path) -> str | None:
    """Patch the installed SDK JWT module and install joserfc. None means ok."""

    openai_py = _find_sdk_openai_py(cli_path)
    if openai_py is None:
        return None
    source = openai_py.read_text(encoding="utf-8").replace("\r\n", "\n")
    if "from authlib.jose import JsonWebKey, jwt" not in source:
        return None
    patched = patch_authlib_jose_to_joserfc(source)
    if "from authlib.jose import" in patched or "JsonWebKey" in patched:
        return (
            f"OpenHands still imports authlib.jose in {openai_py} but the joserfc "
            "rewrite did not match this SDK file. Upgrade the CLI/SDK to 1.22+."
        )
    try:
        openai_py.write_text(patched, encoding="utf-8")
    except OSError as exc:
        return f"Cannot rewrite {openai_py} to use joserfc: {exc}"
    python = _tool_python(openai_py)
    if python is None:
        return f"Rewrote {openai_py} but could not find that env's Python to install joserfc."
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", "joserfc>=1.0.0"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if installed.returncode != 0:
        detail = (installed.stderr or installed.stdout or "").strip()
        return f"Rewrote JWT module to joserfc but pip install failed: {detail}"
    return None


def patch_authlib_jose_to_joserfc(source: str) -> str:
    """Apply the upstream SDK 1.22 JWT API change (authlib.jose -> joserfc)."""

    replacements = (
        (
            "Uses authlib for OAuth handling and aiohttp for the callback server.",
            "Uses joserfc for JWT handling, authlib for OAuth utilities, and aiohttp for the\n"
            "callback server.",
        ),
        (
            "from authlib.jose import JsonWebKey, jwt\n"
            "from authlib.jose.errors import JoseError\n"
            "from authlib.oauth2.rfc7636 import create_s256_code_challenge\n"
            "from httpx import AsyncClient, Client\n",
            "from authlib.oauth2.rfc7636 import create_s256_code_challenge\n"
            "from httpx import AsyncClient, Client\n"
            "from joserfc import jwk, jwt\n"
            "from joserfc.errors import JoseError\n",
        ),
    )
    text = source
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace(
        "self._keys: dict[str, Any] = {}",
        'self._keys: jwk.KeySetSerialization = {"keys": []}',
    )
    text = text.replace("def get_key_set(self) -> Any:", "def get_key_set(self) -> jwk.KeySet:")
    text = re.sub(
        r"if not self\._keys or \(now - self\._fetched_at\) > JWKS_CACHE_TTL_SECONDS:",
        'if (not self._keys["keys"] or (now - self._fetched_at) > JWKS_CACHE_TTL_SECONDS):',
        text,
    )
    text = re.sub(
        r"return JsonWebKey\.import_key_set\(self\._keys\)",
        "return jwk.KeySet.import_key_set(self._keys)",
        text,
    )
    text = re.sub(r"self\._keys = \{\}", 'self._keys = {"keys": []}', text)
    text = re.sub(
        r"claims = jwt\.decode\(access_token, key_set\)\n"
        r"\n"
        r"(?P<indent>[ \t]*)# Validate standard claims \(issuer\)\n"
        r"(?P=indent)claims\.validate\(\)\n"
        r"\n"
        r"(?P=indent)# Extract account ID from nested structure\n"
        r'(?P=indent)auth_info = claims\.get\("https://api\.openai\.com/auth", \{\}\)\n',
        "token = jwt.decode(access_token, key_set)\n"
        "\n"
        r"\g<indent># Validate standard claims (issuer)\n"
        r"\g<indent>claims_registry = jwt.JWTClaimsRegistry()\n"
        r"\g<indent>claims_registry.validate(token.claims)\n"
        "\n"
        r"\g<indent># Extract account ID from nested structure\n"
        r'\g<indent>auth_info = token.claims.get("https://api.openai.com/auth", {})\n',
        text,
    )
    return text


def _find_sdk_openai_py(cli_path: Path) -> Path | None:
    resolved = cli_path.expanduser().resolve()
    roots = [resolved.parent, *resolved.parents]
    uv_tool = Path.home() / ".local" / "share" / "uv" / "tools" / "openhands"
    if uv_tool.is_dir():
        roots.append(uv_tool)
    seen: set[Path] = set()
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        matches = sorted(root.glob("lib/python*/site-packages/openhands/sdk/llm/auth/openai.py"))
        if matches:
            return matches[0]
        nested = root / "openhands" / "sdk" / "llm" / "auth" / "openai.py"
        if nested.is_file():
            return nested
    return None


def _tool_python(openai_py: Path) -> Path | None:
    # .../lib/python3.x/site-packages/openhands/sdk/llm/auth/openai.py
    try:
        tool_root = openai_py.parents[7]
    except IndexError:
        tool_root = None
    candidates: list[Path] = []
    if tool_root is not None:
        candidates.extend(
            [
                tool_root / "bin" / "python",
                tool_root / "bin" / "python3",
            ]
        )
    candidates.extend(
        [
            Path(sys.executable),
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    return None
