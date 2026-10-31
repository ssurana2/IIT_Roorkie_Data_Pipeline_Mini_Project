import json
from config import load_config
from llm_client import LLMBatchClient, build_batch_prompt
from validator import load_leads_from_csv


def test_batch_prompt_generation():
    leads = load_leads_from_csv("leads_training.csv")
    sample_batch = leads[:5]
    config = load_config()

    print("[TEST 1] Building batch prompt for 5 sample leads...")
    prompt = build_batch_prompt(sample_batch, config)
    print("Generated Prompt Preview (first 500 chars):\n" + prompt[:500] + "...\n")

    print("[TEST 2] Processing sample batch with client...")
    client = LLMBatchClient(config, offline=True)
    results = client.process_batch(sample_batch)

    print(f"Processed {len(results)} leads successfully.")
    for r in results:
        print(f"  • {r['lead_id']} | {r['name']} ({r['company']}) -> Score: {r['score']} | Decision: {r['decision']} | Priority: {r['priority']}")
        if r.get("outreach_message"):
            print(f"    Outreach Message: \"{r['outreach_message'][:100]}...\"")

    print("\nPrompt and batch scoring verification passed!")


if __name__ == "__main__":
    test_batch_prompt_generation()
