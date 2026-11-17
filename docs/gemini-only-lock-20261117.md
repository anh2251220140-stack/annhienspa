# Gemini-only provider lock — 2026-11-17

## Policy enforced
- `external_provider()` permits only Gemini. OpenAI/unknown configuration raises ProviderUnavailable before client construction or I/O.
- `embedding_provider()` selects Gemini for Gemini configuration, deterministic local lexical SHA256/256-dimensional L2 vectors for mock. Unknown/OpenAI configuration is rejected.
- Local mock vectors have a separate provider/model/version/dimension identity; existing OpenAI/Gemini indexes are neither reused nor deleted. No indexing was run on existing data.
- The retired OpenAIProvider name remains solely as a compatibility tombstone: construction, _post, structured and embed always raise. Its HTTP implementation and OpenAI endpoint have been removed. GroundedProvider and ProviderUnavailable remain shared with Gemini.
- FR22 and FR23 accept external Gemini only; failures use existing internal rule fallback. FR24 history reads retain ownership/explicit Admin permission checks and do not invoke a provider.
- index_spa rejects unsupported providers before catalog/vector access. Session providerMode cannot label legacy OpenAI settings as active AI.
- tools/openai_test.py is a historical filename shared by Gemini launchers for isolation/getpass helpers. It now defaults to Gemini, refuses OpenAI configuration/key staging, and has no OpenAI live capability. Historical documentation is evidence of earlier releases, not the current provider policy.

## Files changed in this task
- `ai_features/provider_factory.py`
- `ai_features/integration.py`
- `ai_features/assistance.py`
- `ai_features/views.py`
- `ai_features/management/commands/index_spa.py`
- `ai_features/test_assistance.py`
- `ai_features/test_gemini.py`
- `ai_features/test_rag.py`
- `ai_features/test_provider_lock.py` (new)
- `tools/openai_test.py`
- `tools/test_openai_test.py`
- `tools/test_gemini_live.py`

## Verification
| Suite | PASS | FAIL / ERROR | Evidence |
|---|---:|---:|---|
| Django FR21/22/23/24, provider lock, Gemini, RAG, application integration | 136 | 0 / 0 | gemini-only-offline-final-20261117.txt |
| Legacy staging/configuration guard | 21 | 0 / 0 | gemini-only-staging-final-20261117.txt |
| Gemini live launcher — mock transport only | 29 | 0 / 0 | gemini-only-live-offline-final-20261117.txt |
| Gemini launcher plan/fallback | 5 | 0 / 0 | gemini-only-launcher-tests-20261117.txt |
| Numeric grounding | 15 | 0 / 0 | gemini-only-grounding-tests-20261117.txt |
| **Total final distinct tests** | **206** | **0 / 0** | No skipped tests |

Commands use .venv/Scripts/python.exe -B. Main runner: tools/ai_tests.py ai_features.test_provider_lock ai_features.test_assistance.AssistanceTests ai_features.tests.ChatTests ai_features.test_rag ai_features.test_gemini ai_features.test_review_integration ai_features.test_recommendation_integration. Tool suites: -m unittest tools.test_openai_test; tools.test_gemini_live; tools.test_gemini_test; tools.test_numeric_grounding (each in a separate process).

Eight new lock tests prove factory rejection even with legacy key/paid flags set to synthetic values; direct retired adapter entry points cannot send; unknown provider names fail closed; mock embedding remains local; Gemini selection; index command rejection; real Django FR21/22/23/24 fallback/persistence/history ownership under OpenAI configuration; Gemini failure never selects OpenAI.

Initial runs exposed fixture incompatibilities: synthetic 2D embeddings versus the explicit 256D mock namespace; Admin fixture missing read_chat_history permission; lazy SDK import under a mocked HTTP constructor; and the old mock transport helper attempting to pass through the outer runner's denied Client.send. Corrected only fixtures/mock dispatch. Final helper dispatches solely to MockTransport and preserves live guard request validation and deadline hooks; no real sender is restored. Initial reports are retained.

## Safety and remaining acceptance
- Main regression runner blocks MySQL connectors and external HTTP/sockets. SDK tests use synthetic keys and in-process mock transport; no real key input or external API request.
- Only newly owned temporary SQLite test databases/vector files are created/populated/removed by test runners. Existing databases and vector indexes were not changed; no MySQL connection.
- No new migration/model change; makemigrations --check --dry-run reports No changes detected. Test schema setup is confined to temporary SQLite.
- No .env, production configuration, UI, Booking, Billing, PayOS or credentials modified. No commit/push. Existing unrelated modifications preserved.
- Existing running processes need a user-controlled restart to load this source change. No website process was restarted or reconfigured in this task.
- No live Gemini acceptance run; it remains subject to separate approval. Current source cannot call OpenAI through the application/provider/legacy adapter paths reviewed and tested here.
