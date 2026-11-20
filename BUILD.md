# Сборка и выпуск osu! Studio

## 1. Сборка папки (Windows)
```
build_exe.bat
```
Результат: `dist\osu_studio\osu_studio.exe` (+ библиотеки рядом). Запускается без Python.
Данные пользователя хранятся в `%APPDATA%\osu_studio`.

## 2. Установщик
Нужен Inno Setup 6 (https://jrsoftware.org/isinfo.php). `build_exe.bat` вызовет его сам.
Итог: `dist\installer\osu_studio_setup_<версия>.exe`.

## 3. Выпуск обновления
1. Подними версию в `studio_pro\config.py` (`APP_VERSION`) и в `build_exe.bat` (`/DAppVersion=...`).
2. Собери установщик.
3. Создай релиз на GitHub, прикрепи `osu_studio_setup_<версия>.exe`.
4. Сгенерируй манифест:
   ```
   python make_manifest.py dist\installer\osu_studio_setup_0.4.0.exe --version 0.4.0 ^
     --url https://github.com/sk1pti/osu_studio/releases/download/v0.4.0/osu_studio_setup_0.4.0.exe ^
     --notes "что нового"
   ```
5. Загрузи `latest.json` в релиз как отдельный файл. Адрес в `config.py` (`UPDATE_MANIFEST_URL`)
   должен указывать на `.../releases/latest/download/latest.json`.
6. Замени `sk1pti` в `config.py` на свой логин GitHub.

## Что не сделано (нужно до публичного релиза)
- **Подпись кода.** Без сертификата Windows SmartScreen предупреждает о неизвестном издателе.
  Подписать можно `signtool` сертификатом (платный, ~100 $/год).
- **Откат.** Предыдущая версия не хранится; при плохом обновлении пользователь ставит старую вручную.

## Подпись через SignPath (бесплатно для open source)

Автоматизация уже в репозитории: `.github/workflows/release.yml`, `.signpath/artifact-configuration.xml`,
`CODE_SIGNING_POLICY.md`. Чтобы она заработала, нужно сделать вручную:

1. **Репозиторий на GitHub, публичный, с OSI-лицензией** (в архиве — добавь `LICENSE`, например MIT).
2. **Включить 2FA** на GitHub для всех, у кого есть доступ.
3. **Опубликовать неподписанный релиз** (тег `v0.3.0`) — SignPath подписывает только существующие релизы.
4. **Подать заявку** на https://signpath.org/apply.html. Укажи ссылку на репозиторий и релиз.
5. **Дождаться одобрения.** После него в веб-портале SignPath:
   - создать проект, signing policy и artifact configuration (загрузи `.signpath/artifact-configuration.xml`);
   - создать CI-пользователя и API-токен.
6. **В GitHub** (Settings → Secrets and variables → Actions):
   - secret `SIGNPATH_API_TOKEN`;
   - variables `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`, `SIGNPATH_ARTIFACT_CONFIG_SLUG`.
7. **Создать environment `signing`** (Settings → Environments) с обязательным ревьюером — это и есть ручное одобрение каждой подписи.
8. **Заменить `sk1pti`** в `config.py` и в `UPDATE_MANIFEST_URL`.
9. **Выпуск:** `git tag v0.3.0 && git push --tags`. Workflow соберёт, подпишет, создаст манифест и релиз.

Важно: хеш подписанного файла отличается от неподписанного, поэтому `latest.json` формируется
уже после подписи (так сделано в workflow). Не публикуй манифест вручную с хешем неподписанного файла.

Замечания, которые стоит проверить в портале SignPath:
- Схема `artifact-configuration.xml` и имена входов action `signpath/github-action-submit-signing-request`
  сверяются с актуальной документацией https://docs.signpath.io/ — я писал по описанию программы и
  могу разойтись в деталях.
- Подписывается только установщик. Программа внутри него (`osu_studio.exe`) не подписана отдельно.
  Для лучшей совместимости с антивирусами можно добавить подпись exe в тот же запрос, дополнив конфиг.
