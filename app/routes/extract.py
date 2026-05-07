import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.extractors.ccw import extract_ccw
from app.extractors.ssd import extract_ssd

router = APIRouter()

SUPPORTED_TYPES = ["CCW", "SSD"]


@router.post("")
async def extract(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    doc_id: str = Form(...),
    program_row_id: str = Form(...),
    program_display: str = Form(...),
    program_subject: str = Form(...),
    course_row_id: str = Form(...),
    course_name: str = Form(...),
    course_code: str = Form(default=""),
):
    """
    Accept a CCW or SSD file upload and return a structured extraction report.
    No writes to Coda occur here — propose-only.
    """
    if doc_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported doc_type '{doc_type}'. Must be one of {SUPPORTED_TYPES}",
        )

    allowed_extensions = {
        "CCW": [".pdf", ".docx"],
        "SSD": [".pdf", ".docx"],
    }
    filename = file.filename or ""
    ext = os.path.splitext(filename)[-1].lower()
    if ext not in allowed_extensions[doc_type]:
        raise HTTPException(
            status_code=400,
            detail=f"{doc_type} expects {allowed_extensions[doc_type]}, got '{ext}'",
        )

    # Write upload to a temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    context = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "program_row_id": program_row_id,
        "program_display": program_display,
        "program_subject": program_subject,
        "course_row_id": course_row_id,
        "course_name": course_name,
        "course_code": course_code,
        "source_filename": filename,
    }

    try:
        if doc_type == "CCW":
            report = extract_ccw(tmp_path, context)
        elif doc_type == "SSD":
            report = extract_ssd(tmp_path, context)
        else:
            raise HTTPException(status_code=400, detail="Unsupported doc_type")
    finally:
        os.unlink(tmp_path)

    return report
