# Workspace Transfer Safe

## Status: paused / разработка отложена (2026-11-06)

**Not part of the installable MAINFRAME inventory.** Removed from the active DSH profile at the user's request. Keep this directory as development source; do not automatically reinstall or enable it during MAINFRAME updates. The implementation below describes an experimental prototype, not a supported feature.

**Почему отложено:** ограничений пока больше, чем пользы от необязательной функции переноса чатов.

- DSH 0.2.2-rc.1 сохраняет запущенный Host Agent после завершения генерации и переключения чата. Освобождение Client-ссылки не закрывает агент. В исследованном публичном API не найден безопасный способ эксклюзивно заморозить и закрыть существующий агент; холодный перенос требует перезапуска DSH.
- Нельзя снимать чужую блокировку записи, принудительно завершать агент или подменять безопасный перенос снимком живой истории: новые сообщения между копированием и архивированием могут потеряться для пользователя.
- Прототип принимает только закрытые обычные top-level истории v4. Ветки, уже перенесённые чаты, незавершённые ходы, очередь сообщений и активные задачи/напоминания блокируют перенос. Файлы, расписания и внешнее состояние не мигрируют; новый ID и безопасный сброс разрешений неизбежны в текущей реализации.
- Копирование и архивирование не являются единой транзакцией; частичный результат требует ручной проверки, а не слепого повтора. Штатного расширения sidebar для межпроектного drag-and-drop также не установлено.

**Когда вернуться:** после обновлений DSH повторно проверить поддерживаемый API переноса либо эксклюзивной приостановки/закрытия агента с сохранением истории, очередей и фоновой активности. Затем проверить целостность и сценарий из обычного открытого чата на искусственных данных, отдельно визуально проверить штатный диалог. Не ослаблять защитные отказы ради удобства. Повторная установка — только по явному запросу пользователя.

Последняя проверка прототипа 0.1.4: 78 автоматических тестов и native self-test на искусственных чатах прошли; реальный пользовательский перенос и отрисованный диалог не подтверждены. Это не снимает перечисленные ограничения.

## Prototype behavior

English: Minimal local DSH 0.2.2-rc.1 plugin. The conversation menu offers **Move to project…**. The source Host agent must be closed: switching chats only releases the Client view and does not close an activated Host agent. For an activated source, finish other work and restart DSH before retrying. Select an existing project and confirm. It creates a new seeded session ID, verifies the durable log and native projections, then archives the original last. The original log is never deleted. Restore the original through DSH's native archive UI if needed.

Русский: В меню разговора появится **Перенести в проект…**. Агент исходного чата на Host должен быть закрыт: переключение чата и остановка генерации его не закрывают. Для уже запущенного чата завершите другую работу и перезапустите DSH перед повторной попыткой. Выберите существующий проект и подтвердите. Будет создан новый ID, проверена сохранённая история, а оригинал архивирован последним. Безвозвратного удаления нет.

## Boundaries

- Current-format v4, non-seeded, top-level CLOSED sources only. Existing forks, subagents, incomplete turns, queued inbox messages, archived sources and active work are refused.
- Source writer ownership blocks cold resume for the full operation. No live Agent is closed automatically. No Agent or model is started to copy the history.
- The new header and final working-directory event both target the destination. Final permissions are read-only + ask; imported Auto identity is replaced with an ordinary configured preset before the restrictive overrides.
- Files are not copied. Attachment references remain unchanged within this profile. Old absolute paths/spill links may no longer work.
- Schedules remain attached to original IDs. Subagent catalogs, active goals, running jobs, pins and external state are not migrated. Inherited goals stay disarmed on native resume until explicitly resumed.
- Archive-last is not a cross-service atomic transaction. Native archive admission rechecks activity. If any post-copy step fails, the original stays present and a partial copy may remain. **Do not blindly retry**; inspect the reported copy ID and destination first.
- No external network clients, shell execution, lifecycle install scripts, registry doctor, bulk organization, rename override or permanent-delete route. The Client calls only the authenticated same-origin Host endpoint.

## Appearance

The Session action uses DSH's shared `contextMenus` renderer and native monochrome glyph, with the same icon/label columns, focus and keyboard behavior as built-in actions. It sits after “Reveal in Finder” and before the native archive divider, without an extra section. The plugin-manager icon uses transparent blue/teal artwork matching the other MAINFRAME plugins; it adds no nested background tile.

The transfer dialog uses the native Modal description/footer and short native buttons. Destination choices show project titles; the selected directory is shown separately. A concise copy/archive notice replaces the acknowledgement checkbox, and detailed restrictions are collapsed. `source-open`, active-work and seeded-source refusals are localized. This does not add support for transferring activated Host agents.

## Verification

`node --test tests/*.test.mjs` exercises transaction ordering and fail-closed behavior with disposable mocks. The opt-in `workspace_transfer` tool `self_test` creates only synthetic native session logs and temporary workspace registrations, validates the real storage/query/projection path, then archives the fixture logs and removes only the test registrations. Directories and logs are retained, never erased. It is not run at plugin activation. UI presence/rendering requires a connected DSH browser; installation alone does not prove it.

## Provenance

New local Host implementation and minimal Client UI informed by review of Stijnus/dsh-move-to-workspace v0.1.13 (MIT), supplied ZIP SHA256 `0b893b7db723205d33b4ec82dfca6bc5965bd64a8b582964f976e8fda5888257`. This is not installation of that unverified npm artifact. Original source: https://github.com/Stijnus/dsh-move-to-workspace . No guarantee of freedom from bugs or malicious behavior is implied by a bounded source audit.
