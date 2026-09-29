from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
TEMPLATES = ROOT / "templates"

for p in (RAW, MANUAL, PROCESSED, OUTPUT):
    p.mkdir(parents=True, exist_ok=True)
