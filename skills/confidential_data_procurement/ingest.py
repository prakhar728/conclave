"""
Ingestion layer for confidential_data_procurement.

Responsibilities:
- Parse uploaded CSV into a pandas DataFrame
- Parse metadata file (JSON working; PDF/DOCX stubbed)
- Parse buyer policy document (JSON working; PDF/DOCX stubbed)
- Store DataFrames in memory keyed by dataset_id
- Expose upload_handler — the SkillCard callable for POST /upload

The DataFrame NEVER leaves this module as raw data.
Tools in tools.py query it only via aggregate operations.
Cleanup is called by run_skill after the pipeline completes.

Format support matrix:
  CSV:   ✓ working
  JSON:  ✓ working (metadata + buyer policy documents)
  DOCX:  ✗ stubbed
  PDF:   ✗ stubbed
  Excel: ✗ stubbed
"""
from __future__ import annotations

import io
import json
import uuid
from typing import Any

import pandas as pd

from skills.confidential_data_procurement.config import (
    MAX_DATASET_ROWS,
    MAX_DATASET_SIZE_MB,
)

# ---------------------------------------------------------------------------
# In-memory dataset store
# dataset_id -> {
#   "df": pd.DataFrame,
#   "csv_bytes": bytes,        # raw upload bytes — kept for post-deal download
#   "metadata": dict,          # seller-provided metadata
#   "column_definitions": dict, # col_name -> human description
#   "seller_claims": dict,      # claim_key -> claim_value
#   "instance_id": str,
# }
# ---------------------------------------------------------------------------
_datasets: dict[str, dict[str, Any]] = {}

# release_token -> csv_bytes
# Populated by store_authorized_download() when a deal is authorized.
# Persists after cleanup() so the buyer can download post-settlement.
_authorized_downloads: dict[str, bytes] = {}


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def get_dataset(dataset_id: str) -> dict[str, Any]:
    """Return the stored dataset dict. Raises KeyError if not found."""
    if dataset_id not in _datasets:
        raise KeyError(f"Dataset '{dataset_id}' not found. Upload may have expired.")
    return _datasets[dataset_id]


def cleanup(dataset_id: str) -> None:
    """Discard the DataFrame after the pipeline completes."""
    _datasets.pop(dataset_id, None)


def store_authorized_download(release_token: str, dataset_id: str) -> None:
    """
    Move CSV bytes from the dataset store into the authorized downloads map.
    Called when a deal reaches settlement_status='authorized'.
    The bytes persist here after the DataFrame is cleaned up.
    """
    dataset = _datasets.get(dataset_id)
    if dataset and "csv_bytes" in dataset:
        _authorized_downloads[release_token] = dataset["csv_bytes"]


def get_download_bytes(release_token: str) -> bytes:
    """
    Return the CSV bytes for an authorized download token.
    Raises KeyError if the token is not found.
    """
    if release_token not in _authorized_downloads:
        raise KeyError(f"Download token not found or not yet authorized.")
    return _authorized_downloads[release_token]


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse CSV bytes into a DataFrame.
    Enforces size and row limits before returning.
    Raises ValueError with a human-readable message on any failure.
    """
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_DATASET_SIZE_MB:
        raise ValueError(
            f"Dataset exceeds size limit ({size_mb:.1f}MB > {MAX_DATASET_SIZE_MB}MB). "
            "Please upload a smaller file."
        )

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not parse CSV: {e}") from e

    if len(df) > MAX_DATASET_ROWS:
        raise ValueError(
            f"Dataset exceeds row limit ({len(df):,} rows > {MAX_DATASET_ROWS:,}). "
            "Please upload a sample."
        )

    if df.empty:
        raise ValueError("Uploaded CSV is empty.")

    return df


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

def parse_metadata(file_bytes: bytes, file_type: str) -> dict[str, Any]:
    """
    Parse the supplier's metadata file.

    JSON (working): expects keys such as:
        column_definitions: {col_name: description}
        seller_claims:      {claim_key: claim_value}
        source, date_range, license, etc.

    PDF / DOCX / other: stubbed — returns empty metadata with a note.
    """
    file_type = (file_type or "").lower().strip(".")

    if file_type == "json":
        try:
            return json.loads(file_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Could not parse metadata JSON: {e}") from e

    # --- Stubs ---
    _STUB_TYPES = {"pdf", "docx", "doc", "txt", "md"}
    if file_type in _STUB_TYPES:
        return {
            "_stub": True,
            "_stub_reason": (
                f"Metadata format '{file_type}' is not yet supported. "
                "Please upload a JSON metadata file. "
                "Proceeding with empty metadata."
            ),
        }

    return {
        "_stub": True,
        "_stub_reason": (
            f"Unknown metadata format '{file_type}'. "
            "Proceeding with empty metadata."
        ),
    }


def parse_buyer_document(file_bytes: bytes, file_type: str) -> dict[str, Any]:
    """
    Parse a buyer-uploaded policy document.

    JSON (working): expects BuyerPolicy-compatible fields.
    PDF / DOCX: stubbed — buyer should describe requirements in the init chat.
    """
    file_type = (file_type or "").lower().strip(".")

    if file_type == "json":
        try:
            return json.loads(file_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Could not parse policy JSON: {e}") from e

    _STUB_TYPES = {"pdf", "docx", "doc", "txt", "md"}
    if file_type in _STUB_TYPES:
        return {
            "_stub": True,
            "_stub_reason": (
                f"Policy document format '{file_type}' is not yet supported. "
                "Please describe your requirements in the setup chat, "
                "or upload a JSON policy file."
            ),
        }

    return {
        "_stub": True,
        "_stub_reason": (
            f"Unknown policy format '{file_type}'. "
            "Please describe your requirements in the setup chat."
        ),
    }


# ---------------------------------------------------------------------------
# Upload handler (SkillCard.upload_handler)
# ---------------------------------------------------------------------------

def procurement_upload_handler(form: Any, instance_id: str) -> dict[str, Any]:
    """
    Skill-owned handler for POST /upload.
    Called by routes.py with the parsed multipart form and instance_id.

    Expected form fields:
        csv_file      — the dataset CSV (required)
        metadata_file — JSON metadata file (optional)

    Returns:
        {"dataset_id": str}
    """
    # --- Extract CSV ---
    csv_upload = form.get("csv_file")
    if csv_upload is None:
        raise ValueError("csv_file is required")

    csv_bytes: bytes = csv_upload.file.read() if hasattr(csv_upload, "file") else bytes(csv_upload)
    df = parse_csv(csv_bytes)

    # --- Extract metadata (optional) ---
    metadata: dict[str, Any] = {}
    metadata_upload = form.get("metadata_file")
    if metadata_upload is not None:
        meta_bytes = (
            metadata_upload.file.read()
            if hasattr(metadata_upload, "file")
            else bytes(metadata_upload)
        )
        filename = getattr(metadata_upload, "filename", "") or ""
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "json"
        metadata = parse_metadata(meta_bytes, ext)

    dataset_id = str(uuid.uuid4())
    _datasets[dataset_id] = {
        "df": df,
        "csv_bytes": csv_bytes,
        "metadata": metadata,
        "column_definitions": metadata.get("column_definitions", {}),
        "seller_claims": metadata.get("seller_claims", {}),
        "instance_id": instance_id,
    }

    return {"dataset_id": dataset_id}
