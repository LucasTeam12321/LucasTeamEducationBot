from random import choice
import sqlite3
import telebot
from telebot import custom_filters
from telebot.states import StatesGroup, State
from telebot.storage import StateMemoryStorage
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message
import logging

# Конфигурация (ЗАМЕНИТЕ ТОКЕН!)
API_TOKEN = '7748202816:AAGhyNGFDAp940tEW_Bo4okMzopmYQKoQmM'

# Инициализация
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(API_TOKEN, state_storage=state_storage)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class QuizStates(StatesGroup):
    choose_subject = State()
    answer = State()


SUBJECT_MAP = {
    "Математика": "math",
    "История": "history",
    "Литература": "literature"
}


def init_db():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            correct_answers INTEGER DEFAULT 0,
            incorrect_answers INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            subject TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()  # Инициализация при старте


def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton('/quiz'), KeyboardButton('/help'))
    markup.row(KeyboardButton('/score'), KeyboardButton('/leaderboard'))
    return markup


def create_subject_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("Математика"), KeyboardButton("История"))
    markup.row(KeyboardButton("Литература"))
    return markup

def create_options_keyboard(options):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    markup.row(KeyboardButton("🚪 Выход"))  # Кнопка выхода
    return markup


def get_question(subject: str) -> dict:
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT question, options, correct_answer 
            FROM questions 
            WHERE subject = ?
            ORDER BY RANDOM() 
            LIMIT 1
        ''', (subject,))
        result = cursor.fetchone()

        if result:
            return {
                "question": result[0],
                "options": result[1].split(','),
                "correct_answer": result[2]
            }
        return None

    except sqlite3.Error as e:
        logging.error(f"Ошибка БД: {e}")
        return None
    finally:
        conn.close()


@bot.message_handler(commands=["start"])
def handle_start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username or msg.from_user.first_name

    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO players (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        conn.commit()

        bot.send_message(
            msg.chat.id,
            "🎉 Добро пожаловать! Используйте /quiz для старта",
            reply_markup=create_main_keyboard()
        )

    except sqlite3.Error as e:
        logging.error(f"Ошибка: {e}")
    finally:
        conn.close()


@bot.message_handler(commands=["quiz"])
def start_quiz(msg):
    bot.delete_state(msg.from_user.id, msg.chat.id)
    bot.send_message(msg.chat.id, "📚 Выберите предмет:", reply_markup=create_subject_keyboard())
    bot.set_state(msg.from_user.id, QuizStates.choose_subject, msg.chat.id)


@bot.message_handler(state=QuizStates.choose_subject)
def handle_subject_selection(msg: Message):
    subject_key = SUBJECT_MAP.get(msg.text)

    if not subject_key:
        bot.send_message(msg.chat.id, "❌ Выберите предмет из списка!", reply_markup=create_subject_keyboard())
        return
    if question := get_question(subject_key):
        markup = create_options_keyboard(question['options'])

    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM questions WHERE subject = ?', (subject_key,))
        count = cursor.fetchone()[0]

        if count == 0:
            bot.send_message(msg.chat.id, "⚠️ Вопросы временно отсутствуют", reply_markup=create_main_keyboard())
            return

        question = get_question(subject_key)
        if not question:
            raise Exception("Ошибка загрузки вопроса")

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        for option in question['options']:
            markup.add(KeyboardButton(option))

        with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data["correct_answer"] = question['correct_answer']

        bot.send_message(msg.chat.id, question['question'], reply_markup=markup)
        bot.set_state(msg.from_user.id, QuizStates.answer, msg.chat.id)

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        bot.send_message(msg.chat.id, "❌ Системная ошибка", reply_markup=create_main_keyboard())
    finally:
        conn.close()


@bot.message_handler(state=QuizStates.answer)
def handle_answer(msg: Message):
    try:
        if msg.text.strip() == "🚪 Выход":
            bot.delete_state(msg.from_user.id, msg.chat.id)
            bot.send_message(msg.chat.id, "🔙 Возврат в главное меню", reply_markup=create_main_keyboard())
            return

        with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            # Проверка ответа
            correct = msg.text.strip() == data["correct_answer"].strip()
            response = "✅ Правильно! +1 балл" if correct else f"❌ Неверно. Ответ: {data['correct_answer']}"

            # Обновление статистики
            conn = sqlite3.connect('quiz.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE players 
                SET correct_answers = correct_answers + ?,
                    incorrect_answers = incorrect_answers + ?
                WHERE user_id = ?
            ''', (int(correct), int(not correct), msg.from_user.id))
            conn.commit()

            # Получение нового вопроса
            new_question = get_question(data["subject"])

            if new_question:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                for option in new_question['options']:
                    markup.add(KeyboardButton(option))
                markup.row(KeyboardButton("🚪 Выход"))

                # Обновление данных состояния
                data["correct_answer"] = new_question['correct_answer']
                bot.send_message(msg.chat.id, new_question['question'], reply_markup=markup)
            else:
                bot.send_message(msg.chat.id, "🏁 Вопросы закончились!", reply_markup=create_main_keyboard())
                bot.delete_state(msg.from_user.id, msg.chat.id)

    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        bot.send_message(msg.chat.id, "⚠️ Произошла ошибка", reply_markup=create_main_keyboard())
    finally:
        if 'conn' in locals():
            conn.close()


@bot.message_handler(commands=["score"])
def show_score(msg):
    try:
        user_id = msg.from_user.id
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()

        # Получаем статистику из БД
        cursor.execute('''
            SELECT correct_answers, incorrect_answers 
            FROM players 
            WHERE user_id = ?
        ''', (user_id,))

        stats = cursor.fetchone()

        if stats:
            correct, incorrect = stats
            total = correct + incorrect
            response = (
                f"📊 Ваша статистика:\n"
                f"✅ Правильных ответов: {correct}\n"
                f"❌ Неправильных ответов: {incorrect}\n"
                f"🏆 Всего попыток: {total}"
            )
        else:
            response = "❌ Ваша статистика не найдена"

        bot.send_message(msg.chat.id, response, reply_markup=create_main_keyboard())

    except sqlite3.Error as e:
        logging.error(f"Ошибка БД: {e}")
        bot.send_message(msg.chat.id, "⚠️ Ошибка загрузки статистики")
    finally:
        conn.close()


bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(timeout=30, long_polling_timeout=30)
