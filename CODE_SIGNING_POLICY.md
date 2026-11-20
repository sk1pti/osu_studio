# Политика подписи кода

Релизные установщики Windows для osu! Studio подписываются через программу
**SignPath Foundation** (бесплатно для открытых проектов).

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

## Что подписывается
Только установщик `osu_studio_setup_<версия>.exe`, собранный из этого репозитория
скриптами `build_exe.spec` и `installer/osu_studio.iss` в GitHub Actions (`.github/workflows/release.yml`).

## Кто подтверждает подпись
Каждый запрос на подпись вручную одобряет владелец проекта (environment `signing` с обязательным ревьюером).

## Безопасность
- Все участники с доступом к репозиторию и к SignPath используют двухфакторную аутентификацию.
- Закрытый ключ не хранится в репозитории и не попадает на runner — подпись выполняется в облаке SignPath.
- До одобрения заявки релизы помечаются как неподписанные.
