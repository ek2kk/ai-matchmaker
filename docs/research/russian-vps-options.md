# VPS в РФ для closed beta

Дата проверки: **2026-09-03**. Источники — только сайты и документация самих провайдеров. Цены — публичные на дату проверки; финальную сумму надо сверить в калькуляторе при заказе (IP, трафик, backup и НДС могут считаться отдельно).

## Рекомендация

Для первых ~100 пользователей — **Timeweb Cloud MSK 80: 4 vCPU / 8 GB / 80 GB NVMe за 1 800 ₽/мес**. Это ровно целевая конфигурация, есть Москва, готовые backup/аварийная копия и S3/managed PostgreSQL. Разворачивать на одной VM через Docker Compose; PostgreSQL и фото не считать защищёнными, пока не настроены отдельные backup в S3.

Если приоритет — более зрелые managed-сервисы и рост без миграции, выбрать **Selectel**. Если нужен именно hyperscaler/IAM и managed-экосистема — **Yandex Cloud**. Для этой beta они сложнее и обычно дороже простой VM.

## Сравнение

| Провайдер | VM около 4 vCPU / 8 GB / 80–100 GB | Локации РФ | Backup и storage | Managed PostgreSQL | Вывод |
| --- | --- | --- | --- | --- | --- |
| [Timeweb Cloud](https://timeweb.cloud/services/cloud-servers) | **MSK 80 — 1 800 ₽/мес**, 4 × 3.3 GHz, 8 GB, 80 GB NVMe, 1 Gbit/s. Почасовая оплата. | Москва, Санкт-Петербург, Новосибирск. | Один snapshot VM бесплатно на 7 дней; ручные/автоматические backup и для Москвы/СПб аварийная копия. Есть [S3](https://timeweb.cloud/services/s3). | Есть [managed PostgreSQL](https://timeweb.cloud/services/postgresql); automatic backup — 6 ₽/GB/мес. | **Лучший простой старт.** |
| [Selectel Cloud Servers](https://selectel.ru/services/cloud/servers/vm/) | Конфигуратор; публичную фиксированную цену именно для 4/8/80 страница не публикует, поэтому её нужно получить в [калькуляторе](https://selectel.ru/prices/). Почасовое списание, до 3 TB общего бесплатного внешнего трафика/мес. | Москва, Санкт-Петербург, Новосибирск. | Есть snapshot/backup и [S3 Object Storage](https://selectel.ru/services/cloud/object-storage/). | Есть [Cloud Databases PostgreSQL](https://selectel.ru/services/cloud/managed-databases/postgresql/): automatic WAL-G backup, PITR, хранение 7 дней. | **Лучше при росте и желании managed DB.** |
| [Yandex Compute Cloud](https://yandex.cloud/en/docs/compute/pricing) | Гибкий конфигуратор; цены зависят от platform/disk и считаются посекундно. Диск и snapshot оплачиваются отдельно, поэтому одной опубликованной цены «4/8/100» нет. | Russia region, зоны доступности ru-central1. | [Snapshots](https://yandex.cloud/en/docs/compute/concepts/snapshot), Object Storage, отдельный agent-based [Cloud Backup](https://yandex.cloud/en/docs/overview/platform-comparison/vmware/storage-subsystem). | Есть [Managed Service for PostgreSQL](https://yandex.cloud/en/docs/managed-postgresql/pricing); compute, storage и backup учитываются отдельно. | Сильный вариант, но для одной VM избыточен. |
| [VK Cloud](https://cloud.vk.com/products/compute) | Compute/VM доступны, но текущую публичную цену сопоставимой 4/8/80 конфигурации официальный сайт не показывает без console/calculator. | Российские регионы зависят от проекта/сервиса — проверить в console до оплаты. | Есть [Object Storage](https://cloud.vk.com/products/object-storage) и backup-сервисы; детали и цену надо подтвердить в console. | Есть [Cloud Databases](https://cloud.vk.com/products/cloud-databases), включая PostgreSQL. | Рассматривать, если уже есть аккаунт/кредиты VK; не первый выбор без них. |
| [RuVDS](https://ruvds.com/ru/vps_nvme/) | **NVMe Drive 2 — 2 699 ₽/мес** при оплате 3 мес: 4 × 3.4 GHz, 8 GB, 90 GB NVMe. Акция заявлена до 31.12.2026. | Москва, Королёв, Казань, Санкт-Петербург, Екатеринбург, Новосибирск и др. | Есть [backup](https://ruvds.com/ru/helpcenter/backup/), но для off-machine копии администрируешь сам; first-party [инструкция Restic](https://ruvds.com/ru/helpcenter/nastroyka-restic-na-ubuntu-i-debian/). | Нет first-party managed PostgreSQL/Object Storage. | Простой фиксированный VPS, если готов самостоятельно обслуживать data layer. |
| [Cloud.ru Evolution Compute](https://cloud.ru/products/evolution-compute) | Готовый профиль **4 vCPU / 8 GB / 30 GB NVMe**, 100% vCPU; объём диска увеличивается в calculator. Цена зависит от профиля/локации и показывается в console. | Три зоны доступности в дата-центрах РФ. | Условия сервиса предусматривают хранение и восстановление backup; есть [S3 Object Storage](https://cloud.ru/products/object-storage). | Есть [managed PostgreSQL](https://cloud.ru/products/cloud-databases). | Хорошая корпоративная альтернатива, но не проще Timeweb для beta. |

## Что нужно заказать

1. VM `4 vCPU / 8 GB / 80–100 GB NVMe`, Ubuntu LTS, российская локация (для старта — Москва).
2. Один IPv4, домен и DNS; открыть только `80/tcp`, `443/tcp` и SSH по ключу/своему IP.
3. Приватный S3 bucket для encrypted `pg_dump`/WAL и media. Восстановление backup нужно проверить до приглашения пользователей.
4. На старте можно держать PostgreSQL на VM, но не ClickHouse: analytics relay выключить до появления необходимости. Managed PostgreSQL — следующий шаг, а не обязательная часть beta.

## Важные оговорки

- Snapshot VM не заменяет согласованный PostgreSQL backup: для базы нужен логический backup или WAL/PITR; у managed DB это даёт провайдер.
- Для dating-приложения с персональными данными выбрать РФ-локацию, закрыть публичный доступ к БД и bucket, включить шифрование/retention. Юридические обязанности (включая 152-ФЗ) не перекладываются на VPS-провайдера.
- Не привязывать production к рекламным бонусам: они не являются частью базовой ежемесячной стоимости.

## Первичные источники

- Timeweb: [VM и цены](https://timeweb.cloud/services/cloud-servers), [создание VM / backup](https://timeweb.cloud/docs/cloud-servers/manage-servers/create-server), [PostgreSQL](https://timeweb.cloud/services/postgresql), [logical DB backups](https://timeweb.cloud/docs/dbaas/dbaas-manage/logical-backups).
- Selectel: [VM](https://selectel.ru/services/cloud/servers/vm/), [модель оплаты](https://docs.selectel.ru/cloud-servers/about/payment/), [managed DB](https://docs.selectel.ru/managed-databases/about/about-managed-databases/), [PostgreSQL backups](https://docs.selectel.ru/managed-databases/postgresql/backups/).
- Yandex Cloud: [Compute pricing](https://yandex.cloud/en/docs/compute/pricing), [snapshots](https://yandex.cloud/en/docs/compute/concepts/snapshot), [PostgreSQL pricing](https://yandex.cloud/en/docs/managed-postgresql/pricing).
- VK Cloud: [Compute](https://cloud.vk.com/products/compute), [Object Storage](https://cloud.vk.com/products/object-storage), [Cloud Databases](https://cloud.vk.com/products/cloud-databases).
- RuVDS: [NVMe VPS и цены](https://ruvds.com/ru/vps_nvme/), [российские локации](https://ruvds.com/ru-rub), [backup](https://ruvds.com/ru/helpcenter/backup/), [Restic на Ubuntu/Debian](https://ruvds.com/ru/helpcenter/nastroyka-restic-na-ubuntu-i-debian/).
- Cloud.ru: [Evolution Compute](https://cloud.ru/products/evolution-compute), [условия Compute](https://cloud.ru/documents/contracts/terms-of-service/evolution/evolution-compute/description-evolution-compute), [VM zones](https://cloud.ru/docs/virtual-machines/ug/topics/concepts__virtual-machines).
