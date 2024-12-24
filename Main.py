from flask import Flask, render_template, request, redirect, session, url_for
import json

app = Flask(__name__,template_folder="templates")
app.secret_key = 'supersecretkey'

# Файлы хранения данных
USERS_FILE = 'users.json'
TASKS_FILE = 'tasks.json'

# Загрузка и сохранение данных
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []
    except Exception as e:
        print(f"Ошибка при загрузке пользователей: {e}")
        return []

def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении пользователей: {e}")

def load_tasks():
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_tasks(tasks):
    try:
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении задач: {e}")

# Данные
users = load_users()
tasks = load_tasks()

def login_required(func):
    """Проверка авторизации пользователя."""
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/tasks')
@login_required
def task_list():
    """Страница со списком всех заданий."""
    user = next((u for u in users if u['username'] == session['username']), None)
    if not user:
        return redirect(url_for('login'))
    return render_template('task_list.html', tasks=tasks, user=user)

@app.route('/task/<int:task_id>')
@login_required
def view_task(task_id):
    """Просмотр деталей задания."""
    task = next((task for task in tasks if task['id'] == task_id), None)
    if not task:
        return redirect(url_for('task_list'))
    return render_template('view_task.html', task=task)

@app.route('/task/<int:task_id>/start', methods=['GET', 'POST'])
@login_required
def start_task(task_id):
    """Пошаговое выполнение задания с проверкой ошибок и назначением дополнительных заданий."""
    task = next((t for t in tasks if t['id'] == task_id), None)
    if not task:
        return redirect(url_for('task_list'))

    user = next((u for u in users if u['username'] == session['username']), None)
    if not user or user['status'] != 'ученик':
        return redirect(url_for('dashboard'))

    # Инициализация данных
    session.modified = True
    if f"task_{task_id}_current_step" not in session:
        session[f"task_{task_id}_current_step"] = 0
        session[f"task_{task_id}_correct_answers"] = 0
        session[f"task_{task_id}_errors"] = []
        session[f"task_{task_id}_user_answers"] = []

    current_step = session[f"task_{task_id}_current_step"]

    # Если все шаги завершены
    if current_step >= len(task['steps']):
        total_steps = len(task['steps'])
        correct_answers = session.pop(f"task_{task_id}_correct_answers", 0)
        errors = session.pop(f"task_{task_id}_errors", [])
        session.pop(f"task_{task_id}_user_answers", [])
        session.pop(f"task_{task_id}_current_step", None)

        # Сохранение результатов выполнения задания
        if task_id not in user.get('completed_tasks', []):
            user.setdefault('statistics', {'completed_tasks': 0, 'errors': 0})
            user['statistics']['completed_tasks'] += 1
            user['statistics']['errors'] += len(errors)
            user['completed_tasks'] = user.get('completed_tasks', []) + [task_id]

        # Удаление задания из назначенных
        if task_id in user['tasks_assigned']:
            user['tasks_assigned'].remove(task_id)
            save_users(users)  # Сохраняем изменения в данных пользователя

        # Назначение дополнительного задания при наличии ошибок
        message = None
        if errors and task.get("similar_task_id"):
            similar_task_id = task["similar_task_id"]
            similar_task = next((t for t in tasks if t["id"] == similar_task_id), None)

            if similar_task:  # Проверка наличия похожего задания
                if similar_task_id not in user["tasks_assigned"]:
                    user["tasks_assigned"].append(similar_task_id)
                    save_users(users)
                    message = (
                        f"У вас были ошибки, поэтому вам назначено дополнительное задание: "
                        f"<strong>{similar_task['title']}</strong>. Проверьте список своих заданий."
                    )
                else:
                    print("Дополнительное задание уже назначено ранее.")  # Отладка

        # Отображение итоговой страницы
        return render_template(
            'task_completed.html',
            task=task,
            total_steps=total_steps,
            correct_answers=correct_answers,
            errors=errors,
            message=message  # Передаём сообщение в шаблон
        )

    # Проверка ответов пользователя
    error_message = None
    if request.method == 'POST':
        user_answer = request.form.get('answer', '').strip()
        correct_answer = task['steps'][current_step]['answer'].strip()

        # Сохраняем ответ пользователя
        session[f"task_{task_id}_user_answers"].append(user_answer)
        session.modified = True

        if user_answer.lower() == correct_answer.lower():
            session[f"task_{task_id}_correct_answers"] += 1
            session[f"task_{task_id}_current_step"] += 1
            return redirect(url_for('start_task', task_id=task_id))
        else:
            error = {
                "step_number": current_step + 1,
                "question": task['steps'][current_step]['question'],
                "user_answer": user_answer,
                "correct_answer": correct_answer
            }
            session[f"task_{task_id}_errors"].append(error)
            session.modified = True

            error_message = f"Неправильный ответ: {user_answer}. Попробуйте ещё раз!"

    # Если шаг не завершён, вывод страницы вопроса
    return render_template(
        'task_step.html',
        task=task,
        step=task['steps'][current_step],
        step_number=current_step + 1,
        error_message=error_message
    )


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = next((u for u in users if u['username'] == username), None)

        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['status']
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Неправильное имя пользователя или пароль.")
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = next((u for u in users if u['username'] == session['username']), None)
    if not user:
        return redirect(url_for('login'))

    if user['status'] == 'учитель':
        students = [u for u in users if u['status'] == 'ученик' and u['school'] == user['school']]
        
        students_by_class = {}
        for student in students:
            class_name = student['class']
            if class_name not in students_by_class:
                students_by_class[class_name] = []
            students_by_class[class_name].append(student)

        return render_template('dashboard.html',
                               user=user,
                               students_by_class=students_by_class,
                               tasks=tasks)

    if user['status'] == 'админ':
        return render_template('dashboard.html', user=user, users=users, tasks=tasks)

    return render_template('dashboard.html', user=user, tasks=tasks)

@app.route('/logout')
@login_required
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('home'))

@app.route('/assign-task', methods=['GET', 'POST'])
@login_required
def assign_task():
    if session['role'] not in ['учитель', 'админ']:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        task_id = int(request.form['task_id'])

        user = next((u for u in users if u['username'] == username and u['status'] == 'ученик'), None)
        if user:
            if task_id not in user['tasks_assigned']:
                user['tasks_assigned'].append(task_id)
                save_users(users)
                return redirect(url_for('dashboard'))

        return "Пользователь не найден или задание уже назначено."
    
    return render_template('assign_task.html', users=[u for u in users if u['status'] == 'ученик'], tasks=tasks)

@app.route('/add-task', methods=['GET', 'POST'])
@login_required
def add_task():
    if session['role'] not in ['учитель', 'админ']:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        steps_data = request.form['steps']

        steps = [{"question": step.split('|')[0].strip(), "answer": step.split('|')[1].strip()}
                 for step in steps_data.split('\n') if '|' in step]

        new_task = {"id": len(tasks) + 1, "title": title, "description": description, "steps": steps}
        tasks.append(new_task)
        save_tasks(tasks)
        return redirect(url_for('dashboard'))

    return render_template('add_task.html')

@app.route('/view-tasks/<username>')
@login_required
def view_tasks(username):
    user = next((u for u in users if u['username'] == username), None)
    if not user or user['status'] != 'ученик':
        return redirect(url_for('dashboard'))
    assigned_tasks = [task for task in tasks if task['id'] in user['tasks_assigned']]
    return render_template('view_tasks.html', student=user, tasks=assigned_tasks)

if __name__ == '__main__':
    app.run(debug=True)
