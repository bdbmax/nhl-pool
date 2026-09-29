import yaml

from .paths import CONFIG


def load_league() -> dict:
    with open(CONFIG / "league.yaml") as f:
        return yaml.safe_load(f)
