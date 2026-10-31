from datetime import datetime
from typing import Any, Dict, List, Tuple


def evaluate_company_size(size: Any) -> Tuple[float, str]:
    if size is None:
        return 4.0, "Company size missing (needs manual verification)"
    if size < 1:
        return 1.0, "Invalid size (<=0)"
    if size < 10:
        return 2.0, f"Micro-team ({size} employees) below mid-market threshold"
    if 10 <= size < 20:
        return 5.0, f"Early startup ({size} employees), limited budget"
    if 20 <= size < 50:
        return 7.5, f"Growing SMB ({size} employees)"
    if 50 <= size <= 2000:
        return 10.0, f"Ideal mid-market fit ({size} employees)"
    if 2000 < size <= 5000:
        return 7.0, f"Large enterprise ({size} employees), longer procurement"
    return 4.0, f"Mega enterprise ({size} employees), requires strategic enterprise sales"


def evaluate_industry(industry: str, config: Dict[str, Any]) -> Tuple[float, str]:
    if not industry or industry.lower() in ("unknown", "unknown sector"):
        return 2.5, "Industry unknown or unmapped"

    rubric_cfg = config.get("rubric", {}).get("factors", {}).get("industry_fit", {})
    tier_1 = {s.lower() for s in rubric_cfg.get("tier_1", [])}
    tier_2 = {s.lower() for s in rubric_cfg.get("tier_2", [])}

    ind_lower = industry.lower()
    if any(t in ind_lower or ind_lower in t for t in tier_1):
        return 10.0, f"{industry} is core target vertical"
    if any(t in ind_lower or ind_lower in t for t in tier_2):
        return 6.5, f"{industry} is secondary/adjacent vertical"
    return 2.5, f"{industry} is non-core vertical"


def evaluate_source(source: str, config: Dict[str, Any]) -> Tuple[float, str]:
    if not source or source.lower() in ("unknown", "unknown source"):
        return 2.0, "Source unspecified"

    rubric_cfg = config.get("rubric", {}).get("factors", {}).get("source_intent", {})
    high_intent = {s.lower() for s in rubric_cfg.get("high_intent", [])}
    medium_intent = {s.lower() for s in rubric_cfg.get("medium_intent", [])}
    low_intent = {s.lower() for s in rubric_cfg.get("low_intent", [])}

    src_lower = source.lower()
    if any(s in src_lower for s in high_intent):
        return 10.0, f"High direct intent ({source})"
    if any(s in src_lower for s in medium_intent):
        if "referral" in src_lower:
            return 8.5, "Warm referral"
        return 6.5, f"Engaged attendee ({source})"
    if any(s in src_lower for s in low_intent):
        if "content" in src_lower:
            return 4.5, "Passive content download"
        return 3.5, "Cold outbound outreach"
    return 3.0, f"Unclassified source ({source})"


def evaluate_recency(date_str: Any, reference_date_str: str) -> Tuple[float, str]:
    if not date_str:
        return 4.0, "Interaction date missing"
    try:
        dt = datetime.strptime(str(date_str), "%Y-%m-%d")
        ref_dt = datetime.strptime(reference_date_str, "%Y-%m-%d")
        delta_days = (ref_dt - dt).days
    except Exception:
        return 4.0, f"Unable to parse date: {date_str}"

    if delta_days < 0:
        return 9.0, f"Interaction registered recently ({date_str})"
    if delta_days <= 14:
        return 10.0, f"Hot lead ({delta_days} days ago)"
    if delta_days <= 35:
        return 8.5, f"Recent interaction ({delta_days} days ago)"
    if delta_days <= 60:
        return 6.5, f"Warm interaction ({delta_days} days ago)"
    if delta_days <= 120:
        return 4.0, f"Cooling lead ({delta_days} days ago)"
    return 1.5, f"Stale interaction ({delta_days} days ago)"


def score_lead(lead: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    factors_cfg = config.get("rubric", {}).get("factors", {})
    w_size = factors_cfg.get("company_size", {}).get("weight", 0.30)
    w_ind = factors_cfg.get("industry_fit", {}).get("weight", 0.25)
    w_src = factors_cfg.get("source_intent", {}).get("weight", 0.25)
    w_rec = factors_cfg.get("interaction_recency", {}).get("weight", 0.20)

    ref_date = config.get("pipeline", {}).get("target_reference_date", "2024-01-20")

    s_size, r_size = evaluate_company_size(lead.get("company_size"))
    s_ind, r_ind = evaluate_industry(lead.get("industry", ""), config)
    s_src, r_source = evaluate_source(lead.get("source", ""), config)
    s_rec, r_rec = evaluate_recency(lead.get("last_interaction_date"), ref_date)

    composite = (s_size * w_size) + (s_ind * w_ind) + (s_src * w_src) + (s_rec * w_rec)
    final_score = round(composite, 1)

    thresholds = config.get("decision_thresholds", {})
    qual_min = thresholds.get("qualified_min_score", 7.5)
    rev_min = thresholds.get("review_min_score", 5.0)
    prio_high_min = thresholds.get("priority_high_min_score", 8.5)

    data_issues = lead.get("data_issues", [])
    rejection_reasons: List[str] = []

    if s_size <= 4.0:
        rejection_reasons.append(r_size)
    if s_ind <= 3.0:
        rejection_reasons.append(r_ind)
    if s_src <= 4.0:
        rejection_reasons.append(r_source)
    if s_rec <= 3.0:
        rejection_reasons.append(r_rec)

    has_severe_missing = (
        lead.get("name") == "Unknown Contact" or
        lead.get("company") == "Unknown Company" or
        (lead.get("company_size") is None and lead.get("last_interaction_date") is None)
    )

    if has_severe_missing:
        decision = "REVIEW"
        priority = "MEDIUM" if final_score >= 6.0 else "LOW"
        decision_summary = f"Flagged for human review due to incomplete contact/company records: {', '.join(data_issues)}"
    elif final_score >= qual_min and not data_issues:
        decision = "QUALIFIED"
        priority = "HIGH" if final_score >= prio_high_min else "MEDIUM"
        decision_summary = "Meets all target ICP criteria with strong commercial intent"
    elif final_score >= rev_min or data_issues:
        decision = "REVIEW"
        priority = "MEDIUM" if final_score >= 6.0 else "LOW"
        if data_issues:
            decision_summary = f"Borderline fit with data gaps: {'; '.join(data_issues)}"
        else:
            decision_summary = "Borderline qualification score requiring SDR review"
    else:
        decision = "REJECTED"
        priority = "NONE"
        decision_summary = "Fails to meet minimum ICP qualification threshold"

    reasoning_points = [
        f"Company size: {r_size} (Subscore: {s_size}/10, Weight: {int(w_size*100)}%)",
        f"Industry fit: {r_ind} (Subscore: {s_ind}/10, Weight: {int(w_ind*100)}%)",
        f"Acquisition source: {r_source} (Subscore: {s_src}/10, Weight: {int(w_src*100)}%)",
        f"Recency: {r_rec} (Subscore: {s_rec}/10, Weight: {int(w_rec*100)}%)",
    ]
    if data_issues:
        reasoning_points.append(f"Data anomalies detected: {'; '.join(data_issues)}")

    return {
        "lead_id": lead.get("lead_id"),
        "name": lead.get("name"),
        "company": lead.get("company"),
        "company_size": lead.get("company_size"),
        "industry": lead.get("industry"),
        "source": lead.get("source"),
        "last_interaction_date": lead.get("last_interaction_date"),
        "score": final_score,
        "decision": decision,
        "priority": priority,
        "decision_summary": decision_summary,
        "rejection_reasons": rejection_reasons,
        "reasoning": reasoning_points,
        "subscores": {
            "company_size": s_size,
            "industry_fit": s_ind,
            "source_intent": s_src,
            "recency": s_rec,
        },
    }
