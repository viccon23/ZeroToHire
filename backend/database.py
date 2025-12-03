"""
SQLite database management for ZeroToHire tutor application.
Handles persistent storage of conversations, problems, code, and settings.
"""

import sqlite3
import os
from typing import List, Dict, Optional, Any
import json


class Database:
    def __init__(self, db_path: str = "data/zerotohire.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Problems table (track completed problems and attempts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                difficulty TEXT,
                completed BOOLEAN DEFAULT 0,
                completed_at TIMESTAMP,
                attempts_count INTEGER DEFAULT 0,
                first_attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(problem_id)
            )
        """)
        
        # Conversations table (chat message history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Code snapshots table (save code for each problem)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                language TEXT DEFAULT 'python',
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Settings table (user preferences)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT NOT NULL UNIQUE,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    # ==================== Conversation Management ====================
    
    def save_message(self, role: str, content: str, problem_id: Optional[int] = None):
        """Save a chat message to the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (problem_id, role, content)
            VALUES (?, ?, ?)
        """, (problem_id, role, content))
        self.conn.commit()
    
    def get_conversation_history(self, problem_id: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation history. If problem_id provided, only for that problem.
        If limit provided, returns the MOST RECENT messages."""
        cursor = self.conn.cursor()
        
        if problem_id is not None:
            if limit:
                # Get most recent messages in reverse, then we'll flip them
                query = """
                    SELECT role, content, timestamp, problem_id
                    FROM conversations
                    WHERE problem_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                cursor.execute(query, (problem_id, limit))
            else:
                query = """
                    SELECT role, content, timestamp, problem_id
                    FROM conversations
                    WHERE problem_id = ?
                    ORDER BY timestamp ASC
                """
                cursor.execute(query, (problem_id,))
        else:
            if limit:
                # Get most recent messages in reverse, then we'll flip them
                query = """
                    SELECT role, content, timestamp, problem_id
                    FROM conversations
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                cursor.execute(query, (limit,))
            else:
                query = """
                    SELECT role, content, timestamp, problem_id
                    FROM conversations
                    ORDER BY timestamp ASC
                """
                cursor.execute(query)
        
        rows = cursor.fetchall()
        
        # If we used limit, rows are in DESC order, so reverse them to get chronological
        if limit:
            rows = list(reversed(rows))
        
        return [
            {
                'role': row['role'],
                'content': row['content'],
                'timestamp': row['timestamp'],
                'problem_id': row['problem_id']
            }
            for row in rows
        ]
    
    def clear_conversation_history(self, problem_id: Optional[int] = None):
        """Clear conversation history. If problem_id provided, clear only for that problem."""
        cursor = self.conn.cursor()
        if problem_id is not None:
            cursor.execute("DELETE FROM conversations WHERE problem_id = ?", (problem_id,))
        else:
            cursor.execute("DELETE FROM conversations")
        self.conn.commit()
    
    def reset_problem(self, problem_id: int):
        """Completely reset a problem: clear messages, delete code, mark as incomplete."""
        cursor = self.conn.cursor()
        
        # Delete conversation history for this problem
        cursor.execute("DELETE FROM conversations WHERE problem_id = ?", (problem_id,))
        
        # Delete saved code for this problem
        cursor.execute("DELETE FROM code_snapshots WHERE problem_id = ?", (problem_id,))
        
        # Mark problem as incomplete (or delete the entry)
        cursor.execute("DELETE FROM problems WHERE problem_id = ?", (problem_id,))
        
        self.conn.commit()
    
    # ==================== Problem Management ====================
    
    def get_current_problem(self) -> Optional[Dict]:
        """Get the last problem worked on."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT problem_id, title, difficulty, completed
            FROM problems
            ORDER BY last_attempted_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row['problem_id'],
                'title': row['title'],
                'difficulty': row['difficulty'],
                'completed': bool(row['completed'])
            }
        return None
    
    def set_problem(self, problem_id: int, title: str, difficulty: str):
        """Set or update the current problem."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO problems (problem_id, title, difficulty, last_attempted_at, attempts_count)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(problem_id) DO UPDATE SET
                last_attempted_at = CURRENT_TIMESTAMP,
                attempts_count = attempts_count + 1
        """, (problem_id, title, difficulty))
        self.conn.commit()
    
    def mark_problem_complete(self, problem_id: int):
        """Mark a problem as completed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE problems
            SET completed = 1, completed_at = CURRENT_TIMESTAMP
            WHERE problem_id = ?
        """, (problem_id,))
        self.conn.commit()
    
    def mark_problem_incomplete(self, problem_id: int):
        """Mark a problem as incomplete."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE problems
            SET completed = 0, completed_at = NULL
            WHERE problem_id = ?
        """, (problem_id,))
        self.conn.commit()
    
    def is_problem_completed(self, problem_id: int) -> bool:
        """Check if a problem is marked as completed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT completed FROM problems
            WHERE problem_id = ?
        """, (problem_id,))
        
        row = cursor.fetchone()
        return bool(row['completed']) if row else False
    
    def get_completed_problems(self) -> List[int]:
        """Get list of completed problem IDs."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT problem_id FROM problems
            WHERE completed = 1
        """)
        
        return [row['problem_id'] for row in cursor.fetchall()]
    
    # ==================== Code Management ====================
    
    def save_code(self, problem_id: int, code: str, language: str = 'python'):
        """Save code snapshot for a problem."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO code_snapshots (problem_id, code, language)
            VALUES (?, ?, ?)
        """, (problem_id, code, language))
        self.conn.commit()
    
    def get_latest_code(self, problem_id: int) -> Optional[str]:
        """Get the latest saved code for a problem."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT code FROM code_snapshots
            WHERE problem_id = ?
            ORDER BY saved_at DESC
            LIMIT 1
        """, (problem_id,))
        
        row = cursor.fetchone()
        return row['code'] if row else None
    
    def get_code_history(self, problem_id: int, limit: int = 10) -> List[Dict]:
        """Get code history for a problem."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT code, language, saved_at
            FROM code_snapshots
            WHERE problem_id = ?
            ORDER BY saved_at DESC
            LIMIT ?
        """, (problem_id, limit))
        
        return [
            {
                'code': row['code'],
                'language': row['language'],
                'saved_at': row['saved_at']
            }
            for row in cursor.fetchall()
        ]
    
    # ==================== Settings Management ====================
    
    def save_setting(self, key: str, value: Any):
        """Save a setting."""
        cursor = self.conn.cursor()
        value_str = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute("""
            INSERT INTO settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value_str, value_str))
        self.conn.commit()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT setting_value FROM settings
            WHERE setting_key = ?
        """, (key,))
        
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['setting_value'])
            except (json.JSONDecodeError, TypeError):
                return row['setting_value']
        return default
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT setting_key, setting_value FROM settings
        """)
        
        settings = {}
        for row in cursor.fetchall():
            try:
                settings[row['setting_key']] = json.loads(row['setting_value'])
            except (json.JSONDecodeError, TypeError):
                settings[row['setting_key']] = row['setting_value']
        
        return settings
    
    # ==================== Statistics ====================
    
    def get_user_stats(self) -> Dict:
        """Get statistics."""
        cursor = self.conn.cursor()
        
        # Total problems attempted
        cursor.execute("""
            SELECT COUNT(*) as count FROM problems
        """)
        total_attempted = cursor.fetchone()['count']
        
        # Total problems completed
        cursor.execute("""
            SELECT COUNT(*) as count FROM problems WHERE completed = 1
        """)
        total_completed = cursor.fetchone()['count']
        
        # Total messages
        cursor.execute("""
            SELECT COUNT(*) as count FROM conversations
        """)
        total_messages = cursor.fetchone()['count']
        
        # Completion by difficulty
        cursor.execute("""
            SELECT difficulty, COUNT(*) as count
            FROM problems
            WHERE completed = 1
            GROUP BY difficulty
        """)
        by_difficulty = {row['difficulty']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_attempted': total_attempted,
            'total_completed': total_completed,
            'total_messages': total_messages,
            'completed_by_difficulty': by_difficulty,
            'completion_rate': (total_completed / total_attempted * 100) if total_attempted > 0 else 0
        }
    
    # ==================== Cleanup ====================
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
