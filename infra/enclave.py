"""
Dstack agent integration — attestation quotes and output signing.

Inside a Phala CVM the dstack agent is available at http://dstack-agent.
Outside the CVM (local dev) these functions return stub values so the
rest of the service starts without error.
"""

import hashlib
import json
import os

import httpx

DSTACK_AGENT_URL = os.environ.get("DSTACK_AGENT_URL", "http://dstack-agent")
IN_TEE = os.environ.get("IN_TEE", "false").lower() == "true"


def get_attestation_quote(nonce: str = "") -> str:
    """
    Fetch the TDX attestation quote from the dstack agent.
    Returns hex-encoded quote string.
    Falls back to a stub outside the TEE.
    """
    if not IN_TEE:
        return "stub_attestation_quote_not_in_tee"

    resp = httpx.post(
        f"{DSTACK_AGENT_URL}/quote",
        json={"nonce": nonce},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["quote"]


def sign_result(result: dict) -> tuple[str, str]:
    """
    Sign a result dict inside the TEE using the enclave's hardware-bound key.
    Returns (signature_hex, attestation_quote_hex).
    Falls back to stub values outside the TEE.
    """
    if not IN_TEE:
        return "stub_signature_not_in_tee", "stub_attestation_quote_not_in_tee"

    payload = json.dumps(result, sort_keys=True).encode()
    digest = hashlib.sha256(payload).hexdigest()

    sign_resp = httpx.post(
        f"{DSTACK_AGENT_URL}/sign",
        json={"data": digest},
        timeout=10,
    )
    sign_resp.raise_for_status()
    signature = sign_resp.json()["signature"]

    quote = get_attestation_quote(nonce=digest)
    return signature, quote
