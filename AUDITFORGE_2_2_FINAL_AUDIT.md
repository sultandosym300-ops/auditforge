# Финальный инженерный аудит AuditForge 2.2
Гипотеза: новая документальная среда и обучение могут быть реализованы как
проверяемое необязательное расширение без разрушения исходной сдачи GENESIS.

Дата: 23 ноября 2026. Версия пакета 2.2.0; исходный контракт генератора 2.0.1 сохранён.
Это отчёт разработчиков, не официальная оценка GENESIS. Старые результаты 2.1.0 неизменны.

Независимая основная тестовая панель: 48 закупочных и 48 сервисных компаний,
всего 96 компаний. Две обучающие семьи × две тестовые семьи × три checkpoint ×
четыре бюджета × 12 стратегий = 27 648 запусков. Повторные checkpoint и направления
переноса не увеличивают число независимых компаний. В каждой семье 10 из 48
компаний явно clean; другие могут оказаться без нарушений по распределению.

Код исследования: `scripts/document_benchmark.py`; неизменяемый протокол:
`configs/document-study-2.2.json`. Сырые результаты: `reports/document-2.2-*-raw.json`
и CSV. Выбор обеих моделей записан до открытия test-компаний.
Повтор: `python -m scripts.document_benchmark --output work/new-document-study`.
Проверка сохранённых результатов: `python -m scripts.document_release_check`.

## Реализовано
`investigation_v2`: отдельный документ за действие, девять видов источников,
две экономические семьи, частичные и пакетные оплаты, возвраты, FX, период,
компенсирующие расхождения, похожие корректные случаи и clean-компании.
Бухгалтерский баланс проверяется вместе с независимой денежной реконструкцией,
causal before/after и публичной достаточностью. Все источники доступны при
полном бюджете; list_records не даёт обхода стоимости полным пакетом.
Основные файлы: `document_world.py`, `independent_world.py`, `env.py`.

Linear/MLP policy и реальная оптимизация, безопасный JSON checkpoint с pending-batch,
fitted/online blind, informed и untrained/random контроли. Первичные214тестов
сохранены; новый общий набор содержит244теста. Локально23 прежние и6 новые мутации
выявлены. Сравнение браузерной MLP после25эпизодов с native Python:
максимальная разница параметров менее5×10⁻¹⁷. Проверены импорт/экспорт,
validation8компаний,4трассы, RU/KK/EN и мобильная ширина390 без переполнения.

В CI добавлены отдельный untrusted policy image, network none, read-only,
UID65534, cap-dropALL/no-new-privileges, отсутствие evaluator/generator в образе,
паритет реальных обученных linear/MLP между Docker и native.
ДваCPU/4GiB ограничивают evaluator; policy отдельно1CPU/512MiB.

## Научный итог при20действиях
| Обучение → проверка | RL reward | Лучший blind | Лучший informed | Untrained | RL macro F1 |
|---|---:|---:|---:|---:|---:|
| procurement → procurement | -0.418087 | 0.063958 (blind_online) | 0.098482 (budget_aware) | -0.549181 | 0.297950 |
| procurement → service_milestone | -0.354000 | 0.237375 (blind_online) | 0.264361 (budget_aware) | -0.462472 | 0.329861 |
| service_milestone → procurement | -0.201069 | 0.063958 (blind_online) | 0.098482 (budget_aware) | -0.549181 | 0.410417 |
| service_milestone → service_milestone | -0.137250 | 0.237375 (blind_online) | 0.264361 (budget_aware) | -0.462472 | 0.441667 |

- procurement → procurement: RL − blind_online = -0.482045, 95% company-bootstrap [-0.679152; -0.287124].
- procurement → service_milestone: RL − blind_online = -0.591375, 95% company-bootstrap [-0.824329; -0.359875].
- service_milestone → procurement: RL − blind_online = -0.265028, 95% company-bootstrap [-0.449430; -0.078540].
- service_milestone → service_milestone: RL − blind_online = -0.374625, 95% company-bootstrap [-0.569144; -0.174153].

Главная научная цель не достигнута. Отдельный probe показывает обучаемую
reference-following способность на32 альтернативных мирах, но основные6 моделей
её не продемонстрировали. Не следует заменять этот вывод успешным CI.

## Выпуск и проверка
Команды: `python -m unittest discover -s tests -q`,
`python -m scripts.document_adversarial --count 8`,
`python -m scripts.document_mutation`, `python -m scripts.document_release_check`,
`python -m scripts.document_container`, `npm run build`.
Пакет: `python -m scripts.package_submission --output work/AuditForge-2.2.0.zip`.
Исходный train/dev, траектории, пять инструментов, четыре типа, официальный reward,
100действий/60секунд и старые checkpoint/релизы сохранены.

Этот отчёт не подменяет наблюдение успешного внешнего CI. В Release прикладываются
отдельные доказательства его точного SHA, проверки чистого архива и публикации сайта.

Ограничения: синтетические компании и учебные бухгалтерские правила, не реальные
банки и не подтверждение IFRS. Браузер открыт владельцу; закрытая оценка выполняется
отдельно в Docker. Интервалы условны на этих панелях и не скорректированы за
множественные сравнения. Лучший blind в таблице — максимум среди сохранённых
конкурентов на тесте, а не алгоритм, заранее знающий победителя. Ни одной стратегии
не предоставлялись hidden truth при inference; финансовая арифметика общая.
