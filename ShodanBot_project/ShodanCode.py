import os
import shutil
import aiohttp
import sys
import random
import asyncio
import requests
import yt_dlp
import urllib.parse
import html
from dotenv import load_dotenv
from game_logic import enhance_query_with_ai,search_steam_game, get_main_info
from moviepy import VideoFileClip
from aiogram.filters import Command
from groq import AsyncGroq
from pydub import AudioSegment
from aiogram import Bot, Dispatcher, types, F 
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TEMP_DIR = "temp files"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

load_dotenv()

# 1. Получаем путь к папке, где лежит ваш скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Принудительно указываем пути для pydub
AudioSegment.converter = os.path.join(BASE_DIR, "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(BASE_DIR, "ffprobe.exe")

# 3. Добавляем папку в системный PATH (чтобы Windows видела экзешники)
os.environ["PATH"] += os.pathsep + BASE_DIR

# Проверка (выведется в терминал при запуске)
if os.path.exists(AudioSegment.converter) and os.path.exists(AudioSegment.ffprobe):
    print(f"✅ FFmpeg и FFprobe найдены в: {BASE_DIR}")
else:
    print(f"❌ ФАЙЛЫ НЕ НАЙДЕНЫ! Убедитесь, что они лежат в: {BASE_DIR}")

# --- НАСТРОЙКИ ---
BOTTOKEN = os.getenv("BOT_TOKEN")
WEATHER_KEY = os.getenv("WEATHER_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
# Список городов для прогноза
CITIES = ["Тбилиси", "Харьков", "Королев","Алматы"]
# ID чата, куда слать 
CHAT_ID = -1003192156630
# -1003192156630 мейн
# -5192279515 TEST
# Путь к папке с картинками
IMAGE_DIR = r"C:\Users\user\Desktop\python.history\ShodanBot_project\picchi"
TRIGGER_DIR =r"C:\Users\user\Desktop\python.history\ShodanBot_project\Trigger_pics"
TRIGGER_WORDS = ["сука","пидор","блять","сын шлюхи","дебил","долбаеб","долбоеб","уебок","хуесос","даун","шлюха"]


bot = Bot(token=BOTTOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

async def on_startup():
    """Очищает временную папку при каждом запуске бота"""
    if os.path.exists(TEMP_DIR):
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path) # Удаляем файл
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path) # Удаляем подпапку
            except Exception as e:
                print(f'Не удалось удалить {file_path}. Причина: {e}')
    print("Временная папка очищена!")

#Нейронка
groq_client = AsyncGroq(api_key=GROQ_KEY)
user_ai_settings = {}
user_search_cache = {} 




def get_weather(city):
    """Получает погоду через OpenWeatherMap API"""
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_KEY}&units=metric&lang=ru"
    res = requests.get(url).json()
    if res.get("main"):
        temp = round(res["main"]["temp"])
        desc = res["weather"][0]["description"].capitalize()
        return f"📍 {city}: {temp}°C, {desc}"
    return f"❌ Не удалось найти погоду для {city}"

async def send_morning_post():
    """Функция, которая будет запускаться каждое утро"""
    # 1. Собираем прогноз
    weather_report = "Доброе утро! ☀️\n\n" + "\n".join([get_weather(c) for c in CITIES])
    
    # 2. Выбираем случайное фото
    photos = [f for f in os.listdir(IMAGE_DIR) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if photos:
        random_photo = os.path.join(IMAGE_DIR, random.choice(photos))
        photo_file = FSInputFile(random_photo)
        
        # 3. Отправляем в Telegram
        await bot.send_photo(chat_id=CHAT_ID, photo=photo_file, caption=weather_report)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=weather_report)

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    file_id = message.voice.file_id
    input_file = os.path.join(TEMP_DIR, f"{file_id}.m4a")
    
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, input_file)
        
        with open(input_file, "rb") as file_obj:
            transcription = await groq_client.audio.transcriptions.create(
                file=(input_file, file_obj.read()),
                model="whisper-large-v3", 
                response_format="text"
            )
        
        if transcription and transcription.strip():
            recognized_text = transcription.strip()
            
            # 1. Экранируем текст, чтобы избежать ошибок, если Whisper распознает символы < или >
            safe_text = html.escape(recognized_text)
            
            # 2. Оборачиваем текст в сворачиваемую цитату
            reply_text = f"🎙 <b>Расшифровка:</b>\n<blockquote expandable>{safe_text}</blockquote>"
            
            # 3. Отправляем с parse_mode="HTML"
            await message.reply(reply_text, parse_mode="HTML")
            
        else:
            await message.reply("Вытащи хуй изо рта и скажи нормально.")

    except Exception as e:
        print(f"Ошибка Whisper: {e}")
        await message.reply("Произошла ошибка при обращении к нейросети.")
    
    finally:
        if os.path.exists(input_file):
            os.remove(input_file)
 

# --- КОМАНДА /AI (РУБИЛЬНИК) ---
@dp.message(F.text.lower() == "/ai")
async def toggle_ai_command(message: types.Message):
    user_id = message.from_user.id
    # Получаем текущий статус (по умолчанию True)
    current_status = user_ai_settings.get(user_id, True)
    # Меняем на противоположный
    user_ai_settings[user_id] = not current_status
    
    if user_ai_settings[user_id]:
        await message.reply("🧠 *ИИ-помощник ВКЛЮЧЕН*.\nТеперь я буду исправлять опечатки и помогать с поиском серий игр.", parse_mode="Markdown")
    else:
        await message.reply("⚙️ *ИИ-помощник ВЫКЛЮЧЕН*.\nТеперь я ищу игры в Steam строго по твоему тексту.", parse_mode="Markdown")

def build_pagination_keyboard(user_id, page):
    data = user_search_cache.get(user_id)
    if not data or "options" not in data: return None
    options = data["options"]
    ITEMS_PER_PAGE = 3
    start_idx, end_idx = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
    current_options = options[start_idx:end_idx]
    kb = [[InlineKeyboardButton(text=opt, callback_data=f"gs:{opt[:45]}")] for opt in current_options]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pg:{page-1}"))
    if end_idx < len(options): nav.append(InlineKeyboardButton(text="Иное ➡️", callback_data=f"pg:{page+1}"))
    if nav: kb.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(F.text.startswith("/game"))
async def handle_game_command(message: types.Message):
    query = message.text.replace("/game", "").strip()
    if not query: return await message.reply("Пример: /game doom")
    user_id = message.from_user.id
    use_ai = user_ai_settings.get(user_id, True)
    status = await message.answer("🧠 Анализирую..." if use_ai else "🔍 Ищу...")

    try:
        search_target = query 
        if use_ai:
            ai_data = await enhance_query_with_ai(query, groq_client)
            if ai_data.get("type") == "ambiguous":
                await status.delete()
                user_search_cache[user_id] = {"options": ai_data.get("options", [])}
                return await message.answer(f"🤔 Найдено несколько игр по запросу *{query}*:", 
                                            reply_markup=build_pagination_keyboard(user_id, 0), parse_mode="Markdown")
            search_target = ai_data.get("name", query)

        game_data = await search_steam_game(search_target, original_query=query)
        if not game_data:
            return await status.edit_text(f"❌ '{search_target}' не найдена.")
        await send_game_card(message, game_data, status)
    except Exception as e:
        print(f"Error: {e}")
        await message.answer("❌ Ошибка поиска.")

@dp.callback_query(F.data.startswith("pg:"))
async def process_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split(":")[1])
    kb = build_pagination_keyboard(callback.from_user.id, page)
    if not kb: return await callback.answer("Сессия истекла.", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("gs:"))
async def process_game_selection(callback: types.CallbackQuery):
    selected_game = callback.data.split(":")[1]
    await callback.answer()
    status = await callback.message.edit_text(f"🔍 Загружаю *{selected_game}*...", parse_mode="Markdown")
    game_data = await search_steam_game(selected_game)
    if game_data: await send_game_card(callback.message, game_data, status)

async def send_game_card(message, game_data, status_msg):
    appid = game_data['appid']
    display_name = game_data['name']
    
    # Получаем данные из game_logic
    data = await get_main_info(appid, display_name)

    # 1. Плашка Early Access
    ea_warning = "⚠️ *Игра в раннем доступе*\n" if data.get('early_access') else ""
    
    # 2. Формируем текст (БЕЗ обратных кавычек, чтобы шрифт был крупнее)
    # Длина линии ровно 14 символов — идеально для мобилок
    text = (
        f"🎮 *{display_name}*\n"
        f"{ea_warning}"
        f"📅 Дата выхода: *{data.get('release_date', 'Неизвестно')}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👥 Онлайн сейчас: {data.get('online', 0):,}\n"
        f"⭐️ Отзывы: {data.get('reviews', 'Нет данных')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 *Цены в Steam:*\n"
        f"🇷🇺 РФ: {data.get('price_ru', 'Н/Д')}\n"
        f"🇰🇿 КЗ: {data.get('price_kz', 'Н/Д')}\n"
        f"🇺🇦 УА: {data.get('price_ua', 'Н/Д')}"
    )

    # Кнопка под карточкой
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏪 Открыть в Steam", url=f"https://store.steampowered.com/app/{appid}")]
    ])

    # Список картинок по приоритету
    image_variants = [
        f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900_2x.jpg",
        data.get('image'),
        f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
    ]

    # Удаляем сообщение о загрузке
    try:
        await status_msg.delete()
    except:
        pass
    
    # Отправляем карточку
    for img_url in image_variants:
        if not img_url: continue
        try:
            await message.answer_photo(
                photo=img_url, 
                caption=text, 
                parse_mode="Markdown", 
                reply_markup=kb
            )
            return 
        except:
            continue
    
    # Резервный вариант, если картинки не загрузились
    await message.answer(text=text, parse_mode="Markdown", reply_markup=kb)
@dp.message(F.text.startswith("/giff"))
async def cmd_giff(message: types.Message):
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("Ответь на видео! Формат: /giff старт длительность (например: /giff 1.2 3.5)", parse_mode="Markdown")
        return

    # Парсим числа (теперь float для дробных значений)
    parts = message.text.split()
    start_time = 0.0
    duration = 6.0 # По умолчанию

    try:
        if len(parts) > 1:
            start_time = float(parts[1].replace(',', '.')) # заменяем запятую на точку, если юзер ошибся
        if len(parts) > 2:
            duration = float(parts[2].replace(',', '.'))
    except ValueError:
        await message.reply("Используй числа, например: /giff 1.5 2")
        return

    # Ограничение для защиты сервера (макс 5 секунд для гифки)
    duration = min(duration, 5.0)

    status_msg = await message.reply("⚙️ Нарезаю гифку...")
    video = message.reply_to_message.video
    v_path = os.path.join(TEMP_DIR, f"v_{video.file_id}.mp4")
    g_path = os.path.join(TEMP_DIR, f"g_{video.file_id}.gif")

    try:
        await bot.download(video, destination=v_path)

        def process():
            with VideoFileClip(v_path) as clip:
                if start_time >= clip.duration: return "error_time"
                end_time = min(start_time + duration, clip.duration)
                # Используем subclipped для новых версий или subclip для старых
                new_clip = clip.subclipped(start_time, end_time).resized(width=480)
                new_clip.write_gif(g_path, fps=12)
                return "ok"

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, process)

        if res == "ok":
            await message.answer_animation(FSInputFile(g_path), caption=f"🎬 Отрезок: {start_time}-{start_time+duration} сек.")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Ошибка: старт позже конца видео.")

    finally:
        if os.path.exists(v_path): os.remove(v_path)
        if os.path.exists(g_path): os.remove(g_path)
@dp.message(F.text.startswith("/audio"))
async def cmd_audio(message: types.Message):
    target = message.reply_to_message if message.reply_to_message else message
    if not target.video:
        await message.reply("Ответь на видео этой командой, чтобы достать звук!")
        return

    parts = message.text.split()
    start_time = 0.0
    duration = None # По умолчанию вырежем всё, если не указано

    try:
        if len(parts) > 1: start_time = float(parts[1].replace(',', '.'))
        if len(parts) > 2: duration = float(parts[2].replace(',', '.'))
    except ValueError:
        await message.reply("Пример: /audio 10 15.5 (с 10-й секунды, длительность 15.5 сек)")
        return

    status_msg = await message.reply("🔊 Извлекаю аудиодорожку...")
    v_path = os.path.join(TEMP_DIR, f"v_a_{target.video.file_id}.mp4")
    a_path = os.path.join(TEMP_DIR, f"audio_{target.video.file_id}.mp3")

    try:
        await bot.download(target.video, destination=v_path)

        def extract():
            with VideoFileClip(v_path) as clip:
                if start_time >= clip.duration: return "error_time"
                
                # Если duration не задан, берем до конца видео
                end_time = min(start_time + duration, clip.duration) if duration else clip.duration
                
                subclip = clip.subclipped(start_time, end_time)
                # Извлекаем аудио и сохраняем в mp3
                subclip.audio.write_audiofile(a_path, logger=None)
                return "ok"

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, extract)

        if res == "ok":
            await message.answer_audio(FSInputFile(a_path), caption="Вот твое аудио! 🎵")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Ошибка времени.")

    finally:
        if os.path.exists(v_path): os.remove(v_path)
        if os.path.exists(a_path): os.remove(a_path)
# Функция для скачивания видео (выполняется в отдельном потоке, чтобы не вешать бота)
def download_tiktok(url, file_path):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': file_path,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])



@dp.message(F.text.contains("tiktok.com"))
async def tiktok_loader(message: types.Message):
    # Создаем временное имя файла
    video_filename = os.path.join(TEMP_DIR, f"tt_{message.from_user.id}.mp4")
    
    # Отправляем статус
    status_msg = await message.answer("⏳ Скачиваю видео из TikTok...")

    try:
        # 1. Получаем имя пользователя (first_name)
        user_name = message.from_user.first_name
        
        # 2. Создаем список рандомных фраз
        phrases = [
            "прислал крутой видик 🔥",
            "делится медятиной 🎬",
            "нашел что-то интересное 👀",
            " строго рекомендует к ознакомлению 🍿"
        ]
        
        # 3. Выбираем случайную фразу из списка и склеиваем с именем
        random_phrase = random.choice(phrases)
        final_caption = f"👤 {user_name} {random_phrase}"

        # Запускаем скачивание
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, download_tiktok, message.text, video_filename)

        # Отправляем видео в чат с новой динамической подписью
        video_file = FSInputFile(video_filename)
        await message.answer_video(
            video=video_file, 
            caption=final_caption, # Используем нашу сгенерированную подпись
            reply_to_message_id=message.message_id
        )
        
        # Удаляем сообщение о загрузке
        await status_msg.delete()
        
    except Exception as e:
        print(f"Ошибка TikTok: {e}")
        await status_msg.edit_text("❌ Не удалось скачать видео. Возможно, ссылка битая или аккаунт закрыт.")
    
    finally:
        # Чистим HDD
        if os.path.exists(video_filename):
            os.remove(video_filename)

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_text = message.text.lower().strip()

    # --- ЛОГИКА ТРИГГЕРОВ ---
    # Проверяем, есть ли в сообщении триггерное слово
    #if any(word in user_text for word in TRIGGER_WORDS):
        # Получаем список файлов из папки с картинками
       # photos = [f for f in os.listdir(TRIGGER_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
       # if photos:
            #random_photo = os.path.join(TRIGGER_DIR, random.choice(photos))
           # photo_file = FSInputFile(random_photo)
            #await message.answer_photo(photo=photo_file, caption="Не выражаться!")
            #return # Прерываем, чтобы не искать погоду в триггере

    # --- ЛОГИКА ПОГОДЫ (по фразе "погода [город]") ---
    if "погода" in user_text:
        # Убираем слово "погода", чтобы остался только город
        city_name = user_text.replace("погода", "").strip()
        if city_name:
            city_formated = city_name.title()
            result = get_weather(city_formated)
            await message.answer(result)
        else:
             await message.answer("Напишите город после слова 'погода', например: погода Химки")

async def main():
           
    # Настраиваем расписание 
    scheduler.add_job(send_morning_post, "cron", hour=10, minute=10)
    scheduler.start()
    
    print("Бот запущен и ждет утра...")
    await dp.start_polling(bot)

    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")