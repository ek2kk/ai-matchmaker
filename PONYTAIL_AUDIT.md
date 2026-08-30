# Ponytail audit

Scope: весь tracked tree, кроме lockfiles. Проверка ограничена over-engineering и complexity; correctness, security и performance не оценивались. Оценки строк приблизительны и не включают миграции/lockfiles.

1. `delete:` Удалить выполненные разделы 0–11 из исторического implementation-плана; они дублируют source-of-truth в `docs/architecture/` и не имеют входящих ссылок. Оставить только open gates 0.1, 12–14 либо перенести их в roadmap. [`todos.md`](todos.md)
2. `yagni:` Удалить synthetic rerank evaluator и console-script: он всегда формирует synthetic verdict, а runtime всё равно требует human `decision: pass`; до Phase 3 достаточно статичного failing manifest и ручного проверенного артефакта. [`backend/src/ai_dating/ai/eval.py`](backend/src/ai_dating/ai/eval.py), [`backend/pyproject.toml`](backend/pyproject.toml), [`backend/tests/ai/test_rerank_eval.py`](backend/tests/ai/test_rerank_eval.py)
3. `delete:` Убрать OpenRouter как третий взаимозаменяемый local extraction provider. Local fake, DS Lab и production Yandex уже покрывают fallback, дешёвый external smoke path и целевой provider; заменить ветвление одним DS Lab/Yandex path. [`backend/src/ai_dating/ai/client.py`](backend/src/ai_dating/ai/client.py), [`backend/src/ai_dating/ai/extract.py`](backend/src/ai_dating/ai/extract.py), [`backend/src/ai_dating/config.py`](backend/src/ai_dating/config.py), [`backend/tests/ai/test_openrouter.py`](backend/tests/ai/test_openrouter.py)

net: ≈-1,090 lines, -0 deps possible.
