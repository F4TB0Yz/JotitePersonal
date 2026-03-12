import argparse
import json
from typing import Any

import requests


SESSION_COOKIE_NAME = "jt_session"


def _print_result(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_smoke(base_url: str, username: str, password: str, token: str | None) -> int:
    session = requests.Session()

    login_resp = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    login_payload = {
        "status": login_resp.status_code,
        "body": login_resp.json() if login_resp.headers.get("content-type", "").startswith("application/json") else login_resp.text,
    }
    _print_result("Login", login_payload)
    if login_resp.status_code != 200:
        return 1

    cookie = session.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        print("No se obtuvo cookie de sesión; abortando.")
        return 1

    manual_cookie = {"Cookie": f"{SESSION_COOKIE_NAME}={cookie}"}

    if token:
        token_resp = requests.post(
            f"{base_url}/api/config/token",
            headers=manual_cookie,
            json={"authToken": token},
            timeout=30,
        )
        token_payload = {
            "status": token_resp.status_code,
            "body": token_resp.json() if token_resp.headers.get("content-type", "").startswith("application/json") else token_resp.text,
        }
        _print_result("Update authToken", token_payload)

    snapshots_resp = requests.get(
        f"{base_url}/api/returns/snapshots?status=2&limit=5",
        headers=manual_cookie,
        timeout=45,
    )
    _print_result(
        "GET /api/returns/snapshots",
        {
            "status": snapshots_resp.status_code,
            "body": snapshots_resp.json() if snapshots_resp.headers.get("content-type", "").startswith("application/json") else snapshots_resp.text,
        },
    )

    sync_resp = requests.post(
        f"{base_url}/api/returns/sync",
        headers=manual_cookie,
        json={
            "date_from": "2026-03-10",
            "date_to": "2026-03-12",
            "statuses": [1, 2, 3],
            "size": 20,
            "max_pages": 1,
        },
        timeout=60,
    )
    _print_result(
        "POST /api/returns/sync",
        {
            "status": sync_resp.status_code,
            "body": sync_resp.json() if sync_resp.headers.get("content-type", "").startswith("application/json") else sync_resp.text,
        },
    )

    app_resp = requests.get(
        f"{base_url}/api/returns/applications?status=3&date_from=2026-03-10&date_to=2026-03-12&current=1&size=20",
        headers=manual_cookie,
        timeout=60,
    )
    _print_result(
        "GET /api/returns/applications",
        {
            "status": app_resp.status_code,
            "body": app_resp.json() if app_resp.headers.get("content-type", "").startswith("application/json") else app_resp.text,
        },
    )

    printable_resp = requests.get(
        f"{base_url}/api/returns/printable?date_from=2026-03-10&date_to=2026-03-12&current=1&size=20",
        headers=manual_cookie,
        timeout=60,
    )
    printable_body = printable_resp.json() if printable_resp.headers.get("content-type", "").startswith("application/json") else printable_resp.text
    _print_result(
        "GET /api/returns/printable",
        {
            "status": printable_resp.status_code,
            "body": printable_body,
        },
    )

    sample_waybill = None
    if isinstance(printable_body, dict):
        records = (((printable_body.get("data") or {}).get("records") or []))
        if records:
            sample_waybill = records[0].get("waybill_no")

    if sample_waybill:
        print_url_resp = requests.post(
            f"{base_url}/api/returns/print-url",
            headers=manual_cookie,
            json={"waybill_no": sample_waybill, "template_size": 1, "pring_type": 1, "printer": 0},
            timeout=60,
        )
        _print_result(
            "POST /api/returns/print-url",
            {
                "status": print_url_resp.status_code,
                "body": print_url_resp.json() if print_url_resp.headers.get("content-type", "").startswith("application/json") else print_url_resp.text,
            },
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test endpoints de devoluciones")
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="test123")
    parser.add_argument("--token", default=None, help="Auth token J&T para actualizar vía /api/config/token antes del test")
    args = parser.parse_args()

    return run_smoke(args.base_url, args.username, args.password, args.token)


if __name__ == "__main__":
    raise SystemExit(main())
