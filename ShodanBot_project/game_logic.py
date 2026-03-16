import aiohttp
import asyncio
import json
import urllib.parse
from datetime import datetime
from groq import AsyncGroq  # ВАЖНО: Используем AsyncGroq



async def enhance_query_with_ai(query, groq_client):
    current_date = datetime.now().strftime("%B %Y")
    
    prompt = (
        f"Current Date: {current_date}. You are a gaming catalog expert. "
        f"User query: '{query}'. "
        f"RULES: "
        f"1. If the query contains ANY specific identifier, return type 'exact'. "
        f"2. If the query is JUST a franchise name, return type 'ambiguous' with up to 15 specific games. "
        f"3. CRITICAL: For 'ambiguous', you MUST actively include highly anticipated UPCOMING games or officially announced sequels. "
        # ТЕПЕРЬ ПРОСИМ СТАВИТЬ 3000 ГОД ДЛЯ АНОНСОВ
        f"4. Output a list of OBJECTS containing 'name' and 'year'. For unreleased or upcoming games, ALWAYS assign year 3000. " 
        f"5. Translate the query to English. "
        f"OUTPUT FORMAT (JSON ONLY): \n"
        f"{{\"type\": \"exact\", \"name\": \"Exact English Game Name\"}} OR "
        f"{{\"type\": \"ambiguous\", \"options\": [{{\"name\": \"Upcoming Game\", \"year\": 3000}}, {{\"name\": \"Older Game\", \"year\": 2023}}]}}"
    )
    
    try:
        response = await groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={ "type": "json_object" }
        )
        data = json.loads(response.choices[0].message.content)
        
        # --- ЖЕЛЕЗНАЯ СОРТИРОВКА В PYTHON ---
        if data.get("type") == "ambiguous":
            raw_options = data.get("options", [])
            
            # Проверяем, что ИИ послушался и выдал словари с годами
            if raw_options and isinstance(raw_options[0], dict):
                # Сортируем список по ключу 'year' по убыванию (от новых к старым)
                raw_options.sort(key=lambda x: isinstance(x.get("year"), int) and x.get("year") or 0, reverse=True)
                
                # Перезаписываем options, оставляя только чистые названия для кнопок
                data["options"] = [opt.get("name") for opt in raw_options if opt.get("name")]
                
        return data
        
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return {"type": "exact", "name": query}

async def search_steam_game(query, original_query=None):
    async with aiohttp.ClientSession() as session:
        async def fetch(q):
            safe_q = urllib.parse.quote(q)
            url = f"https://store.steampowered.com/api/storesearch/?term={safe_q}&l=english&cc=us"
            try:
                async with session.get(url, timeout=5) as r:
                    data = await r.json()
                    if data.get('total', 0) > 0:
                        top = data['items'][0]
                        return {"appid": str(top['id']), "name": top['name']}
            except: pass
            return None

        result = await fetch(query)
        if not result and original_query and query != original_query:
            result = await fetch(original_query)
        return result

async def get_main_info(appid, game_name):
    results = {
        "price_ru": "Н/Д", "price_kz": "Н/Д", "price_ua": "Н/Д",
        "online": 0, "reviews": "Нет данных",
        "release_date": "Неизвестно",
        "image": None,
        "early_access": False
    }

    async with aiohttp.ClientSession() as session:
        async def fetch_details(cc, key):
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l=russian"
            try:
                async with session.get(url, timeout=5) as r:
                    data = await r.json()
                    if data and data.get(appid, {}).get('success'):
                        info = data[appid]['data']
                        if 'price_overview' in info:
                            results[key] = info['price_overview'].get('final_formatted', "Н/Д")
                        elif info.get('is_free'):
                            results[key] = "Бесплатно"
                        
                        if results["release_date"] == "Неизвестно" and 'release_date' in info:
                            results["release_date"] = info['release_date'].get('date', 'Неизвестно')
                        if not results["image"] and 'header_image' in info:
                            results["image"] = info['header_image']
                            
                        if 'genres' in info:
                            if any(g.get('id') == '70' for g in info['genres']):
                                results['early_access'] = True
            except: pass
        async def fetch_online():
            url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
            try:
                async with session.get(url, timeout=5) as r:
                    data = await r.json()
                    results["online"] = data.get('response', {}).get('player_count', 0)
            except: pass

        async def fetch_reviews():
            url = f"https://store.steampowered.com/appreviews/{appid}?json=1&language=russian"
            try:
                async with session.get(url, timeout=5) as r:
                    data = await r.json()
                    if data and 'query_summary' in data:
                        summary = data['query_summary']
                        if summary.get('total_reviews', 0) > 0:
                            percent = int((summary['total_positive'] / summary['total_reviews']) * 100)
                            results["reviews"] = f"{summary.get('review_score_desc', 'Обзоры')} ({percent}%)"
            except: pass

        await asyncio.gather(
            fetch_details('ru', 'price_ru'),
            fetch_details('kz', 'price_kz'),
            fetch_details('ua', 'price_ua'),
            fetch_online(),
            fetch_reviews()
        )
    return results