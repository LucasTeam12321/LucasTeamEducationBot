import telebot
import sqlite3
import logging
from telebot import custom_filters
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message
from telebot.handler_backends import State, StatesGroup
import random
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Подключение к боту
bot = telebot.TeleBot("7748202816:AAGhyNGFDAp940tEW_Bo4okMzopmYQKoQmM")


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            correct_answers INTEGER DEFAULT 0,
            incorrect_answers INTEGER DEFAULT 0,
            grade REAL DEFAULT 5.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            subject TEXT,
            difficulty INTEGER,
            explanation TEXT,
            link TEXT
        )
    ''')
    conn.commit()
    conn.close()


# Словарь предметов
SUBJECT_MAP = {
    "Математика": "math",
    "История": "history",
    "Литература": "literature",
}


# Состояния бота
class QuizStates(StatesGroup):
    choose_subject = State()
    answer = State()


# --- Функции для создания клавиатур ---
def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("/quiz"))
    markup.add(KeyboardButton("/score"))
    return markup


def create_subject_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for subject in SUBJECT_MAP:
        markup.add(KeyboardButton(subject))
    markup.row(KeyboardButton("🚪 Выход"))
    return markup


def create_options_keyboard(options):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    markup.row(KeyboardButton("🚪 Выход"))
    return markup


# Функция для получения вопроса
def get_question(subject_key, user_id):
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute("SELECT grade FROM players WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        logging.info(f"Результат запроса для user_id {user_id}: {result}")

        if result:
            player_grade = result[0]
            min_difficulty = max(1, int(player_grade - 1))
            max_difficulty = min(11, int(player_grade + 1))

            cursor.execute('''
                SELECT question, correct_answer, options, explanation, link, difficulty
                FROM questions
                WHERE subject = ? AND difficulty BETWEEN ? AND ?
                ORDER BY RANDOM() LIMIT 1
            ''', (subject_key, min_difficulty, max_difficulty))
            question_data = cursor.fetchone()

            if question_data:
                question, correct_answer, options_str, explanation, link, difficulty = question_data
                try:
                    options = json.loads(options_str)
                except json.JSONDecodeError:
                    options = options_str.split(',')
                    options = [opt.strip() for opt in options]

                if correct_answer not in options:
                    options.append(correct_answer)
                random.shuffle(options)
                return {
                    "question": question,
                    "correct_answer": correct_answer,
                    "options": options,
                    "explanation": explanation,
                    "link": link,
                    "difficulty": difficulty
                }
            else:
                return None
        else:
            logging.warning(f"Не найдена оценка для пользователя {user_id}. Используется значение по умолчанию.")
            player_grade = 5.0
            return get_question(subject_key, user_id)  # Рекурсивный вызов с дефолтной оценкой

    except sqlite3.Error as e:
        logging.error(f"Ошибка БД в get_question: {e}")
        return None
    finally:
        if conn:
            conn.close()


# --- Обработчики сообщений ---

@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO players (user_id, username, grade, correct_answers, incorrect_answers) 
            VALUES (?, ?, ?, COALESCE((SELECT correct_answers FROM players WHERE user_id = ?), 0),
                   COALESCE((SELECT incorrect_answers FROM players WHERE user_id = ?), 0))
        ''', (user_id, username, 5.0, user_id, user_id))
        conn.commit()

        # Отправка приветственного сообщения
        # Отправляем приветственное сообщение с главной клавиатурой
        bot.send_message(msg.chat.id, """🎉 Приветствую тебя в LucasTeamEducationBot! 
                Здесь ты можешь сыграть в такие игры как: 
                🔹Виселица
                🔹Математический бой
                🔹Верю - не верю
                 Также ты можешь сыграть в викторину на одну из тем на выбор:
                 🔸Математика
                 🔸История
                 🔸Литература
                Для подробной информации об играх используй /help. Чтобы начать играть в викторину используй /quiz, а чтобы начать игру используй /minigame .""",
                         reply_markup=create_main_keyboard())

        # Логирование успешного старта
        logging.info(f"Пользователь {user_id} (@{username}) начал работу с ботом")

    except sqlite3.Error as e:
        logging.error(f"Ошибка БД при старте: {e}")
        bot.send_message(msg.chat.id, "⚠️ Произошла техническая ошибка. Пожалуйста, попробуйте позже.")
    finally:
        if 'conn' in locals() and conn:
            conn.close()


@bot.message_handler(commands=["help"])
def help(msg):
    text = """
🎓 <b>LucasTeamEducationBot</b> — твой умный помощник в обучении!

📚 <b>Основные команды:</b>
/quiz - Начать викторину (Математика, История, Литература)
/score - Показать статистику и достижения
/help - Эта справка

🎮 <b>Мини-игры:</b>
• Виселица (угадай термин)
• Матбой (решай примеры на время)
• Верю/Не верю (определи истинность)

📊 <b>Особенности:</b>
• Адаптивные вопросы под твой класс (1-11)
• Разбор ответов с учебными материалами
• Система достижений и бейджей
• Ежедневная статистика активности

🏆 <b>Достижения:</b>
Эрудит | Спринтер | Детектор лжи

📆 <i>Новые функции уже в разработке!</i>

Команда разработки:
• @LucasTeamLuke (Лидер)
• @EnidBlaiton

Присоединяйтесь к нашему чату: 
t.me/+6Q4LbNIZFAMwMDI6
"""
    bot.send_message(msg.chat.id, text, reply_markup=create_main_keyboard(), parse_mode='HTML')


@bot.message_handler(commands=["quiz"])
def start_quiz(msg):
    bot.delete_state(msg.from_user.id, msg.chat.id)
    logging.info(f"Пользователь {msg.from_user.id} начал викторину.")
    bot.send_message(msg.chat.id, "📚 Выберите предмет:", reply_markup=create_subject_keyboard())
    bot.set_state(msg.from_user.id, QuizStates.choose_subject, msg.chat.id)


@bot.message_handler(state=QuizStates.choose_subject)
def handle_subject_selection(msg: Message):
    logging.info(f"Пользователь {msg.from_user.id} выбрал предмет: {msg.text}")
    user_id = msg.from_user.id
    if msg.text == "🚪 Выход":
        bot.send_message(msg.chat.id, "Вы вышли из викторины.", reply_markup=create_main_keyboard())
        bot.delete_state(user_id, msg.chat.id)  # Удаляем состояние
        return

    subject_key = SUBJECT_MAP.get(msg.text)

    if not subject_key:
        bot.send_message(msg.chat.id, "Неверный предмет. Пожалуйста, выберите из списка.")
        return

    question = get_question(subject_key, user_id)  # <- ПЕРЕДАЕМ user_id

    if question:
        bot.send_message(msg.chat.id, question["question"], reply_markup=create_options_keyboard(question["options"]))
        bot.set_state(msg.from_user.id, QuizStates.answer, msg.chat.id)
        with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data['correct_answer'] = question['correct_answer']
            data['explanation'] = question['explanation']
            data['link'] = question['link']
            data['difficulty'] = question['difficulty']
    else:
        bot.send_message(msg.chat.id,
                         "Вопросы по этому предмету закончились. Выберите другой предмет или попробуйте позже.")
        bot.set_state(msg.from_user.id, QuizStates.choose_subject, msg.chat.id)


@bot.message_handler(state=QuizStates.answer)
def handle_answer(msg: Message):
    logging.info(f"handle_answer вызван для пользователя {msg.from_user.id} с сообщением: {msg.text}")
    user_id = msg.from_user.id
    with bot.retrieve_data(user_id, msg.chat.id) as data:
        correct_answer = data.get('correct_answer')
        explanation = data.get('explanation')
        link = data.get('link')
        difficulty = data.get('difficulty')

    if msg.text == "🚪 Выход":
        bot.send_message(msg.chat.id, "Вы вышли извикторины.", reply_markup=create_main_keyboard())
        bot.delete_state(user_id, msg.chat.id)  # Удаляем состояние
        return

    if msg.text == correct_answer:
        bot.send_message(msg.chat.id, "✅ Правильно!")
        # ... (код для обновления статистики и оценки)
    else:
        bot.send_message(msg.chat.id, f"❌ Неправильно. Правильный ответ: {correct_answer}")
        # ... (код для обновления статистики и оценки)

    if explanation:
        bot.send_message(msg.chat.id, f"🤓 Пояснение: {explanation}")
    if link:
        bot.send_message(msg.chat.id, f"🔗 Дополнительный материал: {link}")

    question = get_question(SUBJECT_MAP.get(msg.text), user_id)  # <- ПЕРЕДАЕМ user_id
    if question:
        bot.send_message(msg.chat.id, question["question"], reply_markup=create_options_keyboard(question["options"]))
        with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data:
            data['correct_answer'] = question['correct_answer']
            data['explanation'] = question['explanation']
            data['link'] = question['link']
            data['difficulty'] = question['difficulty']

    else:
        bot.send_message(msg.chat.id,
                         "Вопросы по этому предмету закончились. Выберите другой предмет или попробуйте позже.",
                         reply_markup=create_subject_keyboard())
        bot.set_state(msg.from_user.id, QuizStates.choose_subject, msg.chat.id)


@bot.message_handler(
    commands=["score"])  # Обработчик команды /score - выполняется, когда пользователь отправляет команду /score
def show_score(msg):
    try:  # Начинаем блок обработки исключений
        user_id = msg.from_user.id  # Получаем ID пользователя
        conn = sqlite3.connect('quiz.db')  # Подключаемся к базе данных
        cursor = conn.cursor()  # Создаем курсор
        cursor.execute("SELECT correct_answers, incorrect_answers FROM players WHERE user_id = ?",
                       (user_id,))  # Получаем статистику пользователя
        stats = cursor.fetchone()  # Получаем результат запроса

        if stats:  # Если статистика найдена
            correct, incorrect = stats  # Разделяем полученные данные на правильные и неправильные ответы
            total = correct + incorrect  # Вычисляем общее количество ответов
            response = f"📊 Ваша статистика:\n✅ Правильных ответов: {correct}\n❌ Неправильных ответов: {incorrect}\n🏆 Всего попыток: {total}"  # Формируем сообщение со статистикой
        else:  # Если статистика не найдена
            response = "❌ Ваша статистика не найдена"  # Сообщаем об отсутствии статистики

        bot.send_message(msg.chat.id, response,
                         reply_markup=create_main_keyboard())  # Отправляем сообщение со статистикой

    except sqlite3.Error as e:  # Обрабатываем ошибки базы данных
        logging.error(f"Ошибка БД в show_score: {e}")  # Записываем ошибку в лог
        bot.send_message(msg.chat.id, "⚠️ Ошибка загрузки статистики")  # Сообщаем об ошибке
    finally:  # Выполняется всегда
        if conn:  # Если подключение установлено
            conn.close()  # Закрываем подключение


bot.add_custom_filter(custom_filters.StateFilter(bot))

if __name__ == "__main__":
    init_db()
    bot.remove_webhook()
    bot.infinity_polling(timeout=30, long_polling_timeout=30)  # Убрали restart_on_change
