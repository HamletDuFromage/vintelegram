import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from database import Database

logger = logging.getLogger(__name__)

class DBConfigManager:
    def __init__(self, db_path: str = "data/vinted_bot.db"):
        self.db = Database(db_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables and defaults."""
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        return {
            'bot': {
                'token': '',
                'admin_users': []
            },
            'settings': {
                'check_interval': int(os.getenv('CHECK_INTERVAL', 300)),
                'max_items_per_check': int(os.getenv('MAX_ITEMS_PER_CHECK', 10)),
                'default_language': os.getenv('DEFAULT_LANGUAGE', 'en')
            }
        }
    

    
    def get_bot_token(self) -> str:
        """Get bot token from environment or config."""
        return os.getenv('TELEGRAM_BOT_TOKEN') or self.config.get('bot', {}).get('token', '')
    
    def get_admin_users(self) -> List[int]:
        """Get list of admin user IDs."""
        return self.config.get('bot', {}).get('admin_users', [])
    
    def get_chat_config(self, chat_id: int) -> Dict[str, Any]:
        """Get configuration for a specific chat."""
        all_chats = self.db.get_all_chats()
        # Ensure chat_id is an integer for proper dictionary lookup
        chat_id = int(chat_id)
        return all_chats.get(chat_id, {})
    
    def add_chat(self, chat_id: int, name: str = ""):
        """Add a new chat to the database."""
        return self.db.add_chat(chat_id, name)
    
    def add_search_url(self, chat_id: int, url: str) -> bool:
        """Add a search URL for a chat."""
        # Ensure chat_id is an integer
        chat_id = int(chat_id)
        result = self.db.add_search_url(chat_id, url)
        logger.info(f"Adding URL for chat {chat_id}: {url} - Result: {result}")
        return result
    
    def remove_search_url(self, chat_id: int, url: str) -> bool:
        """Remove a search URL for a chat."""
        return self.db.remove_search_url(chat_id, url)
    
    def get_search_urls(self, chat_id: int) -> List[str]:
        """Get all search URLs for a chat."""
        # Ensure chat_id is an integer
        chat_id = int(chat_id)
        urls = self.db.get_search_urls(chat_id)
        logger.info(f"Retrieved {len(urls)} URLs for chat {chat_id}: {urls}")
        return urls
    
    def get_all_chats(self) -> Dict[int, Dict[str, Any]]:
        """Get all chats configuration."""
        return self.db.get_all_chats()
    
    def update_chat_settings(self, chat_id: int, **kwargs):
        """Update chat settings."""
        return self.db.update_chat_settings(chat_id, **kwargs)
    
    def get_bot_settings(self) -> Dict[str, Any]:
        """Get bot settings."""
        return self.config.get('settings', {})
    
    def get_seen_items(self, chat_id: int) -> List[str]:
        """Get seen item IDs for a chat."""
        return self.db.get_seen_items(chat_id)
    
    def add_seen_item(self, chat_id: int, item_id: str, url: str = ""):
        """Add an item ID to the seen items for a chat."""
        if url:
            return self.db.add_seen_item(chat_id, item_id, url)
        else:
            # Fallback for backward compatibility
            return self.db.add_seen_item(chat_id, item_id, "unknown")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self.db.get_stats()
    
    def cleanup_old_seen_items(self, days_old: int = 30) -> int:
        """Clean up seen items older than specified days."""
        return self.db.cleanup_old_seen_items(days_old) 