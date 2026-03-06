"""
FastAPI веб-приложение для админ-панели
"""
from fastapi import FastAPI, HTTPException, Request, Depends, status, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Set
import database as db
import lessons as lessons_db
import recurring_schedule as recurring_db
import simple_auth
from datetime import datetime, timedelta
import os
import time
import json
import asyncio
import secrets
import hashlib
from calendar import monthrange
from urllib.parse import unquote

app = FastAPI(title="Tutor Bot Admin Panel")

# Получаем абсолютные пути
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Версия для кэш-бастинга
CACHE_VERSION = str(int(time.time()))

# Авторизация
security = HTTPBearer()
active_tokens = set()

def create_token() -> str:
    """Создание токена"""
    token = secrets.token_urlsafe(32)
    active_tokens.add(token)
    return token

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Проверка токена"""
    if credentials.credentials not in active_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return True

# Модели данных
class Student(BaseModel):
    user_id: int
    name: str
    username: str
    timezone_offset: int

class Lesson(BaseModel):
    day: str
    time: str

class ScheduleUpdate(BaseModel):
    user_id: int
    lessons: List[Lesson]

class Settings(BaseModel):
    admin_timezone: int
    reminder_minutes_before: int
    homework_check_minutes_before: int
    admin_daily_reminder_time: str
    default_lesson_price: int

class LessonCreate(BaseModel):
    student_id: int
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    price: int

class LessonMove(BaseModel):
    new_date: str
    new_time: str

class RecurringLesson(BaseModel):
    student_id: int
    day_of_week: int  # 0=пн, 1=вт, 2=ср, 3=чт, 4=пт, 5=сб, 6=вс
    time: str
    price: int

# === HTML страницы ===

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    return templates.TemplateResponse("register.html", {
        "request": request
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {
        "request": request
    })

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница админ-панели"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": CACHE_VERSION
    })

# === API авторизации ===

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Регистрация репетитора"""
    result = simple_auth.register(request.email, request.password, request.name)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['message']
        )
    
    return {"status": "success", "message": result['message']}

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Вход в систему"""
    if simple_auth.authenticate(request.email, request.password):
        token = create_token()
        tutor_info = simple_auth.get_tutor_info()
        return {
            "token": token,
            "status": "success",
            "tutor": tutor_info
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

@app.post("/api/auth/logout")
async def logout(authenticated: bool = Depends(verify_token)):
    """Выход из системы"""
    return {"status": "success"}

# === API endpoints ===

@app.get("/api/students")
async def get_students(authenticated: bool = Depends(verify_token)):
    """Получить список всех учеников репетитора"""
    # Получаем tutor_id текущего репетитора
    tutor_id = simple_auth.get_tutor_id()
    
    if not tutor_id:
        raise HTTPException(status_code=500, detail="Tutor ID not found")
    
    # Получаем только учеников этого репетитора
    students = await db.get_students_by_tutor(tutor_id)
    schedule = await db.get_schedule()
    settings = await db.get_settings()
    default_price = settings.get('default_lesson_price', 1000)
    
    result = []
    for user_id, student in students.items():
        student_schedule = schedule.get(user_id, [])
        result.append({
            "user_id": int(user_id),
            "name": student.get("name"),
            "username": student.get("username"),
            "timezone_offset": student.get("timezone_offset"),
            "lessons_count": len(student_schedule),
            "lesson_price": student.get("lesson_price", default_price),
            "schedule": student_schedule
        })
    
    return {"students": result}

@app.get("/api/students/{user_id}")
async def get_student(user_id: int, authenticated: bool = Depends(verify_token)):
    """Получить данные конкретного ученика"""
    student = await db.get_student(user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    schedule = await db.get_student_schedule(user_id)
    
    return {
        "student": student,
        "schedule": schedule
    }

@app.post("/api/students/{user_id}/schedule")
async def update_student_schedule(user_id: int, schedule_update: ScheduleUpdate, authenticated: bool = Depends(verify_token)):
    """Обновить расписание ученика"""
    student = await db.get_student(user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    lessons = [{"day": lesson.day, "time": lesson.time} for lesson in schedule_update.lessons]
    await db.set_student_schedule(user_id, lessons)
    
    return {"status": "success", "message": "Schedule updated"}

@app.post("/api/students/{user_id}/schedule/add")
async def add_lesson(user_id: int, lesson: Lesson, authenticated: bool = Depends(verify_token)):
    """Добавить урок в расписание"""
    student = await db.get_student(user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    await db.add_lesson_to_schedule(user_id, lesson.day, lesson.time)
    
    return {"status": "success", "message": "Lesson added"}

@app.delete("/api/students/{user_id}/schedule")
async def delete_lesson(user_id: int, day: str, time: str, authenticated: bool = Depends(verify_token)):
    """Удалить урок из расписания"""
    await db.remove_lesson_from_schedule(user_id, day, time)
    return {"status": "success", "message": "Lesson deleted"}

@app.get("/api/schedule/week")
async def get_week_schedule(authenticated: bool = Depends(verify_token)):
    """Получить расписание на всю неделю"""
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    week_data = {}
    for day in days_order:
        week_data[day] = []
    
    for user_id, user_schedule in schedule.items():
        student = students.get(user_id)
        if student:
            for lesson in user_schedule:
                week_data[lesson['day']].append({
                    'time': lesson['time'],
                    'student_name': student.get('name'),
                    'student_id': int(user_id)
                })
    
    # Сортируем по времени
    for day in days_order:
        week_data[day].sort(key=lambda x: x['time'])
    
    return {"schedule": week_data}

@app.get("/api/schedule/today")
async def get_today_schedule(authenticated: bool = Depends(verify_token)):
    """Получить расписание на сегодня"""
    settings = await db.get_settings()
    admin_tz_offset = settings['admin_timezone']
    
    import pytz
    admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
    now = datetime.now(admin_tz)
    
    day_name = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][now.weekday()]
    
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    today_lessons = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == day_name:
                student = students.get(user_id)
                if student:
                    today_lessons.append({
                        'time': lesson['time'],
                        'student_name': student.get('name'),
                        'student_username': student.get('username'),
                        'student_id': int(user_id)
                    })
    
    today_lessons.sort(key=lambda x: x['time'])
    
    return {
        "date": now.strftime('%Y-%m-%d'),
        "day": day_name,
        "lessons": today_lessons
    }

@app.get("/api/settings")
async def get_settings(authenticated: bool = Depends(verify_token)):
    """Получить настройки"""
    settings = await db.get_settings()
    
    # Добавляем информацию о репетиторе и его ссылку
    tutor_info = simple_auth.get_tutor_info()
    bot_username = os.getenv('BOT_USERNAME', 'YourBot')  # Имя бота без @
    
    if tutor_info and tutor_info.get('tutor_id'):
        invite_link = f"https://t.me/{bot_username}?start={tutor_info['tutor_id']}"
    else:
        invite_link = None
    
    return {
        "settings": settings,
        "tutor_info": tutor_info,
        "invite_link": invite_link
    }

@app.put("/api/settings")
async def update_settings(settings: Settings, authenticated: bool = Depends(verify_token)):
    """Обновить настройки"""
    await db.save_settings({
        "admin_timezone": settings.admin_timezone,
        "reminder_minutes_before": settings.reminder_minutes_before,
        "homework_check_minutes_before": settings.homework_check_minutes_before,
        "admin_daily_reminder_time": settings.admin_daily_reminder_time,
        "default_lesson_price": settings.default_lesson_price
    })
    
    return {"status": "success", "message": "Settings updated"}

@app.delete("/api/students/{user_id}")
async def delete_student(user_id: int, authenticated: bool = Depends(verify_token)):
    """Удалить ученика, все его уроки и шаблоны"""
    import lessons as lessons_db
    import recurring_schedule as recurring_db
    
    # Удаляем все уроки ученика
    deleted_lessons = await lessons_db.delete_student_lessons(user_id)
    
    # Удаляем все шаблоны ученика
    deleted_templates = await recurring_db.delete_student_templates(user_id)
    
    # Удаляем старое расписание (если есть)
    await db.set_student_schedule(user_id, [])
    
    # Удаляем самого ученика
    students = await db.get_students()
    if str(user_id) in students:
        del students[str(user_id)]
        await db.save_students(students)
    
    return {
        "status": "success", 
        "message": f"Student deleted. Removed {deleted_lessons} lessons and {deleted_templates} templates"
    }

@app.put("/api/students/{user_id}/price")
async def update_student_price(user_id: int, price: int, authenticated: bool = Depends(verify_token)):
    """Обновить цену урока для ученика"""
    await db.update_student_price(user_id, price)
    return {"status": "success", "message": "Price updated"}

class StudentPrice(BaseModel):
    price: int

@app.post("/api/students/{user_id}/price")
async def update_student_price_post(user_id: int, data: StudentPrice, authenticated: bool = Depends(verify_token)):
    """Обновить цену урока для ученика (POST)"""
    await db.update_student_price(user_id, data.price)
    return {"status": "success", "message": "Price updated"}

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(authenticated: bool = Depends(verify_token)):
    """Получить статистику для личного кабинета"""
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Статистика за текущий месяц
    month_stats = await lessons_db.get_stats_for_month(year, month)
    
    # Статистика за текущий год
    year_stats = await lessons_db.get_stats_for_year(year)
    
    # Количество учеников
    students = await db.get_students()
    
    return {
        "current_month": month,
        "current_year": year,
        "month_lessons": month_stats['total_lessons'],
        "month_completed": month_stats['completed_lessons'],
        "month_pending": month_stats['pending_lessons'],
        "month_income": month_stats['completed_income'],
        "month_expected": month_stats['expected_income'],
        "year_lessons": year_stats['total_lessons'],
        "year_completed": year_stats['completed_lessons'],
        "year_income": year_stats['completed_income'],
        "students_count": len(students)
    }

@app.get("/api/dashboard/history")
async def get_dashboard_history(authenticated: bool = Depends(verify_token)):
    """Получить историю статистики"""
    history = await lessons_db.get_history_stats()
    return history

if __name__ == "__main__":
    import uvicorn
    db.ensure_data_dir()
    uvicorn.run(app, host="0.0.0.0", port=8000)

# === API для уроков (новая система) ===

@app.post("/api/lessons")
async def create_lesson(lesson: LessonCreate, authenticated: bool = Depends(verify_token)):
    """Создать урок"""
    try:
        lesson_id = await lessons_db.add_lesson(
            lesson.student_id,
            lesson.date,
            lesson.time,
            lesson.price
        )
        return {"status": "success", "lesson_id": lesson_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/api/lessons/month/{year}/{month}")
async def get_lessons_month(year: int, month: int, authenticated: bool = Depends(verify_token)):
    """Получить уроки за месяц"""
    lessons = await lessons_db.get_lessons_by_month(year, month)
    
    # Добавляем информацию об учениках
    students = await db.get_students()
    
    for lesson in lessons:
        student = students.get(str(lesson['student_id']))
        if student:
            lesson['student_name'] = student['name']
            lesson['student_username'] = student.get('username', '')
    
    return {"lessons": lessons}

@app.post("/api/lessons/{lesson_id:path}/complete")
async def complete_lesson(lesson_id: str = Path(...), authenticated: bool = Depends(verify_token)):
    """Отметить урок как выполненный"""
    success = await lessons_db.mark_lesson_completed(lesson_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    return {"status": "success"}

@app.post("/api/lessons/{lesson_id:path}/uncomplete")
async def uncomplete_lesson(lesson_id: str = Path(...), authenticated: bool = Depends(verify_token)):
    """Отменить выполнение урока"""
    success = await lessons_db.mark_lesson_uncompleted(lesson_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    return {"status": "success"}

@app.get("/api/lessons/available-slots/{date}")
async def get_available_slots(date: str, authenticated: bool = Depends(verify_token)):
    """Получить свободные слоты на дату"""
    slots = await lessons_db.get_available_slots(date)
    return {"slots": slots}

@app.get("/api/lessons/check-time/{date}/{time}")
async def check_time_availability(date: str, time: str, authenticated: bool = Depends(verify_token)):
    """Проверить доступность конкретного времени"""
    result = await lessons_db.check_time_available(date, time)
    return result

@app.post("/api/lessons/{lesson_id:path}/move")
async def move_lesson(lesson_id: str = Path(...), move_data: LessonMove = None, authenticated: bool = Depends(verify_token)):
    """Перенести урок"""
    new_id = await lessons_db.move_lesson(lesson_id, move_data.new_date, move_data.new_time)
    
    if not new_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    return {"status": "success", "new_lesson_id": new_id}

@app.delete("/api/lessons/{lesson_id:path}")
async def delete_lesson(lesson_id: str = Path(...), authenticated: bool = Depends(verify_token)):
    """Удалить урок"""
    success = await lessons_db.delete_lesson(lesson_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    return {"status": "success"}

# === API для шаблонов расписания ===

@app.get("/api/recurring")
async def get_recurring(authenticated: bool = Depends(verify_token)):
    """Получить все шаблоны расписания"""
    templates = await recurring_db.get_all_recurring()
    
    # Добавляем информацию об учениках
    students = await db.get_students()
    
    for template in templates:
        student = students.get(str(template['student_id']))
        if student:
            template['student_name'] = student['name']
    
    return {"templates": templates}

@app.post("/api/recurring")
async def create_recurring(recurring: RecurringLesson, authenticated: bool = Depends(verify_token)):
    """Создать шаблон расписания"""
    template_id = await recurring_db.add_recurring_lesson(
        recurring.student_id,
        recurring.day_of_week,
        recurring.time,
        recurring.price
    )
    
    # Автоматически генерируем уроки
    await recurring_db.auto_generate_lessons()
    
    return {"status": "success", "template_id": template_id}

@app.delete("/api/recurring/{template_id}")
async def delete_recurring(template_id: str, delete_future: bool = False, authenticated: bool = Depends(verify_token)):
    """Удалить шаблон расписания и опционально будущие уроки"""
    success = await recurring_db.delete_recurring(template_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    deleted_lessons = 0
    if delete_future:
        # Удаляем все будущие незавершенные уроки из этого шаблона
        deleted_lessons = await recurring_db.delete_template_future_lessons(template_id)
    
    return {
        "status": "success",
        "deleted_lessons": deleted_lessons
    }

@app.post("/api/recurring/generate")
async def generate_lessons(authenticated: bool = Depends(verify_token)):
    """Сгенерировать уроки из шаблонов"""
    count = await recurring_db.auto_generate_lessons()
    return {"status": "success", "created": count}
