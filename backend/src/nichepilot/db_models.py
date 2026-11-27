"""Nạp toàn bộ model để metadata đầy đủ (Alembic, test so khớp schema)."""

from __future__ import annotations


def import_all_models() -> None:
    import nichepilot.ai.models
    import nichepilot.jobs.models
    import nichepilot.modules.audit.models
    import nichepilot.modules.discovery.models
    import nichepilot.modules.evidence.models
    import nichepilot.modules.identity.models
    import nichepilot.modules.products.models
    import nichepilot.modules.settings.models  # noqa: F401
