"""
FastAPI веб-приложение для админ-панели
"""
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Set
import database as db
from datetime import datetime
import os
import time
import json
import asyncio

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

# WebSocket connections
active_connections: Set[WebSocket] = set()

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

# === HTML страницы ===

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница админ-панели"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": CACHE_VERSION
    })

# === API endpoints ===

@app.get("/api/students")
async def get_students():
    """Получить список всех учеников"""
    students = await db.get_students()
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
async def get_student(user_id: int):
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
async def update_student_schedule(user_id: int, schedule_update: ScheduleUpdate):
    """Обновить расписание ученика"""
    student = await db.get_student(user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    lessons = [{"day": lesson.day, "time": lesson.time} for lesson in schedule_update.lessons]
    await db.set_student_schedule(user_id, lessons)
    
    return {"status": "success", "message": "Schedule updated"}

@app.post("/api/students/{user_id}/schedule/add")
async def add_lesson(user_id: int, lesson: Lesson):
    """Добавить урок в расписание"""
    student = await db.get_student(user_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    await db.add_lesson_to_schedule(user_id, lesson.day, lesson.time)
    
    return {"status": "success", "message": "Lesson added"}

@app.delete("/api/students/{user_id}/schedule")
async def delete_lesson(user_id: int, day: str, time: str):
    """Удалить урок из расписания"""
    await db.remove_lesson_from_schedule(user_id, day, time)
    return {"status": "success", "message": "Lesson deleted"}

@app.get("/api/schedule/week")
async def get_week_schedule():
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
async def get_today_schedule():
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
async def get_settings():
    """Получить настройки"""
    settings = await db.get_settings()
    return {"settings": settings}

@app.put("/api/settings")
async def update_settings(settings: Settings):
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
async def delete_student(user_id: int):
    """Удалить ученика и все его уроки"""
    # Удаляем расписание ученика
    await db.set_student_schedule(user_id, [])
    
    # Удаляем самого ученика
    students = await db.get_students()
    if str(user_id) in students:
        del students[str(user_id)]
        await db.save_students(students)
    
    return {"status": "success", "message": "Student deleted"}

@app.put("/api/students/{user_id}/price")
async def update_student_price(user_id: int, price: int):
    """Обновить цену урока для ученика"""
    await db.update_student_price(user_id, price)
    return {"status": "success", "message": "Price updated"}

class StudentPrice(BaseModel):
    price: int

@app.post("/api/students/{user_id}/price")
async def update_student_price_post(user_id: int, data: StudentPrice):
    """Обновить цену урока для ученика (POST)"""
    await db.update_student_price(user_id, data.price)
    return {"status": "success", "message": "Price updated"}

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Получить статистику для личного кабинета"""
    from datetime import datetime, timedelta
    import calendar
    
    schedule = await db.get_schedule()
    students = await db.get_students()
    settings = await db.get_settings()
    
    # Подсчет уроков
    total_lessons_week = 0
    total_lessons_month = 0
    lessons_by_day = {}
    
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            total_lessons_week += 1
            day = lesson['day']
            if day not in lessons_by_day:
                lessons_by_day[day] = 0
            lessons_by_day[day] += 1
    
    # Уроков в месяц (примерно 4 недели)
    total_lessons_month = total_lessons_week * 4
    
    # Средние уроки в день
    avg_lessons_per_day = total_lessons_week / 7 if total_lessons_week > 0 else 0
    
    # Подсчет дохода
    income_week = 0
    income_month = 0
    
    for user_id, user_schedule in schedule.items():
        student = students.get(user_id)
        if student:
            price = student.get('lesson_price', settings.get('default_lesson_price', 1000))
            lessons_count = len(user_schedule)
            income_week += price * lessons_count
    
    income_month = income_week * 4
    
    return {
        "lessons": {
            "per_day_avg": round(avg_lessons_per_day, 1),
            "per_week": total_lessons_week,
            "per_month": total_lessons_month
        },
        "income": {
            "per_week": income_week,
            "per_month": income_month
        },
        "students_count": len(students),
        "lessons_by_day": lessons_by_day
    }

if __name__ == "__main__":
    import uvicorn
    db.ensure_data_dir()
    uvicorn.run(app, host="0.0.0.0", port=8000)

# === WebSocket для уведомлений ===

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_notification(notification: dict):
    """Отправить уведомление всем подключенным клиентам"""
    if active_connections:
        message = json.dumps(notification)
        for connection in active_connections.copy():
            try:
                await connection.send_text(message)
            except:
                active_connections.remove(connection)

# === API для уведомлений ===

@app.get("/api/notifications")
async def get_notifications():
    """Получить все уведомления"""
    notifications = await db.get_notifications()
    
    # Сортируем по времени создания (новые первые)
    sorted_notifications = sorted(
        notifications.values(),
        key=lambda x: x['created_at'],
        reverse=True
    )
    
    return {"notifications": sorted_notifications}

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Отметить уведомление как прочитанное"""
    await db.mark_notification_read(notification_id)
    return {"status": "success"}

@app.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    """Удалить уведомление"""
    await db.delete_notification(notification_id)
    return {"status": "success"}

@app.post("/api/notifications/clear-all")
async def clear_all_notifications():
    """Очистить все уведомления"""
    await db.save_notifications({})
    return {"status": "success"}

@app.post("/api/notifications/broadcast")
async def broadcast_notification_endpoint(notification: dict):
    """Endpoint для бота чтобы отправить уведомление через WebSocket"""
    await broadcast_notification(notification)
    return {"status": "success"}

@app.post("/api/notifications/new")
async def create_notification(notification: dict):
    """Создать новое уведомление и разослать через WebSocket"""
    # Сохраняем в базу
    notification_id = await db.add_notification(
        user_id=notification['user_id'],
        student_name=notification['student_name'],
        lesson_date=notification['lesson_date'],
        lesson_time=notification['lesson_time'],
        status=notification['status'],
        reason=notification.get('reason')
    )
    
    # Получаем полное уведомление
    notifications = await db.get_notifications()
    full_notification = notifications.get(notification_id)
    
    # Отправляем через WebSocket
    if full_notification:
        await broadcast_notification(full_notification)
    
    return {"status": "success", "notification_id": notification_id}
