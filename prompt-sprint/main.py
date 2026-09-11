import json
import os
import sys

from dotenv import load_dotenv

PROVIDERS = {
    "openrouter": {"key_env": "OPENROUTER_API_KEY", "prefix": "openrouter/", "base_env": None},
    "openai":     {"key_env": "OPENAI_API_KEY",     "prefix": "openai/",     "base_env": None},
    "anthropic":  {"key_env": "ANTHROPIC_API_KEY",  "prefix": "anthropic/",  "base_env": None},
    "gemini":     {"key_env": "GEMINI_API_KEY",     "prefix": "gemini/",     "base_env": None},
    "laguna":     {"key_env": "LAGUNA_API_KEY",     "prefix": "openai/",     "base_env": "LAGUNA_API_BASE"},
}


def load_config(path="config.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_provider(config):
    provider_name = config.get("provider")
    if not provider_name or provider_name not in PROVIDERS:
        supported = ", ".join(PROVIDERS)
        print(
            f'Unknown provider {provider_name!r}. Supported providers: {supported}.',
            file=sys.stderr,
        )
        sys.exit(1)

    spec = PROVIDERS[provider_name]
    key_env = spec["key_env"]
    if not os.getenv(key_env):
        print(
            f'Missing {key_env}. Set it in .env for provider "{provider_name}".',
            file=sys.stderr,
        )
        sys.exit(1)

    base_env = spec["base_env"]
    if base_env and not os.getenv(base_env):
        print(
            f'Missing {base_env}. Set it in .env for provider "{provider_name}".',
            file=sys.stderr,
        )
        sys.exit(1)

    return provider_name, spec


def main():
    load_dotenv()
    config = load_config()
    provider_name, _spec = resolve_provider(config)
    print(f'PromptSprint environment ready for provider "{provider_name}".')


if __name__ == "__main__":
    main()
