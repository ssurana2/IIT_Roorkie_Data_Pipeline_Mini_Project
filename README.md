# Lead Intelligence System (Mini Project)

A production-grade CLI pipeline designed for mid-market B2B SaaS sales teams to automate lead qualification, prioritize outreach queues, and generate tailored introductory messages in high-throughput batches.

---

## 1. Qualification Rubric

Our 4-factor rubric assesses fit against an ideal mid-market SaaS buyer:
1. **Company Size Match (30%)**: Sweet spot of 50–2,000 employees scores 10/10; early-stage startups (10–19) and large enterprises (2,001–5,000) receive partial credit, while micro-teams (<10) are penalized.
2. **Industry Alignment (25%)**: Tier-1 B2B software verticals (SaaS, FinTech, Cybersecurity, Analytics, Healthcare, Logistics) score 10/10; secondary verticals score 6.5/10; non-core sectors (e.g. Government, Hospitality) score 2.5/10.
3. **Acquisition Source & Intent (25%)**: High-intent direct conversions (Inbound demo requests, Sales calls) score 10/10; warm referrals score 8.5/10; engaged webinar attendees score 6.5/10; passive content downloads (4.5/10) and cold LinkedIn outreach (3.5/10) receive lower prioritization.
4. **Interaction Recency (20%)**: Leads active within 14 days score 10/10; 15–35 days score 8.5/10; interactions beyond 120 days are penalized as stale (1.5/10).

**Decision Thresholds:** Composite score $\ge 7.5 \rightarrow$ **QUALIFIED** (Priority: HIGH $\ge 8.5$, else MEDIUM); $5.0–7.4$ or data anomalies $\rightarrow$ **REVIEW**; $< 5.0 \rightarrow$ **REJECTED**.

---

## 2. How to Run the Tool

### Prerequisites
* Python 3.9+ (zero external pip dependencies required for standard execution).
* (Optional) Groq API Key set in `.env` or exported in your shell.

### Quickstart
1. **Set up API Key**:
   ```bash
   cp .env.example .env
   # Edit .env and paste your Groq API key (GROQ_API_KEY=gsk_...)
   ```

2. **Run Pipeline on Production Scale (100 leads)**:
   ```bash
   python3 main.py --input leads_full_scale_100.csv
   ```

3. **Run on Sample Dataset (30 leads)**:
   ```bash
   python3 main.py --input leads.csv
   ```

4. **Run Edge-Case Resilience Suite**:
   ```bash
   python3 main.py --input leads_testing.csv --offline
   ```

5. **CLI Options**:
   * `--input <path>`: Input CSV file path (default: `leads_full_scale_100.csv`).
   * `--batch-size <N>`: Number of leads per batch processed by LLM (default: `10`).
   * `--output <path>`: JSON report destination (default: `output_report.json`).
   * `--output-csv <path>`: CSV report destination (default: `output_report.csv`).
   * `--model <name>`: Override Groq model name.
   * `--offline`: Run deterministic rubric scoring and templated messaging without remote API calls.

---

## 3. Architecture & Error Handling

* **Batch Processing**: Groups leads into batches of 10 per LLM prompt, reducing API requests from 100 to 10 and executing in seconds.
* **Rate Limits & API Failures**: Implements exponential backoff retries (HTTP 429/5xx) and automatically falls back to deterministic rubric scoring if API credits expire, guaranteeing zero pipeline crashes.
* **Human-in-the-Loop Review**: Automatically routes ambiguous leads (scores 5.0–7.4) and leads with corrupted or missing data (missing names, missing company sizes, unparseable dates) to a dedicated human review queue rather than guessing.

---

## 4. Known Limitations & Edge Cases

* **Single-Contact Data**: Evaluates lead fit based on company-level firmographics and channel source; multi-stakeholder committee dynamics or individual buyer seniority (e.g., Director vs. Intern) require enriched CRM contact data.
* **Dynamic Domain Normalization**: Free-form industry strings (e.g. "AI/ML", "Climate Tech") rely on heuristic keyword matching; niche unmapped verticals are flagged for review.
* **Interaction History Depth**: Recency is measured from the single `last_interaction_date`; lifetime touchpoint count or multi-channel engagement frequency is not captured in the flat CSV schema.
