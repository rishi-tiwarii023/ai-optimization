_REGISTRY: dict[str, type] = {}


def register(name: str):
    def decorator(cls: type) -> type:
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_provider(name: str) -> type:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider '{name}'. Registered providers: {sorted(_REGISTRY)}"
        ) from None


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())