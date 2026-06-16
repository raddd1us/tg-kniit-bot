import os # Импортируем модуль os для работы с переменными окружения
from dotenv import load_dotenv # Импортируем функцию load_dotenv

import telebot
from telebot import types
from sentence_transformers import SentenceTransformer, util
import pandas as pd


# ================== НАСТРОЙКИ ==================
# Получаем токен из переменных окружения
# Если токен не найден, os.getenv() вернет None
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверяем, что токен был успешно загружен
if BOT_TOKEN is None:
    print("Ошибка: BOT_TOKEN не найден в файле cc.env или в переменных окружения.")
    print("Убедитесь, что в файле cc.env есть строка 'BOT_TOKEN=ВАШ_ТОКЕН'")
    exit(1) # Завершаем выполнение, если токена нет

bot = telebot.TeleBot(BOT_TOKEN)
# ================== ЛЕНИВАЯ ЗАГРУЗКА МОДЕЛИ ==================
_model = None

def get_model():
    global _model
    if _model is None:
        # Библиотека сама скачает модель из сети при первом запуске
        _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    return _model
# ================== ПРОХОДНЫЕ БАЛЛЫ ==================
PASSING_SCORES = {
    "ФИИТ": 248,
    "МОАИС": 242,
    "ИВТ": 208,
    "ПИ": 265,
    "САУ": 231,
    "КБ": 215
}
user_waiting_score = set()

# ================== ЗАГРУЗКА FAQ ==================
df = pd.read_excel("faq (2).xlsx")
faq_data = []

model = get_model()  # <<< загрузится ОДИН раз

for _, row in df.iterrows():
    q = row.iloc[0]
    a = row.iloc[1]
    if pd.notna(q) and pd.notna(a):
        faq_data.append({
            "question": str(q),
            "answer": str(a),
            "embedding": model.encode(str(q), convert_to_tensor=True)
        })

# ================== ПОИСК ОТВЕТА ==================
def find_faq_answer(user_question):
    user_question = user_question.strip()
    if len(user_question) < 3:
        return None

    user_emb = model.encode(user_question, convert_to_tensor=True)
    best_score = 0
    best_answer = None

    for item in faq_data:
        score = util.cos_sim(user_emb, item["embedding"]).item()
        if score > best_score:
            best_score = score
            best_answer = item["answer"]

    return best_answer if best_score > 0.65 else None

# ================== СТАРТ ==================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🌐 Сайт СГУ КНиИТ"),
        types.KeyboardButton("🔍 Направления"),
        types.KeyboardButton("📅 Календарь"),
        types.KeyboardButton("🧠 Тест на профориентацию"),
        types.KeyboardButton("📊 Калькулятор шансов"),
        types.KeyboardButton("🎓 История поступления"),
        types.KeyboardButton("❓ FAQ")
    )
    bot.send_message(
        message.chat.id,
        f"Привет, {message.from_user.first_name}! 👋\nВыбери действие:",
        reply_markup=markup
    )

# ================== КАЛЬКУЛЯТОР ==================
@bot.message_handler(func=lambda m: m.text == "📊 Калькулятор шансов")
def chance_start(message):
    user_waiting_score.add(message.chat.id)
    bot.send_message(
        message.chat.id,
        "📌 Введи **СУММУ баллов ЕГЭ** (например: 230)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.chat.id in user_waiting_score and m.text.isdigit())
def chance_calc(message):
    total = int(message.text)
    user_waiting_score.discard(message.chat.id)

    result = f"📊 **Шансы при {total} баллах:**\n\n"
    for d, p in PASSING_SCORES.items():
        diff = total - p
        if diff >= 10:
            chance = "🟢 ВЫСОКИЙ ШАНС"
        elif -5 <= diff < 10:
            chance = "🟡 СРЕДНИЙ ШАНС"
        else:
            chance = "🔴 РИСК"
        result += f"**{d}** — {chance}\n"

    bot.send_message(message.chat.id, result, parse_mode="Markdown")

# ================== ССЫЛКИ ==================
def send_link_button(chat_id, text, url):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text, url=url))
    bot.send_message(chat_id, "🔗 Нажми на кнопку:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🌐 Сайт СГУ КНиИТ")
def send_site(message):
    send_link_button(
        message.chat.id,
        "Перейти на сайт СГУ КНиИТ",
        "https://www.sgu.ru/struktura/computersciences"
    )

@bot.message_handler(func=lambda m: m.text == "🔍 Направления")
def send_dirs(message):
    send_link_button(
        message.chat.id,
        "Направления подготовки",
        "https://www.sgu.ru/struktura/computersciences/postupit-k-nam"
    )

@bot.message_handler(func=lambda m: m.text == "📅 Календарь")
def send_schedule(message):
    with open("schedule.jpeg", "rb") as photo:
        bot.send_photo(
            message.chat.id,
            photo,
            caption="📅 Календарь КНиИТ"
        )

# ================== ИСТОРИЯ СТУДЕНТА ==================
@bot.message_handler(func=lambda m: m.text == "🎓 История поступления")
def student_story(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎓 Данила — ФИИТ", callback_data="story_fiit"),
        types.InlineKeyboardButton("🎓 Ярослав — МОАИС", callback_data="story_moais")
    )

    bot.send_message(
        message.chat.id,
        "🎥 Выбери историю поступления:",
        reply_markup=markup
    )


# ================== FAQ ==================
@bot.message_handler(func=lambda m: m.text == "❓ FAQ")
def faq_handler(message):
    bot.send_message(message.chat.id, "Напиши свой вопрос:")

# ================== ТЕСТ НА ПРОФОРИЕНТАЦИЮ ==================
user_test_progress = {}
user_test_scores = {}

questions = [
    ("Тебе проще объяснить что-то на словах, чем нарисовать схему?", "communication"),
    ("Ты легко находишь общий язык с новыми людьми?", "communication"),
    ("Тебе нравится писать тексты или вести соцсети?", "communication"),
    ("Любая поломанная техника в руках просит, чтобы её починили?", "technical"),
    ("Тебе интересно разбираться в 'железе' компьютеров и гаджетов?", "technical"),
    ("Ты любишь собирать/конструировать что-то своими руками?", "technical"),
    ("Тебе нравится работать с инструментами?", "technical"),
    ("Ты часто замечаешь, когда другие люди грустят или злятся без видимой причины?", "social"),
    ("Тебе нравится помогать людям решать их проблемы?", "social"),
    ("Ты готов выслушать чужую точку зрения, даже если не согласен?", "social"),
    ("Тебе реально интересно, из чего сделан предмет и почему он не ломается?", "analytical"),
    ("Ты предпочитаешь работать с числами, графиками и данными?", "analytical"),
    ("Тебе нравится выявлять закономерности в информации?", "analytical"),
    ("Ты любишь сам разбираться в новом и докопаться до сути?", "analytical"),
    ("Видя неудачную рекламу, ты думаешь: 'Я бы сделал круче'?", "creative"),
    ("Тебе нравится придумывать оригинальные решения?", "creative"),
    ("Ты обращаешь внимание на оформление вещей (сайтов, интерьеров)?", "creative"),
    ("Хаос и беспорядок в работе (или в комнате) выводят тебя из себя?", "organizational"),
    ("Тебе нравится планировать дела и распределять задачи?", "organizational"),
    ("Ты легко организуешь людей для общего дела?", "organizational"),
    ("Тебе важно, чтобы всё было структурировано и по плану?", "organizational"),
]

categories = {
    "communication": "💬 **Коммуникации & Языки**\nПодойдут: Маркетолог, HR, PR-менеджер, Журналист, Переводчик",
    "technical": "🔧 **Техника & Практика**\nПодойдут: Программист, Системный администратор, Инженер, Робототехник",
    "social": "🤝 **Социальная сфера & Помощь**\nПодойдут: Психолог, Социальный работник, Менеджер по персоналу",
    "analytical": "📊 **Наука & Аналитика**\nПодойдут: Аналитик данных, Учёный, Исследователь, Финансист",
    "creative": "🎨 **Творчество & Дизайн**\nПодойдут: Дизайнер, Копирайтер, Архитектор, Видеомейкер",
    "organizational": "📈 **Организация & Управление**\nПодойдут: Проектный менеджер, Логист, Руководитель отдела"
}

@bot.message_handler(func=lambda m: m.text == "🧠 Тест на профориентацию")
def test_start(message):
    chat_id = message.chat.id
    user_test_progress[chat_id] = 0
    user_test_scores[chat_id] = {k: 0 for k in categories}
    send_test_question(chat_id)

def send_test_question(chat_id):
    idx = user_test_progress.get(chat_id)
    if idx is None or idx >= len(questions):
        finish_test(chat_id)
        return

    text, _ = questions[idx]
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да", callback_data=f"yes_{idx}"),
        types.InlineKeyboardButton("❌ Нет", callback_data=f"no_{idx}")
    )
    markup.add(types.InlineKeyboardButton("🚫 Прервать тест", callback_data="stop_test"))

    bot.send_message(
        chat_id,
        f"**Вопрос {idx + 1}/{len(questions)}:**\n{text}",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ======= ОГРАНИЧЕННЫЙ CALLBACK =======
@bot.callback_query_handler(func=lambda c: c.data.startswith(("yes_", "no_", "stop_test")))
def test_answer(call):
    chat_id = call.message.chat.id

    if chat_id not in user_test_progress:
        return  # <<< защита от двойного клика

    if call.data == "stop_test":
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, "❌ Тест прерван.")
        user_test_progress.pop(chat_id, None)
        user_test_scores.pop(chat_id, None)
        return

    ans, idx = call.data.split("_")
    idx = int(idx)
    _, category = questions[idx]

    if ans == "yes":
        user_test_scores[chat_id][category] += 1

    user_test_progress[chat_id] += 1
    bot.delete_message(chat_id, call.message.message_id)
    send_test_question(chat_id)

def finish_test(chat_id):
    scores = user_test_scores.get(chat_id)
    if not scores:
        return

    sorted_categories = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result_text = "**🎯 Результаты теста:**\n\n"

    for i, (category, score) in enumerate(sorted_categories):
        max_score = 4 if category in ["technical", "organizational"] else 3
        percentage = (score / max_score) * 100
        result_text += f"{i + 1}. {categories[category]}\n   Совпадение: {percentage:.0f}%\n\n"

    top_category = sorted_categories[0][0]
    result_text += f"💡 **Рекомендация:** обрати внимание на **{top_category}**"

    if top_category in ["technical", "analytical"]:
        result_text += "\n\n🎓 **Факультет КНиИТ тебе отлично подойдёт!**"

    bot.send_message(chat_id, result_text, parse_mode="Markdown")
    user_test_progress.pop(chat_id, None)
    user_test_scores.pop(chat_id, None)

@bot.callback_query_handler(func=lambda c: c.data in ["story_fiit", "story_moais"])
def send_student_story(call):
    chat_id = call.message.chat.id

    if call.data == "story_fiit":
        bot.send_message(chat_id, "🎓 Данила, 1 курс, ФИИТ 👇")
        bot.send_video_note(
            chat_id,
            "DQACAgIAAxkBAAIGa2lBfxghAAFuAkhzNm-yy6XNA0aBJAAC6JAAAgsPEEq3wuFFcQNKfDYE"
        )

    elif call.data == "story_moais":
        bot.send_message(chat_id, "🎓 Ярослав, 1 курс, МОАИС 👇")
        bot.send_video_note(
            chat_id,
            "DQACAgIAAxkBAAIJYGlECdealHfrzJv8AAFnVj7UZDz4KQACtZwAAoDvIEpUcEmMQRTy1TYE"
        )

    bot.answer_callback_query(call.id)

# ================== ВСЕ ОСТАЛЬНЫЕ СООБЩЕНИЯ ==================
@bot.message_handler(func=lambda m: True)
def handle_user_question(message):
    if message.text.startswith('/'):
        return
    if message.chat.id in user_test_progress or message.chat.id in user_waiting_score:
        return

    answer = find_faq_answer(message.text)
    bot.send_message(
        message.chat.id,
        answer if answer else "❓ Не смог найти ответ. Попробуй переформулировать вопрос или выбери действие из меню."
    )

# ================== ЗАПУСК ==================
print("Бот запущен...")
@bot.message_handler(content_types=['video_note'])
def get_video_note_id(message):
    print("VIDEO_NOTE_FILE_ID =", message.video_note.file_id)
bot.polling(none_stop=True)
