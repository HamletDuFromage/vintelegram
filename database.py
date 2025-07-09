import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/vinted_bot.db"):
        self.db_path = db_path
        # Ensure the directory exists
        import os
        db_dir = os.path.dirname(self.db_path)
        if db_dir and db_dir != "":  # Only create directory if there is a directory path
            os.makedirs(db_dir, exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create chats table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS chats (
                        chat_id INTEGER PRIMARY KEY,
                        name TEXT,
                        paused BOOLEAN DEFAULT 0,
                        max_price REAL,
                        min_price REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create search_urls table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        url TEXT NOT NULL,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (chat_id) REFERENCES chats (chat_id),
                        UNIQUE(chat_id, url)
                    )
                ''')
                
                # Create seen_items table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS seen_items (
                        chat_id INTEGER,
                        url TEXT,
                        item_id TEXT,
                        seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (chat_id, url, item_id),
                        FOREIGN KEY (chat_id) REFERENCES chats (chat_id)
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_seen_items_chat_url ON seen_items (chat_id, url)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_seen_items_item_id ON seen_items (item_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_urls_chat ON search_urls (chat_id)')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def add_chat(self, chat_id: int, name: str = "") -> bool:
        """Add a new chat to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO chats (chat_id, name)
                    VALUES (?, ?)
                ''', (chat_id, name))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Added new chat: {chat_id} ({name})")
                    return True
                else:
                    logger.info(f"Chat {chat_id} already exists")
                    return False
                    
        except Exception as e:
            logger.error(f"Error adding chat {chat_id}: {e}")
            return False
    
    def add_search_url(self, chat_id: int, url: str) -> bool:
        """Add a search URL for a chat."""
        try:
            # Ensure chat exists
            self.add_chat(chat_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO search_urls (chat_id, url)
                    VALUES (?, ?)
                ''', (chat_id, url))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Added search URL for chat {chat_id}: {url}")
                    return True
                else:
                    logger.info(f"URL already exists for chat {chat_id}: {url}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error adding search URL: {e}")
            return False
    
    def remove_search_url(self, chat_id: int, url: str) -> bool:
        """Remove a search URL and its seen items for a chat."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove seen items for this URL
                cursor.execute('''
                    DELETE FROM seen_items 
                    WHERE chat_id = ? AND url = ?
                ''', (chat_id, url))
                seen_items_removed = cursor.rowcount
                
                # Remove the search URL
                cursor.execute('''
                    DELETE FROM search_urls 
                    WHERE chat_id = ? AND url = ?
                ''', (chat_id, url))
                url_removed = cursor.rowcount
                
                conn.commit()
                
                if url_removed > 0:
                    logger.info(f"Removed search URL for chat {chat_id}: {url} (cleared {seen_items_removed} seen items)")
                    return True
                else:
                    logger.info(f"URL not found for chat {chat_id}: {url}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing search URL: {e}")
            return False
    
    def get_search_urls(self, chat_id: int) -> List[str]:
        """Get all search URLs for a chat."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT url FROM search_urls 
                    WHERE chat_id = ?
                    ORDER BY added_at
                ''', (chat_id,))
                
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting search URLs: {e}")
            return []
    
    def get_all_chats(self) -> Dict[int, Dict[str, Any]]:
        """Get all chats with their configurations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.chat_id, c.name, c.paused, c.max_price, c.min_price,
                           COUNT(s.url) as url_count
                    FROM chats c
                    LEFT JOIN search_urls s ON c.chat_id = s.chat_id
                    GROUP BY c.chat_id
                ''')
                
                chats = {}
                for row in cursor.fetchall():
                    chat_id, name, paused, max_price, min_price, url_count = row
                    chats[chat_id] = {
                        'name': name,
                        'paused': bool(paused),
                        'max_price': max_price,
                        'min_price': min_price,
                        'search_urls': self.get_search_urls(chat_id),
                        'url_count': url_count
                    }
                
                return chats
                
        except Exception as e:
            logger.error(f"Error getting all chats: {e}")
            return {}
    
    def add_seen_item(self, chat_id: int, item_id: str, url: str) -> bool:
        """Add an item ID to the seen items for a chat and URL."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO seen_items (chat_id, url, item_id)
                    VALUES (?, ?, ?)
                ''', (chat_id, url, item_id))
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.debug(f"Added seen item {item_id} for chat {chat_id}, URL {url}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error adding seen item: {e}")
            return False
    
    def get_seen_items(self, chat_id: int, url: str = "") -> List[str]:
        """Get seen item IDs for a chat (optionally filtered by URL)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if url:
                    cursor.execute('''
                        SELECT item_id FROM seen_items 
                        WHERE chat_id = ? AND url = ?
                    ''', (chat_id, url))
                else:
                    cursor.execute('''
                        SELECT item_id FROM seen_items 
                        WHERE chat_id = ?
                    ''', (chat_id,))
                
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting seen items: {e}")
            return []
    
    def update_chat_settings(self, chat_id: int, **kwargs) -> bool:
        """Update chat settings."""
        try:
            # Ensure chat exists
            self.add_chat(chat_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query dynamically
                valid_fields = ['name', 'paused', 'max_price', 'min_price']
                updates = []
                values = []
                
                for key, value in kwargs.items():
                    if key in valid_fields:
                        updates.append(f"{key} = ?")
                        values.append(value)
                
                if updates:
                    values.append(chat_id)
                    query = f"UPDATE chats SET {', '.join(updates)} WHERE chat_id = ?"
                    cursor.execute(query, values)
                    conn.commit()
                    
                    logger.info(f"Updated settings for chat {chat_id}: {kwargs}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error updating chat settings: {e}")
            return False
    
    def cleanup_old_seen_items(self, days_old: int = 30) -> int:
        """Clean up seen items older than specified days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM seen_items 
                    WHERE seen_at < datetime('now', '-{} days')
                '''.format(days_old))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old seen items (older than {days_old} days)")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old seen items: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get counts
                cursor.execute('SELECT COUNT(*) FROM chats')
                chat_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM search_urls')
                url_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM seen_items')
                seen_items_count = cursor.fetchone()[0]
                
                return {
                    'chats': chat_count,
                    'search_urls': url_count,
                    'seen_items': seen_items_count
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'chats': 0, 'search_urls': 0, 'seen_items': 0} 