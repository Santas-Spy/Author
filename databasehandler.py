import json
import sqlite3
from uuid import UUID, uuid4


class DatabaseHandler:
    def __init__(self, database_name="appdata.db"):
        self.database_name = database_name

    def connect(self):
        connection = sqlite3.connect(self.database_name)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_table(self):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                data_format INTEGER,
                system_prompt TEXT,
                summary TEXT,
                processedSummary BOOLEAN DEFAULT FALSE,
                processedTitle BOOLEAN DEFAULT FALSE,
                processedAnalysis BOOLEAN DEFAULT FALSE,
                processedTags BOOLEAN DEFAULT FALSE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_tags (
                conversation_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,

                PRIMARY KEY (conversation_id, tag_id),

                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (tag_id)
                    REFERENCES tags(id)
                    ON DELETE CASCADE
                )
            """)

    def create_conversation(self) -> str:
        conversation_id = str(uuid4())
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("INSERT INTO conversations (id) VALUES (?)", (conversation_id,))

        return conversation_id

    def add_tag_to_conversation(self, conversation_id: str, tag: str):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
            tag_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO conversation_tags (conversation_id, tag_id) VALUES (?, ?)",
                (conversation_id, tag_id),
            )

    def update_conversation(self, conversation_id: str, data):
        with self.connect() as connection:
            cursor = connection.cursor()

            if "title" in data:
                cursor.execute(
                    """
                    UPDATE conversations
                    SET title = ?, processedTitle = ?
                    WHERE id = ?
                    """,
                    (data["title"], True, str(id)),
                )

            if "summary" in data:
                cursor.execute(
                    """
                    UPDATE conversations
                    SET summary = ?, processedSummary = ?
                    WHERE id = ?
                    """,
                    (data["summary"], True, str(id)),
                )

            if "tags" in data:
                # Get a list of tags
                tags = json.loads(data["tags"])
                for tag in tags:
                    self.add_tag_to_conversation(conversation_id, tag)
