#!/usr/bin/env python3
"""Convenience CLI: python3 scripts/generate_demo_data.py [output_csv]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from datetime import date
from app.services.demo_data_generator import generate_demo_observations

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "demo_generated.csv"
df = generate_demo_observations(start_date=date(2026, 1, 1), n_months=8)
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)
print(f"Generated {len(df)} rows -> {out}")
