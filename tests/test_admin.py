#!/usr/bin/env python3
"""Tests for the local admin server (tools/serve.py).

Serves the admin API on an ephemeral port against a throwaway data dir so the
repo's real data/ is never touched, then exercises the full CRUD surface plus
status transitions, preview, validation and rollback behaviour.

Usage:
    python3 tests/test_admin.py
"""

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVE = ROOT / "tools" / "serve.py"

DATA_FILES = ("masjids.json", "events.json", "speakers.json", "categories.json",
              "settings.json", "districts.json", "editors.json")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Admin:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mvp-admin-"))
        self.data_dir = self.tmp / "data"
        self.public_dir = self.tmp / "public-data"
        self.port = free_port()
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVE),
             "--port", str(self.port),
             "--data-dir", str(self.data_dir),
             "--public-data", str(self.public_dir)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.base = f"http://127.0.0.1:{self.port}"
        self._wait()

    def _wait(self, tries=50):
        for _ in range(tries):
            try:
                self.request("GET", "/api/data")
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("admin server did not start")

    def request(self, method, path, body=None):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8") or "{}")

    def data(self):
        _, payload = self.request("GET", "/api/data")
        return payload

    def status_of(self, method, path, body=None):
        """Like request() but ignores the response body (for non-JSON pages)."""
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def shutdown(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)


def test_crud_masjid_speaker_category():
    admin = Admin()
    try:
        status, created = admin.request("POST", "/api/masjids",
                                        {"name": "Masjid Ujian", "district": "Kangar"})
        assert status == 201, (status, created)
        mid = created["id"]
        assert mid == "masjid-ujian", mid
        # district_id derived from the free-text district
        assert created["record"]["district_id"] == "kangar", created

        status, speaker = admin.request("POST", "/api/speakers",
                                        {"name": "Ustaz Ujian", "description": "Ahli jawatankuasa"})
        assert status == 201, (status, speaker)
        sid = speaker["id"]

        status, cat = admin.request("POST", "/api/categories", {"name": "Kuliyyah"})
        assert status == 201, (status, cat)
        cid = cat["id"]

        # reference the speaker so delete is blocked
        status, ev = admin.request("POST", "/api/events", {
            "title": "Acara Rujukan", "masjid_id": mid, "date": "2026-09-05",
            "start_time": "20:00", "speaker_id": sid,
        })
        assert status == 201, (status, ev)
        eid = ev["id"]

        # update masjid
        status, _ = admin.request("PUT", f"/api/masjids/{mid}",
                                  {"name": "Masjid Ujian Baru", "district": "Arau"})
        assert status == 200, status
        by_id = {m["id"]: m for m in admin.data()["masjids"]}
        assert by_id[mid]["name"] == "Masjid Ujian Baru"

        # delete speaker while referenced -> blocked
        status, resp = admin.request("DELETE", f"/api/speakers/{sid}")
        assert status == 400, (status, resp)
        assert "referenced" in resp["errors"][0]

        # delete masjid while referenced by an event -> blocked
        status, resp = admin.request("DELETE", f"/api/masjids/{mid}")
        assert status == 400, (status, resp)
        assert "referenced" in resp["errors"][0]

        # delete category (unreferenced) -> ok
        status, _ = admin.request("DELETE", f"/api/categories/{cid}")
        assert status == 200, status
        assert cid not in {c["id"] for c in admin.data()["categories"]}

        # drop the referencing event, then masjid can be deleted
        status, _ = admin.request("DELETE", f"/api/events/{eid}")
        assert status == 200, status
        status, _ = admin.request("DELETE", f"/api/masjids/{mid}")
        assert status == 200, status
    finally:
        admin.shutdown()


def test_event_lifecycle_and_status():
    admin = Admin()
    try:
        _, created = admin.request("POST", "/api/masjids", {"name": "Masjid Alwi", "district": "Kangar"})
        mid = created["id"]
        _, cat = admin.request("POST", "/api/categories", {"name": "Kuliyyah"})
        cid = cat["id"]

        status, ev = admin.request("POST", "/api/events", {
            "title": "Kuliyyah Dhuha",
            "masjid_id": mid,
            "date": "2026-09-01",
            "start_time": "09:30",
            "end_time": "10:30",
            "category_id": cid,
            "status": "draft",
        })
        assert status == 201, (status, ev)
        eid = ev["id"]
        assert eid.startswith("evt-20260901-"), eid

        # invalid status transition body -> 400
        status, resp = admin.request("POST", f"/api/events/{eid}/status", {"status": "banana"})
        assert status == 400, (status, resp)

        # publish -> completed (archive)
        for target in ("published", "postponed", "cancelled", "completed"):
            status, resp = admin.request("POST", f"/api/events/{eid}/status", {"status": target})
            assert status == 200, (target, status, resp)
            assert admin.data()["events"][0]["status"] == target

        # invalid date update -> 400 and record unchanged
        status, resp = admin.request("PUT", f"/api/events/{eid}",
                                     {"title": "X", "masjid_id": mid, "date": "bad"})
        assert status == 400, (status, resp)
        ev_after = admin.data()["events"][0]
        assert ev_after["date"] == "2026-09-01", ev_after
    finally:
        admin.shutdown()


def test_recurrence_and_preview():
    admin = Admin()
    try:
        _, created = admin.request("POST", "/api/masjids", {"name": "Masjid Alwi", "district": "Kangar"})
        mid = created["id"]

        status, ev = admin.request("POST", "/api/events", {
            "title": "Kuliyyah Mingguan",
            "masjid_id": mid,
            "date": "2026-09-07",
            "start_time": "20:00",
            "recurrence": {
                "type": "weekly",
                "days": ["monday", "friday"],
                "start_date": "2026-09-07",
                "exceptions": ["2026-09-14"],
            },
        })
        assert status == 201, (status, ev)
        eid = ev["id"]

        saved = admin.data()["events"][0]
        assert saved["recurrence"]["type"] == "weekly"
        assert saved["recurrence"]["exceptions"] == ["2026-09-14"]

        # preview returns html for the event
        status, preview = admin.request("POST", "/api/preview", {"type": "event", "id": eid})
        assert status == 200, (status, preview)
        assert "<html" in preview["html"]
        assert "Kuliyyah Mingguan" in preview["html"]

        # preview for unknown id -> 404
        status, _ = admin.request("POST", "/api/preview", {"type": "event", "id": "nope"})
        assert status == 404, status
    finally:
        admin.shutdown()


def test_validation_rollback():
    admin = Admin()
    try:
        _, created = admin.request("POST", "/api/masjids", {"name": "Masjid Rollback", "district": "Arau"})
        mid = created["id"]

        # create a valid event first
        status, ev = admin.request("POST", "/api/events", {
            "title": "Acara Baik", "masjid_id": mid,
            "date": "2026-09-02", "start_time": "20:00",
        })
        assert status == 201, (status, ev)
        eid = ev["id"]

        # now attempt a masjid whose events reference an unknown masjid via update
        # -> referential integrity check must reject and roll back everything
        status, resp = admin.request("PUT", f"/api/events/{eid}", {
            "title": "Acara Baik", "masjid_id": "masjid-tak-wujud",
            "date": "2026-09-02", "start_time": "20:00",
        })
        assert status == 400, (status, resp)
        assert any("masjid" in e for e in resp["errors"]), resp

        # rolled back: event still references the original masjid
        ev_after = admin.data()["events"][0]
        assert ev_after["masjid_id"] == mid, ev_after

        # add-masjid batch with an invalid event must roll back the masjid too
        status, resp = admin.request("POST", "/api/add-masjid", {
            "masjid": {"name": "Masjid Batch Gagal"},
            "events": [{"title": "", "date": "2026-09-03", "start_time": "20:00"}],
        })
        assert status == 400, (status, resp)
        assert not any(m["name"] == "Masjid Batch Gagal" for m in admin.data()["masjids"])
    finally:
        admin.shutdown()


def test_publish_mirrors_data():
    admin = Admin()
    try:
        _, created = admin.request("POST", "/api/masjids", {"name": "Masjid Publish", "district": "Kangar"})
        assert created["id"] == "masjid-publish"

        status, resp = admin.request("POST", "/api/publish", {})
        assert status == 200, (status, resp)
        assert resp["ok"] is True

        for name in DATA_FILES:
            assert (admin.public_dir / name).is_file(), f"missing mirror: {name}"

        mirror = json.loads((admin.public_dir / "masjids.json").read_text("utf-8"))
        assert any(m["id"] == "masjid-publish" for m in mirror)
    finally:
        admin.shutdown()


def test_district_editor_crud_and_references():
    admin = Admin()
    try:
        # new data dirs start with the official Perlis districts
        districts = admin.data()["districts"]
        assert any(d["id"] == "kangar" for d in districts), districts

        # create an editor
        status, editor = admin.request("POST", "/api/editors",
                                       {"name": "Ustaz Pentadbir", "email": "a@b.co"})
        assert status == 201, (status, editor)
        eid = editor["id"]
        assert eid == "editor-ustaz-pentadbir", eid

        # add a new district
        status, district = admin.request("POST", "/api/districts",
                                         {"name": "Titi Tinggi", "description": "Baharu"})
        assert status == 201, (status, district)
        did = district["id"]
        assert did == "titi-tinggi", did

        # masjid linking district_id + editor_id
        status, masjid = admin.request("POST", "/api/masjids", {
            "name": "Masjid Titi Tinggi",
            "district_id": did,
            "editor_id": eid,
        })
        assert status == 201, (status, masjid)
        mid = masjid["id"]
        assert masjid["record"]["district_id"] == did
        assert masjid["record"]["district"] == "Titi Tinggi", masjid["record"]
        assert masjid["record"]["editor_id"] == eid

        # updating the district name without changing district_id => mismatch must reject
        status, resp = admin.request("PUT", f"/api/districts/{did}",
                                     {"name": "Titi Tinggi Lama", "description": "Baharu"})
        assert status == 400, (status, resp)
        assert any("does not match" in e for e in resp["errors"]), resp

        # delete the referenced district -> blocked
        status, resp = admin.request("DELETE", f"/api/districts/{did}")
        assert status == 400, (status, resp)
        assert "referenced" in resp["errors"][0], resp

        # delete the referenced editor -> blocked
        status, resp = admin.request("DELETE", f"/api/editors/{eid}")
        assert status == 400, (status, resp)
        assert "referenced" in resp["errors"][0], resp

        # once the masjid is gone, both can be deleted
        status, _ = admin.request("DELETE", f"/api/masjids/{mid}")
        assert status == 200, status
        assert admin.request("DELETE", f"/api/districts/{did}")[0] == 200
        assert admin.request("DELETE", f"/api/editors/{eid}")[0] == 200
    finally:
        admin.shutdown()


def test_static_pages_served():
    admin = Admin()
    try:
        for page in ("/admin/index.html", "/admin/events.html", "/admin/event-editor.html",
                     "/admin/masjids.html", "/admin/speakers.html", "/admin/categories.html",
                     "/admin/districts.html", "/admin/editors.html",
                     "/admin/admin.css", "/admin/admin.js"):
            assert admin.status_of("GET", page) == 200, page
        assert admin.status_of("GET", "/admin/add-masjid.html") == 200
        assert admin.status_of("GET", "/api/data") == 200
    finally:
        admin.shutdown()


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
