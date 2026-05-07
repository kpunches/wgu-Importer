import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter()

CODA_API_BASE = "https://coda.io/apis/v1"

# ── TABLE GRID IDs ────────────────────────────────────────────────────────────
GRID_COURSES          = "grid-8i2Q6-eoTP"
GRID_COMPS            = "grid-dXlcRqqYc3"
GRID_COURSES_COMPS    = "grid-VZwiNNkP1B"
GRID_PROGS_COURSES    = "grid-fEebuvIQBl"
GRID_PCC              = "grid-TmGA_WNe3_"
GRID_RSDS             = "grid-5p9sHmnPst"
GRID_PCC_RSDS         = "grid-bYtzEaQQ0t"

# ── COLUMN IDs: _Comps (grid-dXlcRqqYc3) ─────────────────────────────────────
COL_COMPS_TITLE       = "c-IUDUEqDEZ_"
COL_COMPS_STATEMENT   = "c-oImCmcB9nT"
COL_COMPS_AI          = "c-lnB9KKF_Tu"
COL_COMPS_STATUS      = "c-WGYuyaBsT2"
COL_COMPS_IMPORTED_AT = "c-lcOpEkCj5R"
COL_COMPS_SOURCE      = "c-dMBdJWmVEk"
COL_COMPS_UPLOADED_BY = "c-fZh5qSDB48"
COL_COMPS_REQUEST_ID  = "c-CKlvL-K8Cm"

# ── COLUMN IDs: _Courses_Comps (grid-VZwiNNkP1B) ─────────────────────────────
COL_CC_COURSE         = "c-xObNqSoOEJ"   # Course LU
COL_CC_COMP           = "c-HpCOy_i9GQ"   # Competency
COL_CC_ORDER          = "c-lSdUQo1MHL"   # Comp Order
COL_CC_LEVEL          = "c-kEEJh01EC8"   # Competency Level
COL_CC_MODALITY       = "c-YfHIST3JLm"   # Competency Modality
COL_CC_RATIONALE      = "c-kTJHnj27ap"   # Competency Modality Rationale
COL_CC_EVIDENCE       = "c-wQHNTJK75J"   # Potential Evidence
COL_CC_SCOPE_IN       = "c-UvwfC-FDBx"   # Scope - IN
COL_CC_SCOPE_NOTES    = "c-HEZKT1VZvV"   # Additional Competency Scope Notes
COL_CC_STANDARDS      = "c-TeYyPpbGcv"   # Competency Standards Alignment

# ── COLUMN IDs: _Progs_Courses_Comps / PCC (grid-TmGA_WNe3_) ─────────────────
COL_PCC_PC_PAIRING    = "c-WLMD7Ir-os"   # Program to Course Pairing
COL_PCC_COMP          = "c-D-u5Q1gcJp"   # Competency (Canonical)
COL_PCC_AI            = "c-zhDWM-vjeQ"
COL_PCC_STATUS        = "c-kStSa0xNn8"
COL_PCC_IMPORTED_AT   = "c-OajUbwnxYC"
COL_PCC_SOURCE        = "c-HHLc0ISgLQ"
COL_PCC_UPLOADED_BY   = "c-pQA3YBpBBd"
COL_PCC_REQUEST_ID    = "c-miOFU-QNNE"

# ── COLUMN IDs: _RSDs (grid-5p9sHmnPst) ──────────────────────────────────────
COL_RSD_CATEGORY      = "c-oXXx9IvgZ2"   # Skill Category
COL_RSD_TITLE         = "c-sX7bPcfCfg"   # Skill Title
COL_RSD_STATEMENT     = "c-4yIzf4t4cD"   # Skill Statement
COL_RSD_AI            = "c-ieCwpkh-uU"
COL_RSD_STATUS        = "c-3eyQ39_1JY"
COL_RSD_IMPORTED_AT   = "c-ynte8o8CEE"
COL_RSD_SOURCE        = "c-b_DfGco_MJ"
COL_RSD_UPLOADED_BY   = "c-itn4wSDE40"
COL_RSD_REQUEST_ID    = "c-FB6mFJnPdl"

# ── COLUMN IDs: _PCC_RSDs (grid-bYtzEaQQ0t) ──────────────────────────────────
COL_PCCR_SKILL        = "c-x8Iymo5syn"   # Workforce Skill
COL_PCCR_PCC          = "c-5n6qQLcwC1"   # Program Course Competency
COL_PCCR_AI           = "c-u6eatIMrgz"
COL_PCCR_STATUS       = "c-fRPb4a2q9u"
COL_PCCR_IMPORTED_AT  = "c-ZpBwHK9f8h"
COL_PCCR_SOURCE       = "c-qid2Rt1-uB"
COL_PCCR_UPLOADED_BY  = "c-m0nrE2lMCB"
COL_PCCR_REQUEST_ID   = "c-d6bIQgT9Px"


class CommitRequest(BaseModel):
    doc_id: str
    report: dict
    diffs: list
    request_id: str
    uploaded_by: str = "importer"


def coda_headers():
    token = os.environ.get("CODA_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="CODA_API_TOKEN not configured")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def meta_cells(request_id, uploaded_by, source_filename,
               ai_col, status_col, at_col, source_col, by_col, rid_col):
    """Standard import metadata cells written to every row."""
    return [
        {"column": ai_col,     "value": True},
        {"column": status_col, "value": "Imported"},
        {"column": at_col,     "value": datetime.now(timezone.utc).isoformat()},
        {"column": source_col, "value": source_filename},
        {"column": by_col,     "value": uploaded_by},
        {"column": rid_col,    "value": request_id},
    ]


async def create_row(client, doc_id, grid_id, cells, headers):
    payload = {"rows": [{"cells": cells}]}
    resp = await client.post(
        f"{CODA_API_BASE}/docs/{doc_id}/tables/{grid_id}/rows",
        json=payload, headers=headers,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Coda write failed [{grid_id}]: {resp.status_code} {resp.text[:300]}"
        )
    created = resp.json().get("addedRowIds", [])
    return created[0] if created else None


async def update_row(client, doc_id, grid_id, row_id, cells, headers):
    payload = {"row": {"cells": cells}}
    resp = await client.put(
        f"{CODA_API_BASE}/docs/{doc_id}/tables/{grid_id}/rows/{row_id}",
        json=payload, headers=headers,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Coda update failed [{grid_id}/{row_id}]: {resp.status_code} {resp.text[:300]}"
        )


@router.post("")
async def commit(req: CommitRequest):
    report       = req.report
    doc_id       = req.doc_id
    headers      = coda_headers()
    log          = []
    written      = 0
    source_file  = report.get("context", {}).get("source_filename", "")
    course_row_id   = report.get("context", {}).get("course_row_id")
    program_row_id  = report.get("context", {}).get("program_row_id")
    competencies    = report.get("competencies", [])

    async with httpx.AsyncClient(timeout=30.0) as client:

        # ── Step 1-2: Update course-level fields in _Courses ─────────────────
        cl = report.get("course_level", {})
        course_cells = [
            {"column": "c-sgyJdn2bVc", "value": report.get("course_code", "")},
            {"column": "c-nXrSiX6Q7R", "value": report.get("course_name", "")},
            {"column": "c-fBcr85YOgL",  "value": cl.get("scope_notes", "")},
            {"column": "c-sWmJbOaqEx",    "value": cl.get("modality", "")},
            {"column": "c-k928L_ucpO",     "value": cl.get("assessment_rationale", "")},
            {"column": "c-XLbFh1-a65",    "value": cl.get("evidence", "")},
            {"column": "c-lTxHu4kAH6",  "value": cl.get("lr_strategy", "")},
            {"column": "c-orP3pac0Hk", "value": cl.get("asmt_notes", "") or ""},
            {"column": "c-mrpeRPfccr",   "value": cl.get("tools_tech", "")},
        ]

        # Add metadata to course cells
        course_cells += meta_cells(
            req.request_id, req.uploaded_by, source_file,
            "c-865MECYmk6", "c-5BxR50ghP4", "c-6Wr0O_2PFM",
            "c-JHGBvEBY-U", "c-8aw3e0nVap", "c-EKudXRvKLK"
        )

        course_diff = next((d for d in req.diffs if d["table"] == "_Courses"), None)
        if course_diff and course_diff["action"] == "update" and course_row_id:
            await update_row(client, doc_id, GRID_COURSES, course_row_id, course_cells, headers)
            log.append(f"✓ Step 1-2: Updated _Courses {course_row_id}")
        else:
            course_row_id = await create_row(client, doc_id, GRID_COURSES, course_cells, headers)
            log.append(f"✓ Step 1-2: Created _Courses {course_row_id}")
        written += 1

        # ── Step 3: _Progs | _Courses pairing ────────────────────────────────
        pc_diff = next((d for d in req.diffs if d["table"] == "_Progs | _Courses"), None)
        pc_row_id = None
        if pc_diff and pc_diff["action"] == "existing":
            pc_row_id = pc_diff.get("row_id")
            log.append(f"  Step 3: _Progs|_Courses pairing exists ({pc_row_id}) — skipped")
        else:
            pc_cells = [
                {"column": "c-UaE_k1Ivfh", "value": course_row_id},
                {"column": "c-aGpuFk4ifn", "value": program_row_id},
            ]
            pc_row_id = await create_row(client, doc_id, GRID_PROGS_COURSES, pc_cells, headers)
            log.append(f"✓ Step 3: Created _Progs|_Courses {pc_row_id}")
            written += 1

        # ── Steps 4-9: Per-competency cascade ─────────────────────────────────
        for comp in competencies:
            order = comp.get("order", 0)
            title = comp.get("title", "")

            # Step 4: Create competency in _Comps
            comp_cells = [
                {"column": COL_COMPS_TITLE,     "value": title},
                {"column": COL_COMPS_STATEMENT,  "value": comp.get("statement", "")},
            ] + meta_cells(
                req.request_id, req.uploaded_by, source_file,
                COL_COMPS_AI, COL_COMPS_STATUS, COL_COMPS_IMPORTED_AT,
                COL_COMPS_SOURCE, COL_COMPS_UPLOADED_BY, COL_COMPS_REQUEST_ID
            )
            comp_row_id = await create_row(client, doc_id, GRID_COMPS, comp_cells, headers)
            log.append(f"✓ Step 4: Created _Comps [{order}] {title} → {comp_row_id}")
            written += 1

            # Step 5: Map competency to course in _Courses_Comps
            cc_cells = [
                {"column": COL_CC_COURSE,     "value": course_row_id},
                {"column": COL_CC_COMP,        "value": comp_row_id},
                {"column": COL_CC_ORDER,        "value": order},
                {"column": COL_CC_LEVEL,        "value": comp.get("level")},
                {"column": COL_CC_MODALITY,     "value": comp.get("modality", "")},
                {"column": COL_CC_RATIONALE,    "value": comp.get("modality_rationale", "")},
                {"column": COL_CC_EVIDENCE,     "value": comp.get("evidence", "")},
                {"column": COL_CC_SCOPE_NOTES,  "value": comp.get("scope_notes", "")},
                {"column": COL_CC_STANDARDS,    "value": comp.get("standards_alignment", "")},
            ]
            cc_row_id = await create_row(client, doc_id, GRID_COURSES_COMPS, cc_cells, headers)
            log.append(f"✓ Step 5: Created _Courses_Comps [{order}] → {cc_row_id}")
            written += 1

            # Step 6: Create PCC row in _Progs_Courses_Comps
            pcc_cells = [
                {"column": COL_PCC_PC_PAIRING, "value": pc_row_id},
                {"column": COL_PCC_COMP,        "value": comp_row_id},
            ] + meta_cells(
                req.request_id, req.uploaded_by, source_file,
                COL_PCC_AI, COL_PCC_STATUS, COL_PCC_IMPORTED_AT,
                COL_PCC_SOURCE, COL_PCC_UPLOADED_BY, COL_PCC_REQUEST_ID
            )
            pcc_row_id = await create_row(client, doc_id, GRID_PCC, pcc_cells, headers)
            log.append(f"✓ Step 6: Created PCC [{order}] → {pcc_row_id}")
            written += 1

            # Steps 7-9: Skills
            for skill in comp.get("skills", []):
                # Step 7: Create skill in _RSDs
                rsd_cells = [
                    {"column": COL_RSD_CATEGORY,  "value": skill.get("category", "")},
                    {"column": COL_RSD_TITLE,      "value": skill.get("title", "")},
                    {"column": COL_RSD_STATEMENT,  "value": skill.get("statement", "")},
                ] + meta_cells(
                    req.request_id, req.uploaded_by, source_file,
                    COL_RSD_AI, COL_RSD_STATUS, COL_RSD_IMPORTED_AT,
                    COL_RSD_SOURCE, COL_RSD_UPLOADED_BY, COL_RSD_REQUEST_ID
                )
                rsd_row_id = await create_row(client, doc_id, GRID_RSDS, rsd_cells, headers)
                log.append(f"  ✓ Step 7: Created RSD '{skill.get('title')}' → {rsd_row_id}")
                written += 1

                # Step 8: Map skill to PCC in _PCC_RSDs
                pccr_cells = [
                    {"column": COL_PCCR_SKILL, "value": rsd_row_id},
                    {"column": COL_PCCR_PCC,   "value": pcc_row_id},
                ] + meta_cells(
                    req.request_id, req.uploaded_by, source_file,
                    COL_PCCR_AI, COL_PCCR_STATUS, COL_PCCR_IMPORTED_AT,
                    COL_PCCR_SOURCE, COL_PCCR_UPLOADED_BY, COL_PCCR_REQUEST_ID
                )
                pccr_row_id = await create_row(client, doc_id, GRID_PCC_RSDS, pccr_cells, headers)
                log.append(f"  ✓ Step 8: Created _PCC_RSDs → {pccr_row_id}")
                written += 1

        log.append(f"✓ Commit complete — {written} rows written to {doc_id}")

    return {
        "success": True,
        "request_id": req.request_id,
        "rows_written": written,
        "log": log,
    }
