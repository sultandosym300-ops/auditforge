# AuditForge 2.2: контролируемое исследование RL
Гипотеза: исправленные представления наблюдений и обучения повысят качество
при ограниченном бюджете относительно untrained и сильнейшего generator-blind.

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

## Методика
Четыре кандидата: linear REINFORCE, linear Monte Carlo Actor-Critic,
linear REINFORCE с нормализацией advantages и entropy, MLP с одним tanh-слоем
из восьми узлов с теми же дополнениями. Learning rate 0.03, entropy 0.01
для двух последних; три training seed, 150 эпизодов на кандидата.
Нормализация выполняется по четырём независимым траекториям; неполный batch
применяется явно на checkpoint 50/100/150. История хранит реальные optimizer_steps.
Кандидат и checkpoint выбираются по средней validation reward 16 новых компаний
при бюджете 20. Test seed не используются для выбора. Сохранены все кандидаты.

REINFORCE использует baseline до текущего reward, Actor-Critic — замороженные
значения до обновления и Monte Carlo return. Градиенты linear/MLP проверены
finite difference для A logπ + βH. Сохраняются norm/variance градиентов,
variance advantages, entropy, длины эпизодов и изменения весов.
Код: `auditforge/document_training.py`, `auditforge/document_policy.py`.
Агрегаты всех кандидатов: `reports/document-2.2-training-diagnostics.json`.
Gradient variance оценивается между траекториями batch; при batch1 это0,
что не доказывает отсутствия стохастического шума. Признаки масштабированы
в[0,1], но содержат лишь ограниченные типы/ссылки и факт приобретения источников,
а не полное представление бухгалтерских гипотез. Это сохраняющееся слабое место.

## Результаты при 20 действиях
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

Порог практической победы: +0.02 reward и +0.01 F1, положительные нижние границы
95% парных интервалов против blind и untrained. Преимущество полного RL над
сильными blind не подтверждено. MLP не выбран validation; он не объявляется
улучшением. Перебор кандидатов остановлен; отрицательные результаты сохранены.
PPO не реализован: сначала проверены более простые исправленные методы.

Графики: `docs/figures/document-2.2-budgets.svg`, `document-2.2-training.svg`.
Методические первоисточники: [Actor-Critic](https://arxiv.org/abs/1602.01783),
[оценивание advantages](https://arxiv.org/abs/1506.02438),
[PPO](https://arxiv.org/abs/1707.06347). Реализация синхронная CPU, не A3C/GAE/PPO.

Ограничения: синтетические компании и учебные бухгалтерские правила, не реальные
банки и не подтверждение IFRS. Браузер открыт владельцу; закрытая оценка выполняется
отдельно в Docker. Интервалы условны на этих панелях и не скорректированы за
множественные сравнения. Лучший blind в таблице — максимум среди сохранённых
конкурентов на тесте, а не алгоритм, заранее знающий победителя. Ни одной стратегии
не предоставлялись hidden truth при inference; финансовая арифметика общая.
