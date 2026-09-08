"""Shared historical configuration, with an optional shallow local overlay."""
from legacy.paths import ROOT


def load_config() -> dict:
    import yaml

    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
    local = ROOT / "config.local.yaml"
    if local.exists():
        config.update(yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return config
