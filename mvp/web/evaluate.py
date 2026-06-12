"""
evaluate.py — InsurVoice AI · Accuracy Evaluation
---------------------------------------------------
Tests the multi-agent pipeline against 30 realistic customer questions.
Scores intent routing accuracy and response quality.

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

from agents import Orchestrator

# ── Test cases ────────────────────────────────────────────────────────────────
# Each case: (question, expected_route, expected_keywords_in_response)
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

    # Edge cases — should escalate or handle gracefully
    ("I want to speak to a human.",         "escalation", ["connect", "colleague", "moment"]),
    ("I am very angry about my claim.",     "escalation", ["understand", "colleague", "connect"]),
]

def check_keywords(response: str, keywords: list) -> tuple[int, list]:
    """Check how many keywords appear in the response (case-insensitive)."""
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
    print(f"Model: claude-opus-4-6")
    print(f"Test cases: {len(TEST_CASES)}")
    print("=" * 65)

    results = []
    route_correct = 0
    keyword_scores = []

    for i, (question, expected_route, keywords) in enumerate(TEST_CASES, 1):
        agent = Orchestrator(api_key)  # fresh agent per question
        print(f"\n[{i:02d}/{len(TEST_CASES)}] {question[:55]}...")

        try:
            start = time.time()
            result = agent.respond(question)
            elapsed = time.time() - start

            actual_route = result.get("route", "unknown")
            response = result.get("response", "")
            compliant = result.get("compliance", {}).get("compliant", True)

            # Score routing
            route_ok = actual_route == expected_route
            if route_ok:
                route_correct += 1

            # Score keyword coverage
            kw_found, found_list = check_keywords(response, keywords)
            kw_score = kw_found / len(keywords) if keywords else 1.0
            keyword_scores.append(kw_score)

            status = "✓" if route_ok and kw_score >= 0.5 else "✗"
            print(f"  {status} Route: {actual_route} (expected: {expected_route}) | "
                  f"Keywords: {kw_found}/{len(keywords)} | "
                  f"Compliant: {'✓' if compliant else '✗'} | "
                  f"{elapsed:.1f}s")
            if not route_ok:
                print(f"    ⚠ Route mismatch — got '{actual_route}', expected '{expected_route}'")
            if kw_score < 0.5:
                missing = [k for k in keywords if k.lower() not in response.lower()]
                print(f"    ⚠ Missing keywords: {missing}")

            results.append({
                "question": question,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "route_correct": route_ok,
                "keyword_score": kw_score,
                "compliant": compliant,
                "response_length": len(response),
                "latency_s": round(elapsed, 2),
                "response_preview": response[:120],
            })

            time.sleep(0.5)  # gentle rate limiting

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                "question": question,
                "expected_route": expected_route,
                "actual_route": "error",
                "route_correct": False,
                "keyword_score": 0,
                "compliant": False,
                "latency_s": 0,
                "error": str(e),
            })

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(TEST_CASES)
    routing_accuracy = route_correct / total * 100
    avg_keyword = sum(keyword_scores) / len(keyword_scores) * 100 if keyword_scores else 0
    avg_latency = sum(r.get("latency_s", 0) for r in results) / total
    compliance_pass = sum(1 for r in results if r.get("compliant", False)) / total * 100
    overall_pass = sum(1 for r in results if r.get("route_correct") and r.get("keyword_score", 0) >= 0.5)

    print("\n" + "=" * 65)
    print("EVALUATION SUMMARY")
    print("=" * 65)
    print(f"  Routing accuracy:     {routing_accuracy:.0f}%  ({route_correct}/{total} correct routes)")
    print(f"  Keyword coverage:     {avg_keyword:.0f}%  (avg keywords found in response)")
    print(f"  Compliance rate:      {compliance_pass:.0f}%  (EU AI Act + GDPR)")
    print(f"  Overall pass rate:    {overall_pass/total*100:.0f}%  (route + keywords)")
    print(f"  Avg response time:    {avg_latency:.1f}s")
    print(f"  Target routing:       ≥ 85%")
    print(f"  Target keywords:      ≥ 70%")

    routing_ok = routing_accuracy >= 85
    keywords_ok = avg_keyword >= 70
    print(f"\n  Routing:  {'✅ PASS' if routing_ok else '❌ BELOW TARGET'}")
    print(f"  Keywords: {'✅ PASS' if keywords_ok else '❌ BELOW TARGET'}")
    print(f"  Overall:  {'✅ PASS' if routing_ok and keywords_ok else '⚠ NEEDS IMPROVEMENT'}")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "routing_accuracy_pct": round(routing_accuracy, 1),
                "keyword_coverage_pct": round(avg_keyword, 1),
                "compliance_rate_pct": round(compliance_pass, 1),
                "overall_pass_rate_pct": round(overall_pass/total*100, 1),
                "avg_latency_s": round(avg_latency, 2),
                "total_cases": total,
            },
            "results": results,
        }, f, indent=2)
    print(f"\n  Full results saved to: eval_results.json")
    print("=" * 65)

if __name__ == "__main__":
    run_evaluation()
