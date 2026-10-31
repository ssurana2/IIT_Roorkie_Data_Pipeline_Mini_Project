import argparse
import sys
import time
from typing import List

from config import load_config
from llm_client import LLMBatchClient
from reporter import generate_report, save_csv_report, save_json_report
from validator import load_leads_from_csv


def print_summary_table(report: dict) -> None:
    meta = report["metadata"]
    stats = report["aggregated_stats"]

    print("\n" + "=" * 65)
    print("      LEAD INTELLIGENCE SYSTEM - PIPELINE EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Total Leads Processed : {meta['total_leads_processed']}")
    print(f"Execution Time         : {meta['execution_time_seconds']}s")
    print(f"Average Fit Score      : {meta['average_qualification_score']} / 10.0")
    print(f"Batch Size             : {meta['batch_size']}")
    print("-" * 65)
    print(f"Qualified Leads        : {stats['qualified_count']:3d} ({stats['qualified_percentage']}%)")
    print(f"Flagged for Review     : {stats['review_count']:3d} ({stats['review_percentage']}%)")
    print(f"Disqualified Leads     : {stats['disqualified_count']:3d} ({stats['disqualified_percentage']}%)")
    print("-" * 65)
    print("Top Rejection Drivers:")
    for r in stats.get("common_rejection_reasons", [])[:3]:
        print(f"  • {r['reason']} ({r['count']} leads)")
    print("-" * 65)

    samples = report.get("sample_outreach_messages", [])
    if samples:
        print(f"Generated {len(samples)} Sample Outreach Messages:")
        for idx, s in enumerate(samples[:2], 1):
            print(f"\n[{idx}] To: {s['contact_name']} @ {s['company']} (Score: {s['score']})")
            print(f"    Message: \"{s['outreach_message']}\"")
    print("=" * 65 + "\n")


def run_pipeline(input_csv: str, batch_size: int, output_json: str, output_csv: str, offline: bool, model_name: str = None) -> None:
    start_time = time.time()
    config = load_config()

    if model_name:
        config["model"]["name"] = model_name

    print(f"\n[1/4] Ingesting and validating leads from: {input_csv}")
    leads = load_leads_from_csv(input_csv)
    if not leads:
        print("Error: No leads found in input file.")
        sys.exit(1)

    print(f"      Loaded {len(leads)} leads. Batch size: {batch_size}")

    print(f"\n[2/4] Initializing LLM client (Model: {config['model']['name']}, Offline: {offline})")
    client = LLMBatchClient(config, offline=offline)

    print(f"\n[3/4] Processing leads in batches...")
    all_results = []
    num_batches = (len(leads) + batch_size - 1) // batch_size

    for i in range(num_batches):
        batch = leads[i * batch_size : (i + 1) * batch_size]
        print(f"      Processing batch {i + 1}/{num_batches} ({len(batch)} leads)...", end="", flush=True)
        batch_results = client.process_batch(batch)
        all_results.extend(batch_results)
        print(" Done.")

    elapsed = time.time() - start_time

    print(f"\n[4/4] Generating reports and aggregations...")
    report = generate_report(all_results, execution_time_sec=elapsed, batch_size=batch_size)
    save_json_report(report, output_json)
    if output_csv:
        save_csv_report(all_results, output_csv)

    print(f"      Report saved to: {output_json}")
    if output_csv:
        print(f"      CSV output saved to: {output_csv}")

    print_summary_table(report)


def main():
    parser = argparse.ArgumentParser(
        description="Lead Intelligence System: Auto-qualification, priority scoring, and outreach sequencing."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="leads_full_scale_100.csv",
        help="Path to input leads CSV file (default: leads_full_scale_100.csv)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of leads per LLM processing batch (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_report.json",
        help="Path to save output JSON report (default: output_report.json)"
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="output_report.csv",
        help="Path to save tabular CSV output report (default: output_report.csv)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model name (default: from config.yaml or .env)"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline/deterministic mode using rubric scoring and rule-based messaging"
    )

    args = parser.parse_args()
    run_pipeline(
        input_csv=args.input,
        batch_size=args.batch_size,
        output_json=args.output,
        output_csv=args.output_csv,
        offline=args.offline,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
