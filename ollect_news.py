#!/usr/bin/env python3
import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
import requests

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "")

COMPANIES = {
    "tesla": ["tesla", "fsd", "autopilot", "elon musk"],
    "waymo": ["waymo"],
    "uber": ["uber autonomous"],
    "zoox": ["zoox"],
    "cruise": ["cruise", "gm cruise"],
    "aurora": ["aurora innovation"],
    "baidu": ["baidu apollo", "apollo go"],
    "pony": ["pony.ai"],
    "weride": ["weride"],
    "toyota": ["toyota autonomous", "woven city"],
    "honda": ["honda autonomous"],
    "nissan": ["nissan propilot"],
    "tier4": ["tier iv", "autoware"],
}

def detect_company(text):
    text_lower = text.lower()
    for company_id, keywords in COMPANIES.items():
        if any(kw in text_lower for kw in keywords):
            return company_id
    return "other"

def calculate_importance(title, desc):
    text = (title + " " + desc).lower()
    if any(kw in text for kw in ["launch", "announce", "official", "first", "approve"]):
        return "high"
    elif any(kw in text for kw in ["update", "plan", "test", "expand"]):
        return "medium"
    return "low"

def extract_tags(title):
    tags = []
    patterns = {
        "FSD": ["fsd"], "Level4": ["level 4"], "Commercial": ["commercial", "launch"],
        "Partnership": ["partnership", "deal"], "China": ["china", "chinese"],
        "Japan": ["japan"], "USA": ["us", "america", "california"]
    }
    title_lower = title.lower()
    for tag, kws in patterns.items():
        if any(k in title_lower for k in kws):
            tags.append(tag)
    return tags[:5]

def generate_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def fetch_newsapi():
    print("Fetching from NewsAPI...")
    articles = []
    keywords = ["autonomous driving", "robotaxi", "self-driving car"]
    
    for kw in keywords:
        try:
            params = {
                "q": kw, "apiKey": NEWS_API_KEY, "language": "en",
                "sortBy": "publishedAt",
                "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                "pageSize": 20
            }
            resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=30)
            data = resp.json()
            
            if data.get("status") == "ok":
                for a in data.get("articles", []):
                    if a.get("title") and a.get("url"):
                        articles.append({
                            "id": generate_id(a["url"]),
                            "title": a["title"],
                            "summary": (a.get("description") or "")[:300],
                            "source": "news",
                            "sourceDetail": a["source"].get("name", "Unknown"),
                            "company": detect_company(a["title"] + " " + (a.get("description") or "")),
                            "url": a["url"],
                            "publishedAt": a.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                            "engagement": {"likes": 0, "comments": 0, "shares": 0},
                            "importance": calculate_importance(a["title"], a.get("description") or ""),
                            "tags": extract_tags(a["title"])
                        })
        except Exception as e:
            print(f"NewsAPI error: {e}")
    
    print(f"NewsAPI: {len(articles)} articles")
    return articles

def fetch_gnews():
    print("Fetching from GNews...")
    articles = []
    
    try:
        params = {
            "q": "autonomous driving OR robotaxi",
            "token": GNEWS_API_KEY, "lang": "en", "max": 30
        }
        resp = requests.get("https://gnews.io/api/v4/search", params=params, timeout=30)
        data = resp.json()
        
        for a in data.get("articles", []):
            if a.get("title") and a.get("url"):
                articles.append({
                    "id": generate_id(a["url"]),
                    "title": a["title"],
                    "summary": (a.get("description") or "")[:300],
                    "source": "news",
                    "sourceDetail": a.get("source", {}).get("name", "Unknown"),
                    "company": detect_company(a["title"] + " " + (a.get("description") or "")),
                    "url": a["url"],
                    "publishedAt": a.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                    "engagement": {"likes": 0, "comments": 0, "shares": 0},
                    "importance": calculate_importance(a["title"], a.get("description") or ""),
                    "tags": extract_tags(a["title"])
                })
    except Exception as e:
        print(f"GNews error: {e}")
    
    print(f"GNews: {len(articles)} articles")
    return articles

def calc_score(item):
    try:
        pub = item.get("publishedAt", "").replace("Z", "+00:00")
        if "+" not in pub[10:] and "-" not in pub[10:]:
            pub += "+00:00"
        hours = (datetime.now(timezone.utc) - datetime.fromisoformat(pub)).total_seconds() / 3600
        time_score = max(0, 100 - hours * 4)
    except:
        time_score = 50
    
    eng = item.get("engagement", {})
    total = eng.get("likes", 0) + eng.get("comments", 0) * 3 + eng.get("shares", 0) * 2
    eng_score = min(100, (total ** 0.5) * 2) if total > 0 else 10
    
    src_weights = {"official": 1.5, "news": 1.0, "x": 0.8, "reddit": 0.7}
    src_score = src_weights.get(item.get("source", "news"), 1.0) * 30
    
    imp_bonus = {"high": 20, "medium": 10, "low": 0}
    bonus = imp_bonus.get(item.get("importance", "low"), 0)
    
    return round(time_score * 0.3 + eng_score * 0.35 + src_score * 0.2 + bonus * 0.15)

def main():
    print(f"=== News Collection: {datetime.now()} ===")
    
    all_news = []
    all_news.extend(fetch_newsapi())
    all_news.extend(fetch_gnews())
    
    print(f"Total: {len(all_news)} articles")
    
    seen = set()
    unique = []
    for item in all_news:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    
    for item in unique:
        item["priorityScore"] = calc_score(item)
    
    unique.sort(key=lambda x: x.get("priorityScore", 0), reverse=True)
    unique = unique[:100]
    
    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "totalCount": len(unique),
        "news": unique
    }
    
    with open("news-data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(unique)} articles to news-data.json")

if __name__ == "__main__":
    main()
```

4. **「Commit changes」** をクリック

---

### 2. requirements.txt を作成

1. **「Add file」→「Create new file」**

2. ファイル名: `requirements.txt`

3. 内容:
```
requests>=2.28.0
