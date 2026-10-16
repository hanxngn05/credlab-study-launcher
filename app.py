"""Load a checksum-pinned private study bundle; no study data lives in this repo."""

import hashlib
import io
import json
import os
import re
import runpy
import shutil
import tempfile
import zipfile
from pathlib import Path

import streamlit as st
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

MAX_ARCHIVE = 20 * 1024 * 1024
MAX_EXTRACTED = 60 * 1024 * 1024


def extract_verified(content, expected, target):
    """Extract only an authenticated, digest-verified, bounded source bundle."""
    if len(content) > MAX_ARCHIVE or hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Source verification failed")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or sum(item.file_size for item in entries) > MAX_EXTRACTED:
            raise ValueError("Source bundle too large")
        for item in entries:
            parts = Path(item.filename).parts
            if (
                not parts or Path(item.filename).is_absolute() or ".." in parts
                or "\\" in item.filename or "private" in parts
                or (item.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Unsafe source path")
        archive.extractall(target)
    if not (target / "study/cloud_app.py").is_file():
        raise ValueError("Missing study entrypoint")


@st.cache_resource(show_spinner="Loading the study…")
def private_source(file_id, expected, credential_json):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", file_id) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Source is not configured")
    data = json.loads(credential_json)
    scope = "https://www.googleapis.com/auth/drive.file"
    if data.get("type") != "authorized_user" or set(data.get("scopes", [])) != {scope}:
        raise ValueError("Invalid source authorization")
    credential = Credentials.from_authorized_user_info(data, scopes=[scope])
    with AuthorizedSession(credential, refresh_timeout=15, max_refresh_attempts=1) as http:
        response = http.get(
            "https://www.googleapis.com/drive/v3/files/" + file_id,
            params={"alt": "media", "supportsAllDrives": "true"},
            timeout=(10, 45), allow_redirects=False, stream=True,
        )
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(256 * 1024):
            content.extend(chunk)
            if len(content) > MAX_ARCHIVE:
                raise ValueError("Source bundle too large")
    target = Path(tempfile.mkdtemp(prefix="credlab-source-"))
    target.chmod(0o700)
    try:
        extract_verified(bytes(content), expected, target)
    except Exception:
        shutil.rmtree(target)
        raise
    return target


def main():
    try:
        source = private_source(
            str(st.secrets["KDRAMA_SOURCE_FILE_ID"]),
            str(st.secrets["KDRAMA_SOURCE_SHA256"]),
            str(st.secrets["KDRAMA_DRIVE_CREDENTIALS_JSON"]),
        )
    except Exception:
        st.error("The study is unavailable. Please contact the researcher.")
        st.stop()
    # Keep writes outside the cached, immutable source bundle.
    os.environ["KDRAMA_DB"] = str(Path.cwd() / ".study-private/study.sqlite")
    runpy.run_path(str(source / "study/cloud_app.py"), run_name="__main__")


if __name__ == "__main__":
    main()
