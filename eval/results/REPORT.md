# Evaluation: 20 QuixBugs tasks

Model `openai/gpt-4.1-mini`.

| Task | Status | Steps | Cost (USD) | Seconds | Approvals | Verified | Guardrail |
|---|---|---|---|---|---|---|---|
| bitcount | passed | 8 | 0.0025 | 26.1 | 1 | True |  |
| bucketsort | passed | 8 | 0.00184 | 25.2 | 1 | True |  |
| find_first_in_sorted | passed | 8 | 0.00284 | 28.8 | 1 | True |  |
| find_in_sorted | passed | 8 | 0.00285 | 28.2 | 1 | True |  |
| flatten | passed | 8 | 0.00236 | 21.5 | 1 | True |  |
| gcd | passed | 8 | 0.00238 | 20.3 | 1 | True |  |
| get_factors | passed | 8 | 0.00353 | 25.1 | 1 | True |  |
| hanoi | passed | 8 | 0.00298 | 20.9 | 1 | True |  |
| is_valid_parenthesization | passed | 8 | 0.00363 | 27.2 | 1 | True |  |
| kheapsort | passed | 8 | 0.00321 | 22.7 | 1 | True |  |
| kth | passed | 8 | 0.00237 | 19.4 | 1 | True |  |
| lis | passed | 10 | 0.00819 | 45.7 | 1 | True |  |
| max_sublist_sum | failed | 9 | 0.00595 | 41.2 | 0 | None |  |
| mergesort | passed | 10 | 0.00532 | 36.3 | 1 | True |  |
| next_palindrome | passed | 13 | 0.01325 | 62.6 | 1 | True |  |
| pascal | passed | 8 | 0.00379 | 28.1 | 1 | True |  |
| possible_change | passed | 8 | 0.00243 | 21.2 | 1 | True |  |
| powerset | passed | 10 | 0.00448 | 31.9 | 1 | True |  |
| quicksort | passed | 8 | 0.00258 | 20.8 | 1 | True |  |
| sieve | passed | 8 | 0.00277 | 21.6 | 1 | True |  |

```json
{
  "llm_model": "openai/gpt-4.1-mini",
  "tasks": 20,
  "success": 19,
  "success_rate": 0.95,
  "status_counts": {
    "failed": 1,
    "passed": 19
  },
  "avg_steps": 8.6,
  "avg_cost_usd": 0.00396,
  "total_cost_usd": 0.0793,
  "avg_seconds": 28.7,
  "approvals_requested": 19,
  "guardrail_stops": 0,
  "guardrails": {
    "max_steps": 25,
    "max_cost_usd": 0.1,
    "max_tokens": 200000,
    "sandbox_timeout_s": 60,
    "max_fix_attempts": 3,
    "loop_repeat_limit": 3
  }
}
```
