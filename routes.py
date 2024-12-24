@app.route('/add-task', methods=['GET', 'POST'])
def add_task():
    if 'username' in session and session.get('role') == 'teacher':
        if request.method == 'POST':
            task_title = request.form.get('title')
            task_description = request.form.get('description')
            steps_str = request.form.get('steps')
            
            # Проверяем, получены ли данные
            if task_title and task_description and steps_str:
                # Преобразование шагов в список
                steps = [
                    {
                        'question': step.split('|')[0].strip(),
                        'answer': step.split('|')[1].strip()
                    }
                    for step in steps_str.split('\n') if '|' in step
                ]

                # Проверяем, есть ли шаги
                if steps:
                    tasks.append({
                        'id': len(tasks) + 1,
                        'title': task_title,
                        'description': task_description,
                        'steps': steps
                    })
                    # Отладка
                    print(f"Добавлено задание: {tasks[-1]}")

                    # Перенаправление на ту же страницу после добавления
                    return redirect(url_for('add_task'))
        
        # Переход к странице с формой для добавления задач
        return render_template('add_task.html', tasks=tasks)
    return redirect(url_for('login'))
