"""Build an E2B sandbox template using the v3 API with X-API-KEY auth."""
import hashlib
import io
import sys
import tarfile
import time
from pathlib import Path

import httpx

API_KEY = "e2b_6f51493a4a7b4c0ec9c8b1b8a2a7d9b6fd770b7c"
BASE_URL = "https://api.e2b.app"
HEADERS = {"X-API-KEY": API_KEY}

DOCKERFILE = Path(__file__).parent.parent / "e2b.Dockerfile"


def make_tar(dockerfile: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(str(dockerfile), arcname="Dockerfile")
    return buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    client = httpx.Client(headers=HEADERS, timeout=30)

    # 1. Create template + initial build slot
    print("Creating template…")
    r = client.post(f"{BASE_URL}/v3/templates", json={"name": "tgrambotz"})
    r.raise_for_status()
    tmpl = r.json()
    template_id = tmpl["templateID"]
    build_id = tmpl["buildID"]
    print(f"  templateID: {template_id}")
    print(f"  buildID:    {build_id}")

    # 2. Pack Dockerfile into a tar and hash it
    tar_data = make_tar(DOCKERFILE)
    file_hash = sha256(tar_data)
    print(f"  context hash: {file_hash[:16]}…")

    # 3. Get presigned upload URL
    print("Getting upload URL…")
    r = client.get(
        f"{BASE_URL}/templates/{template_id}/files/{file_hash}",
    )
    r.raise_for_status()
    upload_info = r.json()
    upload_url = upload_info["url"]

    # 4. Upload tar
    print("Uploading build context…")
    r = httpx.put(upload_url, content=tar_data, timeout=60)
    r.raise_for_status()
    print("  uploaded OK")

    # 5. Trigger the build
    print("Triggering build…")
    r = client.post(
        f"{BASE_URL}/v2/templates/{template_id}/builds/{build_id}",
        json={"dockerfile": "Dockerfile", "startCommand": "", "envVars": {}},
    )
    r.raise_for_status()
    print("  build started")

    # 6. Poll for completion
    print("Waiting for build to finish…")
    offset = 0
    while True:
        r = client.get(
            f"{BASE_URL}/templates/{template_id}/builds/{build_id}/status",
            params={"logsOffset": offset},
        )
        r.raise_for_status()
        data = r.json()
        for entry in data.get("logs", []):
            print(f"  {entry}")
        offset += len(data.get("logs", []))
        status = data.get("status", "")
        if status == "ready":
            print(f"\nTemplate built successfully!")
            print(f"Template ID: {template_id}")
            print(f"\nUpdate E2B_TEMPLATE in src/tgrambotz/agent.py to: {template_id!r}")
            break
        elif status == "error":
            print(f"\nBuild failed: {data}")
            sys.exit(1)
        time.sleep(3)


if __name__ == "__main__":
    main()
