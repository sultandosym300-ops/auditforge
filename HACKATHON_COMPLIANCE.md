# Соответствие кейсу FinTech хакатона Genesis

Это карта опубликованных требований, а не официальная оценка жюри. Результат конкретного релиза подтверждают успешный GitHub Actions run, `release-evidence.json` и исходный коммит в манифесте ZIP. Архив нельзя объявлять готовым до завершения всех обязательных проверок.

| Критерий | Максимум кейса | Реализация | Проверка и воспроизведение |
|---|---:|---|---|
| RL API и изоляция | 25 | `auditforge/env.py`, `auditforge/agent_runner.py`, `Dockerfile.policy` | 20 контрактных случаев; `python -m scripts.verify_container`; `python -m scripts.jury_broker` |
| Данные и скрытый эталон | 25 | `auditforge/generator.py`, `auditforge/financial_audit.py`, `configs/`, `datasets/` | Независимое восстановление финансов; `python -m scripts.submission_check --archive work/submission/AuditForge-final.zip` |
| Matcher и награда | 25 | `auditforge/matcher.py`, `auditforge/env.py` | 20 случаев награды, независимые ожидания и атакующие примеры; `python -m scripts.ultimate_verify` |
| Воспроизводимость и обобщение | 15 | `auditforge/verify.py`, `auditforge/proof.py`, `trajectories/` | Повтор действий, переименование и перестановки; `python -m scripts.v4_proof_check` |
| Инженерное качество | 10 | README, схемы, лицензии, Docker, CI и манифест | Чистая сборка, тесты, валидация ZIP и точные хеши |

## Обязательные материалы

| Требование | Реализация / материал | Исполняемая проверка | Критерий успешности |
|---|---|---|---|
| Python 3.11, CPU, без сети | `Dockerfile`, `pyproject.toml`, пустые runtime-зависимости | CI: `--network none --cpus 2 --memory 4g` | Версия Python, cgroup и завершение команд подтверждены |
| reset/step, пять инструментов | `auditforge/env.py` | `tests/test_contract.py` | Все контрактные случаи проходят |
| 100 действий, 60 секунд, страницы до 50 записей | `auditforge/env.py` | Контрактные и терминальные регрессии | Ограничения применяются самим ядром |
| Четыре вида ошибок и их взаимодействия | `auditforge/generator.py` | `scripts/ultimate_matrix.py`, финансовый аудитор | Валидные суммы, эталон и причинные связи |
| Полные доказательства, валюта, допуски | `auditforge/matcher.py` | `scripts/ultimate_evidence.py`, `scripts/v4_proof_check.py` | Нет повторного зачёта и ложного вознаграждения |
| Скрытые truth/provenance | Раздельные public / evaluator_private; ограниченный брокер | Тесты приватности, проверка контейнера и ZIP | Агенту и публичным траекториям эталон не передаётся |
| 10 train и 10 dev | `configs/train.json`, `configs/dev.json`, `datasets/` | `scripts/submission_check.py` | Полная регенерация и сравнение, 20 разных эпизодов |
| Четыре базовые политики | `scripts/run_baselines.py` | `python -m scripts.run_baselines --policy all --allow-evaluator-oracle` | Все адаптеры завершаются в лимите; Oracle только доверенному оценщику |
| Траектории | `trajectories/trajectories.jsonl` | Полный повтор в submission_check | Семь обязательных полей, совпадающие действия, наблюдения, награды и флаги |
| Схемы | `docs/public.schema.json`, `docs/findings.schema.json` | Регрессии API и валидация комплекта | Структура соответствует фактическому интерфейсу |
| Лицензия и зависимости | `LICENSE`, `THIRD_PARTY_NOTICES.md`, `docs/licenses/`, npm lockfile | Чистая установка, сборка и проверка состава | Нужные тексты и зафиксированные зависимости присутствуют |
| Архитектура | `docs/DESIGN_NOTE.md` | Проверка состава комплекта | Описаны генерация, ошибки, границы доверия и ограничения |
| Рабочая демонстрация | Сайт, `JURY_LIVE_DEMO_SCRIPT.md` | Семь этапов в настоящем браузере | Реальная компания, действия, находки, доказательства и обучение |
| Автономная проверка | `scripts/ultimate_verify.py`, `scripts/v4_verify.py` | `python -m scripts.v4_verify --full-core` | Ненулевой код при любой проваленной стадии |
| Размер и безопасный архив | `scripts/package_submission.py`, `scripts/submission_check.py` | Проверка ZIP и точного перечня хешей | Меньше 1 GB, нет секретов, кэшей, небезопасных путей и лишних файлов |

Итог по каждому обязательному этапу фиксируется в CI точного коммита. Более тяжёлые исследовательские результаты уже проведены ранее и сохранены отдельно; новые исследования для финальной подготовки не выполняются. Баллы выше — веса критериев кейса, а не присвоенная жюри оценка.
