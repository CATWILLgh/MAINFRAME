window.__ModuleLoader__.load({
  id: '@mainframe/secrets-vault',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const NS = 'secretsVault';
    const en = {
  "recovery": "Recovery key",
  "enableRecovery": "Enable recovery",
  "rotateRecovery": "Replace recovery key",
  "recover": "Recover vault",
  "recoveryTitle": "Save your recovery key",
  "recoveryHelp": "Enter your recovery key and choose a new master password. The old recovery key will be replaced. Existing credential permissions stay unchanged.",
  "recoveryEnableHelp": "Confirm your current master password. This enables recovery and changes the encryption format. Back up vault.v2.json and vault.v2.json.recovery.json together while the vault is locked. This pair is required even when using your password.",
  "recoveryRotateHelp": "Confirm your master password to replace the recovery key. The previous recovery key will stop working with the current vault.",
  "recoveryIssuedHelp": "Shown only now, never in chat or agent tools. Save it outside Harness. Anyone with this key and the vault files can recover your credentials. Old copies of vault files cannot be revoked.",
  "recoveryBackup": "Backups now require both vault.v2.json and vault.v2.json.recovery.json from the same locked vault.",
  "recoveryAck": "I have saved this recovery key outside Harness.",
  "recoveryDone": "Done",
  "recoveryFailure": "The result may already be committed. Refresh and unlock using the master password you just entered, then use Replace recovery key to get a new key. The previous recovery key may no longer work. Preserve both vault files.",
  "commandDescription": "Add a credential privately in Secrets Vault.",
  "panel": "Secrets Vault",
  "subtitle": "Store credentials and control agent access.",
  "lockedHelp": "Unlock to view and manage your credentials.",
  "setupIntro": "Create an encrypted vault for your credentials.",
  "add": "Add credential",
  "edit": "Edit",
  "remove": "Delete",
  "lock": "Lock vault",
  "locked": "Vault locked",
  "unlocked": "Vault unlocked",
  "setup": "Create your vault",
  "unlock": "Unlock vault",
  "setupHelp": "Choose a unique master passphrase. You will need it after Harness restarts. Save the recovery key shown next separately, outside Harness. Without the password or that key, the vault cannot be recovered.",
  "unlockHelp": "Unlock once for this Harness process. Screen lock does not interrupt agents. There is no inactivity timer.",
  "password": "Password",
  "master": "Master password",
  "repeat": "Repeat master password",
  "length": "At least 12 characters",
  "matching": "Passwords match",
  "nontrivial": "Avoid repeated characters and common or predictable passwords. Length alone does not guarantee strength.",
  "show": "Show",
  "hide": "Hide",
  "cancel": "Cancel",
  "close": "Close",
  "save": "Save credential",
  "saving": "Working…",
  "loading": "Loading vault…",
  "retry": "Retry",
  "empty": "No credentials yet",
  "emptyHelp": "Add a token, account password, or SSH key. Only descriptions are shared with agents — never the secret itself.",
  "search": "Search credentials",
  "noMatches": "No matching credentials",
  "name": "Name",
  "description": "Description / purpose",
  "url": "Service URL / HTTPS origin",
  "username": "Username",
  "host": "SSH host",
  "port": "Port",
  "tags": "Tags (comma separated)",
  "kind": "Credential type",
  "token": "API token",
  "ssh-key": "SSH key",
  "privateKey": "Private key",
  "passphrase": "Key passphrase (optional)",
  "secretHelp": "Sent directly to the vault, not to the chat. Saved secrets are never shown again.",
  "replace": "Replace secret",
  "replaceHelp": "Leave this off to keep the existing secret. Replacement requires entering the complete new secret.",
  "allowAgentUse": "Allow agents to use this credential",
  "scopeHelp": "Allow agents to use this credential only for the HTTPS origin / SSH host configured here. Secrets are never returned to agents.",
  "sshHelp": "Agent SSH access requires an existing verified known_hosts entry. For an encrypted private key, enter its passphrase here; it stays private.",
  "httpHelp": "Tokens use Bearer authentication. Account passwords use HTTP Basic authentication over HTTPS.",
  "sessionHelp": "Share this credential’s description with the current conversation",
  "metadataOnly": "Keep secret values out of names, descriptions, URLs, and tags. This metadata may be visible to agents.",
  "deleteTitle": "Delete credential?",
  "deleteHelp": "This permanently removes the saved credential from the vault. It does not revoke access at the service.",
  "allowed": "Agent access enabled",
  "storageOnly": "Storage only",
  "networkError": "Could not reach the vault. Check the connection and try again.",
  "requestError": "The vault could not complete this request. Please try again.",
  "invalidPassword": "Use at least 12 characters and make sure both passwords match.",
  "invalidScope": "Agent access requires an HTTPS URL without a username or password.",
  "refresh": "Refresh",
  "conflictError": "This credential changed in another session. Refresh the list and reopen it before saving.",
  "legacyError": "A legacy Vault was found. Preserve the old files and use the previous plugin. Automatic migration is not supported.",
  "busyError": "The Vault is owned by another Host or has a stale ownership marker. Close the other Host; preserve the files before maintenance. Never remove a marker while a Host might be running.",
  "uncertainError": "The write outcome is uncertain. Preserve the vault files and restart the Host before further operations.",
  "externalError": "Vault files changed externally. Access stopped to avoid overwriting data. Preserve and inspect the files before restarting the Host.",
  "closedError": "The vault is shutting down. Try again after restarting Harness.",
  "ownershipError": "Vault ownership changed. Preserve the files and stop other Hosts before restarting. Never remove a marker while a Host might be running.",
  "unsafePathError": "The vault path or permissions are unsafe. Preserve the files and inspect the path and permissions before retrying."
};
const ru = {
  "recovery": "Ключ восстановления",
  "enableRecovery": "Включить восстановление",
  "rotateRecovery": "Заменить ключ восстановления",
  "recover": "Восстановить хранилище",
  "recoveryTitle": "Сохраните ключ восстановления",
  "recoveryHelp": "Введите ключ восстановления и задайте новый мастер-пароль. Старый ключ восстановления будет заменён. Существующие разрешения на использование учётных данных останутся без изменений.",
  "recoveryEnableHelp": "Подтвердите текущий мастер-пароль. Это включит восстановление и изменит формат шифрования. Пока хранилище заблокировано, сохраните резервную копию vault.v2.json и vault.v2.json.recovery.json вместе. Оба файла необходимы даже при использовании пароля.",
  "recoveryRotateHelp": "Подтвердите мастер-пароль, чтобы заменить ключ восстановления. Предыдущий ключ перестанет работать с текущим хранилищем.",
  "recoveryIssuedHelp": "Ключ показывается только сейчас, никогда — в чате или инструментах агента. Сохраните его вне Harness. Любой, у кого есть этот ключ и файлы хранилища, сможет восстановить ваши учётные данные. Доступ к старым копиям файлов хранилища отозвать нельзя.",
  "recoveryBackup": "Для резервного копирования теперь нужны оба файла: vault.v2.json и vault.v2.json.recovery.json из одного заблокированного хранилища.",
  "recoveryAck": "Я сохранил(а) этот ключ восстановления вне Harness.",
  "recoveryDone": "Готово",
  "recoveryFailure": "Изменения уже могли сохраниться. Обновите данные и разблокируйте хранилище с только что введённым мастер-паролем, затем нажмите «Заменить ключ восстановления», чтобы получить новый ключ. Предыдущий ключ уже может не работать. Сохраните оба файла хранилища.",
  "commandDescription": "Добавить учётные данные приватно в хранилище секретов.",
  "panel": "Хранилище секретов",
  "subtitle": "Храните учётные данные и управляйте доступом агентов.",
  "lockedHelp": "Разблокируйте хранилище для просмотра и управления учётными данными.",
  "setupIntro": "Создайте зашифрованное хранилище для учётных данных.",
  "add": "Добавить учётные данные",
  "edit": "Изменить",
  "remove": "Удалить",
  "lock": "Заблокировать хранилище",
  "locked": "Хранилище заблокировано",
  "unlocked": "Хранилище разблокировано",
  "setup": "Создать хранилище",
  "unlock": "Разблокировать хранилище",
  "setupHelp": "Выберите уникальный мастер-пароль. Он понадобится после перезапуска Harness. Ключ восстановления, который появится далее, сохраните отдельно, вне Harness. Без пароля или этого ключа восстановить хранилище невозможно.",
  "unlockHelp": "Разблокировка действует в течение работы этого процесса Harness. Блокировка экрана не прерывает работу агентов. Таймера бездействия нет.",
  "password": "Пароль",
  "master": "Мастер-пароль",
  "repeat": "Повторите мастер-пароль",
  "length": "Не менее 12 символов",
  "matching": "Пароли совпадают",
  "nontrivial": "Избегайте повторяющихся символов, распространённых и предсказуемых паролей. Одна лишь длина не гарантирует надёжность.",
  "show": "Показать",
  "hide": "Скрыть",
  "cancel": "Отмена",
  "close": "Закрыть",
  "save": "Сохранить учётные данные",
  "saving": "Выполняется…",
  "loading": "Загрузка хранилища…",
  "retry": "Повторить",
  "empty": "Учётных данных пока нет",
  "emptyHelp": "Добавьте токен, пароль учётной записи или SSH-ключ. Агентам доступны только описания — не сами секреты.",
  "search": "Поиск учётных данных",
  "noMatches": "Учётные данные не найдены",
  "name": "Название",
  "description": "Описание / назначение",
  "url": "URL сервиса / источник HTTPS",
  "username": "Имя пользователя",
  "host": "SSH-хост",
  "port": "Порт",
  "tags": "Метки (через запятую)",
  "kind": "Тип учётных данных",
  "token": "API-токен",
  "ssh-key": "SSH-ключ",
  "privateKey": "Закрытый ключ",
  "passphrase": "Пароль ключа (необязательно)",
  "secretHelp": "Отправляется напрямую в хранилище, не в чат. Сохранённые секреты больше не показываются.",
  "replace": "Заменить секрет",
  "replaceHelp": "Оставьте выключенным, чтобы сохранить прежний секрет. Для замены необходимо ввести новый секрет полностью.",
  "allowAgentUse": "Разрешить агентам использовать эти учётные данные",
  "scopeHelp": "Агенты смогут использовать эти учётные данные только для указанного здесь источника HTTPS / SSH-хоста. Сами секреты агентам не передаются.",
  "sshHelp": "Для доступа агента по SSH нужна существующая проверенная запись в known_hosts. Если закрытый ключ зашифрован, введите его пароль здесь; он останется приватным.",
  "httpHelp": "Токены используют авторизацию Bearer. Пароли учётных записей — HTTP Basic через HTTPS.",
  "sessionHelp": "Передать описание этих учётных данных в текущую беседу",
  "metadataOnly": "Не указывайте секреты в названиях, описаниях, URL и метках. Эти метаданные могут быть видны агентам.",
  "deleteTitle": "Удалить учётные данные?",
  "deleteHelp": "Учётные данные будут безвозвратно удалены из хранилища. Это не отзовёт доступ на стороне сервиса.",
  "allowed": "Доступ агентов разрешён",
  "storageOnly": "Только хранение",
  "networkError": "Не удалось связаться с хранилищем. Проверьте соединение и повторите попытку.",
  "requestError": "Не удалось выполнить запрос к хранилищу. Проверьте, что оно разблокировано и поля заполнены правильно.",
  "invalidPassword": "Введите не менее 12 символов и убедитесь, что оба пароля совпадают.",
  "invalidScope": "Для доступа агента нужен URL с HTTPS без имени пользователя и пароля.",
  "refresh": "Обновить",
  "conflictError": "Эти учётные данные изменились в другой сессии. Обновите список и откройте запись заново перед сохранением.",
  "legacyError": "Найдено хранилище старого формата. Сохраните старые файлы и используйте предыдущую версию плагина. Автоматическая миграция не поддерживается.",
  "busyError": "Хранилище занято другим процессом Host или осталась метка владельца. Закройте другой Host; перед обслуживанием сохраните файлы. Не удаляйте метку, пока Host может работать.",
  "uncertainError": "Неизвестно, завершилось ли сохранение. Сохраните файлы хранилища и перезапустите Host перед дальнейшими действиями.",
  "externalError": "Файлы хранилища изменены извне. Доступ остановлен, чтобы не перезаписать данные. Сохраните файлы и проверьте их перед перезапуском Host.",
  "closedError": "Хранилище завершает работу. Повторите попытку после перезапуска Harness.",
  "ownershipError": "Владелец хранилища изменился. Сохраните файлы и остановите другие процессы Host перед перезапуском. Не удаляйте метку, пока Host может работать.",
  "unsafePathError": "Путь к хранилищу или права доступа небезопасны. Сохраните файлы и проверьте путь и права доступа перед повторной попыткой."
};
function registerMainframeLocale(locale, namespace, en, ru) {
  const disposers = new Map();
  let refreshing = false;
  function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      for (const { id } of locale.getSnapshot().locales) {
        const key = id.toLowerCase();
        if (!disposers.has(key)) {
          // Mark before register: it synchronously notifies snapshot subscribers.
          disposers.set(key, null);
          disposers.set(key, locale.register(namespace, id, key === 'ru' ? ru : en));
        }
      }
    } finally { refreshing = false; }
  }
  refresh();
  const unsubscribe = locale.subscribe(refresh);
  return () => {
    unsubscribe();
    for (const dispose of disposers.values()) dispose?.();
    disposers.clear();
  };
}
    // Native management-page metrics; prefixed controls depend only on theme tokens.
    const css = `
.sv-root{font:inherit;font-size:14px;line-height:1.6;color:var(--dsw-alias-label-primary);box-sizing:border-box}
.sv-root *{box-sizing:border-box}
.sv-page{width:100%;height:100%;min-width:0;min-height:0;display:flex;flex-direction:column;align-items:center;gap:32px;padding:0 clamp(24px,4vw,48px) 48px;overflow:auto;background:var(--dsw-alias-bg-base);--dsh-scrollbar-width:9px;--dsh-scrollbar-thumb-border:2px}
.sv-page>.sv-head,.sv-page>.sv-content{width:100%;max-width:960px;flex:none}
.sv-head{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:16px;padding-top:28px}
[data-platform=darwin] .sv-head{padding-top:calc(28px + var(--dsh-frame-top-clearance,0px))}
.sv-heading{min-width:0;max-width:100%}
.sv-toolbar{display:flex;flex:none;justify-content:flex-end;align-items:center;gap:16px;white-space:nowrap}
.sv-title{margin:0;font-size:20px;font-weight:500;line-height:28px}
.sv-muted{color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px;margin:0}
.sv-head .sv-muted{margin-top:4px}
.sv-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.sv-button{display:inline-flex;align-items:center;justify-content:center;gap:6px;flex:none;height:32px;padding:0 12px;border:.5px solid var(--dsw-alias-border-l2);border-radius:16px;background:transparent;color:var(--dsw-alias-label-primary);font:inherit;font-size:13px;line-height:20px;cursor:pointer;transition:background .15s,border-color .15s}
.sv-button:hover:not(:disabled){background:var(--dsw-alias-interactive-bg-hover,var(--dsw-alias-bg-layer-2))}
.sv-button:disabled{opacity:.45;cursor:default}
.sv-primary{border-color:transparent;background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-base);font-weight:500}
.sv-primary:hover:not(:disabled){background:var(--dsw-alias-label-primary);opacity:.85}
.sv-icon{width:28px;height:28px;min-height:28px;padding:4px;border:0;border-radius:8px;color:var(--dsw-alias-label-secondary)}
.sv-root :is(button,input,textarea,select):focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px}
.sv-input{display:block;width:100%;min-width:0;min-height:36px;padding:7px 10px;border:.5px solid var(--dsw-alias-border-l3,var(--dsw-alias-border-l2));border-radius:10px;background:transparent;color:var(--dsw-alias-label-primary);font:inherit;font-size:14px;line-height:20px;transition:border-color .15s}
.sv-input:hover{border-color:var(--dsw-alias-border-l2)}
.sv-input:disabled{opacity:.55}
.sv-input::placeholder{color:var(--dsw-alias-label-tertiary,var(--dsw-alias-label-secondary))}
.sv-input option{background:var(--dsw-alias-bg-layer-1);color:var(--dsw-alias-label-primary)}
.sv-search{display:flex;align-items:center;gap:8px;width:100%;height:36px;padding:0 10px;border:.5px solid var(--dsw-alias-border-l3,var(--dsw-alias-border-l2));border-radius:12px;margin:0 0 16px;color:var(--dsw-alias-label-tertiary,var(--dsw-alias-label-secondary));transition:border-color .15s}
.sv-search:hover{border-color:var(--dsw-alias-border-l2)}
.sv-search:focus-within{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:2px}
.sv-search>svg{flex:none}
.sv-search input{width:100%;min-width:0;height:100%;padding:0;border:0;outline:none!important;background:transparent;color:var(--dsw-alias-label-primary);font:inherit;font-size:14px;line-height:22px}
.sv-search input::placeholder{color:inherit}
.sv-refresh{width:32px;height:32px;min-height:32px;padding:6px;flex:none}
.sv-list{border-top:.5px solid var(--dsw-alias-border-l2)}
.sv-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 0;border-bottom:.5px solid var(--dsw-alias-border-l2)}
.sv-row-main{min-width:0;flex:1}
.sv-name{font-size:14px;line-height:22px;font-weight:500;overflow-wrap:anywhere;margin:0 0 4px}
.sv-detail{font-size:13px;line-height:20px;color:var(--dsw-alias-label-secondary);overflow-wrap:anywhere}
.sv-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.sv-tag{font-size:12px;line-height:18px;padding:1px 7px;border-radius:5px;background:var(--dsw-alias-bg-layer-2);color:var(--dsw-alias-label-secondary)}
.sv-empty{text-align:center;padding:48px 16px;color:var(--dsw-alias-label-secondary)}
.sv-empty>svg{display:block;margin:0 auto 12px;color:var(--dsw-alias-label-tertiary,var(--dsw-alias-label-secondary))}
.sv-empty h2{font-size:14px;line-height:22px;font-weight:400;color:var(--dsw-alias-label-secondary);margin:0 0 6px}
.sv-empty .sv-muted{max-width:460px;margin:0 auto}
.sv-empty .sv-button{margin-top:16px}
.sv-overlay{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;padding:24px;background:color-mix(in srgb,var(--dsw-alias-bg-overlay) 40%,transparent);isolation:isolate}
.sv-dialog{display:flex;flex-direction:column;width:min(560px,100%);max-height:calc(100dvh - 48px);overflow:auto;overscroll-behavior:contain;border:.5px solid var(--dsw-alias-border-l2);border-radius:16px;background:var(--dsw-alias-bg-layer-1);padding:24px;outline:none}
.sv-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}
.sv-dialog-head h2{margin:0;font-size:18px;line-height:26px;font-weight:500}
.sv-form{display:flex;flex-direction:column;gap:16px;min-width:0}
.sv-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.sv-field{display:flex;flex-direction:column;gap:6px;min-width:0;font-size:13px;line-height:20px}
.sv-footer{display:flex;justify-content:flex-end;gap:8px;padding-top:16px;margin-top:4px;border-top:.5px solid var(--dsw-alias-border-l2)}
.sv-secret-row{display:flex;align-items:center;gap:8px}
.sv-secret-row>.sv-input{flex:1}
.sv-desc{min-height:70px;max-height:140px;resize:vertical}
.sv-keytext{min-height:110px;max-height:180px;resize:vertical;font-family:monospace}
.sv-check{display:flex;align-items:flex-start;gap:8px;font-size:13px;line-height:20px}
.sv-check input{width:15px;height:15px;flex:none;margin:3px 0 0;accent-color:var(--dsw-alias-label-primary)}
.sv-checklist{padding-left:18px;margin:0;font-size:12px;line-height:20px;color:var(--dsw-alias-label-secondary)}
.sv-checklist [data-pass=true]{color:var(--dsw-alias-state-success-primary)}
.sv-warning{padding:10px 12px;border-radius:8px;background:var(--dsw-alias-bg-layer-2)}
.sv-error{font-size:13px;line-height:20px;color:var(--dsw-alias-state-error-primary);overflow-wrap:anywhere;margin:0 0 16px}
.sv-concealed{-webkit-text-security:disc}@media(max-width:540px){.sv-page{padding-bottom:32px}
.sv-head{align-items:flex-start}
.sv-row{flex-wrap:wrap}
.sv-row>.sv-actions{width:100%}
.sv-overlay{padding:16px}
.sv-dialog{padding:20px;max-height:calc(100dvh - 32px)}
.sv-grid{grid-template-columns:1fr}}
`;
    const passwordDialogCss='.sv-dialog-password{width:min(440px,100%)}';
    function KeyIcon({size = 18}) { return h('svg',{width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.7,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true}, h('circle',{cx:8,cy:8,r:4.5}),h('path',{d:'m11.3 11.3 9.2 9.2M16 16l2-2m1 5 2-2'})); }
    function RefreshIcon() { return h('svg',{width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.5,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true},h('path',{d:'M20 7v5h-5M20 12a8 8 0 1 0-2.3 5.7M20 7l-2.3-1.7'})); }
    function SearchIcon() { return h('svg',{width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.5,strokeLinecap:'round','aria-hidden':true},h('circle',{cx:10.5,cy:10.5,r:6.5}),h('path',{d:'m15.5 15.5 5 5'})); }
    function PlusIcon() { return h('svg',{width:16,height:16,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.5,strokeLinecap:'round','aria-hidden':true},h('path',{d:'M12 4v16M4 12h16'})); }
    function useStore(controller) { return React.useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getSnapshot); }
    function Button({children,primary,...props}) {return h('button',{type:'button',className:`sv-button${primary?' sv-primary':''}`,...props},children);}
    function Field({label,children}) {return h('label',{className:'sv-field'},h('span',null,label),children);}
    const errorKeys = Object.freeze({VAULT_CONFLICT:'conflictError',LEGACY_VAULT_FORMAT:'legacyError',VAULT_BUSY:'busyError',VAULT_UNCERTAIN_COMMIT:'uncertainError',VAULT_EXTERNAL_CHANGE:'externalError',VAULT_DISPOSED:'closedError',VAULT_OWNERSHIP_LOST:'ownershipError',UNSAFE_VAULT_PATH:'unsafePathError',VAULT_OPERATION_FAILED:'requestError'});
    function controllerFor() {
      let state={ready:false,initialized:false,unlocked:false,recoveryAvailable:false,records:[],pending:false,error:null,modal:null,pendingDraft:null,pendingRequest:null}, serial=0, alive=true, pollTimer=null, polling=false, issuedRecoveryKey=null;
      const listeners=new Set(),seenRequests=new Set();
      const set=(patch)=>{if(alive&&Object.keys(patch).some(key=>!Object.is(state[key],patch[key]))){state={...state,...patch};listeners.forEach(fn=>fn());}};
      const request=async(op,args={})=>{
        let response, result;
        try {response=await fetch(new URL('api/secrets-vault/ui',document.baseURI),{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-Secrets-Vault-UI':'1'},body:JSON.stringify({op,...args})});result=await response.json();}
        catch {throw Object.assign(new Error('networkError'),{localeKey:'networkError'});}
        if(!response.ok||result?.ok!==true){const error=new Error('requestError');error.code=result?.error?.code;error.localeKey=Object.prototype.hasOwnProperty.call(errorKeys,error.code)?errorKeys[error.code]:'requestError';throw error;}
        return result;
      };
      const applyStatus=status=>{
        const patch={ready:true,initialized:Boolean(status.initialized),unlocked:Boolean(status.unlocked),recoveryAvailable:Boolean(status.recoveryAvailable)};
        for(const key of ['pendingDraft','pendingRequest']){const next=status[key]||null;if(JSON.stringify(state[key])!==JSON.stringify(next))patch[key]=next;}
        if(!status.unlocked&&state.records.length)patch.records=[];
        const incoming=status.pendingRequest;
        if(incoming?.id&&!seenRequests.has(incoming.id)&&!state.pending&&!state.modal){seenRequests.add(incoming.id);patch.modal={mode:incoming.mode==='unlock'?'unlock':'add',...(incoming.sessionId?{sessionId:incoming.sessionId}:{})};patch.error=null;}
        set(patch);
      };
      const refresh=async()=>{const status=await request('status');applyStatus(status);if(status.unlocked){const records=(await request('list')).records||[];if(JSON.stringify(state.records)!==JSON.stringify(records))set({records});}};
      const poll=async()=>{if(!alive||polling||state.pending)return;polling=true;const version=serial;try{const status=await request('status');if(alive&&version===serial)applyStatus(status);}catch{/* Foreground actions surface connection errors; background checks stay quiet. */}finally{polling=false;}};
      const mount=()=>{if(pollTimer!==null)return()=>{};poll();pollTimer=setInterval(poll,2000);return()=>{clearInterval(pollTimer);pollTimer=null;};};
      const run=async(work,success)=>{
        if(state.pending)return false;const version=++serial;set({pending:true,error:null});
        try{await work(version);if(alive&&version===serial){await refresh();success?.();}return true;}
        catch(error){if(alive&&version===serial){if(/locked|not.initialized/i.test(error.code||''))set({unlocked:false,records:[],modal:null});set({error:error.localeKey||'requestError'});}return false;}
        finally{if(version===serial)set({pending:false});}
      };
      return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},load:()=>run(async()=>{}),peekIssuedRecovery:()=>issuedRecoveryKey,acknowledgeRecovery:()=>{issuedRecoveryKey=null;set({modal:null,error:null});},issueRecovery:(key,version=serial)=>{if(!alive||version!==serial)return;issuedRecoveryKey=key;set({modal:{mode:'recoveryIssued'}});},open:async(modal)=>{if(state.pending||state.modal?.mode==='recoveryIssued')return;set({error:null});const ok=await run(async()=>{});if(ok)set({modal});},close:()=>{if(!state.pending&&state.modal?.mode!=='recoveryIssued')set({modal:null,error:null});},run,request,set,mount,lock:()=>run(async()=>{await request('lock');set({unlocked:false,...(state.modal?.mode==='recoveryIssued'?{}:{modal:null}),records:[],pendingDraft:null});}),dispose:()=>{alive=false;issuedRecoveryKey=null;clearInterval(pollTimer);pollTimer=null;serial++;state={...state,modal:null,records:[]};listeners.clear();}};
    }
    function Catalog({controller,t}) {
      const s=useStore(controller);const [query,setQuery]=React.useState('');
      React.useEffect(()=>{controller.load();},[controller]);
      const rows=s.records.filter(r=>[r.name,r.description,r.url,r.host,...(r.tags||[])].join(' ').toLowerCase().includes(query.toLowerCase()));
      const open=()=>controller.open({mode:'add'});
      return h('section',{className:'sv-root sv-page'},h('style',null,css),
        h('header',{className:'sv-head','data-window-drag':true},h('div',{className:'sv-heading'},h('h1',{className:'sv-title'},t('panel')),h('p',{className:'sv-muted'},t('subtitle'))),h('div',{className:'sv-toolbar'},h('button',{type:'button',className:'sv-button sv-icon sv-refresh',disabled:s.pending,onClick:()=>controller.load(),'aria-label':t('refresh'),'aria-busy':s.pending,title:t('refresh')},h(RefreshIcon)),s.unlocked&&h(Button,{disabled:s.pending,onClick:()=>controller.open({mode:s.recoveryAvailable?'rotateRecovery':'enableRecovery'})},t(s.recoveryAvailable?'rotateRecovery':'enableRecovery')),s.unlocked&&h(Button,{disabled:s.pending,onClick:()=>controller.lock()},t('lock')),s.unlocked&&h(Button,{primary:true,disabled:s.pending,onClick:open},h(PlusIcon),t('add')))),
        h('div',{className:'sv-content'},s.ready&&s.unlocked&&h('div',{className:'sv-search'},h(SearchIcon),h('input',{type:'search',value:query,onChange:e=>setQuery(e.target.value),'aria-label':t('search'),placeholder:t('search')})),
        s.error&&h('p',{className:'sv-error',role:'alert'},t(s.error)),
        !s.ready?h('p',{className:'sv-muted',role:'status'},t('loading')):!s.unlocked?h('div',{className:'sv-empty'},h(KeyIcon,{size:24}),h('h2',null,t(s.initialized?'locked':'setup')),h('p',{className:'sv-muted'},t(s.initialized?'lockedHelp':'setupIntro')),h(Button,{disabled:s.pending,onClick:()=>controller.open({mode:'unlock'})},t(s.initialized?'unlock':'setup'))):s.records.length===0?h('div',{className:'sv-empty'},h(KeyIcon,{size:24}),h('h2',null,t('empty')),h('p',{className:'sv-muted'},t('emptyHelp')),h(Button,{disabled:s.pending,onClick:open},t('add'))):h(React.Fragment,null,h('div',{className:'sv-list'},rows.length===0?h('p',{className:'sv-muted'},t('noMatches')):rows.map(r=>h('article',{className:'sv-row',key:r.id},h('div',{className:'sv-row-main'},h('h2',{className:'sv-name'},r.name),r.description&&h('div',{className:'sv-detail'},r.description),h('div',{className:'sv-detail'},[t(r.kind),r.username,r.host?r.host+(r.port?`:${r.port}`:''):r.url].filter(Boolean).join(' · ')),h('div',{className:'sv-tags'},h('span',{className:'sv-tag'},t(r.allowAgentUse?'allowed':'storageOnly')),(r.tags||[]).map(tag=>h('span',{className:'sv-tag',key:tag},tag)))),h('div',{className:'sv-actions'},h(Button,{disabled:s.pending,onClick:()=>controller.open({mode:'edit',record:r})},t('edit')),h(Button,{disabled:s.pending,onClick:()=>controller.open({mode:'delete',record:r})},t('remove')))))))));
    }
    function Modal({controller,t}) {
      const s=useStore(controller);React.useEffect(()=>controller.mount(),[controller]);if(!s.modal)return null;
      const mode=s.modal.mode==='recoveryIssued'?'recoveryIssued':!s.initialized?'setup':s.modal.mode==='recover'?'recover':!s.unlocked?'unlock':s.modal.mode;
      return h(Dialog,{key:mode+':'+(s.modal.record?.id||''),controller,t,s,mode});
    }
    function Dialog({controller,t,s,mode}) {
      const ref=React.useRef(null);const closeRef=React.useRef(()=>{});closeRef.current=()=>controller.close();
      React.useEffect(()=>{
        const previous=document.activeElement;const root=ref.current;
        const focusable=()=>Array.from(root.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')).filter(el=>el.getClientRects().length);
        (root.querySelector('input:not(:disabled),select:not(:disabled),textarea:not(:disabled)')||focusable()[0]||root).focus();
        const keydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeRef.current();}if(e.key==='Tab'){const items=focusable();const first=items[0],last=items.at(-1);if(!first){e.preventDefault();root.focus();}else if(e.shiftKey&&(document.activeElement===first||!root.contains(document.activeElement))){e.preventDefault();last.focus();}else if(!e.shiftKey&&(document.activeElement===last||!root.contains(document.activeElement))){e.preventDefault();first.focus();}}};
        const focusin=e=>{if(!root.contains(e.target))(focusable()[0]||root).focus();};
        document.addEventListener('keydown',keydown,true);document.addEventListener('focusin',focusin);
        return()=>{root.querySelectorAll('input,textarea').forEach(input=>{input.value='';});document.removeEventListener('keydown',keydown,true);document.removeEventListener('focusin',focusin);if(previous?.isConnected)previous.focus();};
      },[]);
      const passwordMode=['setup','unlock','recover','enableRecovery','rotateRecovery'].includes(mode);
      const title=t(mode==='recoveryIssued'?'recoveryTitle':passwordMode?mode:mode==='delete'?'deleteTitle':mode==='edit'?'edit':'add');
      return h('div',{className:'sv-root sv-overlay'},h('style',null,css+passwordDialogCss),h('section',{ref,className:`sv-dialog${passwordMode?' sv-dialog-password':''}`,role:'dialog','aria-modal':true,'aria-labelledby':'sv-dialog-title',tabIndex:-1,'aria-busy':s.pending},h('div',{className:'sv-dialog-head'},h('h2',{id:'sv-dialog-title'},title),h('button',{type:'button',className:'sv-button sv-icon','aria-label':t('close'),disabled:s.pending||mode==='recoveryIssued',onClick:()=>controller.close()},h('svg',{width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.5,strokeLinecap:'round','aria-hidden':true},h('path',{d:'m6 6 12 12M18 6 6 18'})))),s.error&&h('p',{className:'sv-error',role:'alert'},t(s.error)),mode==='recoveryIssued'?h(RecoveryIssued,{controller,t,s}):passwordMode?h(PasswordForm,{controller,t,s,mode}):mode==='delete'?h('div',{className:'sv-form'},h('p',{className:'sv-name'},s.modal.record.name),h('p',{className:'sv-muted'},t('deleteHelp')),h('div',{className:'sv-footer'},h(Button,{disabled:s.pending,onClick:()=>controller.close()},t('cancel')),h(Button,{disabled:s.pending,onClick:()=>controller.run(()=>controller.request('delete',{id:s.modal.record.id,revision:s.modal.record.revision}),()=>controller.set({modal:null}))},t('remove')))):h(RecordForm,{controller,t,s})));
    }
    function PasswordForm({controller,t,s,mode}) {
      const [password,setPassword]=React.useState(''),[confirmation,setConfirmation]=React.useState(''),[show,setShow]=React.useState(false),[recoveryKey,setRecoveryKey]=React.useState('');
      const creating=mode==='setup'||mode==='recover';
      const long=Array.from(password).length>=12,match=password.length>0&&password===confirmation;
      const submit=async e=>{e.preventDefault();if(creating&&(!long||!match)){controller.set({error:'invalidPassword'});return;}let issued=null;const ok=await controller.run(async version=>{issued=await controller.request(mode,{password,...(creating?{confirmation}:{}),...(mode==='recover'?{recoveryKey}:{})});if(issued?.recoveryKey)controller.issueRecovery(issued.recoveryKey,version);},()=>{setPassword('');setConfirmation('');setShow(false);setRecoveryKey('');if(!issued?.recoveryKey&&(s.modal.mode==='unlock'||s.modal.mode==='recover'))controller.set({modal:null});});setPassword('');setConfirmation('');setRecoveryKey('');if(!ok&&['setup','recover','enableRecovery','rotateRecovery'].includes(mode))controller.set({error:'recoveryFailure'});};
      return h('form',{className:'sv-form',onSubmit:submit,autoComplete:'off'},h('p',{className:'sv-muted'},t(mode==='setup'?'setupHelp':mode==='recover'?'recoveryHelp':mode==='enableRecovery'?'recoveryEnableHelp':mode==='rotateRecovery'?'recoveryRotateHelp':'unlockHelp')),mode==='recover'&&h(Field,{label:t('recovery')},h('input',{className:'sv-input',type:'password',value:recoveryKey,onChange:e=>setRecoveryKey(e.target.value),required:true,autoComplete:'off',disabled:s.pending,spellCheck:false,autoCapitalize:'none'})),h(Field,{label:t('master')},h('div',{className:'sv-secret-row'},h('input',{className:'sv-input',type:show?'text':'password',value:password,onChange:e=>setPassword(e.target.value),required:true,autoComplete:creating?'new-password':'current-password',disabled:s.pending,spellCheck:false,autoCapitalize:'none'}),h(Button,{disabled:s.pending,onClick:()=>setShow(v=>!v),'aria-pressed':show},t(show?'hide':'show')))),creating&&h(React.Fragment,null,h(Field,{label:t('repeat')},h('input',{className:'sv-input',type:show?'text':'password',value:confirmation,onChange:e=>setConfirmation(e.target.value),required:true,autoComplete:'new-password',disabled:s.pending,spellCheck:false})),h('ul',{className:'sv-checklist','aria-live':'polite'},h('li',{'data-pass':long},`${long?'✓':'○'} ${t('length')}`),h('li',{'data-pass':match},`${match?'✓':'○'} ${t('matching')}`)),h('p',{className:'sv-muted sv-warning'},t('nontrivial'))),h('div',{className:'sv-footer'},h(Button,{disabled:s.pending,onClick:()=>controller.close()},t('cancel')),h(Button,{type:'submit',primary:true,disabled:s.pending||!password||(creating&&(!long||!match))||(mode==='recover'&&!recoveryKey)},t(s.pending?'saving':mode))),mode==='unlock'&&s.recoveryAvailable&&h(Button,{disabled:s.pending,onClick:()=>controller.set({modal:{mode:'recover'},error:null})},t('recover')));
    }
    function RecoveryIssued({controller,t,s}) {
      const [saved,setSaved]=React.useState(false),[key,setKey]=React.useState('');
      React.useEffect(()=>{const issued=controller.peekIssuedRecovery();if(issued)setKey(issued);},[controller]);
      return h('div',{className:'sv-form'},h('p',{className:'sv-muted'},t('recoveryIssuedHelp')),h(Field,{label:t('recovery')},h('textarea',{className:'sv-input sv-keytext',readOnly:true,value:key,autoComplete:'off',spellCheck:false,'aria-label':t('recovery')})),h('p',{className:'sv-muted'},t('recoveryBackup')),h('label',{className:'sv-check'},h('input',{type:'checkbox',checked:saved,onChange:e=>setSaved(e.target.checked)}),t('recoveryAck')),h('div',{className:'sv-footer'},h(Button,{primary:true,disabled:!saved||!key,onClick:()=>controller.acknowledgeRecovery()},t('recoveryDone'))));
    }
    function RecordForm({controller,t,s}) {
      const edit=Boolean(s.modal.record),record=s.modal.record||s.pendingDraft||null,form=React.useRef(null);
      const [kind,setKind]=React.useState(record?.kind||'token'),[replace,setReplace]=React.useState(!edit),[show,setShow]=React.useState(false),[allow,setAllow]=React.useState(Boolean(record?.allowAgentUse));
      const clearSecrets=()=>{form.current?.querySelectorAll('[data-secret]').forEach(input=>{input.value='';});};
      React.useEffect(()=>()=>clearSecrets(),[]);
      const input=(name,options={})=>h('input',{className:'sv-input',name,defaultValue:record?.[name]??'',disabled:s.pending,...options});
      const secretInput=(name,options={})=>h('input',{className:'sv-input',name,type:show?'text':'password','data-secret':true,autoComplete:'new-password',autoCapitalize:'none',spellCheck:false,disabled:s.pending,...options});
      const submit=async e=>{e.preventDefault();const data=new FormData(form.current),metadata={kind,name:String(data.get('name')||'').trim(),description:String(data.get('description')||''),url:String(data.get('url')||''),username:String(data.get('username')||''),host:String(data.get('host')||''),port:data.get('port')?Number(data.get('port')):undefined,tags:String(data.get('tags')||'').split(',').map(x=>x.trim()).filter(Boolean),allowAgentUse:allow};
        if(metadata.allowAgentUse&&kind!=='ssh-key'){try{const url=new URL(metadata.url);if(url.protocol!=='https:'||url.username||url.password)throw new Error();}catch{controller.set({error:'invalidScope'});return;}}
        const secret={};if(replace)for(const key of ['token','password','privateKey','passphrase'])if(data.has(key))secret[key]=String(data.get(key));
        const args=replace?{record:{...metadata,...(edit?{id:record.id,revision:record.revision}:{}),secret}}:{id:record.id,revision:record.revision,metadata};
        if(data.get('share')&&s.modal.sessionId)args.sessionId=s.modal.sessionId;
        await controller.run(()=>controller.request(replace?'save':'updateMetadata',args),()=>controller.set({modal:null}));clearSecrets();setShow(false);
      };
      return h('form',{ref:form,className:'sv-form',onSubmit:submit,autoComplete:'off'},h('p',{className:'sv-muted'},t('metadataOnly')),h('div',{className:'sv-grid'},h(Field,{label:t('name')},input('name',{required:true,maxLength:200})),h(Field,{label:t('kind')},h('select',{className:'sv-input',name:'kind',value:kind,disabled:s.pending||edit,onChange:e=>{clearSecrets();setKind(e.target.value);setAllow(false);setShow(false);}},['token','password','ssh-key'].map(k=>h('option',{key:k,value:k},t(k)))))),h(Field,{label:t('description')},h('textarea',{className:'sv-input sv-desc',name:'description',defaultValue:record?.description||'',disabled:s.pending,maxLength:4000})),h('div',{className:'sv-grid'},h(Field,{label:t('username')},input('username',{autoComplete:'off'})),kind==='ssh-key'?h(Field,{label:t('host')},input('host')):h(Field,{label:t('url')},input('url',{type:'url',placeholder:'https://api.example.com'}))),kind==='ssh-key'&&h(Field,{label:t('port')},input('port',{type:'number',min:1,max:65535,placeholder:'22'})),h(Field,{label:t('tags')},input('tags',{defaultValue:(record?.tags||[]).join(', ')})),edit&&h('div',null,h('label',{className:'sv-check'},h('input',{type:'checkbox',checked:replace,disabled:s.pending,onChange:e=>{clearSecrets();setReplace(e.target.checked);setShow(false);}}),t('replace')),h('p',{className:'sv-muted'},t('replaceHelp'))),replace&&h(React.Fragment,null,h('div',{className:'sv-actions'},h('span',{className:'sv-muted'},t('secretHelp')),h(Button,{disabled:s.pending,onClick:()=>setShow(v=>!v),'aria-pressed':show},t(show?'hide':'show'))),kind==='ssh-key'?h(React.Fragment,null,h(Field,{label:t('privateKey')},h('textarea',{name:'privateKey',className:`sv-input sv-keytext${show?'':' sv-concealed'}`,'data-secret':true,required:true,disabled:s.pending,spellCheck:false,style:show?undefined:{WebkitTextSecurity:'disc'}})),h(Field,{label:t('passphrase')},secretInput('passphrase'))):h(Field,{label:t(kind)},secretInput(kind,{required:true}))),h(React.Fragment,null,h('label',{className:'sv-check'},h('input',{type:'checkbox',checked:allow,disabled:s.pending,onChange:e=>setAllow(e.target.checked)}),t('allowAgentUse')),h('p',{className:'sv-muted'},t('scopeHelp')),h('p',{className:'sv-muted'},t(kind==='ssh-key'?'sshHelp':'httpHelp'))),s.modal.sessionId&&h('label',{className:'sv-check'},h('input',{type:'checkbox',name:'share',defaultChecked:true,disabled:s.pending}),t('sessionHelp')),h('div',{className:'sv-footer'},h(Button,{disabled:s.pending,onClick:()=>controller.close()},t('cancel')),h(Button,{type:'submit',primary:true,disabled:s.pending},t(s.pending?'saving':'save'))));
    }
    return {
      inject:['slots','locale'],
      apply(ctx) {
        ctx.effect(()=>registerMainframeLocale(ctx.locale,NS,en,ru));
        const t=ctx.locale.bind(NS),controller=controllerFor();
        ctx.effect(()=>()=>controller.dispose());
        ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:'secrets-vault',order:10,label:()=>t('panel'),locale:NS},KeyIcon));
        ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:'secrets-vault',locale:NS,inject:()=>({controller})},Catalog));
        ctx.slots.inject('shell.overlay',()=>ctx.slots.register({name:'shell.overlay',id:'secrets-vault',locale:NS,inject:()=>({controller})},Modal));
        // The native composer '+' surface is commandUi, shared with slash commands.
        ctx.inject(['commandUi'],scope=>scope.effect(()=>{
          let disposeCommand,copy;
          const register=()=>{const next=t('panel')+'\n'+t('commandDescription');if(next===copy)return;copy=next;disposeCommand?.();disposeCommand=scope.commandUi.register({name:'secrets-vault',label:()=>t('panel'),description:()=>t('commandDescription'),icon:KeyIcon,available:()=>!controller.getSnapshot().pending,ui:{kind:'action',run:session=>controller.open({mode:'add',sessionId:session.sessionId})}});};
          register();const unsubscribe=ctx.locale.subscribe(register);
          return()=>{unsubscribe();disposeCommand?.();};
        }));
      }
    };
  }
});
