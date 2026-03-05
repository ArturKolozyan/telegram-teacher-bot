"""
Работа с шаблонами расписания (recurring schedule)
"""
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

DATA_DIR = 'data'
RECURRING_FILE = 'recurring_schedule.json'

recurring_lock = asyncio.Lock()

def get_file_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)

async def load_recurring() -> Dict:
    """Загрузить шаблоны расписания"""
    filepath = get_file_path(RECURRING_FILE)
    
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки шаблонов: {e}")
        return {}

async def save_recurring(recurring: Dict):
    """Сохранить шаблоны расписания"""
    filepath = get_file_path(RECURRING_FILE)
    
    async with recurring_lock:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recurring, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения шаблонов: {e}")

async def add_recurring_lesson(student_id: int, day_of_week: int, time: str, price: int):
    """
    Добавить шаблон урока
    day_of_week: 0=понедельник, 1=вторник, ..., 6=воскресенье
    """
    recurring = await load_recurring()
    
    template_id = f"{day_of_week}_{time}_{student_id}"
    recurring[template_id] = {
        'id': template_id,
        'student_id': student_id,
        'day_of_week': day_of_week,
        'time': time,
        'price': price,
        'active': True,
        'created_at': datetime.now().isoformat()
    }
    
    await save_recurring(recurring)
    return template_id

async def get_all_recurring() -> List[Dict]:
    """Получить все шаблоны"""
    recurring = await load_recurring()
    return list(recurring.values())

async def get_recurring_by_student(student_id: int) -> List[Dict]:
    """Получить шаблоны ученика"""
    recurring = await load_recurring()
    return [r for r in recurring.values() if r['student_id'] == student_id]

async def delete_recurring(template_id: str):
    """Удалить шаблон"""
    recurring = await load_recurring()
    
    if template_id in recurring:
        del recurring[template_id]
        await save_recurring(recurring)
        return True
    
    return False

async def generate_lessons_for_month(year: int, month: int):
    """
    Генерировать уроки на месяц из шаблонов
    Возвращает список уроков для создания
    """
    from calendar import monthrange
    import lessons as lessons_db
    
    recurring = await load_recurring()
    
    # Получаем существующие уроки за месяц
    existing_lessons = await lessons_db.get_lessons_by_month(year, month)
    
    # Создаем множество ключей существующих уроков
    # Для перенесенных уроков (is_moved=True) используем оригинальный ключ из from_template
    existing_keys = set()
    moved_lessons_original_keys = set()
    
    for l in existing_lessons:
        key = f"{l['date']}_{l['time']}_{l['student_id']}"
        existing_keys.add(key)
        
        # Если урок был перенесен, запоминаем его оригинальное место
        if l.get('is_moved') and l.get('from_template'):
            # Извлекаем оригинальную дату из moved_from
            if 'moved_from' in l:
                moved_lessons_original_keys.add(l['moved_from'])
    
    # Генерируем уроки из шаблонов
    lessons_to_create = []
    
    first_day = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    
    for day in range(1, last_day + 1):
        date = datetime(year, month, day)
        day_of_week = date.weekday()
        
        date_str = date.strftime('%Y-%m-%d')
        
        # Ищем шаблоны для этого дня недели
        for template in recurring.values():
            if not template.get('active', True):
                continue
            
            if template['day_of_week'] == day_of_week:
                key = f"{date_str}_{template['time']}_{template['student_id']}"
                
                # Пропускаем если:
                # 1. Урок уже существует
                # 2. Это оригинальное место перенесенного урока
                if key not in existing_keys and key not in moved_lessons_original_keys:
                    lessons_to_create.append({
                        'student_id': template['student_id'],
                        'date': date_str,
                        'time': template['time'],
                        'price': template['price'],
                        'from_template': template['id']
                    })
    
    return lessons_to_create

async def auto_generate_lessons():
    """
    Автоматически генерировать уроки на текущий и следующий месяц
    """
    import lessons as lessons_db
    
    now = datetime.now()
    
    # Текущий месяц
    lessons_current = await generate_lessons_for_month(now.year, now.month)
    
    # Следующий месяц
    next_month = now.month + 1
    next_year = now.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    lessons_next = await generate_lessons_for_month(next_year, next_month)
    
    # Создаем уроки
    created_count = 0
    for lesson_data in lessons_current + lessons_next:
        await lessons_db.add_lesson(
            lesson_data['student_id'],
            lesson_data['date'],
            lesson_data['time'],
            lesson_data['price'],
            from_template=lesson_data.get('from_template')
        )
        created_count += 1
    
    return created_count


async def delete_student_templates(student_id: int):
    """Удалить все шаблоны ученика"""
    recurring = await load_recurring()
    
    # Находим все шаблоны ученика
    to_delete = [tid for tid, template in recurring.items() if template['student_id'] == student_id]
    
    # Удаляем
    for tid in to_delete:
        del recurring[tid]
    
    await save_recurring(recurring)
    return len(to_delete)

async def delete_template_future_lessons(template_id: str):
    """Удалить все будущие незавершенные уроки созданные из шаблона"""
    import lessons as lessons_db
    from datetime import datetime
    
    lessons = await lessons_db.load_lessons()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Находим все будущие незавершенные уроки из этого шаблона
    to_delete = []
    for lid, lesson in lessons.items():
        if (lesson.get('from_template') == template_id and 
            not lesson.get('completed') and 
            not lesson.get('is_moved') and
            lesson['date'] >= today):
            to_delete.append(lid)
    
    # Удаляем
    for lid in to_delete:
        del lessons[lid]
    
    await lessons_db.save_lessons(lessons)
    return len(to_delete)
