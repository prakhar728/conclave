"""
Shared pytest configuration for the Conclave test suite.

Provides:
  - @pytest.mark.live  — skip when CONCLAVE_NEARAI_API_KEY is not set
  - base_df            — session-scoped fraud-like DataFrame (~800 rows)
  - matrix_results     — session-scoped list; tests append rows, teardown
                         prints two tables and saves tests/demo_matrix.json
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Generator

import pandas as pd
import pytest

DEMO_JSON_PATH = os.path.join(os.path.dirname(__file__), "demo_matrix.json")


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring a real NearAI API key (skipped in CI)",
    )


def pytest_collection_modifyitems(config, items):
    api_key = os.environ.get("CONCLAVE_NEARAI_API_KEY", "").strip()
    skip_live = pytest.mark.skip(reason="CONCLAVE_NEARAI_API_KEY not set — live tests skipped")
    for item in items:
        if "live" in item.keywords and not api_key:
            item.add_marker(skip_live)


# ---------------------------------------------------------------------------
# Dataset fixture
# ---------------------------------------------------------------------------

def _generate_synthetic_df(n: int = 800) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "transaction_id":    [f"txn_{i:05d}" for i in range(n)],
        "amount":            rng.uniform(1.0, 500.0, n).round(2),
        "merchant_category": rng.choice(["grocery", "gas", "restaurant", "travel", "online"], n),
        "is_fraud":          (rng.uniform(0, 1, n) < 0.04).astype(int),
    })


@pytest.fixture(scope="session")
def base_df() -> pd.DataFrame:
    """Session-scoped clean fraud-like DataFrame (~800 rows, synthetic fallback)."""
    url = "https://raw.githubusercontent.com/dsrscientist/dataset1/master/creditcard_small.csv"
    try:
        import io, requests
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_csv(io.StringIO(resp.text))
            rename = {}
            cols_lower = {c.lower(): c for c in df.columns}
            if "transaction_id" not in cols_lower and "id" in cols_lower:
                rename[cols_lower["id"]] = "transaction_id"
            if "is_fraud" not in cols_lower and "class" in cols_lower:
                rename[cols_lower["class"]] = "is_fraud"
            if rename:
                df = df.rename(columns=rename)
            if {"transaction_id", "amount", "is_fraud"}.issubset(df.columns):
                return df.head(800)
    except Exception:
        pass
    return _generate_synthetic_df(800)


# ---------------------------------------------------------------------------
# Matrix results fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def matrix_results() -> Generator[list[dict], None, None]:
    """
    Session-scoped list. Tests append rows with a "type" field:
      type="evaluation"    — pipeline runs (quality, payment, deal)
      type="renegotiation" — post-evaluation negotiation rounds

    At teardown: prints two formatted tables + saves tests/demo_matrix.json.
    """
    rows: list[dict] = []
    yield rows

    if not rows:
        return

    eval_rows  = [r for r in rows if r.get("type") != "renegotiation"]
    reneg_rows = [r for r in rows if r.get("type") == "renegotiation"]

    # --- Evaluation table ---
    if eval_rows:
        print("\n" + "=" * 96)
        print("EVALUATION MATRIX  (deterministic + LLM agent)")
        print("=" * 96)
        print(f"{'Scenario':<30} {'Seller':<18} {'Buyer':<12} {'Reserve':>8} {'Quality':>8} {'Payment':>9} {'Deal':>5}")
        print("-" * 96)
        for r in eval_rows:
            q   = r.get("quality")
            p   = r.get("payment")
            rv  = r.get("reserve")
            print(
                f"{r.get('scenario',''):<30} {r.get('seller',''):<18} {r.get('buyer',''):<12} "
                f"{'$'+f'{rv:,.0f}' if rv is not None else 'N/A':>8} "
                f"{f'{q:.3f}' if q is not None else 'N/A':>8} "
                f"{'$'+f'{p:,.0f}' if p is not None else 'N/A':>9} "
                f"{'YES' if r.get('deal') else ' NO':>5}"
            )
        print("=" * 96)

    # --- Renegotiation table ---
    if reneg_rows:
        print("\n" + "=" * 90)
        print("RENEGOTIATION MATRIX  (post-evaluation, deterministic only)")
        print("=" * 90)
        print(f"{'Scenario':<35} {'Initial':>9} {'Buyer':>14} {'Seller':>14} {'Final':>9} {'Deal':>5}")
        print("-" * 90)
        for r in reneg_rows:
            init = r.get("initial_offer")
            final = r.get("final_payment")
            print(
                f"{r.get('scenario',''):<35} "
                f"{'$'+f'{init:,.0f}' if init is not None else 'N/A':>9} "
                f"{str(r.get('buyer_action','')):<14} "
                f"{str(r.get('supplier_action','')):<14} "
                f"{'$'+f'{final:,.0f}' if final is not None else '  —':>9} "
                f"{'YES' if r.get('deal') else ' NO':>5}"
            )
        print("=" * 90)

    # --- Save JSON ---
    output = {
        "title":     "Confidential Data Procurement — Demo Results",
        "generated": str(datetime.date.today()),
        "model":     "deepseek-ai/DeepSeek-V3.1",
        "pipeline":  "deterministic → LLM agent (schema match + claim verify) → guardrails",
        "note":      "base_price=0: bad data → payment approaches $0. Reserve not met → deal rejected.",
        "evaluation_matrix": [
            {
                "id":             i + 1,
                "scenario":       r.get("scenario", ""),
                "narrative":      r.get("narrative", ""),
                "seller_variant": r.get("seller", ""),
                "buyer_variant":  r.get("buyer", ""),
                "reserve_price":  r.get("reserve"),
                "quality_score":  round(r["quality"], 4) if r.get("quality") is not None else None,
                "proposed_payment": r.get("payment"),
                "deal":           r.get("deal"),
                "settlement_status": "pending_approval" if r.get("deal") else "rejected",
                "notes":          r.get("notes", []),
                "explanation":    r.get("explanation", ""),
                "schema_matching":    r.get("schema_matching"),
                "claim_verification": r.get("claim_verification"),
            }
            for i, r in enumerate(eval_rows)
        ],
        "renegotiation_matrix": [
            {
                "id":             i + 1,
                "scenario":       r.get("scenario", ""),
                "narrative":      r.get("narrative", ""),
                "initial_offer":  r.get("initial_offer"),
                "buyer_action":   r.get("buyer_action", ""),
                "supplier_action":r.get("supplier_action", ""),
                "final_payment":  r.get("final_payment"),
                "deal":           r.get("deal"),
                "settlement_status": "authorized" if r.get("deal") else "rejected",
            }
            for i, r in enumerate(reneg_rows)
        ],
    }
    with open(DEMO_JSON_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nDemo JSON → {DEMO_JSON_PATH}")
