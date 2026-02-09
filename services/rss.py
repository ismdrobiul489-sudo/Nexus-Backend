import feedparser
import httpx
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Optional, Dict
from pydantic import BaseModel

class RSSItem(BaseModel):
    title: str
    link: str
    pubDate: str
    description: str
    author: Optional[str] = None
    image: Optional[str] = None
    guid: Optional[str] = None

class NewsItem(BaseModel):
    name: str
    url: str
    description: str
    datePublished: str
    provider: List[Dict[str, str]]
    image: Optional[Dict[str, str]] = None

class RSSService:
    
    @staticmethod
    def fetch_feed(url: str) -> List[RSSItem]:
        import re
        print(f"[RSS] Fetching: {url}")
        feed = feedparser.parse(url)
        
        if feed.bozo:
            print(f"[RSS] Warning: {feed.bozo_exception}")
            
        items = []
        for entry in feed.entries:
            # Extract Image (Parity with rssService.ts logic)
            image = None
            
            # 1. Check media tags
            if 'media_content' in entry:
                image = entry.media_content[0]['url']
            elif 'media_thumbnail' in entry:
                image = entry.media_thumbnail[0]['url']
            elif 'links' in entry:
                for link in entry.links:
                    if link.get('type', '').startswith('image/'):
                        image = link['href']
                        break
            
            # 2. Regex fallback (Parity with item.content?.match(/<img[^>]+src="([^">]+)"/))
            if not image:
                content = entry.get('summary', '') or entry.get('description', '') or entry.get('content', [{}])[0].get('value', '')
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    image = img_match.group(1)
            
            # Extract and normalize Date
            pub_date = entry.get('published', entry.get('updated', datetime.now().isoformat()))
            
            # Create Normalized Item
            item = RSSItem(
                title=entry.get('title', 'No Title'),
                link=entry.get('link', ''),
                pubDate=pub_date,
                description=entry.get('summary', entry.get('description', '')),
                author=entry.get('author'),
                image=image,
                guid=entry.get('id', entry.get('link'))
            )
            items.append(item)
            
        return items

    @staticmethod
    async def fetch_news_trends(api_key: str = 'pub_0d3e0eab5e0947f6bd45440a8c615d35') -> List[NewsItem]:
        print("[News] Fetching trends from NewsData.io")
        url = "https://newsdata.io/api/1/latest"
        params = {
            "apikey": api_key,
            "language": "en",
            "country": "gb,us,cn",
            "category": "breaking,technology,science",
            "removeduplicate": "1"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                data = response.json()
                
                if data.get("status") != "success":
                    print(f"[News] Error: {data.get('status')}")
                    return []
                    
                results = []
                for article in data.get("results", []):
                    # Map to BingNewsArticle format which UI expects
                    image_obj = None
                    if article.get("image_url"):
                        image_obj = {"thumbnail": {"contentUrl": article["image_url"]}}
                        
                    results.append(NewsItem(
                        name=article["title"],
                        url=article["link"],
                        description=article.get("description") or "",
                        datePublished=article.get("pubDate", ""),
                        provider=[{"name": article.get("source_id", "NewsData")}],
                        image=image_obj
                    ))
                return results
            except Exception as e:
                print(f"[News] Fetch Error: {e}")
                return []
