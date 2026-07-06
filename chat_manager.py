from typing import List, Dict
from sqlalchemy import create_engine, text

class ChatDatabase:
    def __init__(self, mysql_db_url: str):
        self.engine = create_engine(mysql_db_url)

    def get_history(self, user_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Fetches the recent conversation history directly from Laravel's database."""
        with self.engine.connect() as conn:
            # We use a subquery to get the last N records, then sort chronologically
            query = text("""
                SELECT sender as role, message as content 
                FROM (
                    SELECT sender, message, created_at 
                    FROM chat_messages 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC 
                    LIMIT :limit
                ) sub
                ORDER BY created_at ASC
            """)
            rows = conn.execute(query, {"user_id": user_id, "limit": limit}).mappings().fetchall()
            
            # Map Laravel's 'bot' to LangChain's 'ai'
            history = []
            for row in rows:
                role = "ai" if row["role"] == "bot" else "user"
                history.append({"role": role, "content": row["content"]})
                
            return history