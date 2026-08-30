import json
import os
import sqlite3
from json.decoder import JSONDecodeError
from uuid import uuid4


class DatabaseHandler:
    def __init__(self, database_name="appdata_2.db"):
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source_conversation_id INTEGER NOT NULL,

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

    def save_fact(self, user_id, fact):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("INSERT INTO facts (text) VALUES (?)", (fact,))
            id = cursor.lastrowid
            if id is not None:
                cursor.execute(
                    "INSERT INTO user_facts (user_id, fact_id) VALUES (?, ?)", (user_id, id)
                )

    def delete_fact(self, fact):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT id FROM facts WHERE text = ?", (fact,))
            id = cursor.fetchone()[0]
            cursor.execute("DELETE FROM facts WHERE id = ?", (id,))

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

            rows = cursor.fetchmany()
            print(rows)
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

    def load_conversation(self, conversation_id: str):
        with self.connect() as connection:
            cursor = connection.cursor()

            # 1. Fetch the conversation
            cursor.execute("SELECT * FROM conversations WHERE id = (?)", (conversation_id,))
            conversation = cursor.fetchone()

            if conversation is None:
                return None

            # 2. Fetch the tag_ids linked to this conversation
            cursor.execute(
                "SELECT tag_id FROM conversation_tags WHERE conversation_id = (?) ORDER BY tag_id",
                (conversation_id,),
            )
            tag_ids = [row[0] for row in cursor.fetchall()]

            # 3. Resolve the actual tag rows
            tags = None
            if tag_ids:
                placeholders = ",".join("?" * len(tag_ids))
                cursor.execute(
                    f"SELECT * FROM tags WHERE id IN ({placeholders}) ORDER BY id",
                    tag_ids,
                )
                tags = cursor.fetchall()

            # 4. Return conversation + its tags
            data = {}
            for key in conversation.keys():
                data[key] = conversation[key]
            if tags is not None:
                tag_string = ""
                for tag in tags:
                    tag_string = tag_string + f"{tag['name']}, "
                data["tags"] = tag_string

            if data["content"] == None:
                data["content"] = ""
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

    def list_chat_ids(self):
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT id, title FROM conversations")
            rows = cursor.fetchall()
            ids = [{"id": row[0], "title": row[1]} for row in rows]
            return ids

    def get_chat_title(self, chat_id) -> str | None:
        with self.connect() as connection:
            cursor = connection.cursor()

            cursor.execute("SELECT title FROM conversations WHERE id = (?)", (chat_id,))
            title = cursor.fetchone()[0]
            return title

    def delete_all_chats(self):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations")

    def delete_chat(self, conversation_id):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = (?)", (conversation_id,))
