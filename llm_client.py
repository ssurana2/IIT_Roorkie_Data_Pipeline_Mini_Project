import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from rubric import score_lead

logger = logging.getLogger(__name__)


def generate_personalized_message(lead: Dict[str, Any]) -> str:
    name = lead.get("name", "there")
    company = lead.get("company", "your company")
    industry = lead.get("industry", "your sector")
    source = lead.get("source", "Inbound")
    size = lead.get("company_size")
    size_str = f"with ~{size} team members" if size else ""

    src_lower = source.lower()
    if "demo" in src_lower or "sales call" in src_lower:
        return (
            f"Hi {name}, thanks for reaching out for a demo of our platform. "
            f"Given {company}'s focus in {industry} {size_str}, we've helped similar teams "
            f"streamline pipeline workflows and eliminate manual qualification bottlenecks. "
            f"Are you open to a brief 15-minute sync this Tuesday or Wednesday to explore fit?"
        )
    elif "referral" in src_lower:
        return (
            f"Hi {name}, our mutual network recommended connecting given the great work you're leading at {company}. "
            f"In the {industry} space, scaling organizations often hit operational friction managing high-velocity lead pipelines. "
            f"Would you be open to exchanging ideas on how modern automation is accelerating deal cycles for teams of your scale?"
        )
    elif "webinar" in src_lower:
        return (
            f"Hi {name}, thank you for joining our recent session on automated pipeline intelligence. "
            f"I noticed your focus at {company} in {industry} and thought you might appreciate the case study "
            f"showing how peer companies increased SDR conversion by 4x. Happy to share the deck or discuss further if relevant."
        )
    else:
        return (
            f"Hi {name}, noticed {company}'s strong growth in {industry}. "
            f"We specialize in solving pipeline qualification bottlenecks for fast-growing mid-market teams. "
            f"Would you be open to a quick introductory chat to see how peer organizations are automating lead prioritization?"
        )


def build_batch_prompt(batch: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    leads_repr = []
    for lead in batch:
        leads_repr.append({
            "lead_id": lead.get("lead_id"),
            "name": lead.get("name"),
            "company": lead.get("company"),
            "company_size": lead.get("company_size"),
            "industry": lead.get("industry"),
            "source": lead.get("source"),
            "last_interaction_date": lead.get("last_interaction_date"),
            "data_issues": lead.get("data_issues", []),
        })

    prompt = f"""You are an executive sales operations intelligence system for a mid-market B2B SaaS platform.
Evaluate each inbound lead in this batch against our 4-factor qualification rubric:
1. Company Size (30% weight): Sweet spot is 50-2000 employees. Micro (<10) is rejected. Mega (>5000) requires enterprise review.
2. Industry Fit (25% weight): High priority for SaaS, Cloud, FinTech, Cybersecurity, Analytics, Healthcare, Logistics.
3. Source Intent (25% weight): High for Inbound demo request, Sales call. Moderate for Referral, Webinar. Low for Content download, Cold outreach.
4. Recency (20% weight): <30 days is hot/active. >120 days is stale. Missing dates need review.

Decisions:
- QUALIFIED (score >= 7.5): Ideal fit with strong commercial intent. Assign priority HIGH (score >= 8.5) or MEDIUM.
- REVIEW (score 5.0 - 7.4 or data anomalies): Ambiguous fit or missing critical fields.
- REJECTED (score < 5.0): Low ICP match, micro-scale, or stale interaction.

For each QUALIFIED lead, write a concise (2-3 sentences), highly personalized first outreach message referencing their exact company, industry, and source context.

Respond ONLY with a valid JSON array of objects with the exact schema:
[
  {{
    "lead_id": "LEAD-0001",
    "name": "Contact Name",
    "company": "Company Name",
    "score": 8.5,
    "decision": "QUALIFIED",
    "priority": "HIGH",
    "reasoning": "Explicit 1-2 sentence justification covering size, industry, source, recency.",
    "rejection_reasons": [],
    "outreach_message": "Personalized message for qualified leads, or empty string if not qualified"
  }}
]

Batch to analyze:
{json.dumps(leads_repr, indent=2)}
"""
    return prompt


class LLMBatchClient:
    def __init__(self, config: Dict[str, Any], offline: bool = False):
        self.config = config
        self.offline = offline
        self.model_cfg = config.get("model", {})
        self.api_key = self.model_cfg.get("api_key")
        self.model_name = self.model_cfg.get("name", "openai/gpt-oss-120b")
        self.max_retries = self.model_cfg.get("max_retries", 3)
        self.backoff_seconds = self.model_cfg.get("backoff_seconds", 2.0)
        self.timeout = self.model_cfg.get("request_timeout_seconds", 30)
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    def _call_groq_api(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise sales operations intelligence system. Always output strictly valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": self.model_cfg.get("temperature", 0.1),
            "response_format": {"type": "json_object"} if "llama-3" in self.model_name else None
        }
        if payload.get("response_format") is None:
            del payload["response_format"]

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

        req = urllib.request.Request(self.api_url, data=data, headers=headers)

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    return resp_data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="replace")
                logger.warning("HTTP %d on attempt %d: %s", e.code, attempt, err_text)
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_time = self.backoff_seconds * (2 ** (attempt - 1))
                    logger.info("Retrying in %.1f seconds...", sleep_time)
                    time.sleep(sleep_time)
                else:
                    raise RuntimeError(f"API Error {e.code}: {err_text}")
            except Exception as e:
                logger.warning("Network error on attempt %d: %s", attempt, str(e))
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
                else:
                    raise

        raise RuntimeError("Max retries exceeded for LLM batch request")

    def process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.offline and self.api_key:
            try:
                prompt = build_batch_prompt(batch, self.config)
                raw_response = self._call_groq_api(prompt)
                parsed = self._extract_json_array(raw_response)
                if parsed and len(parsed) == len(batch):
                    return self._merge_llm_results(batch, parsed)
            except Exception as e:
                logger.warning("LLM API call failed (%s); using deterministic rubric scoring.", str(e))

        return self._process_batch_deterministic(batch)

    def _extract_json_array(self, text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list):
                        return val
        except Exception:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return []

    def _merge_llm_results(self, batch: List[Dict[str, Any]], llm_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        llm_map = {item.get("lead_id"): item for item in llm_list if isinstance(item, dict)}
        results = []

        for lead in batch:
            lead_id = lead.get("lead_id")
            base_score = score_lead(lead, self.config)
            llm_item = llm_map.get(lead_id)

            if llm_item:
                score = llm_item.get("score", base_score["score"])
                decision = str(llm_item.get("decision", base_score["decision"])).upper()
                priority = str(llm_item.get("priority", base_score["priority"])).upper()
                reasoning = llm_item.get("reasoning")
                if isinstance(reasoning, list):
                    reasoning_str = "; ".join(reasoning)
                else:
                    reasoning_str = str(reasoning) if reasoning else base_score["decision_summary"]

                msg = llm_item.get("outreach_message", "")
                if decision == "QUALIFIED" and not msg:
                    msg = generate_personalized_message(lead)

                results.append({
                    "lead_id": lead_id,
                    "name": lead.get("name"),
                    "company": lead.get("company"),
                    "company_size": lead.get("company_size"),
                    "industry": lead.get("industry"),
                    "source": lead.get("source"),
                    "last_interaction_date": lead.get("last_interaction_date"),
                    "score": round(float(score), 1),
                    "decision": decision,
                    "priority": priority,
                    "reasoning": reasoning_str,
                    "rejection_reasons": llm_item.get("rejection_reasons") or base_score["rejection_reasons"],
                    "outreach_message": msg if decision == "QUALIFIED" else None,
                    "data_issues": lead.get("data_issues", []),
                })
            else:
                results.append(self._lead_to_result(lead, base_score))

        return results

    def _process_batch_deterministic(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for lead in batch:
            base_score = score_lead(lead, self.config)
            results.append(self._lead_to_result(lead, base_score))
        return results

    def _lead_to_result(self, lead: Dict[str, Any], base_score: Dict[str, Any]) -> Dict[str, Any]:
        decision = base_score["decision"]
        msg = generate_personalized_message(lead) if decision == "QUALIFIED" else None
        return {
            "lead_id": lead.get("lead_id"),
            "name": lead.get("name"),
            "company": lead.get("company"),
            "company_size": lead.get("company_size"),
            "industry": lead.get("industry"),
            "source": lead.get("source"),
            "last_interaction_date": lead.get("last_interaction_date"),
            "score": base_score["score"],
            "decision": decision,
            "priority": base_score["priority"],
            "reasoning": " | ".join(base_score["reasoning"]),
            "rejection_reasons": base_score["rejection_reasons"],
            "outreach_message": msg,
            "data_issues": lead.get("data_issues", []),
        }
