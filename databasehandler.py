import json
import os
import sqlite3
from json.decoder import JSONDecodeError
from uuid import uuid4

from state import settings


class DatabaseHandler:
    def __init__(self, database_name="appdata.db"):
        self.database_name = database_name
        self.create_tables()

    def _get_database_location(self):
        db_location = settings.readSetting("system.database_location", self.database_name)
        dir = "data/"
        os.makedirs(dir, exist_ok=True)
        return f"{dir}/{db_location}"

    def connect(self):
        # Remove transactions while testing
        connection = sqlite3.connect(self._get_database_location(), isolation_level=None)
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
                last_processed_index INTEGER DEFAULT 0,
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source_conversation_id TEXT,

                    FOREIGN KEY (source_conversation_id)
                        REFERENCES conversations(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    user_id INTEGER NOT NULL,
                    fact_id INTEGER NOT NULL,

                    PRIMARY KEY(user_id, fact_id),

                    FOREIGN KEY (user_id)
                        REFERENCES users(id),

                    FOREIGN KEY (fact_id)
                        REFERENCES facts(id)
                        ON DELETE CASCADE
                )
            """)

            # Ensure a default user exists for ID 0
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO users (id) VALUES (0)")

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

    def create_user(self):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("INSERT INTO users (id) VALUES (NULL);")
            id = cursor.lastrowid
            return id

    def save_fact(self, user_id, conversation_id, fact: str):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                "INSERT INTO facts (text, source_conversation_id) VALUES (?, ?)",
                (fact, conversation_id),
            )
            id = cursor.lastrowid
            if id is not None:
                cursor.execute("INSERT INTO user_facts (user_id, fact_id) VALUES (?, ?)", (user_id, id))

    def delete_fact(self, fact):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM facts WHERE text = ?", (fact,))

    def delete_all_facts(self):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM facts")

    def get_user_facts(self, user_id):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT facts.text
                FROM facts
                JOIN user_facts ON facts.id = user_facts.fact_id
                WHERE user_facts.user_id = ?
                """,
                (user_id,),
            )

            rows = cursor.fetchall()
            return [row[0] for row in rows]

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

        for field in data:
            if field in allowed_fields:
                fields.append(f"{field} = ?")
                values.append(data[field])
            else:
                print(f"WARNING: Attempting to set field {field} but database does not allow it")

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
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except JSONDecodeError:
                    print(f"Could not parse tags: {tags}")

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

    def load_conversation(self, conversation_id: str, user_id: int = 0):
        def insert_tags(data):
            # Fetch the tag_ids linked to this conversation
            cursor.execute(
                "SELECT tag_id FROM conversation_tags WHERE conversation_id = (?) ORDER BY tag_id",
                (conversation_id,),
            )
            tag_ids = [row[0] for row in cursor.fetchall()]

            # Resolve the actual tag rows
            tags = None
            if tag_ids:
                placeholders = ",".join("?" * len(tag_ids))
                cursor.execute(
                    f"SELECT * FROM tags WHERE id IN ({placeholders}) ORDER BY id",
                    tag_ids,
                )
                tags = cursor.fetchall()

            # Load tags into the table
            if tags is not None:
                tag_string = ""
                for tag in tags:
                    tag_string = tag_string + f"{tag['name']}, "
                data["tags"] = tag_string

            return data

        def insert_facts(data):
            # Fetch the facts linked to this conversation
            cursor.execute(
                """
                SELECT facts.text
                    FROM facts
                    JOIN user_facts ON facts.id = user_facts.fact_id
                    WHERE user_facts.user_id = (?) AND facts.source_conversation_id = (?)
            """,
                (user_id, conversation_id),
            )
            facts = cursor.fetchall()
            data["Chat Specific Facts"] = []
            for fact in facts:
                data["Chat Specific Facts"].append(fact["text"])

            # Fetch generic facts not linked to any conversation
            cursor.execute(
                """
                SELECT facts.text
                    FROM facts
                    JOIN user_facts ON facts.id = user_facts.fact_id
                    WHERE user_facts.user_id = (?) AND facts.source_conversation_id IS NULL
            """,
                (user_id,),
            )
            facts = cursor.fetchall()
            data["Generic Facts"] = []
            for fact in facts:
                data["Generic Facts"].append(fact["text"])

            return data

        with self.connect() as connection:
            cursor = connection.cursor()

            # 1. Fetch the conversation
            cursor.execute("SELECT * FROM conversations WHERE id = (?)", (conversation_id,))
            conversation = cursor.fetchone()

            if conversation is None:
                return None

            data = {}
            for key in conversation.keys():
                data[key] = conversation[key]

            if data["content"] == None:
                data["content"] = ""

            data = insert_facts(data)
            data = insert_tags(data)
            return data

    def check_conversation_status(self, conversation_id: str):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """SELECT content, processedSummary, processedTitle, processedAnalysis, processedTags
                   FROM conversations WHERE id = (?)""",
                (conversation_id,),
            )

            row = cursor.fetchone()
            return {
                "hasText": row[0] != None,
                "processedSummary": row[1],
                "processedTitle": row[2],
                "processedAnalysis": row[3],
                "processedTags": row[4],
            }

    def list_chat_ids(self) -> list[dict[str, str]]:
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT id, title FROM conversations")
            rows = cursor.fetchall()
            ids = [{"id": row[0], "title": row[1]} for row in rows]
            return ids

    def get_chat_title(self, chat_id: str) -> str | None:
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT title FROM conversations WHERE id = (?)", (chat_id,))
            title = cursor.fetchone()[0]
            return title

    def load_all_conversations(self):
        ids = self.list_chat_ids()
        conversations = []
        for id in ids:
            conversations.append(self.load_conversation(id["id"]))
        return conversations

    def get_last_processed_index(self, chat_id: str):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT last_processed_index FROM conversations WHERE id = ?", (chat_id,))
            index = cursor.fetchone()[0]
            return index

    def set_last_processed_index(self, chat_id: str, index: int):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE conversation SET last_processed_index = (?) WHERE id = (?)",
                (index, chat_id),
            )

    def delete_all_chats(self):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations")

    def delete_chat(self, conversation_id):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = (?)", (conversation_id,))
