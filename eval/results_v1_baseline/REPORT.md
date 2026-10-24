# Evaluation: 20 QuixBugs tasks

Model `openai/gpt-4.1-mini`.

| Task | Status | Steps | Cost (USD) | Seconds | Approvals | Verified | Guardrail |
|---|---|---|---|---|---|---|---|
| bitcount | passed | 8 | 0.00222 | 24.6 | 1 | True |  |
| bucketsort | passed | 8 | 0.00171 | 23.7 | 1 | True |  |
| find_first_in_sorted | passed | 8 | 0.00224 | 24.8 | 1 | True |  |
| find_in_sorted | passed | 8 | 0.00224 | 24.9 | 1 | True |  |
| flatten | passed | 8 | 0.00154 | 17.4 | 1 | True |  |
| gcd | passed | 8 | 0.00215 | 22.2 | 1 | True |  |
| get_factors | passed | 8 | 0.00303 | 27.2 | 1 | True |  |
| hanoi | passed | 8 | 0.00291 | 25.3 | 1 | True |  |
| is_valid_parenthesization | passed | 8 | 0.004 | 28.8 | 1 | True |  |
| kheapsort | passed | 8 | 0.00274 | 23.5 | 1 | True |  |
| kth | failed | 9 | 0.00412 | 32.6 | 0 | None |  |
| lis | passed | 10 | 0.00449 | 34.0 | 1 | True |  |
| max_sublist_sum | failed | 9 | 0.00512 | 34.1 | 0 | None |  |
| mergesort | failed | 9 | 0.00327 | 28.5 | 0 | None |  |
| next_palindrome | failed | 9 | 0.00882 | 40.1 | 0 | None |  |
| pascal | passed | 8 | 0.00306 | 23.8 | 1 | True |  |
| possible_change | stopped | 3 | 0.0011 | 9.3 | 0 | None | loop detected: read_file({"path": "possible_change-f56d7264/python_testcases/test_possible_chan called 3 times |
| powerset | failed | 9 | 0.00365 | 29.9 | 0 | None |  |
| quicksort | passed | 8 | 0.0022 | 20.7 | 1 | True |  |
| sieve | passed | 8 | 0.00256 | 22.8 | 1 | True |  |

```json
{
  "llm_model": "openai/gpt-4.1-mini",
  "tasks": 20,
  "success": 14,
  "success_rate": 0.7,
  "status_counts": {
    "failed": 5,
    "passed": 14,
    "stopped": 1
  },
  "avg_steps": 8.1,
  "avg_cost_usd": 0.00316,
  "total_cost_usd": 0.0632,
  "avg_seconds": 25.9,
  "approvals_requested": 14,
  "guardrail_stops": 1,
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
