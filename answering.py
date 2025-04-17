import sqlite3
import requests
import json
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Настройки YandexGPT
YC_FOLDER_ID = "ВАШ_FOLDER_ID"  # Идентификатор каталога
YC_API_KEY = "ВАШ_API_KEY"  # API-ключ сервисного аккаунта
YC_MODEL = "general"  # Используемая модель


# Инициализация базы данных
def init_db():
    with sqlite3.connect('qa_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS qa (
                question TEXT PRIMARY KEY,
                answer TEXT NOT NULL
            )
        ''')
        conn.commit()


# Проверка существующего вопроса
def get_answer_from_db(question: str) -> str:
    with sqlite3.connect('qa_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT answer FROM qa WHERE question = ?', (question,))
        result = cursor.fetchone()
        return result[0] if result else None


# Сохранение нового вопроса и ответа
def save_to_db(question: str, answer: str):
    with sqlite3.connect('qa_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO qa (question, answer)
            VALUES (?, ?)
        ''', (question, answer))
        conn.commit()


# Генерация ответа с помощью YandexGPT
def get_ai_response(question: str) -> str:
    try:
        headers = {
            "Authorization": f"Api-Key {YC_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "modelUri": f"gpt://{YC_FOLDER_ID}/{YC_MODEL}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 2000
            },
            "messages": [
                {
                    "role": "user",
                    "text": question
                }
            ]
        }

        response = requests.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            result = json.loads(response.text)
            return result['result']['alternatives'][0]['message']['text']
        else:
            return f"Ошибка API: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Ошибка при запросе к нейросети: {str(e)}"


# Обработчик сообщений
def handle_message(update: Update, context: CallbackContext):
    user_question = update.message.text.strip()

    # Проверяем базу данных
    db_answer = get_answer_from_db(user_question)

    if db_answer:
        response_text = f"Ответ из базы данных:\n{db_answer}"
    else:
        # Если нет в базе - получаем новый ответ
        ai_response = get_ai_response(user_question)
        save_to_db(user_question, ai_response)
        response_text = f"Новый ответ от нейросети:\n{ai_response}"

    update.message.reply_text(response_text)


# Главная функция
def main():
    init_db()

    updater = Updater("ВАШ_TELEGRAM_BOT_TOKEN")
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()