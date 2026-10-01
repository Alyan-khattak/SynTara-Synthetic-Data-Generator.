# Model Bake-off Results

Candidates run against 5 realistic spec-generation requests from this project's main feature.

| Model | Valid/5 | Avg latency (s) | Mode | Notes |
|---|---|---|---|---|
| `openai/gpt-oss-20b` | 4/5 | 1.63 | json_object | errors: banking_relational: schema error — 8 validation errors for Spec ← backup |
| `openai/gpt-oss-120b` | 5/5 | 2.14 | json_object | errors: none **← PRIMARY** |
| `qwen/qwen3.8-27b` | 3/5 | 4.84 | json_object | errors: invoices: Error code: 429 - {'error': {'message': "Request too large for model `qwen/qwen3.8-27b` in organization `org_01kpkbcx82fb7s3ram4j6cgpd4` service tier `on_demand` on output tokens per minute (OTPM): Limit 1000, Requested 2048. The request's expected output tokens exceed the enforced limit; reduce max_tokens (or the request's expected output) and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing", 'type': 'tokens', 'code': 'rate_limit_exceeded'}}; product_inventory: Error code: 429 - {'error': {'message': "Request too large for model `qwen/qwen3.8-27b` in organization `org_01kpkbcx82fb7s3ram4j6cgpd4` service tier `on_demand` on output tokens per minute (OTPM): Limit 1000, Requested 2048. The request's expected output tokens exceed the enforced limit; reduce max_tokens (or the request's expected output) and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing", 'type': 'tokens', 'code': 'rate_limit_exceeded'}} |

**Primary model chosen:** `openai/gpt-oss-120b`  
**Backup model:** `openai/gpt-oss-20b`

## Licence notes
- `openai/gpt-oss-20b` and `openai/gpt-oss-120b`: Apache 2.0 (VERIFY at https://huggingface.co/openai/gpt-oss-20b)
- `qwen/qwen3.8-27b`: Qwen License (VERIFY at https://huggingface.co/Qwen/Qwen3.8-27B)
