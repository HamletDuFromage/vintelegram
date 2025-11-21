import lbc
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urlparse, unquote
import time

logger = logging.getLogger(__name__)

class LeBonCoinClient:
    def __init__(self, config_manager=None):
        self.lbc = lbc.Client()
        self.last_check_times = {}  # Track last check time for each URL
        self.config_manager = config_manager

    def refresh_session(self):
        pass

    def randomize_user_agent(self):
        pass
    
    def search_items(self, url: str, max_items: int = 10) -> List[Any]:
        """Search for items using a LeBonCoin URL."""
        url = unquote(url)
        items = self.lbc.search(url, limit=max_items, page=1)
        
        logger.info(f"Found {len(items.ads)} items for URL: {url}")
        res = [
            item for item in items.ads
            if not any(
                attr.key == "transaction_status" and (attr.value == "pending" or attr.value == "sold")
                for attr in item.attributes
            )
        ]
        return res
    
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
        """Format a Leboncoin item for Telegram message."""
        try:
            title = getattr(item, "subject", "No title")
            price = getattr(item, "price", "N/A")
            currency = getattr(item, "currency", "")
            url = getattr(item, "url", "")
            images = getattr(item, "images", [])
            brand = getattr(item, "brand", "Unknown brand")

            # Take first image if exists
            photo_url = images[0] if images else None

            message = f"🛍️ *{title}*\n"
            message += f"🏷️ Brand: {brand}\n"
            message += f"💰 Price: {price} {currency}\n"

            if url:
                message += f"🔗 [View on Leboncoin]({url})\n"

            if photo_url:
                message += f"📸 [Photo]({photo_url})\n"

            if search_url:
                message += f"🔍 [Search URL]({search_url})\n"

            return message

        except Exception as e:
            logger.error(f"Error formatting item message: {e}")
            return f"Error formatting item: {str(item)[:100]}..."
    
    def validate_url(self, url: str) -> bool:
        """Validate if a URL is a valid LeBonCoin search URL."""
        try:
            parsed = urlparse(url)
            return 'leboncoin' in parsed.netloc.lower()
        except Exception:
            return False
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = LeBonCoinClient()
    test_url = "https://www.leboncoin.fr/recherche?text=La+Pavoni"  # replace with a valid LeBonCoin URL

    if client.validate_url(test_url):
        items = client.search_items(test_url, max_items=5)
        print(f"Found {len(items)} items.")
        for item in items:
            print(item)
            print(client.format_item_message(item, search_url=test_url))
    else:
        print("Invalid LeBonCoin URL")