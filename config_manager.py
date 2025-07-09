import yaml
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
        self._ensure_config_structure()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as file:
                    loaded_config = yaml.safe_load(file)
                    if loaded_config is None:
                        return self._get_default_config()
                    return loaded_config
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure."""
        return {
            'bot': {
                'token': '',
                'admin_users': []
            },
            'chats': {},
            'settings': {
                'check_interval': 300,
                'max_items_per_check': 10,
                'default_language': 'en'
            }
        }
    
    def _ensure_config_structure(self):
        """Ensure the config has the proper structure."""
        if self.config is None:
            self.config = self._get_default_config()
        elif 'chats' not in self.config or self.config['chats'] is None:
            self.config['chats'] = {}
        if 'bot' not in self.config:
            self.config['bot'] = {'token': '', 'admin_users': []}
        if 'settings' not in self.config:
            self.config['settings'] = {
                'check_interval': 300,
                'max_items_per_check': 10,
                'default_language': 'en'
            }
    
    def _save_config(self):
        """Save configuration to YAML file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as file:
                yaml.dump(self.config, file, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
    
    def get_bot_token(self) -> str:
        """Get bot token from environment or config."""
        return os.getenv('TELEGRAM_BOT_TOKEN') or self.config.get('bot', {}).get('token', '')
    
    def get_admin_users(self) -> List[int]:
        """Get list of admin user IDs."""
        return self.config.get('bot', {}).get('admin_users', [])
    
    def get_chat_config(self, chat_id: int) -> Dict[str, Any]:
        """Get configuration for a specific chat."""
        chat_id_str = str(chat_id)
        return self.config.get('chats', {}).get(chat_id_str, {})
    
    def add_chat(self, chat_id: int, name: str = ""):
        """Add a new chat to the configuration."""
        chat_id_str = str(chat_id)
        logger.info(f"Adding chat: {chat_id} ({name})")
        
        if chat_id_str not in self.config['chats']:
            self.config['chats'][chat_id_str] = {
                'name': name,
                'search_urls': [],
                'notifications': True,
                'max_price': None,
                'min_price': None,
                'created_at': datetime.now().isoformat(),
                'seen_item_ids': []
            }
            self._save_config()
            logger.info(f"Added new chat: {chat_id} ({name})")
        else:
            logger.info(f"Chat {chat_id} already exists")
    
    def add_search_url(self, chat_id: int, url: str) -> bool:
        """Add a search URL for a chat."""
        chat_id_str = str(chat_id)
        if 'chats' not in self.config:
            self.config['chats'] = {}
        if chat_id_str not in self.config['chats']:
            self.add_chat(chat_id)
        
        chat_config = self.config['chats'][chat_id_str]
        if 'search_urls' not in chat_config:
            chat_config['search_urls'] = []
        
        if url not in chat_config['search_urls']:
            chat_config['search_urls'].append(url)
            self._save_config()
            logger.info(f"Added search URL for chat {chat_id}: {url}")
            return True
        return False
    
    def remove_search_url(self, chat_id: int, url: str) -> bool:
        """Remove a search URL for a chat."""
        chat_id_str = str(chat_id)
        if 'chats' not in self.config or chat_id_str not in self.config['chats']:
            return False
        chat_config = self.config['chats'][chat_id_str]
        search_urls = chat_config.get('search_urls', [])
        
        if url in search_urls:
            search_urls.remove(url)
            
            # Clear seen items for this URL
            self.clear_seen_items_for_url(chat_id, url)
            
            self._save_config()
            logger.info(f"Removed search URL for chat {chat_id}: {url}")
            return True
        return False
    
    def get_search_urls(self, chat_id: int) -> List[str]:
        """Get all search URLs for a chat."""
        chat_config = self.get_chat_config(chat_id)
        return chat_config.get('search_urls', [])
    
    def get_all_chats(self) -> Dict[str, Dict[str, Any]]:
        """Get all chats configuration."""
        return self.config.get('chats', {})
    
    def update_chat_settings(self, chat_id: int, **kwargs):
        """Update chat settings."""
        chat_id_str = str(chat_id)
        if 'chats' not in self.config:
            self.config['chats'] = {}
        if chat_id_str not in self.config['chats']:
            self.add_chat(chat_id)
        
        chat_config = self.config['chats'][chat_id_str]
        for key, value in kwargs.items():
            chat_config[key] = value
        
        self._save_config()
        logger.info(f"Updated settings for chat {chat_id}: {kwargs}")
    
    def get_bot_settings(self) -> Dict[str, Any]:
        """Get bot settings."""
        return self.config.get('settings', {})
    
    def get_seen_items(self, chat_id: int) -> List[str]:
        """Get seen item IDs for a chat."""
        chat_config = self.get_chat_config(chat_id)
        return chat_config.get('seen_item_ids', [])
    
    def add_seen_item(self, chat_id: int, item_id: str, url: str = None):
        """Add an item ID to the seen items for a chat."""
        chat_id_str = str(chat_id)
        if 'chats' not in self.config:
            self.config['chats'] = {}
        if chat_id_str not in self.config['chats']:
            self.add_chat(chat_id)
        
        chat_config = self.config['chats'][chat_id_str]
        if 'seen_item_ids' not in chat_config:
            chat_config['seen_item_ids'] = []
        if 'seen_items_by_url' not in chat_config:
            chat_config['seen_items_by_url'] = {}
        
        # Add to general seen items
        if item_id not in chat_config['seen_item_ids']:
            chat_config['seen_item_ids'].append(item_id)
        
        # Add to URL-specific seen items
        if url:
            if url not in chat_config['seen_items_by_url']:
                chat_config['seen_items_by_url'][url] = []
            if item_id not in chat_config['seen_items_by_url'][url]:
                chat_config['seen_items_by_url'][url].append(item_id)
        
        self._save_config()
        logger.info(f"Added seen item {item_id} for chat {chat_id}")
    
    def clear_seen_items_for_url(self, chat_id: int, url: str):
        """Clear seen items for a specific URL."""
        chat_id_str = str(chat_id)
        if 'chats' not in self.config or chat_id_str not in self.config['chats']:
            return
        
        chat_config = self.config['chats'][chat_id_str]
        if 'seen_items_by_url' in chat_config and url in chat_config['seen_items_by_url']:
            removed_items = chat_config['seen_items_by_url'].pop(url)
            self._save_config()
            logger.info(f"Cleared {len(removed_items)} seen items for URL {url} in chat {chat_id}") 