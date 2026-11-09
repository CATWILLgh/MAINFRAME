window.__ModuleLoader__.load({
  id: '@mainframe/dsh-workspace-transfer-safe',
  factory(require) {
    const React = require('react');
    const { Modal, Button, IconRightUpOutlineRegular } = require('@deepseek-ai/dsh-client-ui-primitives');
    const h = React.createElement;
    const NS = 'mainframe-workspace-transfer-safe';
    // Keep these dictionaries in sync with the exported locale resources.
    const en = {
      "action": "Move to project…",
      "title": "Move to project",
      "conversation": "Conversation: {title}",
      "destination": "Destination project",
      "choose": "Choose an existing project",
      "noProjects": "No other existing projects are available.",
      "loading": "Loading projects…",
      "workspaceError": "Projects could not be loaded. Reconnect the page and try again.",
      "cwd": "New working directory: {path}",
      "closed": "This version only moves chats whose Host agent is closed. Switching chats does not close an activated agent; restart DSH first. This action never stops work for you.",
      "copy": "Create a copy with a new ID, then archive the original. No files will be moved.",
      "permissions": "The copy starts with a read-only sandbox rooted at the destination and approvals set to ask (on request). Previous broader permissions are not carried over.",
      "schedules": "Active tasks and reminders prevent moving. Scheduled tasks are not migrated.",
      "files": "Project files are not copied or moved. Old paths in messages and tool results remain historical references.",
      "cancel": "Cancel",
      "confirm": "Move",
      "pending": "Moving…",
      "sourceOpen": "DSH still holds this chat open, even if it is idle. Moving it is not supported in this state. Cancel, restart DSH after other work finishes, then try again. Switching chats or refreshing the page is not enough.",
      "failed": "Move failed: {message}",
      "invalidResponse": "The server returned an unexpected response. Check the project list before trying again.",
      "networkError": "The request could not be completed. Check whether a copy was created before trying again.",
      "navigationError": "The copy was created and the original archived, but opening the copy failed. Open the destination project to find it.",
      "partial": "A partial transfer may exist. Copy ID: {id}. Refresh the project list and inspect this copy before doing anything else. Do not repeat the transfer.",
      "success": "The copy was created and the original archived.",
      "openCopy": "Open copy",
      "close": "Close",
      "details": "Permissions and limitations",
      "seededSource": "Forked and previously transferred chats are not supported yet.",
      "activeSource": "This chat has active work or reminders. Finish or cancel them before moving."
    };
    const ru = {
      "action": "Перенести в проект…",
      "title": "Перенести в проект",
      "conversation": "Разговор: {title}",
      "destination": "Проект назначения",
      "choose": "Выберите существующий проект",
      "noProjects": "Других существующих проектов нет.",
      "loading": "Загрузка проектов…",
      "workspaceError": "Не удалось загрузить проекты. Переподключите страницу и повторите попытку.",
      "cwd": "Новая рабочая папка: {path}",
      "closed": "Эта версия переносит только чаты с закрытым агентом на Host. Переключение чатов не закрывает запущенный агент — нужен перезапуск DSH. Перенос сам ничего не останавливает.",
      "copy": "Создадим копию с новым ID, затем архивируем оригинал. Файлы не переносятся.",
      "permissions": "Копия запускается в песочнице только для чтения с корнем в папке назначения и подтверждениями ask (по запросу). Прежние расширенные разрешения не сохраняются.",
      "schedules": "Активные задачи и напоминания блокируют перенос. Запланированные задачи не переносятся.",
      "files": "Файлы проектов не копируются и не перемещаются. Старые пути в сообщениях и результатах инструментов остаются историческими ссылками.",
      "cancel": "Отмена",
      "confirm": "Перенести",
      "pending": "Перенос…",
      "sourceOpen": "DSH всё ещё держит этот чат открытым, даже если генерация завершена. Перенос в таком состоянии не поддерживается. Нажмите «Отмена», дождитесь завершения другой работы, перезапустите DSH и повторите перенос. Переключения чата или обновления страницы недостаточно.",
      "failed": "Не удалось перенести: {message}",
      "invalidResponse": "Сервер вернул неожиданный ответ. Проверьте список проектов перед повторной попыткой.",
      "networkError": "Не удалось завершить запрос. Перед повторной попыткой проверьте, не создана ли уже копия.",
      "navigationError": "Копия создана, оригинал архивирован, но открыть копию не удалось. Найдите её в проекте назначения.",
      "partial": "Возможен частичный перенос. ID копии: {id}. Обновите список проектов и проверьте копию перед дальнейшими действиями. Не повторяйте перенос.",
      "success": "Копия создана, оригинал архивирован.",
      "openCopy": "Открыть копию",
      "close": "Закрыть",
      "details": "Разрешения и ограничения",
      "seededSource": "Ветки и ранее перенесённые чаты пока не поддерживаются.",
      "activeSource": "В чате есть активная работа или напоминания. Завершите или отмените их перед переносом."
    };
    // The shared context-menu renderer owns glyph/label columns and keyboard
    // handling; do not insert a legacy component row with its own layout.
    function TransferIcon() { return h(IconRightUpOutlineRegular); }
    function Overlay({ source, workspaces, settle, transfer, openCopy, t }) {
      const request = React.useSyncExternalStore(source.subscribe, source.getSnapshot);
      if (!request) return null;
      return h(TransferForm, { key: request.sessionId, request, workspaces, settle, transfer, openCopy, t });
    }
    function TransferForm({ request, workspaces, settle, transfer, openCopy, t }) {
      const subscribe = React.useCallback((listener) => workspaces.list.subscribe(listener), [workspaces]);
      const getSnapshot = React.useCallback(() => workspaces.list.getSnapshot(), [workspaces]);
      const snapshot = React.useSyncExternalStore(subscribe, getSnapshot);
      const [workspaceId, setWorkspaceId] = React.useState('');
      const [busy, setBusy] = React.useState(false);
      const [error, setError] = React.useState('');
      const [createdId, setCreatedId] = React.useState(null);
      const [partialId, setPartialId] = React.useState(null);
      const [uncertain, setUncertain] = React.useState(false);
      const lock = React.useRef(false);
      const alive = React.useRef(true);
      React.useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
      const ready = snapshot.state === 'idle' && snapshot.phase === 'ready';
      const items = snapshot.items.filter((row) => !row.sessionIds.includes(request.sessionId));
      const selected = items.find((row) => row.workspaceId === workspaceId);
      const close = () => { if (!lock.current) settle(); };
      const navigate = async (id) => {
        try { await openCopy(id); if (alive.current) settle(); }
        catch { if (alive.current) setError(t('navigationError')); }
      };
      const confirm = async () => {
        if (lock.current || !ready || !selected || createdId || partialId || uncertain) return;
        lock.current = true;
        setBusy(true);
        setError('');
        try {
          const result = await transfer(request.sessionId, selected.workspaceId);
          if (!alive.current) return;
          setCreatedId(result.sessionId);
          await navigate(result.sessionId);
        } catch (reason) {
          if (alive.current && ['partial-transfer', 'source-close-failed'].includes(reason.code) && reason.copySessionId) {
            setPartialId(reason.copySessionId);
            setUncertain(true);
            setError(t('partial', { id: reason.copySessionId }));
          } else if (alive.current) {
            if (['network', 'invalid-response', 'partial-transfer', 'source-close-failed'].includes(reason.code)) setUncertain(true);
            setError(reason.code === 'source-open' ? t('sourceOpen') :
            reason.code === 'seeded-source' ? t('seededSource') :
            reason.code === 'session-active' ? t('activeSource') :
            reason.code === 'network' ? t('networkError') :
            reason.code === 'invalid-response' ? t('invalidResponse') :
            t('failed', { message: reason.message }));
          }
        } finally {
          lock.current = false;
          if (alive.current) setBusy(false);
        }
      };
      const id = React.useId();
      const secondary = { color: 'var(--dsw-alias-label-secondary)', margin: 0 };
      return h(Modal, {
        open: true, onClose: close, closeLabel: t('close'), title: t('title'),
        description: t('conversation', { title: request.displayTitle || request.sessionId }),
        footer: h(React.Fragment, null,
          h(Button, { variant: 'outline', disabled: busy, onClick: close }, t(createdId ? 'close' : 'cancel')),
          createdId ? h(Button, { variant: 'primary', disabled: busy, onClick: () => navigate(createdId) }, t('openCopy')) :
            uncertain ? null : h(Button, { variant: 'primary', disabled: busy || !ready || !selected, onClick: confirm }, t(busy ? 'pending' : 'confirm'))),
      }, h('div', { style: { display: 'grid', gap: 12, minWidth: 0, lineHeight: 1.5, overflowWrap: 'anywhere' }, 'aria-busy': busy },
        createdId ? h('p', { role: 'status', style: { margin: 0 } }, t('success')) : uncertain ? null : h(React.Fragment, null,
          h('div', { style: { display: 'grid', gap: 6, minWidth: 0 } },
            h('label', { htmlFor: id }, t('destination')),
            h('select', {
              id, value: workspaceId, disabled: busy || !ready || items.length === 0, 'data-modal-autofocus': true,
              'aria-describedby': selected ? `${id}-path` : undefined,
              onChange(event) { setWorkspaceId(event.target.value); setError(''); },
              style: { boxSizing: 'border-box', width: '100%', minWidth: 0, font: 'inherit', color: 'var(--dsw-alias-label-primary)', background: 'var(--dsw-alias-bg-layer-1)', colorScheme: 'inherit', border: '1px solid var(--dsw-alias-border-l2)', borderRadius: 8, padding: '8px 10px' },
            }, h('option', { value: '' }, t('choose')),
            items.map((row) => h('option', { key: row.workspaceId, value: row.workspaceId, title: row.path }, row.title))),
            selected ? h('p', { id: `${id}-path`, style: { ...secondary, fontSize: '0.9em' } }, selected.path) : null),
          !ready ? h('p', { role: 'status', style: secondary }, t(snapshot.error ? 'workspaceError' : 'loading')) :
            items.length === 0 ? h('p', { role: 'status', style: secondary }, t('noProjects')) : null,
          h('p', { style: secondary }, t('copy')),
          h('details', null,
            h('summary', { style: { cursor: 'pointer', color: 'var(--dsw-alias-label-secondary)' } }, t('details')),
            h('div', { style: { display: 'grid', gap: 8, paddingTop: 8 } },
              ['closed', 'permissions', 'schedules', 'files'].map(key => h('p', { key, style: secondary }, t(key)))))),
        error ? h('p', { role: 'alert', style: { margin: 0, color: 'var(--dsw-alias-state-error-primary)' } }, error) : null));
    }
    return {
      inject: ['slots', 'locale', 'workspaces', 'uiWorkspace', 'contextMenus'],
      apply(ctx) {
        let pending = null;
        let disposed = false;
        const listeners = new Set();
        const source = { getSnapshot: () => pending, subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); } };
        const setRequest = (value) => { if (disposed) return; pending = value; for (const listener of listeners) listener(); };
        ctx.effect(() => ctx.locale.register(NS, { en, ru }), 'workspace transfer: dictionaries');
        ctx.effect(() => () => { disposed = true; pending = null; listeners.clear(); }, 'workspace transfer: dispose');
        const transfer = async (sessionId, workspaceId) => {
          let response;
          try {
            response = await fetch('/api/mainframe/workspace-transfer', {
              method: 'POST', credentials: 'same-origin', redirect: 'error',
              headers: { 'Content-Type': 'application/json', 'x-mainframe-workspace-transfer': '1' },
              body: JSON.stringify({ sessionId, workspaceId }),
            });
          } catch { throw Object.assign(new Error(''), { code: 'network' }); }
          let result;
          try { result = await response.json(); }
          catch { throw Object.assign(new Error(''), { code: 'invalid-response' }); }
          if (!result || typeof result !== 'object') throw Object.assign(new Error(''), { code: 'invalid-response' });
          if (!response.ok || result.ok !== true) {
            const detail = result.error;
            const code = detail && typeof detail === 'object' ? detail.code : detail;
            const message = typeof detail === 'string' ? detail : detail && typeof detail.message === 'string' ? detail.message : null;
            if (code === 'source-open') throw Object.assign(new Error(''), { code });
            if (!message) throw Object.assign(new Error(''), { code: 'invalid-response' });
            throw Object.assign(new Error(message), { code: typeof code === 'string' ? code : 'failed',
              copySessionId: detail && typeof detail.copySessionId === 'string' ? detail.copySessionId : null });
          }
          if (typeof result.sessionId !== 'string' || !result.sessionId || result.sessionId === sessionId || result.workspaceId !== workspaceId)
            throw Object.assign(new Error(''), { code: 'invalid-response' });
          return result;
        };
        const t = ctx.locale.bind(NS);
        ctx.effect(() => ctx.contextMenus.register({
          id: 'mainframe.workspace-transfer', target: 'session', order: 550,
          observe: () => [ctx.locale],
          resolve: ({ sessionId, displayTitle }) => [{
            id: 'move', label: t('action'), icon: { key: 'mainframe.workspace-transfer' },
            run: () => { if (!pending) setRequest({ sessionId, displayTitle }); },
          }],
        }), 'workspace transfer: session menu');
        ctx.slots.inject('contextMenu.icon', () => ctx.slots.register({
          name: 'contextMenu.icon', key: 'mainframe.workspace-transfer',
        }, TransferIcon));
        ctx.slots.inject('shell.overlay', () => ctx.slots.register({
          name: 'shell.overlay', id: 'mainframe.workspace-transfer-dialog', order: 500, locale: NS,
          inject: () => ({ source, workspaces: ctx.workspaces, settle: () => setRequest(null), transfer,
            openCopy: (sessionId) => ctx.uiWorkspace.openSession(sessionId) }),
        }, Overlay));
      },
    };
  },
});
