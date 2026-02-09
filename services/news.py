import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class NewsService:
    # Parity: These match the NewsArticle interface in newsApiService.ts
    MOCK_NEWS_DATA = [
        {
            "title": "AI Revolution: ChatGPT Reaches 100 Million Users",
            "description": "OpenAI's ChatGPT has achieved a remarkable milestone by reaching 100 million active users.",
            "content": "OpenAI's ChatGPT has achieved a remarkable milestone by reaching 100 million active users, making it the fastest-growing consumer application in history.",
            "url": "https://example.com/ai-revolution",
            "image": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=400",
            "publishedAt": (datetime.utcnow() - timedelta(hours=2)).isoformat() + "Z",
            "source": "TechCrunch",
            "category": "technology"
        },
        {
            "title": "Climate Summit 2024: World Leaders Commit to Net Zero",
            "description": "At the global climate summit, world leaders have pledged ambitious new targets.",
            "content": "At the global climate summit, world leaders have pledged ambitious new targets to achieve net-zero emissions by 2050.",
            "url": "https://example.com/climate-summit",
            "image": "https://images.unsplash.com/photo-1569163139394-de4798aa62b6?w=400",
            "publishedAt": (datetime.utcnow() - timedelta(hours=5)).isoformat() + "Z",
            "source": "BBC News",
            "category": "general"
        }
    ]

    @classmethod
    async def fetch_news_data_io(cls, category: str, country: str = 'us', api_key: str = None) -> List[Dict[str, Any]]:
        if not api_key:
            raise ValueError("NewsData.io requires an API key.")
            
        url = f"https://newsdata.io/api/1/news?apikey={api_key}&category={category}&country={country}&language=en"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30.0)
                data = resp.json()
                
                if data.get("status") != 'success':
                    # Parity: Match error handling from newsApiService.ts
                    error_msg = data.get("results", {}).get("message") if isinstance(data.get("results"), dict) else "NewsData.io API error"
                    raise Exception(error_msg)
                
                results = data.get("results", [])
                return [
                    {
                        "title": item.get("title") or '',
                        "description": item.get("description") or '',
                        "content": item.get("content") or item.get("description") or '',
                        "url": item.get("link") or '',
                        "image": item.get("image_url") or '',
                        "publishedAt": item.get("pubDate") or datetime.utcnow().isoformat() + "Z",
                        "source": item.get("source_id") or 'NewsData',
                        "category": category
                    } for item in results
                ]
        except Exception as e:
            print(f"[NewsData.io] Error: {e}")
            raise e

    @classmethod
    async def fetch_gnews(cls, category: str, country: str = 'us', api_key: str = None) -> List[Dict[str, Any]]:
        if not api_key:
            raise ValueError("GNews requires an API key.")
            
        url = f"https://gnews.io/api/v4/top-headlines?category={category}&country={country}&apikey={api_key}&max=20"
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30.0)
                data = resp.json()
                
                if data.get("errors"):
                    raise Exception(data["errors"][0] or "GNews API error")
                
                articles = data.get("articles", [])
                return [
                    {
                        "title": item.get("title") or '',
                        "description": item.get("description") or '',
                        "content": item.get("content") or item.get("description") or '',
                        "url": item.get("url") or '',
                        "image": item.get("image") or '',
                        "publishedAt": item.get("publishedAt") or datetime.utcnow().isoformat() + "Z",
                        "source": item.get("source", {}).get("name") if isinstance(item.get("source"), dict) else 'GNews',
                        "category": category
                    } for item in articles
                ]
        except Exception as e:
            print(f"[GNews] Error: {e}")
            raise e

    # Maintain existing methods for backward compatibility but use refined mapping
    @classmethod
    async def fetch_trends(cls, api_key: str) -> List[Dict[str, Any]]:
        try:
            return await cls.fetch_news_data_io(category="top", country="us", api_key=api_key)
        except Exception:
            return cls.MOCK_NEWS_DATA
