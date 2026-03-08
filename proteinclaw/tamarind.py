from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError

from proteinclaw.env import get_env_value


BASE_URL = "https://app.tamarind.bio/api"
DEFAULT_POLL_INTERVAL_SECONDS = 60


class TamarindError(RuntimeError):
    pass


def has_tamarind_key(root: Path) -> bool:
    return bool(get_env_value(root, "TAMARIND"))


def _headers(root: Path, content_type: str | None = "application/json") -> dict[str, str]:
    api_key = get_env_value(root, "TAMARIND")
    if not api_key:
        raise TamarindError("Missing TAMARIND API key in environment or .env file.")
    headers = {"x-api-key": api_key, "User-Agent": "proteinclaw/0.1.0"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _request(root: Path, method: str, path: str, body: bytes | None = None, content_type: str | None = "application/json") -> str:
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=_headers(root, content_type=content_type),
        method=method,
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def request_json(root: Path, method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    try:
        response = _request(root, method, path, body=body, content_type="application/json")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        message = detail or exc.reason or "HTTP request failed"
        raise TamarindError(f"HTTP {exc.code}: {message}") from exc
    if not response or not response.strip():
        return {}
    return json.loads(response)


def request_text(root: Path, method: str, path: str, payload: dict | None = None) -> str:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    try:
        return _request(root, method, path, body=body, content_type="application/json")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        message = detail or exc.reason or "HTTP request failed"
        raise TamarindError(f"HTTP {exc.code}: {message}") from exc


def upload_file(root: Path, local_path: Path, folder: str) -> dict:
    path = f"/upload/{urllib.parse.quote(local_path.name)}?folder={urllib.parse.quote(folder)}"
    body = local_path.read_bytes()
    try:
        response = _request(root, "PUT", path, body=body, content_type="application/octet-stream")
    except HTTPError as exc:
        if exc.code != 308 or not exc.headers.get("Location"):
            raise
        redirected = urllib.request.Request(
            exc.headers["Location"],
            data=body,
            headers=_headers(root, content_type="application/octet-stream"),
            method="PUT",
        )
        with urllib.request.urlopen(redirected, timeout=60) as response:
            response = response.read().decode("utf-8")
    uploaded = json.loads(response) if response.strip() else {"message": "File uploaded successfully"}
    uploaded["storagePath"] = f"{folder}/{local_path.name}"
    return uploaded


def submit_job(root: Path, job_name: str, job_type: str, settings: dict) -> dict:
    response = request_text(
        root,
        "POST",
        "/submit-job",
        {
            "jobName": job_name,
            "type": job_type,
            "settings": settings,
        },
    )
    if not response.strip():
        return {"message": "Job submitted successfully", "jobName": job_name}
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"message": response.strip(), "jobName": job_name}


def get_job(root: Path, job_name: str) -> dict:
    payload = request_json(root, "GET", f"/jobs?jobName={urllib.parse.quote(job_name)}")
    if "JobStatus" in payload:
        return payload
    for key, value in payload.items():
        if key == "statuses":
            continue
        if isinstance(value, dict) and value.get("JobName") == job_name:
            return value
    return payload


def wait_for_job(
    root: Path,
    job_name: str,
    timeout_seconds: int = 1800,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    status_callback=None,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        payload = get_job(root, job_name)
        status = payload.get("JobStatus")
        if status != last_status and status_callback is not None:
            status_callback(status or "unknown")
            last_status = status
        if status == "Complete":
            return payload
        if status in {"Stopped", "Deleted"}:
            raise TamarindError(f"Tamarind job {job_name} ended with status {status}.")
        time.sleep(poll_interval)
    raise TamarindError(f"Tamarind job {job_name} did not complete within {timeout_seconds} seconds.")


def get_result_url(root: Path, job_name: str) -> str:
    return request_text(root, "POST", "/result", {"jobName": job_name}).strip().strip('"')


def download_result_archive(result_url: str, output_zip: Path) -> Path:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(result_url, output_zip)
    return output_zip


def extract_result_archive(zip_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(output_dir)
        return [output_dir / name for name in archive.namelist()]


def run_tamarind_job(
    root: Path,
    job_name: str,
    job_type: str,
    settings: dict,
    output_dir: Path,
    upload_path: Path | None = None,
    upload_folder: str | None = None,
    file_setting_key: str | None = None,
    logger=None,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_settings = dict(settings)
    if upload_path:
        if not upload_folder:
            raise TamarindError("upload_folder is required when upload_path is provided.")
        if logger:
            logger(f"uploading `{upload_path}` to Tamarind folder `{upload_folder}`.")
        uploaded = upload_file(root, upload_path, upload_folder)
        if file_setting_key:
            resolved_settings[file_setting_key] = uploaded["storagePath"]
        if logger:
            logger(f"upload succeeded as `{uploaded['storagePath']}`.")
    if logger:
        logger(f"submitting Tamarind job `{job_name}` with settings `{json.dumps(resolved_settings, sort_keys=True)}`.")
    submit_job(root, job_name, job_type, resolved_settings)
    wait_for_job(
        root,
        job_name,
        poll_interval=poll_interval,
        status_callback=(lambda status: logger(f"Tamarind status for `{job_name}` -> {status}.") if logger else None),
    )
    result_url = get_result_url(root, job_name)
    archive_path = output_dir / f"{job_name}.zip"
    if logger:
        logger(f"downloading result archive from `{result_url}`.")
    download_result_archive(result_url, archive_path)
    extracted = extract_result_archive(archive_path, output_dir)
    if logger:
        logger(f"extracted {len(extracted)} files into `{output_dir}`.")
    return {
        "job_name": job_name,
        "result_url": result_url,
        "archive_path": str(archive_path),
        "output_dir": str(output_dir),
        "downloaded_files": [str(path) for path in extracted],
        "settings": resolved_settings,
    }
