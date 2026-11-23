"""Render Russian reports and scientific figures from completed, retained measurements."""
import json
from pathlib import Path
import shutil
import statistics

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'work/document-study-2.2';reports=ROOT/'reports'
    summary=json.loads((source/'summary.json').read_text(encoding='utf8'))
    for file in source.iterdir():
        if file.suffix in ('.json','.csv'):
            shutil.copyfile(file,reports/('document-2.2-'+file.name))
    adaptive=json.loads((reports/'document-2.2-adaptive-probe.json').read_text(encoding='utf8'))
    diagnostics=[]
    for family in summary['transfer']:
        for candidate in range(4):
            histories=[json.loads(file.read_text(encoding='utf8'))['checkpoint']['history']
                       for file in source.glob(f'{family}-candidate-{candidate}-seed-*-ep-150.json')]
            rows=[row for history in histories for row in history]
            diagnostics.append(dict(family=family,candidate=candidate,training_runs=len(histories),
                observed_training_episodes=len(rows),mean_steps=statistics.mean(r['steps'] for r in rows),
                early_stop_fraction=statistics.mean(r['steps']<20 for r in rows),
                **{key:statistics.mean(r.get(key,0.) for r in rows)
                   for key in ('reward','gradient_norm','gradient_variance','advantage_variance','mean_entropy','weight_change')}))
    (reports/'document-2.2-training-diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n',encoding='utf8')
    table=['| Обучение → проверка | RL reward | Лучший blind | Лучший informed | Untrained | RL macro F1 |',
           '|---|---:|---:|---:|---:|---:|']
    comparisons=[]
    for trained,targets in summary['transfer'].items():
        for tested,panel in targets.items():
            scores=panel['summary']['20']
            blind=max(('blind_statistical','blind_online','reconciliation','fixed_source','random_valid'),key=lambda p:scores[p]['reward'])
            informed=max(('budget_aware','greedy','heuristic_search'),key=lambda p:scores[p]['reward'])
            table.append(f"| {trained} → {tested} | {scores['learned']['reward']:.6f} | {scores[blind]['reward']:.6f} ({blind}) | {scores[informed]['reward']:.6f} ({informed}) | {scores['untrained']['reward']:.6f} | {scores['learned']['macro_f1']:.6f} |")
            pair=next(r for r in panel['paired'] if r['budget']==20 and r['right']==blind and r['metric']=='reward')
            comparisons.append(f"- {trained} → {tested}: RL − {blind} = {pair['difference']:.6f}, 95% company-bootstrap [{pair['bootstrap_95'][0]:.6f}; {pair['bootstrap_95'][1]:.6f}].")
    results='\n'.join(table)
    intervals='\n'.join(comparisons)
    common='''
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
'''
    limitation='''
Ограничения: синтетические компании и учебные бухгалтерские правила, не реальные
банки и не подтверждение IFRS. Браузер открыт владельцу; закрытая оценка выполняется
отдельно в Docker. Интервалы условны на этих панелях и не скорректированы за
множественные сравнения. Лучший blind в таблице — максимум среди сохранённых
конкурентов на тесте, а не алгоритм, заранее знающий победителя. Ни одной стратегии
не предоставлялись hidden truth при inference; финансовая арифметика общая.
'''
    documents={
      'RL_STUDY':f'''# AuditForge 2.2: контролируемое исследование RL
Гипотеза: исправленные представления наблюдений и обучения повысят качество
при ограниченном бюджете относительно untrained и сильнейшего generator-blind.
{common}
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
{results}

{intervals}

Порог практической победы: +0.02 reward и +0.01 F1, положительные нижние границы
95% парных интервалов против blind и untrained. Преимущество полного RL над
сильными blind не подтверждено. MLP не выбран validation; он не объявляется
улучшением. Перебор кандидатов остановлен; отрицательные результаты сохранены.
PPO не реализован: сначала проверены более простые исправленные методы.

Графики: `docs/figures/document-2.2-budgets.svg`, `document-2.2-training.svg`.
Методические первоисточники: [Actor-Critic](https://arxiv.org/abs/1602.01783),
[оценивание advantages](https://arxiv.org/abs/1506.02438),
[PPO](https://arxiv.org/abs/1707.06347). Реализация синхронная CPU, не A3C/GAE/PPO.
{limitation}''',
      'GENERATOR_BLIND_BENCHMARK':f'''# Generator-blind и информированные конкуренты
Гипотеза: знание распределения генератора объясняет часть преимущества старых
эвристик; RL следует сравнивать с сильными конкурентами обеих категорий.
{common}
## Доступная информация
Generator-blind: `blind_online` использует уже приобретённые источники и
документальную достаточность; `blind_statistical` дополнительно обучает частоты
публичных документальных исходов на тех же 150 train-компаниях и том же бюджете20.
Нет импорта генератора, truth, provenance или отчёта evaluator в policy-модуле.
Во время test статистика обученного blind заморожена; online обновляется только
по документам текущей компании. Общие бухгалтерские правила разрешены всем.

Generator-aware: `budget_aware`, `greedy`, `heuristic_search` знают вероятности
механизмов нового мира (.65/.50), равномерное распределение целей и структуру
финансовых связей. Это информированные эвристики, не доступ к конкретным меткам
и не математически оптимальный oracle. Search перебирает допустимые портфели
направлений; greedy использует энтропийное приближение. Старые v1-конкуренты с
исходными коэффициентами сохранены без изменений и обозначаются informed.

Контроли: untrained той же архитектуры/инициализации, случайные веса,
случайные запросы, фиксированный порядок, обычная сверка и ablation без
признаков документов. Все используют одинаковый бюджет и decoder.
Источник: `auditforge/document_policy.py`, `DocumentTrainer.fit_blind`.

## Измеренные результаты
{results}

{intervals}

RL пока не обошёл сильнейший generator-blind. Нельзя объяснять весь отрицательный
результат версии2.1 только доступом baseline к формуле генератора.
{limitation}''',
      'TRANSFER_REPORT':f'''# Двунаправленный перенос между финансовыми семействами
Гипотеза: приобретённая стратегия запросов переносится между независимыми
экономическими механизмами без дополнительного обучения.
{common}
Закупки создаются по количествам, ценам и частичным поставкам в
`document_world.procurement_events`. Сервисное семейство в
`independent_world.service_books` самостоятельно создаёт часы, этапы, удержания,
платежи, возвраты и проводки; `inject_service_faults` самостоятельно вносит причины
четырёх нарушений. Оно не вызывает старый generate или закупочный конструктор.
Сериализация документов, схема денег, бухгалтерский decoder и judge общие —
это явно ограничивает независимость. Два семейства не называются двумя банками.

Методика: отдельный выбор модели в каждой train-семье, затем оба направления
без дообучения, те же test-компании для честных парных сравнений.

## Матрица при бюджете20
{results}

{intervals}

Перенос не доказал устойчивое преимущество RL. Полные micro/macro F1, TP/FP/FN,
clean-метрики и бюджеты10/20/40/100 доступны в сыром JSON/CSV.
Источник: `auditforge/independent_world.py`, `scripts/document_benchmark.py`.
{limitation}''',
      'ADVERSARIAL_REPORT':f'''# Независимые атакующие проверки 2.2
Гипотеза: усложнение мира сохраняет финансовую причинность, достаточность
доказательств и границы доверия.

Методика и размер: отдельная панель32 компаний (две семьи × clean/nonclean ×8seed),
независимый Fraction-аудитор и `reference_evaluator.py`, перебирающий соответствия.
Проверены14 групп: денежная реконструкция/причинный replay, покрытие источников,
полная разрешимость, FP=0, совпадение судей, атаки на findings, приватные поля,
одноисточниковые запросы, скрытый evaluation reward, приобретённые доказательства,
бюджет, точный replay, неверные JSON-запросы и неизменность fixtures.
Все14 групп пройдены. ID/order-преобразования не изменили full-budget F1.

Атаки: чужая компания/evidence, частичный набор, дубликат, неверная сумма и валюта,
подмена ID, boolean вместо денег, неверный тип и timestamp. Некорректные публичные
книги отвергает независимый аудитор, а не молча исправляет policy.
Баланс сам по себе не считается доказательством корректности.

Локальные мутации: все23 прежних и6 новых выявлены. Новые включают знак actor,
знак entropy, critic return, нормализацию, boolean-параметры и повреждение источника.
Ошибки импорта и компиляции не засчитываются как выявленные мутации.
Исходные файлы не изменялись во время мутационных испытаний.

## Адаптивность
Все6 выбранных основных checkpoint не выбрали оптимальный следующий документ
в отдельном reference-following probe и не переключились между парными мирами.
Этот отрицательный результат: `reports/document-2.2-adaptive.json`.

После него отдельно зафиксирован диагностический протокол,400 reward-only
эпизодов на закупочных контрфактических парах, новые test-root и16 независимых
базовых компаний (32 альтернативных мира двух семейств). Первый journal-запрос
одинаково задан всем. Финальная linear policy выбрала оптимальный следующий
документ32/32, переключилась16/16; fixed/untrained1/32. Reward:
{adaptive['test']['summary']['learned']['reward']:.6f} против
{adaptive['test']['summary']['fixed']['reward']:.6f}. Это проверка способности
архитектуры учиться следовать ссылке, не исправление основного полного агента.
Отдельный обученный probe не подменяет основные checkpoint в таблицах.

`closing_transfer` v1 использует иной механизм recognition, поэтому старые
операционные признаки не гарантируют калиброванный риск. Диагностика сохранена
в adversarial JSON; старый генератор и его результаты не переписаны.

Повтор: `python -m scripts.document_adversarial --count 8`; мутации:
`python -m scripts.document_mutation`; diagnostic training:
`python -m scripts.document_adaptive_probe` (не перезаписывает завершённый отчёт).
Код: `scripts/document_adversarial.py`, `document_mutation.py`,
`document_adaptive_probe.py`; данные: `reports/document-2.2-adversarial.json`,
`document-2.2-mutation.json`, `document-2.2-legacy-mutation.json`, `document-2.2-adaptive-probe.json`.
Проверены перечисленные атаки, а не отсутствие всех возможных shortcut.
{limitation}''',
      'JURY_DEMO':'''# Техническая демонстрация AuditForge 2.2
Гипотеза: эксперимент и доказательства можно воспроизвести по сохранённому
checkpoint без выбора выгодного seed и без платных API.

Одна демонстрационная компания service_milestone, seed22022003, бюджет20.
Seed зафиксирован до основного test. Используется первый replicate модели,
выбранной по validation. Сравниваются learned, untrained, blind_statistical,
heuristic_search и random_valid. Вывод содержит все запросы, полученные отдельные
документы, findings, суммы, evidence, F1/reward и результат независимого evaluator.

Запуск: `python -m scripts.document_demo --output work/my-document-demo.json`.
Фактические результаты: `reports/document-2.2-demo.json`. Неудачный seed не заменяется.
Код: `scripts/document_demo.py`, `auditforge/document_policy.py`.

Сценарий показа до3минут:
1. 0:00–0:30 — Training Lab → расследование по документам v2 → сервисы,
   бюджет20, выбрать алгоритм/архитектуру, создать модель.
2. 0:30–1:10 — реальные шаги обучения, изменения весов и optimizer_steps,
   train/validation графики. Открыть ограничения: арифметика общая, RL выбирает источники.
3. 1:10–1:50 — отдельная проверка новых компаний; прочитать категории информации
   baseline и показать не только лучшую строку.
4. 1:50–2:20 — сравнение расследований: развернуть запрос, конкретный источник
   и поданные evidence. Проверить независимый judge в техническом JSON.
5. 2:20–3:00 — Proof Center, точный коммит и внешний CI; отдельно показать
   adaptive-probe32мира и объяснить, почему он не равен успеху полного агента.

Старый видеоролик не является демонстрацией2.2. Новый ролик не записан.
Готовы работающий интерфейс, повторяемый технический сценарий и реальные трассы.
Одна компания не доказывает превосходство; для выводов используется панель96компаний.
''',
      'LIMITATIONS':'''# Ограничения AuditForge 2.2
Проверяемое утверждение: какие выводы поддержаны экспериментами и какие остаются открытыми.

1. Основной RL не показал практически/статистически подтверждённого превосходства
   над сильнейшим generator-blind. Рост относительно untrained не равен победе над правилами.
2. Все6 основных checkpoint провалили отдельную короткую контрфактическую проверку
   следующего запроса. Специализированный reward-trained probe решил32/32 ситуаций,
   но ему заранее задан первый journal-запрос; это узкая диагностическая задача.
3. Четыре кандидата, триseed,150эпизодов — ограниченный поиск. Тест после просмотра
   не использовался для нового подбора основных моделей. PPO не реализован.
4. Реально независимы экономические события, проводки и causal mutations сервисов;
   схема, serializer, decoder и reward общие. Два синтетических семейства не являются
   моделью банковского рынка или подтверждением переноса в реальные банки.
5. Договоры, банковские подтверждения, акты и allocation документы добавляют
   подтверждающие связи, но часть из них избыточна для четырёх официальных типов.
   Это структурированные JSON, не OCR/NLP свободного текста и не юридическая экспертиза.
6. Индекс раскрывает типы источников и связи case. Это допустимые публичные данные,
   но возможный статистический shortcut. Проверка не доказывает отсутствия всех shortcut.
7. Общий decoder детерминированный: модель не обучает денежную арифметику. При
   достаточном бюджете полный аудитор решает компании; RL не обязателен для полного решения.
8. Нормализация advantages доступна в интерфейсе только для REINFORCE. MLP сохранён
   как проверенный кандидат, но validation его не выбрала и преимущество не заявляется.
9. Парные bootstrap CI кластеризуются по компаниям;96компаний, не27648 независимых
   наблюдений. Нет коррекции множественных сравнений и гарантии за пределами панели.
10. Браузер открыт, локальное хранилище и checkpoint доступны пользователю.
    Изоляция policy подтверждается отдельным Docker-тестом, не интерфейсом.
11. На этой Windows-машине Docker отсутствует. Реальные закрытые испытания выполняются
    в GitHub Actions; окончательное доказательство — успешный run точного коммита,
    скачанный им проверенный ZIP и SHA-256. Текст отчёта сам по себе его не заменяет.
12. Старое /api/me может возвращать404 до резервного Supabase/guest пути.
    Проверенный browser E2E использует гостя, не новый внешний аккаунт.
13. Старый ролик не соответствует2.2; новый ролик не записан. Официальная оценка
    GENESIS,100/100, победа и superiority не заявляются.

Методика: сопоставление исходников, raw-результатов96компаний,16контрфактических
компаний диагностического probe, аудита32компаний и реального browser/native parity.
Повтор: `python -m scripts.document_release_check`; основные данные:
`reports/document-2.2-summary.json`, `document-2.2-adaptive*.json`.
Код: `auditforge/document_training.py`, `document_world.py`, `independent_world.py`.
''',
      'FINAL_AUDIT':f'''# Финальный инженерный аудит AuditForge 2.2
Гипотеза: новая документальная среда и обучение могут быть реализованы как
проверяемое необязательное расширение без разрушения исходной сдачи GENESIS.
{common}
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
{results}

{intervals}

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
{limitation}'''
    }
    for name,body in documents.items():
        (ROOT/f'AUDITFORGE_2_2_{name}.md').write_text(body.strip()+'\n',encoding='utf8')
    figures(summary,source)


def figures(summary,source):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=ROOT/'docs/figures';out.mkdir(exist_ok=True)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ax,(trained,tested) in zip(axes.flat,[(a,b) for a in summary['transfer'] for b in summary['transfer'][a]]):
        panel=summary['transfer'][trained][tested]['summary'];budgets=[10,20,40,100]
        for policy in ('learned','untrained','blind_online','blind_statistical','budget_aware','heuristic_search'):
            ax.plot(budgets,[panel[str(b)][policy]['reward'] for b in budgets],marker='o',label=policy)
        ax.set(title=f'{trained} → {tested}',xlabel='Action budget',ylabel='Mean official reward',ylim=(-1.05,1.05))
        ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7)
    fig.savefig(out/'document-2.2-budgets.svg');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,family in zip(axes,summary['transfer']):
        for candidate in range(4):
            histories=[json.loads(file.read_text(encoding='utf8'))['checkpoint']['history']
                       for file in source.glob(f'{family}-candidate-{candidate}-seed-*-ep-150.json')]
            points=list(range(25,151,25))
            values=[statistics.mean(row['reward'] for history in histories for row in history[n-25:n]) for n in points]
            ax.plot(points,values,marker='o',label=f'candidate{candidate}')
        ax.set(title=family,xlabel='Training episodes',ylabel='Train reward, trailing25',ylim=(-1.05,1.05));ax.grid(alpha=.2);ax.legend()
    fig.savefig(out/'document-2.2-training.svg');plt.close(fig)


if __name__=='__main__':main()
