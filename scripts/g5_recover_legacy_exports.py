"""Explicit authorized SSH read-only recovery. No POST, service or model calls."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path("research/experiments/2026-09-12-g5-legacy-server-recovery")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-i",
       "/Users/michaelwang/.ssh/roommind_tencent", "ubuntu@43.162.83.232"]
STATIC = ["/tmp/g22-transcripts.json", "/tmp/g23-transcripts.json",
    "/tmp/roommind-g3.4-evaluated-transcripts.json", "/tmp/roommind-g3.4-debug-bundle.json.gz",
    "/tmp/g39-final-evaluation.json", "/tmp/g39-debug-bundle.json",
    "/tmp/roommind-g41-final-evaluation.json", "/tmp/roommind-g41-debug-bundle.json"] + [
    f"/tmp/{folder}/{name}" for folder in ("roommind-g36-audit", "roommind-g44-776890ab", "roommind-g45-analysis")
    for name in ("transcripts.json", "debug-bundle.json", "final-evaluation.json")]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())


def fetch(job):
    mode, origin, name = job
    if mode == "historical-file":
        read = "from pathlib import Path; data=Path(" + repr(origin) + ").read_bytes()"
    else:
        read = "import urllib.request; data=urllib.request.urlopen(" + repr(origin) + ",timeout=120).read()"
    code = "import sys,hashlib; " + read + "; sys.stdout.buffer.write(hashlib.sha256(data).hexdigest().encode()+b'\\n'+data)"
    result = subprocess.run(SSH + ["python3 -c " + shlex.quote(code)], capture_output=True, timeout=150)
    if result.returncode: return {"mode": mode, "origin": origin, "status": "failed", "error": result.stderr.decode()[-800:]}
    expected, data = result.stdout.split(b"\n", 1)
    sha = hashlib.sha256(data).hexdigest()
    if expected.decode() != sha: raise ValueError("SSH transfer checksum mismatch")
    write(ROOT / name, data)
    return {"mode": mode, "origin": origin, "path": str(ROOT / name), "status": "downloaded",
            "bytes": len(data), "sha256": sha, "remote_stream_sha256": expected.decode()}


def main():
    ROOT.mkdir(exist_ok=False)
    jobs = [("historical-file", p, "historical/" + p.removeprefix("/tmp/")) for p in STATIC]
    documents = []
    for p in sorted(Path("docs").glob("EXPERIMENT_G*RESULTS.md")):
        match = re.match(r"EXPERIMENT_G([234])(?:_(\d+))?", p.name)
        if not match or match[1] == "4" and int(match[2] or 0) > 5: continue
        ids = re.findall(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", p.read_text())
        if not ids: continue
        batch = ids[0]
        documents.append({"document": str(p), "batch_uuid": batch, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        for endpoint in ("transcripts.json", "debug-bundle.json", "final-evaluation"):
            url = f"http://127.0.0.1:8910/api/game/batch-experiments/{batch}/{endpoint}"
            jobs.append(("current-read-only-export", url, f"current/{batch}/{endpoint if endpoint.endswith('.json') else endpoint + '.json'}"))
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for row in pool.map(fetch, jobs):
            records.append(row)
            print(json.dumps({k:row[k] for k in ("mode", "status", "origin")}), flush=True)
    report = {"scope": "authorized-legacy-read-only-ssh-recovery", "documents": documents, "files": records,
        "historical_bytes_preserved": True, "current_exports_are_new_views_not_original_export_bytes": True,
        "no_deploy_restart_model_or_batch_mutation": True}
    write(ROOT / "recovery-receipt.json", json.dumps(report, sort_keys=True).encode())
    print(json.dumps({"downloaded": sum(r["status"] == "downloaded" for r in records), "failed": sum(r["status"] != "downloaded" for r in records)}))


if __name__ == "__main__": main()
