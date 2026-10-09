# Cloud.ru Evolution Compute: personal staging configuration

Проверено: 2026-09-03. Источники в этом документе — только официальные
страницы и тарифы Cloud.ru.

## Выбор

**Одна Evolution Compute VM: 2 vCPU / 4 GB RAM, обычная VM (не 10%/30% и не
прерываемая), 30 GB SSD NVMe, Ubuntu 24.04 LTS, один public IP.**

На ней запускаются Docker Compose сервисы: Caddy (единственные опубликованные
порты `80`/`443`), FastAPI API, worker, PostgreSQL с `pgvector`/PostGIS и
приватный volume для временных тестовых медиа. ClickHouse и relay не
запускаются.

Это самый дешёвый разумный вариант для личного staging и ручных тестов одного
разработчика. GPU не нужен: DS Lab остаётся внешним provider для ML. Данные
только тестовые и удаляемые, поэтому Cloud.ru backup не включаем.

## Следующий размер при переходе к beta

Для закрытой beta хранить реальные данные или медиа на этом staging нельзя.
Следующий разумный размер — `4 vCPU / 8 GB / 100 GB` с backup и отдельной
политикой восстановления. В актуальном тарифе доступны также `2 vCPU / 8 GB`
и `4 vCPU / 8 GB`; это обычные VM, не `10%`/`30%` guaranteed и не прерываемые.

| Flavor и диск | VM/час с НДС | Total за 30 дней, без egress |
| --- | ---: | ---: |
| 2 vCPU / 4 GB + 30 GB, без backup | 2,9707 ₽ | **2 630,81 ₽** |
| 2 vCPU / 4 GB + 50 GB | 2,9707 ₽ | 3 070,01 ₽ |
| 2 vCPU / 8 GB + 50 GB | 5,5022 ₽ | 4 892,69 ₽ |
| 4 vCPU / 8 GB + 50 GB | 5,9414 ₽ | 5 208,91 ₽ |
| 2 vCPU / 4 GB + 80 GB | 2,9707 ₽ | 3 539,07 ₽ |

В total включены public IP, NVMe и, кроме staging-строки, резерв 50/80 GB
backup storage по 720 часов; исходящий трафик не включён. У Cloud.ru есть только
помегабайтная тарификация диска и backup, поэтому 50 GB и 80 GB — доступные размеры, а не отдельные
bundles: `0,01586 ₽/GB-час` и `0,005856 ₽/GB-час` соответственно.

Для текущего staging `2 / 4 / 30` достаточно: PostgreSQL, API и worker делят
всего 4 GB, поэтому не включать ClickHouse, ограничить worker concurrency одним
job и не загружать реальные фото. При первом sustained OOM или задержках
увеличить RAM/диск без смены архитектуры.

## Что выбрать в консоли

| Поле | Значение |
| --- | --- |
| Platform | Evolution Compute |
| Zone | Default **enabled** zone, в которой доступны Ubuntu 24.04 и выбранный flavor |
| Image / OS | Public image **Ubuntu 24.04 LTS (64-bit)** |
| Flavor | **2 vCPU / 4 GB RAM**, обычная VM (не `10%`, не `30%`, не preemptible) |
| Disks | Один **SSD NVMe 30 GB**: ОС, PostgreSQL, Docker volumes и только временный test-media volume |
| Network | Новый VPC и одна подсеть с public IP; VM получает private IP и один public IP |
| Security group | Inbound: TCP `80`, `443` from `0.0.0.0/0`; TCP `22` только с личного статического IP разработчика. PostgreSQL, Docker/ClickHouse порты наружу не открывать. |
| SSH | Только existing public SSH key; password SSH не включать |
| Backup | **Не включать**: данные staging тестовые и удаляемые. Перед изменением схемы достаточно локального dump, если нужно сохранить текущий тестовый сценарий. |

Cloud.ru не публикует стабильное, не зависящее от проекта имя «региона» или
zone, пригодное для выбора заранее: доступные зоны, образы и свободные flavor
зависят от проекта. Консоль позволяет выбрать zone, а docs предписывают сменить
zone, если ресурс временно недоступен. Поэтому выбираем default enabled zone,
а не придумываем название географии.

В штатном backup Cloud.ru есть полные и инкрементальные копии, но для этого
одноразового staging они не требуются. Включить их до появления реальных
пользовательских данных.

## Стоимость

Ниже — расчёт **за 30 суток (720 часов), с НДС**, по текущему тарифу
Evolution Compute от 29 июня 2026 года:

| Ресурс | Тариф | 30 дней |
| --- | ---: | ---: |
| VM 2 vCPU / 4 GB | 2,9707 ₽/час | 2 138,90 ₽ |
| SSD NVMe 30 GB | 0,01586 ₽/GB-час | 342,58 ₽ |
| Public IP | 0,2074 ₽/час | 149,33 ₽ |
| Backup storage | отключён | 0 ₽ |
| **Итого без исходящего трафика** |  | **2 630,81 ₽/30 дней** |

Исходящий трафик с public IP также нельзя честно включить в фиксированный итог:
по тарифу он стоит
`0,00366 ₽/MB` (около `3,75 ₽/GiB`). Следить за ним нужно с первого дня,
особенно при раздаче фотографий из VM.

## Стартовый grant

Новый физлицо-аккаунт может получить **4 000 бонусов** «Тест Evolution» за
первую привязанную карту: одна карта не должна была быть привязана к другому
Cloud.ru account, grant выдаётся один раз на cloud физлица и действует 60 дней.
Один бонус равен одному рублю. CPU/GPU исключения касаются GPU, поэтому эта
CPU-only VM попадает в допустимое использование. Grant покроет всю стоимость
первых 30 дней и примерно 45 дней непрерывного staging без учёта egress.

## Official sources

- [Evolution Compute тарифы, версия 260619](https://cloud.ru/documents/tariffs/evolution/evolution-compute) — VM, SSD NVMe, public IP, outbound traffic и backup storage.
- [Создание VM](https://cloud.ru/docs/virtual-machines/ug/topics/guides__create-vm) — zones, images, disk/network/security-group и SSH-key settings.
- [Public OS images](https://cloud.ru/docs/virtual-machines/ug/topics/concepts__images) — Ubuntu 24.04 LTS availability.
- [Backups](https://cloud.ru/docs/backup-evolution/ug/topics/concepts__backups) — full/incremental copies and retention behavior.
- [Start grant conditions](https://cloud.ru/docs/billing/ug/topics/concepts__start_grant) — 4,000 bonus terms and exclusions.
