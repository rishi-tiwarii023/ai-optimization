from __future__ import annotations

from src.arms.reporting.metrics import MetricsCollector, ModelMetrics

__all__ = ["MetricsCollector", "ModelMetrics", "generate_dashboard"]


def __getattr__(name: str):
    if name == "generate_dashboard":
        from src.arms.reporting.dashboard import generate_dashboard

        return generate_dashboard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
