from pyVinted import Vinted
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse, parse_qs
import time

logger = logging.getLogger(__name__)

class VintedClient:
    def __init__(self, config_manager=None):
        self.vinted = Vinted()
        self.last_check_times = {}  # Track last check time for each URL
        self.config_manager = config_manager
    
    def search_items(self, url: str, max_items: int = 10) -> List[Any]:
        """Search for items using a Vinted URL."""
        # Use pyVinted items.search method directly with URL
        items = self.vinted.items.search(url, max_items, 1)
        
        logger.info(f"Found {len(items)} items for URL: {url}")
        return items
    
    def get_new_items(self, url: str, chat_id: int, max_items: int = 10) -> List[Any]:
        """Get new items since last check for a specific URL."""
        items = self.search_items(url, max_items)
        
        if not self.config_manager:
            logger.warning("No config manager provided, returning all items as new")
            return items
        
        # Get seen items for this chat
        seen_items = set(self.config_manager.get_seen_items(chat_id))
        
        # Filter items by ID to avoid duplicates
        new_items = []
        for item in items:
            if str(item.id) not in seen_items:
                new_items.append(item)
                # Mark as seen with URL tracking
                self.config_manager.add_seen_item(chat_id, str(item.id), url)
        
        logger.info(f"Found {len(new_items)} new items for URL: {url}")
        return new_items
    
    def format_item_message(self, item: Any, search_url: str = "") -> str:
        """Format an item for Telegram message."""
        try:
            title = item.title
            price = item.price
            currency = item.currency
            url = item.url
            photo_url = item.photo
            brand = getattr(item, 'brand_title', 'Unknown brand')
            
            message = f"🛍️ *{title}*\n"
            message += f"🏷️ Brand: {brand}\n"
            message += f"💰 Price: {price} {currency}\n"
            
            if url:
                message += f"🔗 [View on Vinted]({url})\n"
            
            if photo_url:
                message += f"📸 [Photo]({photo_url})\n"
            
            if search_url:
                message += f"🔍 [Search URL]({search_url})\n"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting item message: {e}")
            return f"Error formatting item: {str(item)[:100]}..."
    
    def validate_url(self, url: str) -> bool:
        """Validate if a URL is a valid Vinted search URL."""
        try:
            parsed = urlparse(url)
            return 'vinted' in parsed.netloc.lower()
        except Exception:
            return False 