import csv
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def parse_company_size(raw_val: Any) -> Tuple[Optional[int], Optional[str]]:
    if raw_val is None:
        return None, "Missing company size"
    s = str(raw_val).strip()
    if not s or s.upper() in ("NA", "N/A", "NONE", "NULL", "UNKNOWN"):
        return None, "Company size unspecified"
    try:
        cleaned = "".join(ch for ch in s if ch.isdigit())
        if not cleaned:
            return None, f"Invalid company size format: {raw_val}"
        val = int(cleaned)
        return val, None
    except ValueError:
        return None, f"Could not parse company size: {raw_val}"


def parse_date(raw_val: Any) -> Tuple[Optional[datetime], Optional[str]]:
    if raw_val is None:
        return None, "Missing interaction date"
    s = str(raw_val).strip()
    if not s or s.upper() in ("NA", "N/A", "NONE", "NULL", "UNKNOWN"):
        return None, "Interaction date unspecified"
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt), None
        except ValueError:
            continue
    return None, f"Unrecognized date format: {raw_val}"


def sanitize_lead(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    name = str(raw.get("name", "")).strip()
    company = str(raw.get("company", "")).strip()
    industry = str(raw.get("industry", "")).strip()
    source = str(raw.get("source", "")).strip()
    raw_size = raw.get("company_size")
    raw_date = raw.get("last_interaction_date")

    parsed_size, size_issue = parse_company_size(raw_size)
    parsed_date, date_issue = parse_date(raw_date)

    data_issues = []
    if not name or name.upper() in ("NA", "UNKNOWN"):
        data_issues.append("Missing or placeholder contact name")
    if not company or company.upper() in ("NA", "UNKNOWN"):
        data_issues.append("Missing company name")
    if not industry or industry.upper() in ("NA", "UNKNOWN", "UNKNOWN SECTOR"):
        data_issues.append("Unknown or unmapped industry")
    if not source or source.upper() in ("NA", "UNKNOWN", "UNKNOWN SOURCE"):
        data_issues.append("Missing acquisition source")
    if size_issue:
        data_issues.append(size_issue)
    if date_issue:
        data_issues.append(date_issue)

    return {
        "lead_id": f"LEAD-{index:04d}",
        "raw_index": index,
        "name": name if name else "Unknown Contact",
        "company": company if company else "Unknown Company",
        "company_size": parsed_size,
        "raw_size": raw_size,
        "industry": industry if industry else "Unknown",
        "source": source if source else "Unknown",
        "last_interaction_date": parsed_date.strftime("%Y-%m-%d") if parsed_date else None,
        "raw_date": raw_date,
        "data_issues": data_issues,
        "has_data_issues": len(data_issues) > 0,
    }


def load_leads_from_csv(file_path: str) -> List[Dict[str, Any]]:
    leads = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            leads.append(sanitize_lead(row, idx))
    return leads
