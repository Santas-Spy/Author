import json
import os
import sqlite3
from uuid import UUID, uuid4


class DatabaseHandler:
    def __init__(self, database_name="appdata.db"):
        dir = "data/"
        os.makedirs(dir, exist_ok=True)
        self.database_name = f"{dir}/{database_name}"
        self.create_tables()

    def connect(self):
        connection = sqlite3.connect(self.database_name)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        return connection

    def create_tables(self):
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
        allowed_fields = {
            "title",
            "content",
            "data_format",
            "system_prompt",
            "summary",
            "processedSummary",
            "processedTitle",
            "processedAnalysis",
            "processedTags",
        }

        # Handle conversation fields
        fields = []
        values = []

        for field in allowed_fields:
            if field in data:
                fields.append(f"{field} = ?")
                values.append(data[field])

        if fields:
            values.append(conversation_id)

            with self.connect() as connection:
                cursor = connection.cursor()

                cursor.execute(
                    f"""
                    UPDATE conversations
                    SET {", ".join(fields)}
                    WHERE id = ?
                    """,
                    values,
                )

        # Handle tags separately because they belong in conversation_tags
        if "tags" in data:
            tags = data["tags"]

            # Support either a JSON string or a Python list
            print(tags, flush=True)
            if isinstance(tags, str):
                tags = json.loads(tags)

            with self.connect() as connection:
                cursor = connection.cursor()

                # Remove existing tags
                cursor.execute(
                    """
                    DELETE FROM conversation_tags
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                )

                # Add new tags
                for tag in tags:
                    cursor.execute(
                        "INSERT OR IGNORE INTO tags (name) VALUES (?)",
                        (tag,),
                    )

                    cursor.execute(
                        "SELECT id FROM tags WHERE name = ?",
                        (tag,),
                    )

                    tag_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO conversation_tags
                        (conversation_id, tag_id)
                        VALUES (?, ?)
                        """,
                        (conversation_id, tag_id),
                    )

    def load_conversation(self, conversation_id: str):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM conversations WHERE id = (?)", (conversation_id,))
            conversation = cursor.fetchone()
            return conversation

    def check_conversation_status(self, conversation_id: str):
        print(conversation_id)
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """SELECT processedSummary, processedTitle, processedAnalysis, processedTags
                   FROM conversations WHERE id = (?)""",
                (conversation_id,),
            )

            row = cursor.fetchone()
            return {
                "processedSummary": row[0],
                "processedTitle": row[1],
                "processedAnalysis": row[2],
                "processedTags": row[3],
            }

    def list_chat_ids(self):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT id, title FROM conversations")
            rows = cursor.fetchall()
            ids = [{"id": row[0], "title": row[1]} for row in rows]
            return ids

    def delete_all_chats(self):
        pass

    def delete_chat(self, conversation_id):
        pass
