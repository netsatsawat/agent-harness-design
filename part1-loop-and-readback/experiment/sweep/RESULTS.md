# Sweep results, 2026-10-27 (sweep/results.csv, tests.csv, runs.jsonl)

openai-agents 0.24.0, SDK default max_turns 10, 20 runs per cell, local qwen3.5 0.8b/2b/4b/9b paired by seed (McNemar),
hosted gpt-6-astra and gpt-6.1-sol unpaired (Fisher), Holm across 48 p-values. Hosted spend 1.68 USD for the sweep (the
ledger total, 1.83 USD, also holds 43 earlier smoke calls). 0 excluded runs.
Arms: default = SDK fixed line ('An error occurred while running the tool. Please try again.'). old_default = 0.22.3 line
with the error text (the 422 body lists the allowed values, priority codes WITHOUT their meaning). note = approved message
naming the field, allowed values with meaning, and the next step. Tasks: priority (server-only codes, success = P1) and phone
(inferable E.164 format, success = exactly +14155550132). The first call was never forced to fail. On the phone task, some
hosted first calls were already right (gpt-6-astra 7/1/1 and gpt-6.1-sol 1/0/0 of 20, for default/old_default/note).

| model | task | fixed line | old line (error text) | note | wrong value accepted (by arm) |
|---|---|---|---|---|---|
| qwen3.5:0.8b | priority | 0/20 | 1/20 | 16/20 | old_default: 15 (P0:15) |
| qwen3.5:0.8b | phone | 0/20 | 2/20 | 0/20 | old_default: 1 (+1415550132:1), note: 4 (+4155550132:4) |
| qwen3.5:2b | priority | 0/20 | 1/20 | 20/20 | old_default: 19 (P0:19) |
| qwen3.5:2b | phone | 3/20 | 19/20 | 0/20 | note: 19 (+4155550132:19) |
| qwen3.5:4b | priority | 1/20 | 2/20 | 20/20 | old_default: 18 (P0:18) |
| qwen3.5:4b | phone | 1/20 | 20/20 | 20/20 | none |
| qwen3.5:9b | priority | 0/20 | 19/20 | 20/20 | old_default: 1 (P0:1) |
| qwen3.5:9b | phone | 8/20 | 20/20 | 20/20 | none |
| gpt-6-astra | priority | 0/20 | 20/20 | 20/20 | none |
| gpt-6-astra | phone | 20/20 | 20/20 | 20/20 | none |
| gpt-6.1-sol | priority | 0/20 | 20/20 | 20/20 | none |
| gpt-6.1-sol | phone | 20/20 | 20/20 | 20/20 | none |

Plain readings (all checked against the CSV):
- Priority, the fix needs values only the server knows: the fixed line got 0 of 20 on both GPT-6 models and on three of four
  Qwen sizes (1 of 20 on 4b). Every hosted default run gave up after 3 or 4 model calls. The note fixed 20 of 20 on every model
  except the 0.8b (16 of 20).
- Old line with the raw error text: the 422 lists P0, P1, P2 with no meaning. The 0.8b, 2b and 4b models picked P0 in 15, 19
  and 18 of 20 runs: an accepted call with the wrong priority. The 9b got P1 in 19 of 20 runs (P0 once), and both GPT-6
  models got P1 in all 20.
- Phone, the fix can be inferred: both GPT-6 models fixed every failed call even from the fixed line (astra 13 of 13, sol 19
  of 19). The small Qwen models mostly did not (0, 3, 1, 8 of 20).
- The note can still mislead a small model: after it, the 2b sent +4155550132 in 19 of 20 runs (country code dropped). The
  server accepted that number, so the run looked successful while the message went to the wrong number. Same for 4 of 20
  on the 0.8b.
- Scope: two made-up services, one tool per task, four sizes of one open family plus two hosted OpenAI models, 20 runs per
  cell. The system prompt tells the model to read the error and retry (the script's own line, not an SDK default).
