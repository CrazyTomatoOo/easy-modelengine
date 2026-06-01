import sqlite3
import threading
import uuid
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class TaskRecord:
    id: str
    task_type: str
    state: str
    model_source: str
    model_id: str
    revision: str
    local_cache_dir: str
    remote_host: Optional[str] = None
    remote_path: Optional[str] = None


class Database:
    """SQLite database access layer with thread-local connections."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def close(self):
        """Close the thread-local connection if it exists."""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
    
    def init_schema(self):
        """Initialize database schema with all required tables."""
        conn = self._get_connection()
        
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                model_source TEXT NOT NULL,
                model_id TEXT NOT NULL,
                revision TEXT NOT NULL DEFAULT 'main',
                local_cache_dir TEXT NOT NULL,
                remote_host TEXT,
                remote_path TEXT,
                file_filter TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                total_files INTEGER DEFAULT 0,
                completed_files INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                completed_bytes INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS task_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                remote_url TEXT,
                expected_hash TEXT,
                hash_algorithm TEXT,
                download_state TEXT DEFAULT 'pending',
                download_bytes INTEGER DEFAULT 0,
                local_path TEXT,
                verify_state TEXT DEFAULT 'pending',
                actual_hash TEXT,
                transfer_state TEXT DEFAULT 'pending',
                transfer_bytes INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                UNIQUE(task_id, file_path),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS server_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                host TEXT NOT NULL,
                port INTEGER DEFAULT 22,
                username TEXT NOT NULL,
                auth_type TEXT NOT NULL,
                encrypted_auth BLOB NOT NULL,
                auth_salt BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                level TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL,
                file_path TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        conn.commit()
    
    def create_task(
        self,
        task_type: str,
        model_source: str,
        model_id: str,
        local_cache_dir: str,
        revision: str = "main",
        remote_host: Optional[str] = None,
        remote_path: Optional[str] = None,
        file_filter: Optional[str] = None
    ) -> str:
        """Create a new task and return its ID."""
        task_id = str(uuid.uuid4())
        
        conn = self._get_connection()
        conn.execute('''
            INSERT INTO tasks (
                id, task_type, model_source, model_id, revision,
                local_cache_dir, remote_host, remote_path, file_filter
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id, task_type, model_source, model_id, revision,
            local_cache_dir, remote_host, remote_path, file_filter
        ))
        conn.commit()
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Retrieve a task by ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            'SELECT * FROM tasks WHERE id = ?',
            (task_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return TaskRecord(
            id=row['id'],
            task_type=row['task_type'],
            state=row['state'],
            model_source=row['model_source'],
            model_id=row['model_id'],
            revision=row['revision'],
            local_cache_dir=row['local_cache_dir'],
            remote_host=row['remote_host'],
            remote_path=row['remote_path']
        )
    
    def update_task_state(
        self,
        task_id: str,
        state: str,
        completed_files: Optional[int] = None,
        total_files: Optional[int] = None,
        completed_bytes: Optional[int] = None,
        total_bytes: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update task state and optionally progress info."""
        conn = self._get_connection()
        
        updates = ['state = ?', 'updated_at = CURRENT_TIMESTAMP']
        params = [state]
        
        if completed_files is not None:
            updates.append('completed_files = ?')
            params.append(completed_files)
        
        if total_files is not None:
            updates.append('total_files = ?')
            params.append(total_files)
        
        if completed_bytes is not None:
            updates.append('completed_bytes = ?')
            params.append(completed_bytes)
        
        if total_bytes is not None:
            updates.append('total_bytes = ?')
            params.append(total_bytes)
        
        if error_message is not None:
            updates.append('error_message = ?')
            params.append(error_message)
        
        if state == 'completed':
            updates.append('completed_at = CURRENT_TIMESTAMP')
        
        params.append(task_id)
        
        cursor = conn.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        return cursor.rowcount > 0
    
    def add_task_file(
        self,
        task_id: str,
        file_path: str,
        file_size: int,
        remote_url: Optional[str] = None,
        expected_hash: Optional[str] = None,
        hash_algorithm: Optional[str] = None
    ) -> int:
        """Add a file to a task. Returns the file ID."""
        conn = self._get_connection()
        cursor = conn.execute('''
            INSERT INTO task_files (
                task_id, file_path, file_size, remote_url,
                expected_hash, hash_algorithm
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            task_id, file_path, file_size, remote_url,
            expected_hash, hash_algorithm
        ))
        conn.commit()
        
        return cursor.lastrowid
    
    def get_task_files(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all files for a task."""
        conn = self._get_connection()
        cursor = conn.execute(
            'SELECT * FROM task_files WHERE task_id = ?',
            (task_id,)
        )
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def update_file_state(
        self,
        file_id: int,
        download_state: Optional[str] = None,
        download_bytes: Optional[int] = None,
        local_path: Optional[str] = None,
        verify_state: Optional[str] = None,
        actual_hash: Optional[str] = None,
        transfer_state: Optional[str] = None,
        transfer_bytes: Optional[int] = None,
        retry_count: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update file state."""
        conn = self._get_connection()
        
        updates = []
        params = []
        
        if download_state is not None:
            updates.append('download_state = ?')
            params.append(download_state)
        
        if download_bytes is not None:
            updates.append('download_bytes = ?')
            params.append(download_bytes)
        
        if local_path is not None:
            updates.append('local_path = ?')
            params.append(local_path)
        
        if verify_state is not None:
            updates.append('verify_state = ?')
            params.append(verify_state)
        
        if actual_hash is not None:
            updates.append('actual_hash = ?')
            params.append(actual_hash)
        
        if transfer_state is not None:
            updates.append('transfer_state = ?')
            params.append(transfer_state)
        
        if transfer_bytes is not None:
            updates.append('transfer_bytes = ?')
            params.append(transfer_bytes)
        
        if retry_count is not None:
            updates.append('retry_count = ?')
            params.append(retry_count)
        
        if error_message is not None:
            updates.append('error_message = ?')
            params.append(error_message)
        
        if not updates:
            return True
        
        params.append(file_id)
        
        cursor = conn.execute(
            f"UPDATE task_files SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        return cursor.rowcount > 0
    
    def save_server_config(
        self,
        name: str,
        host: str,
        username: str,
        auth_type: str,
        encrypted_auth: bytes,
        auth_salt: bytes,
        port: int = 22
    ) -> int:
        """Save or update server configuration."""
        conn = self._get_connection()
        
        cursor = conn.execute('''
            INSERT INTO server_configs (
                name, host, port, username, auth_type,
                encrypted_auth, auth_salt
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                host = excluded.host,
                port = excluded.port,
                username = excluded.username,
                auth_type = excluded.auth_type,
                encrypted_auth = excluded.encrypted_auth,
                auth_salt = excluded.auth_salt,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            name, host, port, username, auth_type,
            encrypted_auth, auth_salt
        ))
        conn.commit()
        
        return cursor.lastrowid
    
    def get_server_configs(self) -> List[Dict[str, Any]]:
        """Retrieve all server configurations."""
        conn = self._get_connection()
        cursor = conn.execute('SELECT * FROM server_configs')
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def set_setting(self, key: str, value: str):
        """Set an application setting."""
        conn = self._get_connection()
        conn.execute('''
            INSERT INTO app_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        ''', (key, value))
        conn.commit()
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get an application setting."""
        conn = self._get_connection()
        cursor = conn.execute(
            'SELECT value FROM app_settings WHERE key = ?',
            (key,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return default
        
        return row['value']
