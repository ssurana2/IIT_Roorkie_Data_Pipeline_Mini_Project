import os
from typing import Any, Dict


def load_env(env_path: str = ".env") -> Dict[str, str]:
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip().strip("\"'")
    return env


def get_default_config() -> Dict[str, Any]:
    return {
        "model": {
            "provider": "groq",
            "name": "openai/gpt-oss-120b",
            "temperature": 0.1,
            "max_retries": 3,
            "backoff_seconds": 2.0,
            "request_timeout_seconds": 30,
        },
        "pipeline": {
            "batch_size": 10,
            "default_input": "leads_full_scale_100.csv",
            "output_json": "output_report.json",
            "output_csv": "output_report.csv",
            "target_reference_date": "2024-01-20",
        },
        "rubric": {
            "factors": {
                "company_size": {
                    "weight": 0.30,
                    "sweet_spot_min": 50,
                    "sweet_spot_max": 2000,
                },
                "industry_fit": {
                    "weight": 0.25,
                    "tier_1": [
                        "SaaS", "Software", "Cloud", "FinTech", "Cybersecurity",
                        "Analytics", "Healthcare", "Logistics", "InsurTech",
                        "HealthTech", "AI/ML", "Enterprise Software", "Tech"
                    ],
                    "tier_2": [
                        "Retail", "Manufacturing", "Marketing", "Finance",
                        "Legal", "Telecom", "Real Estate", "Consulting",
                        "Construction", "Energy", "Biotech"
                    ],
                },
                "source_intent": {
                    "weight": 0.25,
                    "high_intent": ["Inbound demo request", "Sales call"],
                    "medium_intent": ["Referral", "Webinar attendee"],
                    "low_intent": ["Content download", "LinkedIn outreach"],
                },
                "interaction_recency": {
                    "weight": 0.20,
                    "fresh_days": 30,
                    "moderate_days": 60,
                    "stale_days": 120,
                },
            }
        },
        "decision_thresholds": {
            "qualified_min_score": 7.5,
            "review_min_score": 5.0,
            "priority_high_min_score": 8.5,
        },
    }


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    config = get_default_config()

    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                parsed = yaml.safe_load(f)
                if isinstance(parsed, dict):
                    _deep_update(config, parsed)
        except ImportError:
            pass

    env = load_env()
    api_key = env.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if api_key:
        config["model"]["api_key"] = api_key
    model_override = env.get("GROQ_MODEL") or os.environ.get("GROQ_MODEL")
    if model_override:
        config["model"]["name"] = model_override

    return config


def _deep_update(base: Dict[str, Any], update: Dict[str, Any]) -> None:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
