"""Report export tests (CSV, XLSX, PDF)."""

from __future__ import annotations

import io

import openpyxl


def test_csv_export(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/reports/datasets/{seeded_dataset}.csv", headers=user_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.content.decode("utf-8")
    assert "timestamp,value" in body
    assert len(body.splitlines()) >= 47  # header + meta rows + data


def test_xlsx_export(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/reports/datasets/{seeded_dataset}.xlsx", headers=user_headers
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws.title == "test-revenue"
    assert ws.max_row >= 46


def test_pdf_export(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/reports/datasets/{seeded_dataset}.pdf", headers=user_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


def test_unsupported_export_format(client, user_headers, seeded_dataset):
    resp = client.get(
        f"/api/v1/reports/datasets/{seeded_dataset}.json", headers=user_headers
    )
    assert resp.status_code == 422


def test_export_requires_auth(client, seeded_dataset):
    assert client.get(f"/api/v1/reports/datasets/{seeded_dataset}.csv").status_code == 401
