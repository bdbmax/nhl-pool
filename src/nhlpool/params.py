import json

from .models import marcel
from .paths import CONFIG


def load(name: str = "b1") -> dict:
    """Tuned parameters on top of the model defaults (tuples restored)."""
    path = CONFIG / f"params_{name}.json"
    p = dict(marcel.DEFAULT)
    if path.exists():
        p.update(json.loads(path.read_text()))
    for k in ("w", "gp_w", "g_w", "gr_w"):
        if p.get(k) is not None:
            p[k] = tuple(p[k])
    return p
