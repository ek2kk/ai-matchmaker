# Domain Docs

## Перед domain work

1. Прочитать корневой `AGENTS.md`, `docs/client-brief.md` и `docs/architecture/overview.md`.
2. Прочитать `CONTEXT.md`, если он существует.
3. Прочитать релевантные ADR из `docs/adr/`, если каталог существует.

Если `CONTEXT.md` или `docs/adr/` отсутствуют, продолжать без предупреждений. Создавать их только когда `/domain-modeling` фиксирует новый термин или решение.

## Layout

Это single-context repo:

```
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

Использовать термины из `CONTEXT.md`, когда он появится. Если вывод противоречит ADR, явно отметить конфликт.
