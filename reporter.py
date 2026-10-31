import csv
import json
from collections import Counter
from typing import Any, Dict, List


def generate_report(results: List[Dict[str, Any]], execution_time_sec: float, batch_size: int) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {"error": "No leads processed"}

    qualified = [r for r in results if r.get("decision") == "QUALIFIED"]
    review = [r for r in results if r.get("decision") == "REVIEW"]
    rejected = [r for r in results if r.get("decision") == "REJECTED"]

    scores = [r.get("score", 0.0) for r in results]
    avg_score = round(sum(scores) / total, 2)

    all_rejection_reasons = []
    for r in results:
        reasons = r.get("rejection_reasons") or []
        for reason in reasons:
            all_rejection_reasons.append(reason)

    reason_counts = Counter(all_rejection_reasons).most_common(5)
    common_rejections = [{"reason": r, "count": c} for r, c in reason_counts]

    priority_queue = sorted(
        qualified,
        key=lambda x: (0 if x.get("priority") == "HIGH" else 1, -x.get("score", 0)),
    )

    sample_messages = []
    for q in priority_queue[:5]:
        sample_messages.append({
            "lead_id": q.get("lead_id"),
            "contact_name": q.get("name"),
            "company": q.get("company"),
            "industry": q.get("industry"),
            "source": q.get("source"),
            "score": q.get("score"),
            "outreach_message": q.get("outreach_message"),
        })

    return {
        "metadata": {
            "total_leads_processed": total,
            "execution_time_seconds": round(execution_time_sec, 2),
            "batch_size": batch_size,
            "average_qualification_score": avg_score,
        },
        "aggregated_stats": {
            "qualified_count": len(qualified),
            "qualified_percentage": round((len(qualified) / total) * 100, 1),
            "review_count": len(review),
            "review_percentage": round((len(review) / total) * 100, 1),
            "disqualified_count": len(rejected),
            "disqualified_percentage": round((len(rejected) / total) * 100, 1),
            "common_rejection_reasons": common_rejections,
        },
        "sample_outreach_messages": sample_messages,
        "priority_queue": [
            {
                "lead_id": q.get("lead_id"),
                "name": q.get("name"),
                "company": q.get("company"),
                "score": q.get("score"),
                "priority": q.get("priority"),
                "industry": q.get("industry"),
                "source": q.get("source"),
            }
            for q in priority_queue
        ],
        "flagged_leads_for_review": [
            {
                "lead_id": r.get("lead_id"),
                "name": r.get("name"),
                "company": r.get("company"),
                "score": r.get("score"),
                "reasoning": r.get("reasoning"),
                "data_issues": r.get("data_issues", []),
            }
            for r in review
        ],
        "disqualified_leads": [
            {
                "lead_id": r.get("lead_id"),
                "name": r.get("name"),
                "company": r.get("company"),
                "score": r.get("score"),
                "rejection_reasons": r.get("rejection_reasons", []),
            }
            for r in rejected
        ],
        "lead_results": results,
    }


def save_json_report(report_data: Dict[str, Any], filepath: str) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)


def save_csv_report(results: List[Dict[str, Any]], filepath: str) -> None:
    fieldnames = [
        "lead_id", "name", "company", "company_size", "industry", "source",
        "last_interaction_date", "score", "decision", "priority",
        "reasoning", "outreach_message"
    ]
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)
