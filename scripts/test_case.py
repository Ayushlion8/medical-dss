#!/usr/bin/env python3
"""
scripts/test_case.py — submit a synthetic vignette to the running API
Usage:  python scripts/test_case.py [--case 1]
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

API = "http://localhost:8000/api"

CASES = {
    1: {
        "case_id": "test-001-pneumothorax",
        "patient_context": {
            "age": 28, "sex": "M",
            "chief_complaint": "sudden right-sided pleuritic chest pain and dyspnea",
            "hpi": "Tall thin male, sudden sharp right chest pain at rest. No trauma.",
            "pmh": [],
            "meds": [],
            "vitals": {"BP": "122/78", "HR": 104, "RR": 22, "SpO2": 94},
            "labs": {}
        },
        "images": [],
        "preferences": {"recency_years": 5, "max_citations": 6}
    },
    2: {
        "case_id": "test-002-PE",
        "patient_context": {
            "age": 64, "sex": "M",
            "chief_complaint": "acute dyspnea and hypoxemia after long-haul flight",
            "hpi": "Post-flight acute dyspnea and mild pleuritic pain.",
            "pmh": ["HTN", "prostate cancer"],
            "meds": ["metformin"],
            "vitals": {"BP": "98/60", "HR": 120, "RR": 28, "SpO2": 88},
            "labs": {"D_dimer": 1200, "troponin": 0.03}
        },
        "images": [],
        "preferences": {"recency_years": 5, "max_citations": 8}
    }
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=int, default=1, choices=[1, 2])
    args = parser.parse_args()

    payload = CASES[args.case]
    print(f"\n==> Submitting case: {payload['case_id']}")
    print(f"    Chief complaint: {payload['patient_context']['chief_complaint']}\n")

    with httpx.Client(timeout=300) as client:
        resp = client.post(f"{API}/analyze-case", json=payload)

    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()

    print("─── IMAGING FINDINGS ─────────────────────────────────")
    for name, f in (data.get("imaging_findings") or {}).items():
        print(f"  {name}: {f['prob']:.0%}")

    print("\n─── DIFFERENTIALS ────────────────────────────────────")
    for d in data.get("differentials", []):
        print(f"  #{d['probability_rank']} {d['dx']}  [{d['icd10']}]")

    print("\n─── RED FLAGS ────────────────────────────────────────")
    for rf in data.get("red_flags", []):
        print(f"  ⚠  {rf}")

    print("\n─── NEXT STEPS ──────────────────────────────────────")
    for ns in data.get("next_steps", []):
        print(f"  → {ns}")

    print(f"\n─── CITATIONS ({len(data.get('citations', []))}) ──────────────────────────────")
    for c in data.get("citations", [])[:3]:
        print(f"  [{c['id']}] {c.get('source', '')} ({c.get('year', 'n/d')})")
        print(f"       \"{c['quote'][:80]}...\"")

    print(f"\n─── GROUNDEDNESS ─────────────────────────────────────")
    g = data.get("groundedness", {})
    print(f"  Verified: {g.get('verified')}  | {g.get('note', '')}")

    print(f"\n─── AGENT TRACES ─────────────────────────────────────")
    for t in data.get("traces", []):
        print(f"  {t['agent']:<30} {t['duration_ms']:>8.1f} ms")

    if data.get("report_url"):
        print(f"\n  PDF report: http://localhost:8000{data['report_url']}.pdf")

    # Save full response
    out = Path(f"test_result_{payload['case_id']}.json")
    out.write_text(json.dumps(data, indent=2))
    print(f"\n  Full result saved to: {out}\n")


if __name__ == "__main__":
    main()
