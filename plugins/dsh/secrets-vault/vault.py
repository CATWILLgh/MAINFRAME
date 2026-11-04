"""Private SQLCipher worker. JSON-line stdin/stdout only; never logs requests."""
import sys
import os
import json
import uuid
import fcntl
from pathlib import Path
import sqlcipher3 as sqlite

os.umask(0o077)


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, path):
        self.path = Path(path).absolute()
        self.db = None

    def status(self):
        return {"exists": self.path.is_file(), "unlocked": self.db is not None}

    def lock(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        return self.status()

    def _open(self, password, create=False):
        if not isinstance(password, str) or not password or len(password) > 4096 or '\x00' in password:
            raise VaultError("Invalid password.")
        if self.db is not None:
            raise VaultError("Lock the vault first.")
        if self.path.is_symlink():
            raise VaultError("Unsafe vault path.")
        if not create and not self.path.is_file():
            raise VaultError("Vault is not initialized.")
        db = None
        try:
            # mode=rw prevents unlock from creating a missing file.
            uri = self.path.as_uri() + "?mode=rw"
            db = sqlite.connect(uri, uri=True, timeout=5)
            version = db.execute("PRAGMA cipher_version").fetchone()
            if not version or not version[0]:
                raise VaultError("SQLCipher is unavailable.")
            # SQLCipher key pragma cannot be parameter-bound. Quote SQL text explicitly.
            db.execute("PRAGMA key = '" + password.replace("'", "''") + "'")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("SELECT count(*) FROM sqlite_master").fetchone()
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA secure_delete=ON")
            if create:
                db.executescript("CREATE TABLE vault_meta(version INTEGER NOT NULL); INSERT INTO vault_meta VALUES(1); CREATE TABLE entries(id TEXT PRIMARY KEY, metadata TEXT NOT NULL, secret TEXT NOT NULL, created TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')), updated TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));")
                db.commit()
            if db.execute("SELECT version FROM vault_meta").fetchone() != (1,):
                raise VaultError("Unsupported vault format.")
            self.db = db
            os.chmod(self.path, 0o600)
            return self.status()
        except Exception:
            if db is not None:
                db.close()
            raise VaultError("Unable to open vault. Check password and vault file.") from None

    def setup(self, password=None, confirmation=None):
        if not isinstance(password, str) or len(password) < 12 or len(password) > 4096 or '\x00' in password or password != confirmation:
            raise VaultError("Use a password of at least 12 characters and matching confirmation.")
        if self.db is not None or self.path.exists():
            raise VaultError("Vault already exists.")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.parent.is_symlink():
            raise VaultError("Unsafe vault directory.")
        os.chmod(self.path.parent, 0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            return self._open(password, create=True)
        except Exception:
            # Only remove this newly reserved empty/failed setup file.
            if self.path.exists():
                self.path.unlink()
            raise

    def unlock(self, password=None):
        return self._open(password)

    def rekey(self, password=None):
        if not isinstance(password, str) or len(password) < 12 or len(password) > 4096 or '\x00' in password:
            raise VaultError("Invalid encryption key.")
        db = self._require()
        db.commit()
        try:
            db.execute("PRAGMA rekey = '" + password.replace("'", "''") + "'")
            db.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return self.status()
        except Exception:
            self.lock()
            raise VaultError("Unable to update vault encryption key.") from None

    def _require(self):
        if self.db is None:
            raise VaultError("Vault is locked.")
        return self.db

    @staticmethod
    def _metadata(value):
        if not isinstance(value, dict):
            raise VaultError("Invalid metadata.")
        string_fields = {"label", "provider", "type", "notes", "username", "url", "name", "kind", "description", "host"}
        allowed = string_fields | {"tags", "port", "allowAgentUse"}
        if set(value) - allowed:
            raise VaultError("Unsupported metadata fields.")
        for key, item in value.items():
            if key in string_fields:
                if not isinstance(item, str) or len(item) > (8192 if key in {"notes", "description"} else 2048) or '\x00' in item:
                    raise VaultError("Invalid metadata field.")
            elif key == "allowAgentUse":
                if type(item) is not bool:
                    raise VaultError("Invalid agent-use permission.")
            elif key == "port":
                if type(item) is not int or not 1 <= item <= 65535:
                    raise VaultError("Invalid port.")
            elif key == "tags":
                if not isinstance(item, list) or len(item) > 100 or any(not isinstance(tag, str) or len(tag) > 128 or '\x00' in tag for tag in item):
                    raise VaultError("Invalid tags.")
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded) > 32768:
            raise VaultError("Metadata is too large.")
        return encoded

    def list(self):
        rows = self._require().execute("SELECT id,metadata,created,updated FROM entries ORDER BY updated DESC,id").fetchall()
        return [{"id": r[0], "metadata": json.loads(r[1]), "created": r[2], "updated": r[3]} for r in rows]

    def save(self, metadata=None, secret=None, id=None):
        db = self._require()
        meta = self._metadata(metadata)
        if not isinstance(secret, (dict, str)):
            raise VaultError("Invalid secret.")
        data = json.dumps(secret, ensure_ascii=False)
        if len(data) > 1048576:
            raise VaultError("Secret is too large.")
        if id is None:
            id = str(uuid.uuid4())
            with db:
                db.execute("INSERT INTO entries(id,metadata,secret) VALUES(?,?,?)", (id, meta, data))
        else:
            self._id(id)
            with db:
                cur = db.execute("UPDATE entries SET metadata=?,secret=?,updated=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (meta, data, id))
                if cur.rowcount != 1:
                    raise VaultError("Entry not found.")
        return {"id": id}

    @staticmethod
    def _id(id):
        if not isinstance(id, str) or len(id) > 128:
            raise VaultError("Invalid entry id.")

    def delete(self, id=None):
        db = self._require()
        self._id(id)
        with db:
            db.execute("DELETE FROM entries WHERE id=?", (id,))
        return {"deleted": True}

    def updateMetadata(self, id=None, metadata=None):
        db = self._require()
        self._id(id)
        meta = self._metadata(metadata)
        with db:
            cur = db.execute("UPDATE entries SET metadata=?,updated=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?", (meta, id))
            if cur.rowcount != 1:
                raise VaultError("Entry not found.")
        return {"id": id}

    def internalGet(self, id=None):
        self._id(id)
        row = self._require().execute("SELECT secret FROM entries WHERE id=?", (id,)).fetchone()
        if row is None:
            raise VaultError("Entry not found.")
        return json.loads(row[0])


def main():
    if len(sys.argv) != 2:
        return 2
    # Hold a stable advisory lock for this worker lifetime, including while locked.
    # Never unlink the lock inode: a second Host must fail closed, not race rekeys.
    database_path = Path(sys.argv[1]).absolute()
    directory = database_path.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
        return 3
    lock_fd = os.open(str(database_path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(lock_fd)
        return 3
    vault = Vault(sys.argv[1])
    allowed = {"status", "setup", "unlock", "lock", "rekey", "list", "save", "delete", "updateMetadata", "internalGet"}
    try:
        for line in sys.stdin:
            request_id = None
            req = params = result = reply = None
            try:
                if len(line) > 2097152:
                    raise VaultError("Request is too large.")
                req = json.loads(line)
                request_id = req.get("id")
                method = req.get("method")
                if method not in allowed:
                    raise VaultError("Unsupported operation.")
                params = req.get("params", {})
                if not isinstance(params, dict):
                    raise VaultError("Invalid request.")
                result = getattr(vault, method)(**params)
                reply = {"id": request_id, "result": result}
            except VaultError as exc:
                reply = {"id": request_id, "error": str(exc)}
            except Exception:
                reply = {"id": request_id, "error": "Vault operation failed."}
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            # Do not retain the previous request/password/secret while idle.
            # Immutable Python strings cannot be guaranteed zeroized.
            req = params = result = reply = line = None
    finally:
        vault.lock()
        os.close(lock_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
