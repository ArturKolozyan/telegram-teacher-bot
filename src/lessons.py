"""
Работа с уроками (новая система на основе дат)
"""
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

DATA_DIR = 'data'
LESSONS_FILE = 'lessons.json'

lessons_lock = asyncio.Lock()

def get_file_path(filename: str) -> str:
    """Возвращает полный путь к файлу"""
    return os.path.join(DATA_DIR, filename)

async def load_lessons() -> Dict:
    """Загрузить все уроки"""
    filepath = get_file_path(LESSONS_FILE)
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки уроков: {e}")
        return {}

async def save_lessons(lessons: Dict):
    """Сохранить уроки"""
    filepath = get_file_path(LESSONS_FILE)
    
    async with lessons_lock:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(lessons, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения уроков: {e}")

async def add_lesson(student_id: int, date: str, time: str, price: int, from_template: str = None):
    """Добавить урок"""
    lessons = await load_lessons()
    
    lesson_id = f"{date}_{time}_{student_id}"
    
    # Проверяем что урок еще не существует
    if lesson_id in lessons:
        return lesson_id
    
    # ПРОВЕРКА КОНФЛИКТОВ: проверяем что на это время нет других уроков
    conflict_key = f"{date}_{time}_"
    for existing_id in lessons.keys():
        if existing_id.startswith(conflict_key):
            # Есть урок на это время с другим учеником
            raise ValueError(f"На {date} в {time} уже есть урок")
    
    lessons[lesson_id] = {
        'id': lesson_id,
        'student_id': student_id,
        'date': date,  # YYYY-MM-DD
        'time': time,  # HH:MM
        'price': price,
        'completed': False,
        'from_template': from_template,
        'created_at': datetime.now().isoformat()
    }
    
    await save_lessons(lessons)
    return lesson_id

async def get_lessons_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """Получить уроки за период"""
    lessons = await load_lessons()
    
    result = []
    for lesson in lessons.values():
        if start_date <= lesson['date'] <= end_date:
            result.append(lesson)
    
    return sorted(result, key=lambda x: (x['date'], x['time']))

async def get_lessons_by_date(date: str) -> List[Dict]:
    """Получить уроки на конкретную дату"""
    lessons = await load_lessons()
    
    result = []
    for lesson in lessons.values():
        if lesson['date'] == date:
            result.append(lesson)
    
    return sorted(result, key=lambda x: x['time'])

async def get_lessons_by_month(year: int, month: int) -> List[Dict]:
    """Получить уроки за месяц"""
    from calendar import monthrange
    
    start_date = f"{year}-{month:02d}-01"
    last_day = monthrange(year, month)[1]
    end_date = f"{year}-{month:02d}-{last_day}"
    
    return await get_lessons_by_date_range(start_date, end_date)

async def get_lesson(lesson_id: str) -> Optional[Dict]:
    """Получить урок по ID"""
    lessons = await load_lessons()
    return lessons.get(lesson_id)

async def mark_lesson_completed(lesson_id: str):
    """Отметить урок как выполненный"""
    lessons = await load_lessons()
    
    if lesson_id in lessons:
        lessons[lesson_id]['completed'] = True
        lessons[lesson_id]['completed_at'] = datetime.now().isoformat()
        await save_lessons(lessons)
        return True
    
    return False

async def mark_lesson_uncompleted(lesson_id: str):
    """Отменить выполнение урока"""
    lessons = await load_lessons()
    
    if lesson_id in lessons:
        lessons[lesson_id]['completed'] = False
        if 'completed_at' in lessons[lesson_id]:
            del lessons[lesson_id]['completed_at']
        await save_lessons(lessons)
        return True
    
    return False

async def move_lesson(lesson_id: str, new_date: str, new_time: str):
    """Перенести урок на другую дату/время"""
    lessons = await load_lessons()
    
    if lesson_id not in lessons:
        return False
    
    lesson = lessons[lesson_id]
    
    # Удаляем старый урок
    del lessons[lesson_id]
    
    # Создаем новый с новой датой
    new_id = f"{new_date}_{new_time}_{lesson['student_id']}"
    lessons[new_id] = {
        'id': new_id,
        'student_id': lesson['student_id'],
        'date': new_date,
        'time': new_time,
        'price': lesson['price'],
        'completed': False,
        'created_at': lesson['created_at'],
        'moved_from': lesson_id,
        'moved_at': datetime.now().isoformat(),
        'is_moved': True,  # Защита от перезаписи шаблонами
        'from_template': lesson.get('from_template')  # Сохраняем связь с шаблоном
    }
    
    await save_lessons(lessons)
    return new_id

async def get_available_slots(date: str) -> List[Dict]:
    """Получить свободные слоты на дату"""
    import database as db
    
    lessons = await load_lessons()
    students = await db.get_students()
    
    # Все возможные временные слоты (рабочее время 6:00 - 24:00)
    all_slots = [f"{h:02d}:00" for h in range(6, 24)]  # 06:00 - 23:00
    
    # Занятые слоты на эту дату
    busy_slots = {}
    
    for lesson in lessons.values():
        if lesson['date'] == date:
            student = students.get(str(lesson['student_id']))
            student_name = student['name'] if student else 'Ученик'
            busy_slots[lesson['time']] = student_name
    
    # Формируем список свободных и занятых слотов
    result = []
    for slot in all_slots:
        is_busy = slot in busy_slots
        slot_info = {
            'time': slot,
            'available': not is_busy
        }
        
        if is_busy:
            slot_info['student_name'] = busy_slots[slot]
        
        result.append(slot_info)
    
    return result

async def delete_lesson(lesson_id: str):
    """Удалить урок"""
    lessons = await load_lessons()
    
    if lesson_id in lessons:
        del lessons[lesson_id]
        await save_lessons(lessons)
        return True
    
    return False

async def get_student_lessons(student_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
    """Получить уроки ученика"""
    lessons = await load_lessons()
    
    result = []
    for lesson in lessons.values():
        if lesson['student_id'] == student_id:
            if start_date and lesson['date'] < start_date:
                continue
            if end_date and lesson['date'] > end_date:
                continue
            result.append(lesson)
    
    return sorted(result, key=lambda x: (x['date'], x['time']))

async def get_stats_for_month(year: int, month: int) -> Dict:
    """Получить статистику за месяц"""
    lessons = await get_lessons_by_month(year, month)
    
    total_lessons = len(lessons)
    completed_lessons = len([l for l in lessons if l['completed']])
    pending_lessons = total_lessons - completed_lessons
    
    completed_income = sum(l['price'] for l in lessons if l['completed'])
    expected_income = sum(l['price'] for l in lessons if not l['completed'])
    total_income = completed_income + expected_income
    
    return {
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
        'pending_lessons': pending_lessons,
        'completed_income': completed_income,
        'expected_income': expected_income,
        'total_income': total_income
    }


async def get_stats_for_year(year: int) -> Dict:
    """Получить статистику за год"""
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    lessons = await get_lessons_by_date_range(start_date, end_date)
    
    total_lessons = len(lessons)
    completed_lessons = len([l for l in lessons if l['completed']])
    pending_lessons = total_lessons - completed_lessons
    
    completed_income = sum(l['price'] for l in lessons if l['completed'])
    expected_income = sum(l['price'] for l in lessons if not l['completed'])
    total_income = completed_income + expected_income
    
    return {
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
        'pending_lessons': pending_lessons,
        'completed_income': completed_income,
        'expected_income': expected_income,
        'total_income': total_income
    }


async def get_history_stats() -> Dict:
    """Получить историю статистики по месяцам"""
    lessons = await load_lessons()
    
    # Группируем уроки по годам и месяцам
    history = {}
    
    for lesson in lessons.values():
        date_parts = lesson['date'].split('-')
        year = int(date_parts[0])
        month = int(date_parts[1])
        
        key = f"{year}-{month:02d}"
        
        if key not in history:
            history[key] = {
                'year': year,
                'month': month,
                'total_lessons': 0,
                'completed_lessons': 0,
                'completed_income': 0,
                'total_income': 0
            }
        
        history[key]['total_lessons'] += 1
        history[key]['total_income'] += lesson['price']
        
        if lesson['completed']:
            history[key]['completed_lessons'] += 1
            history[key]['completed_income'] += lesson['price']
    
    # Сортируем по дате (новые первые)
    sorted_history = sorted(history.values(), key=lambda x: (x['year'], x['month']), reverse=True)
    
    return {'history': sorted_history}


async def delete_student_lessons(student_id: int):
    """Удалить все уроки ученика"""
    lessons = await load_lessons()
    
    # Находим все уроки ученика
    to_delete = [lid for lid, lesson in lessons.items() if lesson['student_id'] == student_id]
    
    # Удаляем
    for lid in to_delete:
        del lessons[lid]
    
    await save_lessons(lessons)
    return len(to_delete)


async def check_time_available(date: str, time: str, duration_hours: int = 1) -> Dict:
    """
    Проверить доступность времени для урока
    Возвращает: {available: bool, conflicts: [список конфликтующих уроков]}
    """
    import database as db
    from datetime import datetime, timedelta
    
    lessons = await load_lessons()
    students = await db.get_students()
    
    # Парсим время начала
    start_hour, start_minute = map(int, time.split(':'))
    start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(hours=duration_hours)
    
    conflicts = []
    
    # Проверяем все уроки на эту дату
    for lesson in lessons.values():
        if lesson['date'] != date:
            continue
        
        # Парсим время существующего урока
        lesson_hour, lesson_minute = map(int, lesson['time'].split(':'))
        lesson_start = datetime.strptime(f"{date} {lesson['time']}", "%Y-%m-%d %H:%M")
        lesson_end = lesson_start + timedelta(hours=1)  # Урок = 1 час
        
        # Проверяем пересечение времени
        if (start_time < lesson_end and end_time > lesson_start):
            student = students.get(str(lesson['student_id']))
            student_name = student['name'] if student else 'Ученик'
            conflicts.append({
                'time': lesson['time'],
                'student_name': student_name,
                'lesson_id': lesson['id']
            })
    
    return {
        'available': len(conflicts) == 0,
        'conflicts': conflicts
    }
