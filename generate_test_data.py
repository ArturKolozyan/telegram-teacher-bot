"""
Генерация тестовых данных для разработки
"""
import json
import os
import random
from datetime import datetime, timedelta

DATA_DIR = 'data'

# Имена для генерации
FIRST_NAMES = [
    'Александр', 'Дмитрий', 'Максим', 'Сергей', 'Андрей', 'Алексей', 'Артём', 'Илья', 'Кирилл', 'Михаил',
    'Анна', 'Мария', 'Елена', 'Ольга', 'Татьяна', 'Наталья', 'Ирина', 'Екатерина', 'Светлана', 'Юлия',
    'Иван', 'Павел', 'Николай', 'Владимир', 'Егор'
]

LAST_NAMES = [
    'Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев', 'Соколов', 'Михайлов', 'Новиков',
    'Фёдоров', 'Морозов', 'Волков', 'Алексеев', 'Лебедев', 'Семёнов', 'Егоров', 'Павлов', 'Козлов', 'Степанов',
    'Николаев', 'Орлов', 'Андреев', 'Макаров', 'Никитин'
]

# Временные слоты для уроков
TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00']

# Цены
PRICES = [1000, 1200, 1500, 1800, 2000]

def generate_students(count=25):
    """Генерация учеников"""
    students = {}
    
    for i in range(count):
        user_id = 1000000 + i
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        username = f"user{i+1}"
        timezone_offset = 3  # МСК
        lesson_price = random.choice(PRICES)
        
        students[str(user_id)] = {
            'user_id': user_id,
            'name': name,
            'username': username,
            'timezone_offset': timezone_offset,
            'lesson_price': lesson_price,
            'registered_at': datetime.now().isoformat()
        }
    
    return students

def generate_recurring_schedule(students):
    """Генерация шаблонов расписания (2 урока в неделю на ученика)"""
    recurring = {}
    used_slots = set()
    
    for user_id, student in students.items():
        # Выбираем 2 случайных дня недели (0-6 = пн-вс)
        days = random.sample(range(7), 2)
        
        for day in days:
            # Ищем свободный слот
            attempts = 0
            while attempts < 20:
                time = random.choice(TIME_SLOTS)
                slot_key = f"{day}_{time}"
                
                if slot_key not in used_slots:
                    used_slots.add(slot_key)
                    
                    template_id = f"{day}_{time}_{user_id}"
                    recurring[template_id] = {
                        'id': template_id,
                        'student_id': int(user_id),
                        'day_of_week': day,
                        'time': time,
                        'price': student['lesson_price'],
                        'active': True,
                        'created_at': datetime.now().isoformat()
                    }
                    break
                
                attempts += 1
    
    return recurring

def generate_lessons_from_templates(recurring, year, month):
    """Генерация уроков из шаблонов на месяц"""
    from calendar import monthrange
    
    lessons = {}
    
    first_day = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    
    for day in range(1, last_day + 1):
        date = datetime(year, month, day)
        day_of_week = date.weekday()
        
        date_str = date.strftime('%Y-%m-%d')
        
        # Ищем шаблоны для этого дня недели
        for template in recurring.values():
            if template['day_of_week'] == day_of_week:
                lesson_id = f"{date_str}_{template['time']}_{template['student_id']}"
                
                # Случайно отмечаем некоторые прошедшие уроки как выполненные
                is_past = date < datetime.now()
                completed = is_past and random.random() < 0.9  # 90% прошедших уроков выполнены
                
                lessons[lesson_id] = {
                    'id': lesson_id,
                    'student_id': template['student_id'],
                    'date': date_str,
                    'time': template['time'],
                    'price': template['price'],
                    'completed': completed,
                    'from_template': template['id'],
                    'created_at': datetime.now().isoformat()
                }
                
                if completed:
                    lessons[lesson_id]['completed_at'] = date.isoformat()
    
    return lessons

def main():
    """Генерация всех тестовых данных"""
    print("🔄 Генерация тестовых данных...")
    
    # Создаем папку data если её нет
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # Генерируем учеников
    print("👥 Генерация 25 учеников...")
    students = generate_students(25)
    
    with open(os.path.join(DATA_DIR, 'students.json'), 'w', encoding='utf-8') as f:
        json.dump(students, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Создано {len(students)} учеников")
    
    # Генерируем шаблоны расписания
    print("📅 Генерация шаблонов расписания (2 урока в неделю на ученика)...")
    recurring = generate_recurring_schedule(students)
    
    with open(os.path.join(DATA_DIR, 'recurring_schedule.json'), 'w', encoding='utf-8') as f:
        json.dump(recurring, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Создано {len(recurring)} шаблонов")
    
    # Генерируем уроки на текущий месяц
    now = datetime.now()
    print(f"📚 Генерация уроков на {now.strftime('%B %Y')}...")
    lessons_current = generate_lessons_from_templates(recurring, now.year, now.month)
    
    # Генерируем уроки на следующий месяц
    next_month = now.month + 1
    next_year = now.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    print(f"📚 Генерация уроков на {datetime(next_year, next_month, 1).strftime('%B %Y')}...")
    lessons_next = generate_lessons_from_templates(recurring, next_year, next_month)
    
    # Объединяем уроки
    all_lessons = {**lessons_current, **lessons_next}
    
    with open(os.path.join(DATA_DIR, 'lessons.json'), 'w', encoding='utf-8') as f:
        json.dump(all_lessons, f, ensure_ascii=False, indent=2)
    
    completed_count = sum(1 for l in all_lessons.values() if l['completed'])
    print(f"✅ Создано {len(all_lessons)} уроков ({completed_count} выполнено, {len(all_lessons) - completed_count} запланировано)")
    
    # Создаем пустые файлы для других данных
    for filename in ['notifications.json', 'homework_responses.json']:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    # Создаем настройки
    settings = {
        'admin_timezone': 3,
        'reminder_minutes_before': 60,
        'homework_check_minutes_before': 5,
        'admin_daily_reminder_time': '08:00',
        'default_lesson_price': 1000
    }
    
    with open(os.path.join(DATA_DIR, 'settings.json'), 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    
    print("\n✨ Тестовые данные успешно созданы!")
    print(f"📊 Статистика:")
    print(f"   - Учеников: {len(students)}")
    print(f"   - Шаблонов: {len(recurring)}")
    print(f"   - Уроков: {len(all_lessons)}")
    print(f"   - Выполнено: {completed_count}")
    print(f"   - Запланировано: {len(all_lessons) - completed_count}")
    
    # Подсчет дохода
    completed_income = sum(l['price'] for l in all_lessons.values() if l['completed'])
    expected_income = sum(l['price'] for l in all_lessons.values() if not l['completed'])
    
    print(f"\n💰 Доход:")
    print(f"   - За выполненные: {completed_income:,} ₽")
    print(f"   - Ожидаемый: {expected_income:,} ₽")
    print(f"   - Всего: {completed_income + expected_income:,} ₽")

if __name__ == '__main__':
    main()
