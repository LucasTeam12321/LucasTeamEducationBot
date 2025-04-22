from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import logging
import random
import json
from werkzeug.security import generate_password_hash, check_password_hash

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Замените на реальный секретный ключ

# Словарь предметов
SUBJECT_MAP = {
    "Математика": "math",
    "История": "history",
    "Литература": "literature",
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
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

# Функция для создания клавиатур (теперь это будут кнопки в HTML)
def get_subjects():
    return list(SUBJECT_MAP.keys())

# Функция для получения вопроса
def get_question(subject_key, user_id):
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        print(f"User ID in get_question: {user_id}")  # Отладочная печать user_id

        cursor.execute("SELECT grade FROM players WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        logging.info(f"Результат запроса для user_id {user_id}: {result}")

        if result and result[0] is not None:  # Проверка на None и пустой результат
            player_grade = result[0]
            min_difficulty = max(1, int(player_grade - 1))
            max_difficulty = min(11, int(player_grade + 1))

            cursor.execute('''
                SELECT id, question, correct_answer, options, explanation, link, difficulty
                FROM questions
                WHERE subject = ? AND difficulty BETWEEN ? AND ?
                ORDER BY RANDOM() LIMIT 1
            ''', (subject_key, min_difficulty, max_difficulty))
            question_data = cursor.fetchone()

            if question_data:
                q_id, question, correct_answer, options_str, explanation, link, difficulty = question_data
                try:
                    options = json.loads(options_str)
                except json.JSONDecodeError:
                    options = options_str.split(',')
                    options = [opt.strip() for opt in options]

                if correct_answer not in options:
                    options.append(correct_answer)
                random.shuffle(options)
                return {
                    "id": q_id,
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
            # Обработка случая, когда пользователь не найден или grade is NULL
            logging.warning(f"Не найдена оценка или пользователь {user_id}. Используется значение по умолчанию.")
            min_difficulty = 4  # Для оценки 5.0
            max_difficulty = 6  # Для оценки 5.0

            cursor.execute('''
                SELECT id, question, correct_answer, options, explanation, link, difficulty
                FROM questions
                WHERE subject = ? AND difficulty BETWEEN ? AND ?
                ORDER BY RANDOM() LIMIT 1
            ''', (subject_key, min_difficulty, max_difficulty))
            question_data = cursor.fetchone()

            if question_data:
                q_id, question, correct_answer, options_str, explanation, link, difficulty = question_data
                try:
                    options = json.loads(options_str)
                except json.JSONDecodeError:
                    options = options_str.split(',')
                    options = [opt.strip() for opt in options]

                if correct_answer not in options:
                    options.append(correct_answer)
                random.shuffle(options)
                return {
                    "id": q_id,
                    "question": question,
                    "correct_answer": correct_answer,
                    "options": options,
                    "explanation": explanation,
                    "link": link,
                    "difficulty": difficulty
                }
            else:
                return None


    except sqlite3.Error as e:
        logging.error(f"Ошибка БД в get_question: {e}")
        return None
    finally:
        if conn:
            conn.close()
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
                SELECT id, question, correct_answer, options, explanation, link, difficulty
                FROM questions
                WHERE subject = ? AND difficulty BETWEEN ? AND ?
                ORDER BY RANDOM() LIMIT 1
            ''', (subject_key, min_difficulty, max_difficulty))
            question_data = cursor.fetchone()

            if question_data:
                q_id, question, correct_answer, options_str, explanation, link, difficulty = question_data
                try:
                    options = json.loads(options_str)
                except json.JSONDecodeError:
                    options = options_str.split(',')
                    options = [opt.strip() for opt in options]

                if correct_answer not in options:
                    options.append(correct_answer)
                random.shuffle(options)
                return {
                    "id": q_id,
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

# Обновление статистики пользователя
def update_user_stats(user_id, is_correct):
    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        
        if is_correct:
            cursor.execute("UPDATE players SET correct_answers = correct_answers + 1 WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("UPDATE players SET incorrect_answers = incorrect_answers + 1 WHERE user_id = ?", (user_id,))
        
        # Обновляем оценку пользователя на основе его успехов
        cursor.execute('''
            UPDATE players SET grade = 
            CASE 
                WHEN (correct_answers + incorrect_answers) = 0 THEN 5.0
                ELSE 1.0 + 10.0 * correct_answers / (correct_answers + incorrect_answers)
            END
            WHERE user_id = ?
        ''', (user_id,))
        
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Ошибка БД при обновлении статистики: {e}")
    finally:
        if conn:
            conn.close()

# Маршруты Flask
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            conn = sqlite3.connect('quiz.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, password FROM players WHERE username = ?", (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                flash('Вы успешно вошли в систему!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        except sqlite3.Error as e:
            logging.error(f"Ошибка БД при входе: {e}")
            flash('Произошла ошибка при входе', 'danger')
        finally:
            if conn:
                conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        try:
            conn = sqlite3.connect('quiz.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO players (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Это имя пользователя уже занято', 'danger')
        except sqlite3.Error as e:
            logging.error(f"Ошибка БД при регистрации: {e}")
            flash('Произошла ошибка при регистрации', 'danger')
        finally:
            if conn:
                conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('index'))
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect('quiz.db')
        cursor = conn.cursor()
        cursor.execute("SELECT correct_answers, incorrect_answers, grade FROM players WHERE user_id = ?", (session['user_id'],))
        stats = cursor.fetchone()
        print(f"Session: {session}")  # Отладочный вывод - печать всей сессии
        print(f"Stats from DB: {stats}") # Отладочный вывод - печать результата запроса к БД

        if stats:
            correct, incorrect, grade = stats
            total = correct + incorrect
            accuracy = (correct / total * 100) if total > 0 else 0
        else:
            # Здесь обрабатываем случай, когда пользователь не найден
            correct = incorrect = total = accuracy = 0
            grade = 5.0  # Или другое значение по умолчанию

        # Округляем grade только если он не None.  Если None, используем значение по умолчанию
        grade = round(grade, 1) if grade is not None else 5.0

    except sqlite3.Error as e:
        logging.error(f"Ошибка БД в dashboard: {e}")
        flash('Ошибка загрузки статистики', 'danger')
        return redirect(url_for('index'))  # Redirect to index in case of error
    finally:
        if conn:
            conn.close()

    return render_template('dashboard.html',
                         username=session.get('username'),  # Use .get to avoid KeyError if username is missing
                         correct=correct,
                         incorrect=incorrect,
                         total=total,
                         accuracy=round(accuracy, 1),
                         grade=grade,  # Already rounded
                         subjects=get_subjects())


@app.route('/quiz/<subject>', methods=['GET', 'POST'])
def quiz(subject):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    subject_key = SUBJECT_MAP.get(subject)
    if not subject_key:
        flash('Неверный предмет', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # ... (обработка ответа пользователя)
        # ... (flash messages о правильности ответа)
        pass  #  Не делаем redirect после ответа

    question = get_question(subject_key, session['user_id'])

    if not question:  # Если вопросов нет, только тогда делаем redirect
        flash('Вопросы по этому предмету закончились. Попробуйте позже.', 'warning')
        return redirect(url_for('dashboard'))

    return render_template('quiz.html',
                         subject=subject,
                         question=question['question'],
                         question_id=question['id'],
                         options=question['options'])


    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    subject_key = SUBJECT_MAP.get(subject)
    if not subject_key:
        flash('Неверный предмет', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Обработка ответа пользователя
        question_id = request.form.get('question_id')
        user_answer = request.form.get('answer')
        
        try:
            conn = sqlite3.connect('quiz.db')
            cursor = conn.cursor()
            cursor.execute("SELECT correct_answer, explanation, link FROM questions WHERE id = ?", (question_id,))
            question_data = cursor.fetchone()
            
            if question_data:
                correct_answer, explanation, link = question_data
                is_correct = (user_answer == correct_answer)
                update_user_stats(session['user_id'], is_correct)
                
                flash('✅ Правильно!' if is_correct else f'❌ Неправильно! Правильный ответ: {correct_answer}', 
                      'success' if is_correct else 'danger')
                
                if explanation:
                    flash(f'🤓 Пояснение: {explanation}', 'info')
                if link:
                    flash(f'🔗 Дополнительный материал: {link}', 'info')
        except sqlite3.Error as e:
            logging.error(f"Ошибка БД при проверке ответа: {e}")
            flash('Ошибка при проверке ответа', 'danger')
        finally:
            if conn:
                conn.close()
    
    # Получаем новый вопрос
    question = get_question(subject_key, session['user_id'])
    if not question:
        flash('Вопросы по этому предмету закончились. Попробуйте позже.', 'warning')
        return redirect(url_for('dashboard'))
    
    return render_template('quiz.html', 
                         subject=subject,
                         question=question['question'],
                         question_id=question['id'],
                         options=question['options'])

@app.route('/help')
def help():
    return render_template('help.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)