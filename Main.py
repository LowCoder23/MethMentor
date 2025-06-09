from flask import Flask, render_template, request, redirect, session, url_for
import json

app = Flask(__name__,template_folder="templates")
app.secret_key = 'supersecretkey'

# Файлы хранения данных
USERS_FILE = 'users.json'
TASKS_FILE = 'tasks.json'

def get_next_task_id(sections):
    max_id = 0
    for section in sections:
        for subsection in section['subsections']:
            for task in subsection['tasks']:
                if task['id'] > max_id:
                    max_id = task['id']
    return max_id + 1

def load_tasks():
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('sections', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_tasks(sections):
    try:
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'sections': sections}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении задач: {e}")

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
    """Запуск задачи с проверкой и фиксацией ошибок."""
    # Найти задание
    task = next((task for task in tasks if task['id'] == task_id), None)
    if not task:
        return redirect(url_for('task_list'))

    # Найти пользователя
    user = next((u for u in users if u['username'] == session['username']), None)
    if not user or user['status'] != 'ученик':
        return redirect(url_for('dashboard'))

    # Инициализация сессии
    session.modified = True  # Важно для обновления sессии!
    if f"task_{task_id}_current_step" not in session:
        print("Инициализация данных сессии")  # Отладка
        session[f"task_{task_id}_current_step"] = 0
        session[f"task_{task_id}_correct_answers"] = 0
        session[f"task_{task_id}_errors"] = []
        session[f"task_{task_id}_user_answers"] = []

    current_step = session[f"task_{task_id}_current_step"]

    # Если задания закончились
    if current_step >= len(task['steps']):
        total_steps = len(task['steps'])
        correct_answers = session.pop(f"task_{task_id}_correct_answers", 0)
        errors = session.pop(f"task_{task_id}_errors", [])
        user_answers = session.pop(f"task_{task_id}_user_answers", [])
        session.pop(f"task_{task_id}_current_step", None)

        # Сохранение статистики
        if task_id not in user.get('completed_tasks', []):
            user.setdefault('statistics', {'completed_tasks': 0, 'errors': 0})
            user['statistics']['completed_tasks'] += 1
            user['statistics']['errors'] += len(errors)
            user['completed_tasks'] = user.get('completed_tasks', []) + [task_id]
            save_users(users)

        print(f"Ошибки для передачи на итоговую страницу: {errors}")  # Отладка
        return render_template(
            'task_completed.html',
            task=task,
            total_steps=total_steps,
            correct_answers=correct_answers,
            errors=errors,
            user_answers=user_answers,
        )

    # Обработка ответа
    error_message = None
    if request.method == 'POST':
        user_answer = request.form.get('answer', '').strip()
        correct_answer = task['steps'][current_step]['answer'].strip()

        # Сохраняем ответ пользователя
        session[f"task_{task_id}_user_answers"].append(user_answer)
        session.modified = True

        if user_answer.lower() == correct_answer.lower():
            print(f"Правильный ответ на шаге {current_step + 1}")  # Отладка
            session[f"task_{task_id}_correct_answers"] += 1
            session[f"task_{task_id}_current_step"] += 1
            session.modified = True
            return redirect(url_for('start_task', task_id=task_id))
        else:
            # Сохраняем ошибку
            error = {
                "step_number": current_step + 1,
                "question": task['steps'][current_step]['question'],
                "user_answer": user_answer,
                "correct_answer": correct_answer
            }
            session[f"task_{task_id}_errors"].append(error)
            session.modified = True
            error_message = f"Неправильный ответ: {user_answer}"
            print(f"Ошибка добавлена: {error}")  # Отладка

    # Отображение текущего шага
    return render_template(
        'task_step.html',
        task=task,
        step=task['steps'][current_step],
        step_number=current_step + 1,
        error_message=error_message,
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

        user = next((u for u in users if u['username'] == username), None)
        if not user or user['status'] != 'ученик':
            return render_template('assign_task.html', 
                                 users=[u for u in users if u['status'] == 'ученик'], 
                                 tasks=tasks,
                                 error="Ученик не найден")

        if task_id in user.get('tasks_assigned', []):
            return render_template('assign_task.html', 
                                 users=[u for u in users if u['status'] == 'ученик'], 
                                 tasks=tasks,
                                 error="Это задание уже назначено ученику")

        if task_id not in [task['id'] for task in tasks]:
            return render_template('assign_task.html', 
                                 users=[u for u in users if u['status'] == 'ученик'], 
                                 tasks=tasks,
                                 error="Задание не найдено")

        if 'tasks_assigned' not in user:
            user['tasks_assigned'] = []
        user['tasks_assigned'].append(task_id)
        save_users(users)
        return redirect(url_for('dashboard'))
    
    return render_template('assign_task.html', 
                         users=[u for u in users if u['status'] == 'ученик'], 
                         tasks=tasks)

@app.route('/add-task', methods=['GET', 'POST'])
@login_required
def add_task():
    if session['role'] not in ['учитель', 'админ']:
        return redirect(url_for('dashboard'))

    sections = load_tasks()
    
    if request.method == 'POST':
        # ... существующий код ...
        
        section_id = int(request.form.get('section_id'))
        subsection_id = int(request.form.get('subsection_id'))
        
        section = next((s for s in sections if s['id'] == section_id), None)
        subsection = next((sub for sub in section['subsections'] 
                          if sub['id'] == subsection_id), None)
        
        if not section or not subsection:
            return render_template('add_task.html', 
                                 sections=sections,
                                 error="Раздел/подраздел не найден")
        
        new_task = {
            "id": get_next_task_id(sections),  # Нужно реализовать эту функцию
            # ... остальные поля задачи ...
        }
        
        subsection['tasks'].append(new_task)
        save_tasks(sections)
        return redirect(url_for('list_sections'))
    
    return render_template('add_task.html', sections=sections)

@app.route('/view-tasks/<username>')
@login_required
def view_tasks(username):
    user = next((u for u in users if u['username'] == username), None)
    if not user or user['status'] != 'ученик':
        return redirect(url_for('dashboard'))
    assigned_tasks = [task for task in tasks if task['id'] in user['tasks_assigned']]
    return render_template('view_tasks.html', student=user, tasks=assigned_tasks)

@app.route('/sections')
def list_sections():
    sections = load_tasks()
    return render_template('sections.html', sections=sections)

@app.route('/add-section', methods=['GET', 'POST'])
@login_required
def add_section():
    if session['role'] not in ['учитель', 'админ']:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        
        if not title:
            return render_template('add_section.html', error="Название раздела обязательно")
        
        sections = load_tasks()
        new_id = max([s['id'] for s in sections], default=0) + 1
        
        sections.append({
            "id": new_id,
            "title": title,
            "subsections": []
        })
        
        save_tasks(sections)
        return redirect(url_for('list_sections'))
    
    return render_template('add_section.html')

@app.route('/add-subsection', methods=['GET', 'POST'])
@login_required
def add_subsection():
    if session['role'] not in ['учитель', 'админ']:
        return redirect(url_for('dashboard'))

    sections = load_tasks()
    
    if request.method == 'POST':
        section_id = int(request.form.get('section_id'))
        title = request.form.get('title', '').strip()
        
        if not title:
            return render_template('add_subsection.html', 
                                 sections=sections,
                                 error="Название подраздела обязательно")
        
        section = next((s for s in sections if s['id'] == section_id), None)
        if not section:
            return render_template('add_subsection.html', 
                                 sections=sections,
                                 error="Раздел не найден")
        
        new_id = max([sub['id'] for sub in section['subsections']], default=0) + 1
        
        section['subsections'].append({
            "id": new_id,
            "title": title,
            "tasks": []
        })
        
        save_tasks(sections)
        return redirect(url_for('list_sections'))
    
    return render_template('add_subsection.html', sections=sections)

if __name__ == '__main__':
    app.run(debug=True)
