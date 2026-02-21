import logging
from datetime import datetime, timedelta
from typing import List, Dict
import pytz
from aiogram import Bot

import database as db

DAYS_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6
}

async def get_lessons_for_datetime(target_datetime: datetime, admin_tz_offset: int) -> List[Dict]:
    """Получить все уроки на конкретную дату и время (в часовом поясе админа)"""
    schedule = await db.get_schedule()
    students = await db.get_students()
    
    day_name = list(DAYS_MAP.keys())[target_datetime.weekday()]
    target_time = target_datetime.strftime('%H:%M')
    
    lessons = []
    for user_id, user_schedule in schedule.items():
        for lesson in user_schedule:
            if lesson['day'] == day_name and lesson['time'] == target_time:
                student = students.get(user_id)
                if student:
                    lessons.append({
                        'user_id': int(user_id),
                        'student': student,
                        'day': day_name,
                        'time': target_time
                    })
    
    return lessons

async def convert_time_to_user_tz(admin_time: datetime, admin_tz_offset: int, user_tz_offset: int) -> datetime:
    """Конвертировать время из часового пояса админа в часовой пояс ученика"""
    # Разница в часах
    diff = user_tz_offset - admin_tz_offset
    return admin_time + timedelta(hours=diff)

async def check_and_send_reminders(bot: Bot):
    """Проверить и отправить напоминания ученикам"""
    try:
        settings = await db.get_settings()
        admin_tz_offset = settings['admin_timezone']
        reminder_hours = settings['reminder_hours_before']
        
        # Текущее время в часовом поясе админа
        admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
        now_admin = datetime.now(admin_tz)
        
        # Округляем до минут для точного сравнения
        current_minute = now_admin.replace(second=0, microsecond=0)
        
        # Время урока = текущее время + время напоминания
        lesson_time = current_minute + timedelta(hours=reminder_hours)
        
        # Получаем уроки на это время
        lessons = await get_lessons_for_datetime(lesson_time, admin_tz_offset)
        
        for lesson in lessons:
            user_id = lesson['user_id']
            student = lesson['student']
            
            # Проверяем, не отправляли ли уже напоминание
            date_str = lesson_time.strftime('%Y-%m-%d')
            
            # Проверяем есть ли уже запись о напоминании (через homework_response)
            # Если есть любой ответ, значит напоминание уже отправлялось
            response = await db.get_homework_response(date_str, lesson['time'], user_id)
            if response:
                continue
            
            # Создаем пустую запись чтобы не отправлять повторно
            await db.save_homework_response(date_str, lesson['time'], user_id, "pending", None)
            
            # Конвертируем время в часовой пояс ученика
            user_tz_offset = student['timezone_offset']
            user_lesson_time = await convert_time_to_user_tz(lesson_time, admin_tz_offset, user_tz_offset)
            
            # Формируем сообщение
            day_names_ru = {
                'monday': 'Понедельник',
                'tuesday': 'Вторник',
                'wednesday': 'Среда',
                'thursday': 'Четверг',
                'friday': 'Пятница',
                'saturday': 'Суббота',
                'sunday': 'Воскресенье'
            }
            
            message = (
                f"🔔 Напоминание об уроке!\n\n"
                f"{day_names_ru[lesson['day']]} {user_lesson_time.strftime('%d.%m')}\n"
                f"⏰ {user_lesson_time.strftime('%H:%M')}\n\n"
                f"Домашнее задание выполнено?"
            )
            
            # Клавиатура
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Сделано", callback_data=f"hw_done_{date_str}_{lesson['time']}"),
                    InlineKeyboardButton(text="❌ Не сделано", callback_data=f"hw_not_done_{date_str}_{lesson['time']}")
                ]
            ])
            
            try:
                await bot.send_message(user_id, message, reply_markup=keyboard)
                logging.info(f"Отправлено напоминание ученику {user_id}")
            except Exception as e:
                logging.error(f"Не удалось отправить напоминание ученику {user_id}: {e}")
    
    except Exception as e:
        logging.error(f"Ошибка в check_and_send_reminders: {e}")

async def check_and_send_homework_reports(bot: Bot, admin_id: int):
    """Проверить и отправить отчеты по ДЗ админу"""
    try:
        settings = await db.get_settings()
        admin_tz_offset = settings['admin_timezone']
        report_minutes = settings['homework_check_minutes_before']
        
        # Текущее время в часовом поясе админа
        admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
        now_admin = datetime.now(admin_tz)
        
        # Время урока = текущее время + время отчета
        lesson_time = now_admin + timedelta(minutes=report_minutes)
        
        # Получаем уроки на это время
        lessons = await get_lessons_for_datetime(lesson_time, admin_tz_offset)
        
        if not lessons:
            return
        
        # Группируем уроки по времени (для групповых занятий)
        lessons_by_time = {}
        for lesson in lessons:
            key = f"{lesson['day']}_{lesson['time']}"
            if key not in lessons_by_time:
                lessons_by_time[key] = []
            lessons_by_time[key].append(lesson)
        
        # Отправляем отчет по каждому уроку
        for time_key, lesson_group in lessons_by_time.items():
            date_str = lesson_time.strftime('%Y-%m-%d')
            time_str = lesson_group[0]['time']
            
            message = f"📊 Урок через {report_minutes} минут\n"
            message += f"{lesson_time.strftime('%d.%m')} в {time_str}\n\n"
            
            for lesson in lesson_group:
                user_id = lesson['user_id']
                student = lesson['student']
                
                # Получаем ответ ученика
                response = await db.get_homework_response(date_str, time_str, user_id)
                
                name = student.get('name', 'Без имени')
                username = student.get('username', '')
                username_str = f"@{username}" if username else ""
                
                message += f"{name} ({username_str}):\n"
                
                if not response or response['status'] == 'pending':
                    message += "⚠️ Не ответил\n\n"
                elif response['status'] == 'done':
                    message += "✅ Сделано\n\n"
                else:
                    message += f"❌ Не сделано\n"
                    if response.get('reason'):
                        message += f"Причина: {response['reason']}\n\n"
                    else:
                        message += "\n"
            
            try:
                await bot.send_message(admin_id, message)
                logging.info(f"Отправлен отчет по ДЗ админу")
            except Exception as e:
                logging.error(f"Не удалось отправить отчет админу: {e}")
    
    except Exception as e:
        logging.error(f"Ошибка в check_and_send_homework_reports: {e}")

async def send_admin_daily_reminder(bot: Bot, admin_id: int):
    """Отправить админу ежедневное напоминание о расписании"""
    try:
        settings = await db.get_settings()
        admin_tz_offset = settings['admin_timezone']
        
        # Текущее время в часовом поясе админа
        admin_tz = pytz.timezone(f'Etc/GMT{-admin_tz_offset:+d}')
        now_admin = datetime.now(admin_tz)
        
        # Получаем все уроки на сегодня
        schedule = await db.get_schedule()
        students = await db.get_students()
        
        day_name = list(DAYS_MAP.keys())[now_admin.weekday()]
        
        today_lessons = []
        for user_id, user_schedule in schedule.items():
            for lesson in user_schedule:
                if lesson['day'] == day_name:
                    student = students.get(user_id)
                    if student:
                        today_lessons.append({
                            'time': lesson['time'],
                            'student': student
                        })
        
        # Сортируем по времени
        today_lessons.sort(key=lambda x: x['time'])
        
        day_names_ru = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда',
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        if not today_lessons:
            message = "🔔 Доброе утро!\n\nСегодня уроков нет. Отдыхай! 😊"
        else:
            message = f"🔔 Доброе утро! Твое расписание на сегодня:\n\n"
            message += f"{day_names_ru[day_name]} {now_admin.strftime('%d.%m')}\n"
            message += f"У вас {len(today_lessons)} {'урок' if len(today_lessons) == 1 else 'уроков' if len(today_lessons) < 5 else 'уроков'}:\n\n"
            
            for lesson in today_lessons:
                name = lesson['student'].get('name', 'Без имени')
                username = lesson['student'].get('username', '')
                username_str = f"(@{username})" if username else ""
                message += f"├ {lesson['time']} - {name} {username_str}\n"
        
        try:
            await bot.send_message(admin_id, message)
            logging.info("Отправлено ежедневное напоминание админу")
        except Exception as e:
            logging.error(f"Не удалось отправить ежедневное напоминание админу: {e}")
    
    except Exception as e:
        logging.error(f"Ошибка в send_admin_daily_reminder: {e}")
