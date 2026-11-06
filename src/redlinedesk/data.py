"""Loaders for the RedlineDesk raw data files."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def load_config() -> dict:
    return json.loads((DATA_DIR / "scoring-config.json").read_text())


def load_contracts() -> dict:
    return json.loads((DATA_DIR / "contracts.json").read_text())


def load_playbook() -> dict:
    return json.loads((DATA_DIR / "playbook.json").read_text())


def load_golden() -> list[dict]:
    return json.loads((DATA_DIR / "golden_set.json").read_text())["pairs"]
