import telebot # Импортируем библиотеку для работы с Telegram API
import sqlite3 # Импортируем библиотеку для работы с базой данных SQLite
import logging
from telebot import custom_filters
import sqlite3
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message # Импортируем типы данных для работы с клавиатурой и сообщениями
from telebot.handler_backends import State, StatesGroup # Импортируем классы для управления состояниями бота
import random # Импортируем библиотеку для генерации случайных чисел
import json # Импортируем библиотеку для работы с JSON данными

# Настройка логирования - записываем информацию о работе бота в файл или консоль
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Подключение к боту - указываем токен, полученный от BotFather
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
            incorrect_answers INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            options TEXT,
            correct_answer TEXT,
            subject TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Словарь для сопоставления предметов
SUBJECT_MAP = {
    "Математика": "math",
    "История": "history",
    "Литература": "literature",
}

# Состояния бота - используются для отслеживания текущего этапа взаимодействия с пользователем
class QuizStates(StatesGroup):
    choose_subject = State() # Состояние выбора предмета
    answer = State() # Состояние ответа на вопрос

# Функция для создания главной клавиатуры
def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True) # Создаем объект клавиатуры
    markup.add(KeyboardButton("/quiz")) # Добавляем кнопку для начала викторины
    markup.add(KeyboardButton("/score")) # Добавляем кнопку для просмотра статистики
    return markup # Возвращаем созданную клавиатуру

# Функция для создания клавиатуры с выбором предмета
def create_subject_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True) # Создаем объект клавиатуры
    for subject in SUBJECT_MAP: # Перебираем все предметы
        markup.add(KeyboardButton(subject)) # Добавляем кнопку для каждого предмета
    markup.row(KeyboardButton("🚪 Выход")) # Добавляем кнопку для выхода
    return markup # Возвращаем созданную клавиатуру

# Функция для создания клавиатуры с вариантами ответа
def create_options_keyboard(options):
    markup = ReplyKeyboardMarkup(resize_keyboard=True) # Создаем объект клавиатуры
    for option in options: # Перебираем все варианты ответа
        markup.add(KeyboardButton(option)) # Добавляем кнопку для каждого варианта
    markup.row(KeyboardButton("🚪 Выход")) # Добавляем кнопку для выхода
    return markup # Возвращаем созданную клавиатуру

# Функция для получения вопроса из базы данных
def get_question(subject_key, user_id):
    try: # Начинаем блок обработки исключений (ошибок)
        conn = sqlite3.connect('quiz.db') # Подключаемся к базе данных
        cursor = conn.cursor() # Создаем курсор для выполнения запросов

        # Получаем вопрос с учетом класса игрока
        cursor.execute('''
            SELECT id, question, correct_answer, options, difficulty
            FROM questions
            WHERE subject = ?
            AND difficulty BETWEEN
                (SELECT MAX(1.0, rating - 1.0) FROM players WHERE user_id = ?)
                AND (SELECT MIN(11.0, rating + 1.0) FROM players WHERE user_id = ?)
            ORDER BY RANDOM()
            LIMIT 1
        ''', (subject_key, user_id, user_id))
        questions = cursor.fetchall()

        if questions: # Проверяем, есть ли вопросы по заданному предмету
            # Выбираем случайный вопрос из списка
            random_question = questions[0]
            question_id, question, correct_answer, options_str, question_difficulty = random_question

            try:  # Пытаемся преобразовать строку с вариантами ответов из JSON формата в список
                options = json.loads(options_str)
            except json.JSONDecodeError: # Если преобразование не удалось (не JSON формат)
                # Разделяем строку с вариантами ответов по запятой
                options = options_str.split(',')
                options = [opt.strip() for opt in options] # Удаляем лишние пробелы из каждого варианта ответа

            if correct_answer not in options: # Если правильного ответа нет среди вариантов
                options.append(correct_answer) # Добавляем правильный ответ к вариантам

            random.shuffle(options) # Перемешиваем варианты ответов случайным образом
            return { # Возвращаем словарь с вопросом, правильным ответом и вариантами ответов
                "question": question,
                "correct_answer": correct_answer,
                "options": options
            }
        else: # Если вопросов по заданному предмету нет
            return None # Возвращаем None

    except sqlite3.Error as e: # Обрабатываем ошибки базы данных
        logging.error(f"Ошибка БД в get_question: {e}") # Записываем ошибку в лог
        return None # Возвращаем None
    finally: # Этот блок выполняется всегда, даже если возникли ошибки
        if conn: # Если подключение к базе данных установлено
            conn.close() # Закрываем подключение


# Обработчик команды /start - выполняется, когда пользователь отправляет команду /start
@bot.message_handler(commands=["start"])
def start(msg):
    user_id = msg.from_user.id
    username = msg.from_user.username
    try:
        init_db()  # Инициализируем БД при старте
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO players (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        conn.commit() # Сохраняем изменения в базе данных
        # Отправляем приветственное сообщение с главной клавиатурой
        with open("Картинка_start.jpg", 'rb') as photo:
            bot.send_photo(msg.chat.id, photo)
        bot.send_message(msg.chat.id, "🎉 Приветствую тебя в LucasTeamEducationBot! \n Здесь ты можешь сыграть в такие игры как: \n 🔹Виселица\n 🔹Математический бой\n 🔹Верю - не верю\n  Также ты можешь сыграть в викторину на одну из тем на выбор:\n  🔸Математика\n  🔸История\n  🔸Литература\n Для подробной информации об играх используй /help. \n Чтобы начать играть в викторину используй /quiz.\n Чтобы начать игру используй /minigame .", reply_markup=create_main_keyboard())
    except sqlite3.Error as e: # Обрабатываем ошибки базы данных
        logging.error(f"Ошибка БД при старте: {e}") # Записываем ошибку в лог
    finally: # Этот блок выполняется всегда
        if conn: # Если подключение к базе данных установлено
            conn.close() # Закрываем подключение
    user_id = msg.from_user.id
    username = msg.from_user.username
    try:
        init_db()  # Инициализируем БД при старте
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO players (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        conn.commit() # Сохраняем изменения в базе данных
        # Отправляем приветственное сообщение с главной клавиатурой
        bot.send_message(msg.chat.id, "🎉 Добро пожаловать! Используйте /quiz для старта", reply_markup=create_main_keyboard())
    except sqlite3.Error as e: # Обрабатываем ошибки базы данных
        logging.error(f"Ошибка БД при старте: {e}") # Записываем ошибку в лог
    finally: # Этот блок выполняется всегда
        if conn: # Если подключение к базе данных установлено
            conn.close() # Закрываем подключение

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

# Обработчик команды /quiz - выполняется, когда пользователь отправляет команду /quiz
@bot.message_handler(commands=["quiz"])
def start_quiz(msg):
    bot.delete_state(msg.from_user.id, msg.chat.id) # Сбрасываем состояние пользователя
    # Отправляем сообщение с просьбой выбрать предмет и клавиатурой с предметами
    bot.send_message(msg.chat.id, "📚 Выберите предмет:", reply_markup=create_subject_keyboard())
    # Устанавливаем состояние пользователя в "выбор предмета"
    bot.set_state(msg.from_user.id, QuizStates.choose_subject, msg.chat.id)


@bot.message_handler(state=QuizStates.choose_subject) # Обработчик выбора предмета - выполняется, когда пользователь находится в состоянии выбора предмета
def handle_subject_selection(msg: Message):
    if msg.text.strip() == "🚪 Выход":  # Если пользователь нажал кнопку "Выход"
        bot.delete_state(msg.from_user.id, msg.chat.id) # Сбрасываем состояние
        bot.send_message(msg.chat.id, "🔙 Возврат в главное меню", reply_markup=create_main_keyboard()) # Возвращаемся в главное меню
        return # Прерываем выполнение функции


    subject_key = SUBJECT_MAP.get(msg.text) # Получаем ключ предмета из словаря SUBJECT_MAP
    if not subject_key: # Если ключ не найден (пользователь ввел неверный предмет)
        bot.send_message(msg.chat.id, "❌ Выберите предмет из списка!", reply_markup=create_subject_keyboard()) # Просим выбрать предмет из списка
        return # Прерываем выполнение функции

    try: # Начинаем блок обработки исключений
        conn = sqlite3.connect('quiz.db') # Подключаемся к базе данных
        cursor = conn.cursor() # Создаем курсор

        # Проверяем, есть ли вопросы по выбранному предмету
        cursor.execute('SELECT COUNT(*) FROM questions WHERE subject = ?', (subject_key,))
        count = cursor.fetchone()[0] # Получаем количество вопросов
        if count == 0: # Если вопросов нет
            bot.send_message(msg.chat.id, "⚠️ Вопросы временно отсутствуют", reply_markup=create_main_keyboard()) # Сообщаем об отсутствии вопросов
            bot.delete_state(msg.from_user.id, msg.chat.id) # Сбрасываем состояние
            return # Прерываем выполнение функции

        user_id = msg.from_user.id
        # Получаем рейтинг игрока
        cursor.execute('SELECT rating FROM players WHERE user_id = ?', (user_id,))
        player_rating = cursor.fetchone()[0]
        
        question = get_question(subject_key, user_id) # Получаем вопрос с учетом рейтинга
        if not question: # Если вопрос не найден
            raise ValueError("Ошибка загрузки вопроса") # Вызываем исключение

        markup = ReplyKeyboardMarkup(resize_keyboard=True) # Создаем клавиатуру с вариантами ответа
        for option in question['options']: # Перебираем варианты ответа
            markup.add(KeyboardButton(option)) # Добавляем кнопку для каждого варианта

        with bot.retrieve_data(msg.from_user.id, msg.chat.id) as data: # Получаем данные о пользователе
            data["correct_answer"] = question['correct_answer'] # Сохраняем правильный ответ
            data["subject"] = subject_key # Сохраняем выбранный предмет

        bot.send_message(msg.chat.id, question['question'], reply_markup=markup) # Отправляем вопрос с клавиатурой вариантов ответа
        bot.set_state(msg.from_user.id, QuizStates.answer, msg.chat.id) # Устанавливаем состояние пользователя в "ответ на вопрос"

    except (sqlite3.Error, ValueError) as e: # Обрабатываем ошибки
        logging.error(f"Ошибка: {e}", exc_info=True) # Записываем ошибку в лог
        bot.send_message(msg.chat.id, "❌ Системная ошибка", reply_markup=create_main_keyboard()) # Сообщаем об ошибке
        bot.delete_state(msg.from_user.id, msg.chat.id) # Сбрасываем состояние
    finally: # Выполняется всегда
        if conn: # Если подключение установлено
            conn.close() # Закрываем подключение


@bot.message_handler(state=QuizStates.answer) # Обработчик ответа на вопрос - выполняется, когда пользователь находится в состоянии ответа на вопрос
def handle_answer(msg: Message):
    try: # Начинаем блок обработки исключений
        if msg.text.startswith('/'): # Если сообщение начинается с / (команда)
            bot.process_new_messages([msg])  # Обрабатываем команду
            bot.delete_state(msg.from_user.id, msg.chat.id) # Сбрасываем состояние
            return # Выходим из функции

        logging.info(f"Получен ответ: {msg.text} от пользователя {msg.from_user.id} в состоянии {bot.get_state(msg.from_user.id, msg.chat.id)}") # Записываем в лог полученный ответ
        chat_id = msg.chat.id # Получаем ID чата
        user_id = msg.from_user.id # Получаем ID пользователя


        if msg.text.startswith("/"):  # Если сообщение - команда (не должно сюда попадать после первой проверки)
            return # Игнорируем

        if msg.text.strip() == "🚪 Выход": # Если пользователь нажал кнопку "Выход"
            bot.delete_state(user_id, chat_id) # Сбрасываем состояние
            bot.send_message(chat_id, "🔙 Возврат в главное меню", reply_markup=create_main_keyboard()) # Возвращаемся в главное меню
            return # Выходим из функции

        with bot.retrieve_data(user_id, chat_id) as data: # Получаем данные пользователя
            user_answer = msg.text.strip().lower() # Приводим ответ пользователя к нижнему регистру и убираем пробелы
            correct_answer = data["correct_answer"].strip().lower() # Приводим правильный ответ к нижнему регистру и убираем пробелы
            correct = user_answer == correct_answer # Сравниваем ответы

            # Формируем сообщение о результате
            if correct: # Если ответ верный
                result_message = "✅ Верно!"
            else: # Если ответ неверный
                result_message = f"❌ Неверно. Правильный ответ: {correct_answer}"

            conn = sqlite3.connect('quiz.db') # Подключаемся к базе данных
            cursor = conn.cursor() # Создаем курсор
            # Обновляем статистику пользователя в базе данных
            cursor.execute('''
                UPDATE players 
                SET correct_answers = correct_answers + ?, incorrect_answers = incorrect_answers + ? 
                WHERE user_id = ?
            ''', (int(correct), int(not correct), user_id))
            conn.commit() # Сохраняем изменения
            conn.close() # Закрываем подключение

            new_question = get_question(data["subject"]) # Получаем следующий вопрос

            if new_question: # Если есть следующий вопрос
                markup = create_options_keyboard(new_question['options']) # Создаем клавиатуру с вариантами ответа
                data["correct_answer"] = new_question['correct_answer']  # Сохраняем правильный ответ
                bot.send_message(chat_id, result_message) # Отправляем результат предыдущего вопроса
                bot.send_message(chat_id, new_question['question'], reply_markup=markup) # Отправляем следующий вопрос
            else: # Если вопросов больше нет
                bot.send_message(chat_id, result_message) # Отправляем результат последнего вопроса
                bot.send_message(chat_id, "🏁 Вопросы закончились!", reply_markup=create_main_keyboard()) # Сообщаем об окончании викторины
                bot.delete_state(user_id, chat_id) # Сбрасываем состояние

    except Exception as e: # Обрабатываем ошибки
        logging.error(f"Ошибка в handle_answer: {str(e)}", exc_info=True) # Записываем ошибку в лог
        bot.send_message(chat_id, "⚠️ Произошла ошибка. Попробуйте ещё раз.") # Сообщаем об ошибке



@bot.message_handler(commands=["score"]) # Обработчик команды /score - выполняется, когда пользователь отправляет команду /score
def show_score(msg):
    try: # Начинаем блок обработки исключений
        user_id = msg.from_user.id # Получаем ID пользователя
        conn = sqlite3.connect('quiz.db') # Подключаемся к базе данных
        cursor = conn.cursor() # Создаем курсор
        cursor.execute("SELECT correct_answers, incorrect_answers FROM players WHERE user_id = ?", (user_id,)) # Получаем статистику пользователя
        stats = cursor.fetchone() # Получаем результат запроса

        if stats: # Если статистика найдена
            correct, incorrect = stats # Разделяем полученные данные на правильные и неправильные ответы
            total = correct + incorrect # Вычисляем общее количество ответов
            response = f"📊 Ваша статистика:\n✅ Правильных ответов: {correct}\n❌ Неправильных ответов: {incorrect}\n🏆 Всего попыток: {total}" # Формируем сообщение со статистикой
        else: # Если статистика не найдена
            response = "❌ Ваша статистика не найдена" # Сообщаем об отсутствии статистики

        bot.send_message(msg.chat.id, response, reply_markup=create_main_keyboard()) # Отправляем сообщение со статистикой

    except sqlite3.Error as e: # Обрабатываем ошибки базы данных
        logging.error(f"Ошибка БД в show_score: {e}") # Записываем ошибку в лог
        bot.send_message(msg.chat.id, "⚠️ Ошибка загрузки статистики") # Сообщаем об ошибке
    finally: # Выполняется всегда
        if conn: # Если подключение установлено
            conn.close() # Закрываем подключение


bot.add_custom_filter(custom_filters.StateFilter(bot)) # Добавляем фильтр состояний
bot.infinity_polling(timeout=30, long_polling_timeout=30) # Запускаем бота