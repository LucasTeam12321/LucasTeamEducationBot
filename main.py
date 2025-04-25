from random import choice, randint
import sqlite3
import telebot
from telebot import custom_filters
from telebot.states import StatesGroup, State
from telebot.storage import StateMemoryStorage
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Message

# Конфигурация
API_TOKEN = '7748202816:AAGhyNGFDAp940tEW_Bo4okMzopmYQKoQmM'

# Глобальная переменная для хранения состояния игры
user_data = {}

# Инициализация бота
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(API_TOKEN, state_storage=state_storage, use_class_middlewares=True)


# Определение состояний
class QuizStates(StatesGroup):
    question = State()
    answer = State()
    guess_number = State()  # Новое состояние для игры "Угадай число"


# Функция для создания основной клавиатуры
def create_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    # Первая строка: /score и /leaderboard
    markup.row(KeyboardButton('/score'), KeyboardButton('/leaderboard'))
    # Вторая строка: /quiz
    markup.row(KeyboardButton('/quiz'))
    markup.row(KeyboardButton('/minigame1'), KeyboardButton('/minigame2'))  # Добавляем обе мини-игры
    return markup


# Функция для создания клавиатуры с вариантами ответов
def create_options_keyboard(options):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for option in options:
        markup.add(KeyboardButton(option))
    return markup


# Функция для создания клавиатуры с кнопками для игры
def create_tic_tac_toe_keyboard():
    cmds_keyboard = ReplyKeyboardMarkup()
    cmds_keyboard.row(KeyboardButton("0 0"), KeyboardButton("0 1"), KeyboardButton("0 2"))
    cmds_keyboard.row(KeyboardButton("1 0"), KeyboardButton("1 1"), KeyboardButton("1 2"))
    cmds_keyboard.row(KeyboardButton("2 0"), KeyboardButton("2 1"), KeyboardButton("2 2"))
    cmds_keyboard.add(KeyboardButton("/stop"))
    return cmds_keyboard


# Функция для получения случайного вопроса из базы данных
def get_random_question():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    cursor.execute('SELECT question, options, correct_answer FROM questions ORDER BY RANDOM() LIMIT 1')
    row = cursor.fetchone()

    conn.close()

    if row:
        question, options_str, correct_answer = row
        options = options_str.split(',')  # Преобразуем строку в список
        return {
            "question": question,
            "options": options,
            "correct_answer": correct_answer
        }
    return None


# Функция для получения статистики игрока
def get_player_stats(user_id):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    cursor.execute('SELECT correct_answers, incorrect_answers, score, minigames_played FROM players WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            "correct_answers": row[0],
            "incorrect_answers": row[1],
            "score": row[2],
            "minigames_played": row[3]
        }
    return {
        "correct_answers": 0,
        "incorrect_answers": 0,
        "score": 0,
        "minigames_played": 0
    }


# Функция для обновления статистики игрока
def update_player_stats(user_id, username=None, correct_answers=0, incorrect_answers=0, score=0, minigames_played=0):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    # Проверяем, существует ли игрок в базе данных
    cursor.execute('SELECT user_id FROM players WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        # Обновляем существующую запись
        cursor.execute('''
            UPDATE players
            SET correct_answers = correct_answers + ?,
                incorrect_answers = incorrect_answers + ?,
                score = score + ?,
                minigames_played = minigames_played + ?
            WHERE user_id = ?
        ''', (correct_answers, incorrect_answers, score, minigames_played, user_id))
    else:
        # Создаем новую запись
        cursor.execute('''
            INSERT INTO players (user_id, username, correct_answers, incorrect_answers, score, minigames_played)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, correct_answers, incorrect_answers, score, minigames_played))

    conn.commit()
    conn.close()


# Функция для получения топа игроков
def get_leaderboard():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    # Выбираем топ-10 игроков по количеству правильных ответов
    cursor.execute('''
        SELECT user_id, score
        FROM players
        ORDER BY score DESC
        LIMIT 10
    ''')
    rows = cursor.fetchall()

    conn.close()

    return rows


# Функция для получения состояния доски в виде строки
def get_board_state_3t(board):
    return "\n".join("".join(board[i]) for i in range(3))


# Функция для проверки, закончилась ли игра
def is_game_over_3t(board):
    for player in ["✖️", "⭕"]:
        if [player] * 3 in board:
            return player
        if [player] * 3 in [[board[row][col] for row in range(3)] for col in range(3)]:
            return player
        if [player] * 3 in [[board[i][i] for i in range(3)], [board[i][2 - i] for i in range(3)]]:
            return player
    if "🔲" not in get_board_state_3t(board):
        return "🔲"


# Функция для отправки сообщения о победе
def send_win_message_3t(winner, user_id):
    if winner == "🔲":
        bot.send_message(user_id, "Все клетки закончились. Ничья!", reply_markup=create_main_keyboard())
    elif winner == "⭕":
        bot.send_message(user_id, "Вы выиграли! 🎉 +1 очко!", reply_markup=create_main_keyboard())
        update_player_stats(user_id, score=1)  # Начисляем 1 очков и увеличиваем счётчик мини-игр
    else:
        bot.send_message(user_id, "Бот выиграл! 😢", reply_markup=create_main_keyboard())
    update_player_stats(user_id, minigames_played=1)  # Увеличиваем счётчик мини-игр в любом случае

# Функция для получения хода бота
def get_move_3t(board):
    available_moves = []
    for row in range(3):
        for col in range(3):
            if board[row][col] == "🔲":
                available_moves.append((row, col))
    return choice(available_moves)


# Обработчик команды /start
@bot.message_handler(commands=["start"])
def start(msg):
    # Инициализируем счетчики очков
    user_id = msg.from_user.id
    stats = get_player_stats(user_id)

    with bot.retrieve_data(user_id, msg.chat.id) as data:
        data["correct_answers"] = stats["correct_answers"]
        data["incorrect_answers"] = stats["incorrect_answers"]

    bot.send_message(msg.chat.id, "Приветствую в мире знаний! \n Я твой виртуальный помощник, созданный увлечь тебя "
                                  "захватывающим квизом. Давай проверим твои знания и расширим горизонты вместе! ✨",
                     reply_markup=create_main_keyboard())


# Обработчик команды /score
@bot.message_handler(commands=["score"])
def show_score(msg):
    user_id = msg.from_user.id
    stats = get_player_stats(user_id)

    # Отправляем статистику пользователю
    bot.send_message(msg.chat.id, f"📊 Ваша статистика:\n"
                                  f"✅ Правильных ответов: {stats['correct_answers']}\n"
                                  f"❌ Неправильных ответов: {stats['incorrect_answers']}\n"
                                  f"🏆 Очков: {stats['score']}\n"
                                  f"🎮 Сыграно мини-игр: {stats['minigames_played']}",
                     reply_markup=create_main_keyboard())


# Обработчик команды /leaderboard
@bot.message_handler(commands=["leaderboard"])
def show_leaderboard(msg):
    # Получаем топ игроков
    leaderboard = get_leaderboard()

    if not leaderboard:
        bot.send_message(msg.chat.id, "Топ игроков пока пуст. Станьте первым! 🏆",
                         reply_markup=create_main_keyboard())
        return

    # Формируем сообщение с топом игроков
    leaderboard_message = "🏆 Топ игроков:\n"
    for i, (user_id, correct_answers) in enumerate(leaderboard, start=1):
        try:
            user = bot.get_chat_member(user_id, user_id).user
            username = user.username if user.username else user.first_name
        except Exception:
            username = f"Пользователь {user_id}"

        leaderboard_message += f"{i}. {username}: {correct_answers} ✅\n"

    bot.send_message(msg.chat.id, leaderboard_message,
                     reply_markup=create_main_keyboard())


# Обработчик команды /quiz
@bot.message_handler(commands=["quiz"])
def start_quiz(msg):
    user_id = msg.from_user.id
    bot.set_state(user_id, QuizStates.question, msg.chat.id)
    ask_question(msg)


# Обработчик команды /reset
@bot.message_handler(commands=["reset"])
def reset_score(msg):
    user_id = msg.from_user.id

    # Сбрасываем счетчики очков в базе данных
    update_player_stats(user_id, -get_player_stats(user_id)["correct_answers"],
                        -get_player_stats(user_id)["incorrect_answers"])

    # Сбрасываем счетчики очков в состоянии
    with bot.retrieve_data(user_id, msg.chat.id) as data:
        data["correct_answers"] = 0
        data["incorrect_answers"] = 0

    bot.send_message(msg.chat.id, "🔄 Счетчик очков сброшен. Начнем заново!",
                     reply_markup=create_main_keyboard())


@bot.message_handler(commands=["minigame1"])
def start_tic_tac_toe(message: Message):
    user_id = message.from_user.id

    # Инициализация игрового поля
    user_data[user_id] = [["🔲"] * 3 for _ in range(3)]

    # Первый ход бота
    row, col = get_move_3t(user_data[user_id])
    user_data[user_id][row][col] = "✖️"

    # Создание клавиатуры для игры
    cmds_keyboard = create_tic_tac_toe_keyboard()

    # Отправка начального состояния доски
    bot.send_message(user_id, get_board_state_3t(user_data[user_id]), reply_markup=cmds_keyboard)

    # Установка состояния игры
    bot.set_state(user_id, "playing_tic_tac_toe", message.chat.id)


@bot.message_handler(commands=["minigame2"])
def start_guess_number(message: Message):
    user_id = message.from_user.id

    # Загадываем число от 1 до 100
    secret_number = randint(1, 100)
    attempts_left = 8  # Количество попыток

    # Сохраняем данные игры в состоянии пользователя
    with bot.retrieve_data(user_id, message.chat.id) as data:
        data["secret_number"] = secret_number
        data["attempts_left"] = attempts_left

    # Отправляем сообщение с правилами игры
    bot.send_message(user_id, "🎮 Игра 'Угадай число'!\n"
                              "Я загадал число от 1 до 100. У тебя есть 8 попыток, чтобы угадать его.\n"
                              "Введи число и попробуй угадать!",
                     reply_markup=ReplyKeyboardRemove())

    # Устанавливаем состояние игры
    bot.set_state(user_id, QuizStates.guess_number, message.chat.id)


# Функция для задания вопроса
def ask_question(msg):
    user_id = msg.from_user.id
    chat_id = msg.chat.id

    # Получаем случайный вопрос из базы данных
    question_data = get_random_question()
    if not question_data:
        bot.send_message(chat_id, "Вопросы закончились! 🎉",
                         reply_markup=create_main_keyboard())
        return

    question = question_data["question"]
    options = question_data["options"]
    correct_answer = question_data["correct_answer"]

    # Сохраняем правильный ответ в состоянии пользователя
    with bot.retrieve_data(user_id, chat_id) as data:
        data["correct_answer"] = correct_answer

    # Создаем клавиатуру с вариантами ответов
    markup = create_options_keyboard(options)

    bot.send_message(chat_id, question, reply_markup=markup)
    bot.set_state(user_id, QuizStates.answer, chat_id)


# Обработчик ответа на вопрос
@bot.message_handler(state=QuizStates.answer)
def check_answer(msg):
    user_id = msg.from_user.id
    chat_id = msg.chat.id

    with bot.retrieve_data(user_id, chat_id) as data:
        correct_answer = data["correct_answer"]

    if msg.text == correct_answer:
        # Увеличиваем счетчик правильных ответов и начисляем 1 очко
        update_player_stats(user_id, correct_answers=1, score=1)  # Добавлено score=1
        bot.send_message(chat_id, "Правильно! 🎉 +1 очко!", reply_markup=create_main_keyboard())
    else:
        # Увеличиваем счетчик неправильных ответов
        update_player_stats(user_id, incorrect_answers=1)
        bot.send_message(chat_id, f"Неправильно. Правильный ответ: {correct_answer}",
                         reply_markup=create_main_keyboard())

    # Задаем следующий вопрос
    ask_question(msg)


@bot.message_handler(func=lambda message: bot.get_state(message.from_user.id, message.chat.id) == "playing_tic_tac_toe")
def handle_tic_tac_toe_move(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == "/stop":
        bot.send_message(user_id, "Игра остановлена. Спасибо за игру!", reply_markup=create_main_keyboard())
        bot.delete_state(user_id, chat_id)
        return

    try:
        row, col = map(int, message.text.split())
        if user_data[user_id][row][col] != "🔲":
            bot.send_message(user_id, "Невозможный ход. Попробуйте снова.", reply_markup=create_tic_tac_toe_keyboard())
            return

        # Ход пользователя
        user_data[user_id][row][col] = "⭕"

        # Проверка на победу пользователя
        winner = is_game_over_3t(user_data[user_id])
        if winner:
            bot.send_message(user_id, get_board_state_3t(user_data[user_id]))
            send_win_message_3t(winner, user_id)
            bot.delete_state(user_id, chat_id)
            return

        # Ход бота
        row, col = get_move_3t(user_data[user_id])
        user_data[user_id][row][col] = "✖️"

        # Проверка на победу бота
        winner = is_game_over_3t(user_data[user_id])
        if winner:
            bot.send_message(user_id, get_board_state_3t(user_data[user_id]))
            send_win_message_3t(winner, user_id)
            bot.delete_state(user_id, chat_id)
            return

        # Отправка обновленного состояния доски
        bot.send_message(user_id, get_board_state_3t(user_data[user_id]), reply_markup=create_tic_tac_toe_keyboard())

    except Exception as e:
        print(e)
        bot.send_message(user_id, "Некорректный ввод. Введите координаты в формате '0 0'.",
                         reply_markup=create_tic_tac_toe_keyboard())

@bot.message_handler(state=QuizStates.guess_number)
def handle_guess_number(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    with bot.retrieve_data(user_id, chat_id) as data:
        secret_number = data["secret_number"]
        attempts_left = data["attempts_left"]

    try:
        guess = int(message.text)  # Преобразуем введённое значение в число

        if guess < 1 or guess > 100:
            bot.send_message(user_id, "Введи число от 1 до 100!")
            return

        attempts_left -= 1  # Уменьшаем количество оставшихся попыток

        if guess == secret_number:
            # Пользователь угадал число
            bot.send_message(user_id, f"🎉 Поздравляю! Ты угадал число {secret_number} за {8 - attempts_left} попыток! +5 очков!",
                             reply_markup=create_main_keyboard())
            update_player_stats(user_id, score=5, minigames_played=1)  # Начисляем 5 очков и увеличиваем счётчик мини-игр
            bot.delete_state(user_id, chat_id)  # Завершаем игру
            return

        if attempts_left == 0:
            # Попытки закончились
            bot.send_message(user_id, f"😢 К сожалению, попытки закончились. Я загадал число {secret_number}.",
                             reply_markup=create_main_keyboard())
            update_player_stats(user_id, minigames_played=1)  # Увеличиваем счётчик мини-игр
            bot.delete_state(user_id, chat_id)  # Завершаем игру
            return

        # Подсказка пользователю
        if guess < secret_number:
            bot.send_message(user_id, f"⬆️ Загаданное число больше. Осталось попыток: {attempts_left}")
        else:
            bot.send_message(user_id, f"⬇️ Загаданное число меньше. Осталось попыток: {attempts_left}")

        # Обновляем количество оставшихся попыток в состоянии
        with bot.retrieve_data(user_id, chat_id) as data:
            data["attempts_left"] = attempts_left

    except ValueError:
        # Если пользователь ввёл не число
        bot.send_message(user_id, "Пожалуйста, введи число от 1 до 100.")
        return  # Прерываем выполнение функции, чтобы не уменьшать attempts_left


# Обработчик неизвестных команд
@bot.message_handler(func=lambda message: True)
def error_message(message):
    bot.send_message(message.from_user.id, "Я вас не понял🤷‍♀️",
                     reply_markup=create_main_keyboard())


# Регистрируем фильтр состояний
bot.add_custom_filter(custom_filters.StateFilter(bot))

# Запуск бота
bot.infinity_polling()
