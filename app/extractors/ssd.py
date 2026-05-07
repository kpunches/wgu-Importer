"""
SSD (Scope and Sequence Document) extractor — Phase 2 stub.
Full implementation follows CCW reference implementation.
"""


def extract_ssd(file_path: str, context: dict) -> dict:
    return {
        "doc_type": "SSD",
        "course_name": context.get("course_name", ""),
        "course_code": context.get("course_code", ""),
        "is_redevelopment": False,
        "previous_course_code": None,
        "context": context,
        "course_level": {},
        "competencies": [],
        "unknown_content": [
            {"field": "SSD extraction", "content": "SSD extractor not yet implemented — Phase 2"}
        ],
        "tables": [],
        "errors": ["SSD extraction not yet implemented"],
    }
