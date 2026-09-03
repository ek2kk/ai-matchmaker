# Cloud.ru Evolution Compute: closed beta configuration

Проверено: 2026-09-03. Источники в этом документе — только официальные
страницы и тарифы Cloud.ru.

## Выбор

**Одна Evolution Compute VM: 4 vCPU / 8 GB RAM, 100% guaranteed vCPU, 100 GB
SSD NVMe, Ubuntu 24.04 LTS, один public IP.**

На ней запускаются Docker Compose сервисы: Caddy (единственные опубликованные
порты `80`/`443`), FastAPI API, worker, PostgreSQL с `pgvector`/PostGIS и
приватный volume для медиа. ClickHouse и relay на beta не запускаются.

Это минимальная production-подобная конфигурация для закрытой beta до 100
пользователей. `2 vCPU / 4 GB` дешевле, но оставляет слишком мало RAM после
PostgreSQL, ОС и контейнеров; `4 vCPU / 8 GB` — рекомендуемый выбор. GPU не
нужен: DS Lab остаётся внешним provider для ML.

## Что выбрать в консоли

| Поле | Значение |
| --- | --- |
| Platform | Evolution Compute |
| Zone | Default **enabled** zone, в которой доступны Ubuntu 24.04 и выбранный flavor |
| Image / OS | Public image **Ubuntu 24.04 LTS (64-bit)** |
| Flavor | **4 vCPU / 8 GB RAM**, обычная VM (не `10%`, не `30%`, не preemptible) |
| Disks | Один **SSD NVMe 100 GB**: ОС, PostgreSQL, Docker volumes и небольшой закрытый media volume |
| Network | Новый VPC и одна подсеть с public IP; VM получает private IP и один public IP |
| Security group | Inbound: TCP `80`, `443` from `0.0.0.0/0`; TCP `22` только с личного статического IP разработчика. PostgreSQL, Docker/ClickHouse порты наружу не открывать. |
| SSH | Только existing public SSH key; password SSH не включать |
| Backup | План: ежедневный backup VM, 14 full restore points / 14 дней; перед каждым deploy дополнительно выполнить PostgreSQL logical dump и проверить восстановление |

Cloud.ru не публикует стабильное, не зависящее от проекта имя «региона» или
zone, пригодное для выбора заранее: доступные зоны, образы и свободные flavor
зависят от проекта. Консоль позволяет выбрать zone, а docs предписывают сменить
zone, если ресурс временно недоступен. Поэтому выбираем default enabled zone,
а не придумываем название географии.

В штатном backup Cloud.ru есть полные и инкрементальные копии; storage
тарифицируется, поэтому retention указан как осознанный лимит. Он защищает от
потери VM/диска, но не заменяет независимый зашифрованный PostgreSQL dump:
одна Cloud.ru account/region остаётся общим failure domain.

## Стоимость

Ниже — расчёт **за 30 суток (720 часов), с НДС**, по текущему тарифу
Evolution Compute от 29 июня 2026 года:

| Ресурс | Тариф | 30 дней |
| --- | ---: | ---: |
| VM 4 vCPU / 8 GB | 5,9414 ₽/час | 4 277,81 ₽ |
| SSD NVMe 100 GB | 0,01586 ₽/GB-час | 1 141,92 ₽ |
| Public IP | 0,2074 ₽/час | 149,33 ₽ |
| Backup storage, резерв 100 GB | 0,005856 ₽/GB-час | 421,63 ₽ |
| **Итого без исходящего трафика** |  | **5 990,69 ₽/30 дней** |

Backup storage — budget reserve, а не гарантированная цена: фактический объём
зависит от full/incremental chain и изменения данных. Исходящий трафик с public
IP также нельзя честно включить в фиксированный итог: по тарифу он стоит
`0,00366 ₽/MB` (около `3,75 ₽/GiB`). Следить за ним нужно с первого дня,
особенно при раздаче фотографий из VM.

## Стартовый grant

Новый физлицо-аккаунт может получить **4 000 бонусов** «Тест Evolution» за
первую привязанную карту: одна карта не должна была быть привязана к другому
Cloud.ru account, grant выдаётся один раз на cloud физлица и действует 60 дней.
Один бонус равен одному рублю. CPU/GPU исключения касаются GPU, поэтому эта
CPU-only VM попадает в допустимое использование. Grant покроет примерно 20
дней этой конфигурации без учёта egress и возможного превышения backup storage.

## Official sources

- [Evolution Compute тарифы, версия 260619](https://cloud.ru/documents/tariffs/evolution/evolution-compute) — VM, SSD NVMe, public IP, outbound traffic и backup storage.
- [Создание VM](https://cloud.ru/docs/virtual-machines/ug/topics/guides__create-vm) — zones, images, disk/network/security-group и SSH-key settings.
- [Public OS images](https://cloud.ru/docs/virtual-machines/ug/topics/concepts__images) — Ubuntu 24.04 LTS availability.
- [Backups](https://cloud.ru/docs/backup-evolution/ug/topics/concepts__backups) — full/incremental copies and retention behavior.
- [Start grant conditions](https://cloud.ru/docs/billing/ug/topics/concepts__start_grant) — 4,000 bonus terms and exclusions.
