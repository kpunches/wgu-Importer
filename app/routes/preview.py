import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

CODA_API_BASE = "https://coda.io/apis/v1"


class PreviewRequest(BaseModel):
    doc_id: str
    report: dict  # Full extraction report from /extract


def coda_headers():
    token = os.environ.get("CODA_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="CODA_API_TOKEN not configured")
    return {"Authorization": f"Bearer {token}"}


@router.post("")
async def preview(req: PreviewRequest):
    """
    Given an extraction report, read live Coda state and compute per-row
    diffs (new / update / existing / conflict) without writing anything.
    Returns an augmented report with diff decisions attached.
    """
    report = req.report
    doc_id = req.doc_id
    headers = coda_headers()

    diffs = []
    errors = []

    # ── Check course row exists ──────────────────────────────────────────────
    course_row_id = report.get("context", {}).get("course_row_id")
    if course_row_id:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CODA_API_BASE}/docs/{doc_id}/tables/grid-8i2Q6-eoTP/rows/{course_row_id}",
                headers=headers,
            )
        if resp.status_code == 200:
            diffs.append({
                "table": "_Courses",
                "row_id": course_row_id,
                "action": "update",
                "note": "Course row exists — will update course-level fields",
            })
        elif resp.status_code == 404:
            diffs.append({
                "table": "_Courses",
                "row_id": None,
                "action": "new",
                "note": "Course row not found — will create",
            })
        else:
            errors.append(f"_Courses lookup failed: HTTP {resp.status_code}")

    # ── Check _Progs | _Courses pairing ─────────────────────────────────────
    program_row_id = report.get("context", {}).get("program_row_id")
    if program_row_id and course_row_id:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CODA_API_BASE}/docs/{doc_id}/tables/grid-fEebuvIQBl/rows",
                headers=headers,
                params={"query": f"c-UaE_k1Ivfh:{course_row_id}"},
            )
        if resp.status_code == 200:
            rows = resp.json().get("items", [])
            if rows:
                diffs.append({
                    "table": "_Progs | _Courses",
                    "row_id": rows[0]["id"],
                    "action": "existing",
                    "note": "Program-course pairing already exists",
                })
            else:
                diffs.append({
                    "table": "_Progs | _Courses",
                    "row_id": None,
                    "action": "new",
                    "note": "Will create program-course pairing",
                })
        else:
            errors.append(f"_Progs|_Courses lookup failed: HTTP {resp.status_code}")

    # ── Competency checks would go here (Phase 3) ───────────────────────────
    # For now, flag all competencies as new (safe default)
    comps = report.get("competencies", [])
    for comp in comps:
        diffs.append({
            "table": "_Comps",
            "row_id": None,
            "action": "new",
            "note": f"Competency {comp.get('order')}: {comp.get('title')} — will create",
        })

    return {
        "doc_id": doc_id,
        "diffs": diffs,
        "errors": errors,
        "ready_to_commit": len(errors) == 0,
    }
