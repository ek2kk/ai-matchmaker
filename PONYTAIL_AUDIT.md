# Ponytail audit

Scope: весь tracked tree, кроме lockfiles. Проверка ограничена over-engineering и complexity; correctness, security и performance не оценивались. Оценки строк приблизительны и не включают миграции/lockfiles.

1. `delete:` Удалить выполненные разделы 0–11 из исторического implementation-плана; они дублируют source-of-truth в `docs/architecture/` и не имеют входящих ссылок. Оставить только open gates 0.1, 12–14 либо перенести их в roadmap. [`todos.md`](todos.md)
2. `yagni:` Удалить synthetic rerank evaluator и console-script: он всегда формирует synthetic verdict, а runtime всё равно требует human `decision: pass`; до Phase 3 достаточно статичного failing manifest и ручного проверенного артефакта. [`backend/src/ai_dating/ai/eval.py`](backend/src/ai_dating/ai/eval.py), [`backend/pyproject.toml`](backend/pyproject.toml), [`backend/tests/ai/test_rerank_eval.py`](backend/tests/ai/test_rerank_eval.py)
net: ≈-990 lines, -0 deps possible.
