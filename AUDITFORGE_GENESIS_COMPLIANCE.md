# Проверка по официальному FinTech-кейсу Genesis

Это матрица команды разработки, не оценка жюри. Максимумы — веса критериев.
Обязательный компактный генератор 2.0.1 и 10+10 открытых эпизодов сохранены.
Пакет 2.1.0 добавляет необязательный профиль; он не подменяет закрытые
стандартные задачи и не вводит новый обязательный тип ошибки.

| Критерий | Максимум | Требование и реализация | Код | Команда | Фактический результат / риск | Независимая проверка жюри |
|---|---:|---|---|---|---|---|
| RL API и изоляция | 25 | reset/step, пять инструментов, 100 действий/60 секунд, terminal/truncated, неверный ввод, закрытые ответы | auditforge/env.py; agent_runner.py; Dockerfile.policy; Dockerfile.sequential-policy | python -m scripts.ultimate_contract; python -m scripts.verify_container; python -m scripts.sequential_container | 20 локальных контрактных проверок успешны; OS-изоляция подтверждается отдельным CI. Браузер открыт | Свои вредоносные политики и проверка effective cgroup/UID/network/files |
| Данные и эталон | 25 | Четыре типа, два взаимодействия, чистые случаи, provenance, денежные единицы и достаточные документы | generator.py; realistic.py; investigation_world.py; reconcile.py | python -m scripts.ultimate_matrix; python -m scripts.sequential_adversarial | 20 стандартных закрытых конфигураций локального стенда успешны; 24 новые компании полностью разрешимы при большом бюджете | Проверить причинные before/after, округление, независимые суммы и ложные сигналы |
| Matcher и reward | 25 | Максимальное взаимно однозначное соответствие; тип/IDs/сумма/валюта/evidence; неизменённая официальная формула | matcher.py; reference_evaluator.py; tests/test_jury_reward.py | python -m unittest tests.test_reference_evaluator tests.test_jury_reward -q | 11 тестов, включая 700 малых графов и атакующие JSON; reference ограничен 16 truths | Свои неоднозначные совпадения, дубли, денежные границы и тайм-аут |
| Воспроизводимость и обобщение | 15 | Зафиксированные seed/config, JSONL, replay, ID/order-пары, train/validation/test и отдельный transfer | configs/; scripts/jury_replay.py; sequential_benchmark.py; sequential_acceptance.py | python -m scripts.ultimate_verify --seed 801973140685; python -m scripts.sequential_acceptance | 20 стандартных пар успешны; 576 повторов V2 совпали. Превосходства RL и переноса на реальные банки нет | Новые скрытые seed, преобразования, новые причинные механизмы |
| Инженерия и объяснение | 10 | Python 3.11, зафиксированные зависимости, одна команда проверки, журналы/схемы, ZIP-манифест, офлайн Docker | pyproject.toml; scripts/package_submission.py; submission_check.py; .github/workflows/verify.yml; docs/ | python -m unittest discover -s tests -q; python -m scripts.submission_check --archive PATH | 214 локальных тестов; свежий CI отдельно проверяет ZIP после распаковки и сеть none/2 CPU/4 GiB | Скачать приложенный CI-архив и повторить команды, сравнить SHA-256 |
| ИТОГО | 100 | Результаты локального стенда не равны официальным баллам | AUDITFORGE_LIMITATIONS.md | — | Официальная оценка неизвестна | Проверки организаторов имеют приоритет |

Обязательные материалы: LICENSE, README, зафиксированные зависимости, исходники
среды/генератора/matcher, схемы и четыре официальных адаптера, 10 train + 10 dev,
траектории, тесты, docs/DESIGN_NOTE.md и сценарий демонстрации. Их наличие,
содержимое и replay проверяет `scripts/submission_check.py` на каждом архиве.

Исходный релиз `genesis-2026-fintech-final` остаётся исторической сдачей.
Новое исследование создано 23 ноября 2026; задним числом оно в сдачу не включается.
