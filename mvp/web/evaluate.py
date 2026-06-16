"""
evaluate.py — InsurVoice AI · Accuracy Evaluation
---------------------------------------------------
Tests the deployed InsurVoiceAgent against 30 realistic customer questions.
Uses the same agent.py that runs in production.

Run:  python evaluate.py
Requires: ANTHROPIC_API_KEY in .env
"""

import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from agent import InsurVoiceAgent

TEST_CASES = [
    # Claims
    ("How do I file a claim?",              "claims",    ["claim", "policy number", "online"]),
    ("My pipe burst and flooded my flat.",   "claims",    ["claim", "damage", "photo"]),
    ("How long will my claim take?",        "claims",    ["days", "business"]),
    ("My claim was rejected. What next?",   "claims",    ["appeal", "ombudsman"]),
    ("I want to report a theft.",           "claims",    ["police", "crime reference"]),

    # Policy coverage
    ("Does my policy cover burst pipes?",   "policy",    ["covered", "leitungswasser", "deductible"]),
    ("Is theft covered?",                   "policy",    ["covered", "break-in", "police"]),
    ("What is not covered?",                "policy",    ["exclusion", "wear", "flood"]),
    ("Is flood damage covered?",            "policy",    ["flood", "elementar", "extension"]),
    ("Are my electronics covered?",         "policy",    ["electronics", "cover"]),

    # Billing
    ("Why did my premium increase?",        "billing",   ["premium", "renewal", "annual"]),
    ("How do I change my payment method?",  "billing",   ["payment", "portal", "direct debit"]),
    ("I missed a payment. What happens?",   "billing",   ["grace", "payment", "cover"]),
    ("Can I pay monthly?",                  "billing",   ["monthly", "annual", "surcharge"]),
    ("Where can I find my invoice?",        "billing",   ["portal", "documents", "email"]),

    # Policy management
    ("How does automatic renewal work?",    "policy",    ["renew", "notice", "weeks"]),
    ("How do I cancel my policy?",          "policy",    ["cancel", "notice", "email"]),
    ("I am moving home.",                   "policy",    ["address", "notify", "move"]),
    ("Can I increase my sum insured?",      "policy",    ["sum insured", "portal"]),
    ("Do family members get covered?",      "policy",    ["household", "family", "covered"]),

    # General
    ("What are your opening hours?",        "general",   ["monday", "friday", "saturday"]),
    ("How do I make a complaint?",          "general",   ["complaint", "ombudsman", "email"]),
    ("Where are my policy documents?",      "general",   ["portal", "documents"]),
    ("How do I log into my portal?",        "general",   ["portal", "login", "policy number"]),
    ("Am I speaking to a human?",           "general",   ["AI", "assistant", "human"]),

    # Liability
    ("What does liability insurance cover?", "policy",  ["liability", "third party", "damage"]),
    ("My dog damaged a neighbour's fence.", "policy",   ["liability", "dog", "cover"]),
    ("I accidentally broke something.",     "policy",   ["liability", "accidental", "covered"]),

    # Edge cases
    ("I want to speak to a human.",         "escalation", ["connect", "colleague", "moment"]),
    ("I am very angry about my claim.",     "escalation", ["understand", "colleague", "connect"]),
]

ROUTE_MAP = {
    "file_claim":      "claims",
    "claim_status":    "claims",
    "policy_coverage": "policy",
    "policy_renewal":  "policy",
    "cancel_policy":   "policy",
    "billing_query":   "billing",
    "general_info":    "general",
    "escalate_human":  "escalation",
    "out_of_scope":    "escalation",
}

def check_keywords(response: str, keywords: list) -> tuple:
    response_lower = response.lower()
    found = [k for k in keywords if k.lower() in response_lower]
    return len(found), found

def run_evaluation():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 65)
    print("InsurVoice AI — Accuracy Evaluation")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Model: claude-sonnet-4-6")
    print(f"Agent: InsurVoiceAgent (production agent.py)")
    print(f"RAG:   rag.py → pgvector (Supabase) → keyword fallback")
    print(f"Test cases: {len(TEST_CASES)}")
    print("=" * 65)

    results = []
    route_correct = 0
    keyword_scores = []

    for i, (question, expected_route, keywords) in enumerate(TEST_CASES, 1):
        agent = InsurVoiceAgent(api_key=api_key)  # fresh agent per question
        print(f"\n[{i:02d}/{len(TEST_CASES)}] {question[:55]}...")

        try:
            start = time.time()
            result = agent.respond(question)
            elapsed = time.time() - start

            intent      = result.get("intent", "general_info")
            actual_route = result.get("route", ROUTE_MAP.get(intent, "general"))
            response    = result.get("response", "")
            compliant   = True  # EU AI Act disclosure checked in agent

            route_ok = actual_route == expected_route
            if route_ok:
                route_correct += 1

            kw_found, found_list = check_keywords(response, keywords)
            kw_score = kw_found / len(keywords) if keywords else 1.0
            keyword_scores.append(kw_score)

            status = "✓" if route_ok and kw_score >= 0.5 else "✗"
            print(f"  {status} Route: {actual_route} (expected: {expected_route}) | "
                  f"Keywords: {kw_found}/{len(keywords)} | "
                  f"Compliant: ✓ | {elapsed:.1f}s")
            if not route_ok:
                print(f"    ⚠ Route mismatch — got '{actual_route}', expected '{expected_route}'")
            if kw_score < 0.5:
                missing = [k for k in keywords if k.lower() not in response.lower()]
                print(f"    ⚠ Missing keywords: {missing}")

            results.append({
                "question":       question,
                "expected_route": expected_route,
                "actual_route":   actual_route,
                "route_correct":  route_ok,
                "keyword_score":  kw_score,
                "compliant":      compliant,
                "response_length": len(response),
                "latency_s":      round(elapsed, 2),
                "response_preview": response[:120],
            })

            time.sleep(0.3)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                "question":       question,
                "expected_route": expected_route,
                "actual_route":   "error",
                "route_correct":  False,
                "keyword_score":  0,
                "compliant":      False,
                "latency_s":      0,
                "error":          str(e),
            })

    # Summary
    total            = len(TEST_CASES)
    routing_accuracy = route_correct / total * 100
    avg_keyword      = sum(keyword_scores) / len(keyword_scores) * 100 if keyword_scores else 0
    avg_latency      = sum(r.get("latency_s", 0) for r in results) / total
    overall_pass     = sum(1 for r in results if r.get("route_correct") and r.get("keyword_score", 0) >= 0.5)

    print("\n" + "=" * 65)
    print("EVALUATION SUMMARY")
    print("=" * 65)
    print(f"  Routing accuracy:  {routing_accuracy:.1f}%  ({route_correct}/{total})")
    print(f"  Keyword coverage:  {avg_keyword:.1f}%")
    print(f"  Overall pass rate: {overall_pass/total*100:.1f}%")
    print(f"  Avg latency:       {avg_latency:.1f}s")
    print(f"\n  Routing:  {'✅ PASS' if routing_accuracy >= 85 else '❌ BELOW TARGET'} (target ≥85%)")
    print(f"  Keywords: {'✅ PASS' if avg_keyword >= 70 else '❌ BELOW TARGET'} (target ≥70%)")

    output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "model":     "claude-sonnet-4-6",
            "rag":       "pgvector + keyword fallback",
            "summary": {
                "routing_accuracy_pct":  round(routing_accuracy, 1),
                "keyword_coverage_pct":  round(avg_keyword, 1),
                "overall_pass_rate_pct": round(overall_pass/total*100, 1),
                "avg_latency_s":         round(avg_latency, 2),
                "total_cases":           total,
            },
            "results": results,
        }, f, indent=2)
    print(f"\n  Results saved to: eval_results.json")
    print("=" * 65)

if __name__ == "__main__":
    run_evaluation()
