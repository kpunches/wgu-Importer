"""
CCW (Course Competency Worksheet) extractor.
Uses python-docx for DOCX files, PyMuPDF for PDFs.
Preserves hyperlinks as markdown [text](url) inline.
"""
import re
from docx import Document
from docx.oxml.ns import qn


def _build_rel_map(doc):
    """Return rId -> URL map from document relationships."""
    rels = {}
    for rel in doc.part.rels.values():
        if "hyperlink" in rel.reltype:
            rels[rel.rId] = rel._target
    return rels


def _extract_para_with_links(para, rels):
    """Extract paragraph text with hyperlinks as markdown [text](url)."""
    result = []
    for child in para._p:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "hyperlink":
            r_id = child.get(qn("r:id"))
            url = rels.get(r_id, "")
            text = "".join(
                r.text for r in child.findall(".//" + qn("w:t")) if r.text
            )
            result.append(f"[{text}]({url})" if url and text else text)
        elif tag == "r":
            t = child.find(qn("w:t"))
            if t is not None and t.text:
                result.append(t.text)
    return "".join(result)


def _extract_cell(cell, rels):
    """Extract all paragraphs in a cell, preserving hyperlinks."""
    parts = []
    for para in cell.paragraphs:
        text = _extract_para_with_links(para, rels)
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _parse_modality_and_rationale(text):
    """Split 'Modality: OA Rationale: ...' into components."""
    modality = ""
    rationale = text
    m = re.match(r"Modality:\s*(\S+)\s*Rationale:\s*(.*)", text, re.DOTALL)
    if m:
        modality = m.group(1).strip()
        rationale = m.group(2).strip()
    return modality, rationale


def _parse_evidence(text):
    """Split combined assessment text into evidence and modality/rationale."""
    # Evidence text often follows the modality block
    return text.strip()


def extract_ccw(file_path: str, context: dict) -> dict:
    """
    Extract structured data from a CCW DOCX file.
    Returns the full extraction report dict.
    """
    doc = Document(file_path)
    rels = _build_rel_map(doc)
    tables = doc.tables

    unknown_content = []
    errors = []

    # ── Course-level tables (Tables 0-3) ─────────────────────────────────────
    course_level = {
        "scope_notes": "",
        "modality": "",
        "assessment_rationale": "",
        "evidence": "",
        "lr_strategy": "",
        "tools_tech": "",
        "asmt_notes": None,
    }

    TABLE_LABELS = {
        "course level scope notes": "scope_notes",
        "course level assessment strategy and recommendations": "assessment_block",
        "course level lr strategy and recommendations": "lr_strategy",
        "course level critical tools and technologies strategy and recommendations": "tools_tech",
    }

    comp_tables = []

    for i, table in enumerate(tables):
        if len(table.rows) < 2:
            unknown_content.append({
                "field": f"Table {i} (unexpected shape)",
                "content": _extract_cell(table.rows[0].cells[0], rels) if table.rows else "",
            })
            continue

        header = _extract_cell(table.rows[0].cells[0], rels).strip().lower()
        content = _extract_cell(table.rows[1].cells[0], rels).strip()

        matched = False
        for label, field in TABLE_LABELS.items():
            if label in header:
                matched = True
                if field == "assessment_block":
                    # Parse "Modality: X Rationale: ..." from content
                    modality, rationale = _parse_modality_and_rationale(content)
                    course_level["modality"] = modality
                    course_level["assessment_rationale"] = rationale
                    # Evidence is a separate field if present after rationale
                    # For CCW it's combined; split on known evidence marker
                    if "Evidence" in content:
                        ev_split = content.split("Evidence", 1)
                        course_level["assessment_rationale"] = ev_split[0].replace(f"Modality: {modality}", "").replace("Rationale:", "").strip()
                        course_level["evidence"] = "Evidence" + ev_split[1]
                else:
                    course_level[field] = content
                break

        if not matched:
            # Competency tables have "Competency Title:" in row[0]
            if "competency title:" in header or (
                len(table.columns) == 3 and len(table.rows) >= 4
            ):
                comp_tables.append(table)
            else:
                unknown_content.append({"field": f"Table {i}: {header[:60]}", "content": content[:500]})

    # ── Competency tables ─────────────────────────────────────────────────────
    competencies = []

    for order, table in enumerate(comp_tables, start=1):
        comp = {
            "order": order,
            "title": "",
            "statement": "",
            "level": None,
            "modality": "",
            "modality_rationale": "",
            "evidence": "",
            "scope_notes": "",
            "standards_alignment": "",
            "skills": [],
        }

        ROW_LABELS = {
            "competency title:": "title",
            "competency statement:": "statement",
            "target level": "level",
            "assessment recommendations": "assessment_block",
            "additional scope notes and requirements": "scope_notes",
            "cswe alignment": "standards_alignment",
        }

        skills_start = None
        skills_end = None

        for r_idx, row in enumerate(table.rows):
            if not row.cells:
                continue
            label = _extract_cell(row.cells[0], rels).strip().lower()

            # Skills rows: header row has "skill category / skill title / skill statements"
            if "skill category" in label:
                skills_start = r_idx + 1
                continue
            if skills_start and "competency detail" in label:
                skills_end = r_idx
                skills_start = None

            matched = False
            for key, field in ROW_LABELS.items():
                if key in label:
                    matched = True
                    # Use col[1] for data when table has 3 cols, else col[0]
                    data_cell_idx = 1 if len(row.cells) > 1 else 0
                    value = _extract_cell(row.cells[data_cell_idx], rels).strip()

                    # Strip the label prefix from inline values
                    for prefix in ["Competency Title:", "Competency Statement:", "Target Level"]:
                        if value.lower().startswith(prefix.lower()):
                            value = value[len(prefix):].strip()

                    if field == "level":
                        try:
                            comp["level"] = int(value)
                        except ValueError:
                            comp["level"] = None
                            errors.append(f"Comp {order}: could not parse level '{value}'")
                    elif field == "assessment_block":
                        modality, rationale = _parse_modality_and_rationale(value)
                        comp["modality"] = modality
                        comp["modality_rationale"] = rationale
                    elif field == "title":
                        comp["title"] = value.split("\n")[0].strip()
                    else:
                        comp[field] = value
                    break

            # Collect skill rows
            if skills_start and r_idx >= skills_start and (skills_end is None or r_idx < skills_end):
                if len(row.cells) >= 3:
                    cat  = _extract_cell(row.cells[0], rels).strip()
                    title = _extract_cell(row.cells[1], rels).strip()
                    stmt  = _extract_cell(row.cells[2], rels).strip()
                    if cat and title and stmt:
                        comp["skills"].append({
                            "category": cat,
                            "title": title,
                            "statement": stmt,
                        })

        competencies.append(comp)

    # ── Table row count estimates ─────────────────────────────────────────────
    n_comps = len(competencies)
    n_skills = sum(len(c["skills"]) for c in competencies)

    tables_summary = [
        {"name": "_Courses",               "new": 0, "updated": 1, "existing": 1},
        {"name": "_Comps",                 "new": n_comps, "updated": 0, "existing": 0},
        {"name": "_Courses | _Comps",      "new": n_comps, "updated": 0, "existing": 0},
        {"name": "_Progs | _Courses",      "new": 0, "updated": 0, "existing": 1},
        {"name": "_Progs_Courses | _Comps","new": n_comps, "updated": 0, "existing": 0},
        {"name": "_RSDs (Workforce Skills)","new": n_skills, "updated": 0, "existing": 0},
        {"name": "_PCC | _RSDs",           "new": n_skills, "updated": 0, "existing": 0},
        {"name": "DG_Courses L1 Sections", "new": 1, "updated": 0, "existing": 0},
    ]

    return {
        "doc_type": "CCW",
        "course_name": context.get("course_name", ""),
        "course_code": context.get("course_code", ""),
        "is_redevelopment": False,
        "previous_course_code": None,
        "context": context,
        "course_level": course_level,
        "competencies": competencies,
        "unknown_content": unknown_content,
        "tables": tables_summary,
        "errors": errors,
    }
