from pyVinted import Vinted
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from pyVinted.requester import requester
import requests
import ua_generator
from dataclasses import dataclass
import argparse

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.pop("timeout", 10)
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return super().send(request, **kwargs)

class VintedClient:
    @dataclass
    class Item:
        title: str
        price: Any
        currency: str
        url: str
        photo_url: str
        brand: str
        created_at: datetime
        id: str
        search_url: str = ""

        @classmethod
        def from_raw(cls, item: Any, search_url: str = ""):
            """Create an Item from a raw object or dict."""
            try:
                if isinstance(item, dict):
                    price_info = item.get("price")
                    if isinstance(price_info, dict):
                        price = price_info.get("amount")
                        currency = price_info.get("currency_code", "EUR")
                    else:
                        price = price_info
                        currency = item.get("currency", "EUR")

                    photo_info = item.get("photo")
                    photo_url = photo_info.get("url", "") if isinstance(photo_info, dict) else (photo_info or "")

                    url = item.get("url", "")
                    if url and url.startswith("/"):
                        url = f"https://www.vinted.fr{url}"

                    brand = (
                        item.get("brand_title")
                        or (item.get("item_box") or {}).get("first_line")
                        or (item.get("brand_dto") or {}).get("title")
                        or "Unknown brand"
                    )

                    return cls(
                        title=item.get("title", ""),
                        price=price,
                        currency=currency,
                        url=url,
                        photo_url=photo_url,
                        brand=brand,
                        created_at=datetime.now(timezone.utc),
                        id=str(item.get("id", "")),
                        search_url=search_url,
                    )

                return cls(
                    title=getattr(item, "title", ""),
                    price=getattr(item, "price", None),
                    currency=getattr(item, "currency", "EUR"),
                    url=getattr(item, "url", ""),
                    photo_url=getattr(item, "photo", ""),
                    brand=getattr(item, "brand_title", "Unknown brand"),
                    created_at=getattr(item, "created_at_ts", datetime.now(timezone.utc)),
                    id=str(getattr(item, "id", "")),
                    search_url=search_url,
                )
            except Exception as e:
                logger.error(f"Error creating Item: {e}")
                fallback_id = str(item.get("id", "")) if isinstance(item, dict) else str(getattr(item, "id", ""))
                return cls(
                    title="",
                    price=None,
                    currency="",
                    url="",
                    photo_url="",
                    brand="Unknown brand",
                    created_at=datetime.min,
                    id=fallback_id,
                    search_url=search_url,
                )

    def __init__(self, config_manager=None, randomize_ua: bool = False):
        self.vinted = Vinted()
        self._setup_session()
        self.last_check_times = {}  # Track last check time for each URL
        self.failed_attempts = 0
        self.config_manager = config_manager
        self.randomize_ua = randomize_ua

    def _setup_session(self):
        """Setup requester session with timeouts."""
        # requester.session is a global session in pyVinted
        # Ensure it has the timeout adapter
        adapter = TimeoutHTTPAdapter(timeout=10)
        requester.session.mount("https://", adapter)
        requester.session.mount("http://", adapter)

    def refresh_session(self):
        self.vinted = Vinted()
        self._setup_session()

    def randomize_user_agent(self):
        requester.session = requests.Session()
        self._setup_session()
        requester.HEADER["User-Agent"] = ua_generator.generate(device='desktop', platform='windows').text
        requester.session.headers.update(requester.HEADER)

    def set_proxy(self, proxy: Dict[str, str]) -> None:
        requester.session.proxies = proxy
        #ip = requester.session.get("https://api.ipify.org", timeout=10).text
        logger.info(f"Switched to new proxy: {proxy}")
        #return ip

    def search_items(self, url: str, max_items: int = 10) -> List[Any]:
        """Search for items using a Vinted URL."""
        self.failed_attempts += 1
        if self.randomize_ua:
            self.randomize_user_agent()
        res = self.vinted.items.search(url, max_items, 1)
        items = [VintedClient.Item.from_raw(item, search_url=url) for item in res]

        self.failed_attempts = 0
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
        now = datetime.now(timezone.utc)
        new_items = []
        for item in items:
            if str(item.id) not in seen_items:
                if now - item.created_at < timedelta(days=7):
                    new_items.append(item)
                # Mark as seen with URL tracking
                self.config_manager.add_seen_item(chat_id, str(item.id), url)
        
        return new_items
    
    def format_item_dict(self, item: Any) -> Dict[str, Any]:
        """Format an item into a dictionary."""
        try:
            item_dict = {
                "title": item.title,
                "price": item.price,
                "currency": item.currency,
                "url": item.url,
                "photo_url": item.photo,
                "brand": getattr(item, 'brand_title', 'Unknown brand'),
                "search_url": item.search_url,
            }
            return item_dict
            
        except Exception as e:
            logger.error(f"Error formatting item dict: {e}")
            return {"error": f"Error formatting item"}

    def format_item_message(self, item: "VintedClient.Item") -> str:
        message = f"🆕 *{item.title}*\n"
        message += f"💰 Price: {item.price} {item.currency}\n"
        message += f"🏷️ Brand: {item.brand}\n"

        if item.url:
            message += f"🔗 [View on Vinted]({item.url})\n"

        if item.photo_url:
            message += f"📸 [Photo]({item.photo_url})\n"

        if item.search_url:
            message += f"🔍 [Search URL]({item.search_url})\n"

        return message

    def validate_url(self, url: str) -> bool:
        """Validate if a URL is a valid Vinted search URL."""
        try:
            parsed = urlparse(url)
            return 'vinted' in parsed.netloc.lower()
        except Exception:
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Vinted Client CLI")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g., http://user:pass@host:port)")
    args = parser.parse_args()

    client = VintedClient()
    
    if args.proxy:
        try:
            client.set_proxy({"https": args.proxy})
        except Exception as e:
            print(f"Error setting proxy: {e}")

    test_url = "https://www.vinted.fr/catalog?search_text=linux" 
    if client.validate_url(test_url):
        items = client.search_items(test_url, max_items=5)
        print(f"Found {len(items)} items.")
        for item in items:
            print(item)
            print(client.format_item_message(item))
    else:
        print("Invalid Vinted URL")