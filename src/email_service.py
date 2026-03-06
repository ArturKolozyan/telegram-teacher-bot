"""
Сервис отправки email с кодами подтверждения
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
FROM_NAME = os.getenv('FROM_NAME', 'Tutor Bot')

def send_verification_code(to_email: str, code: str, name: str = None) -> bool:
    """Отправить код подтверждения на email"""
    try:
        # Создаем сообщение
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Код подтверждения: {code}'
        msg['From'] = f'{FROM_NAME} <{FROM_EMAIL}>'
        msg['To'] = to_email
        
        # Текст письма
        greeting = f'Здравствуйте, {name}!' if name else 'Здравствуйте!'
        
        text = f"""
{greeting}

Ваш код подтверждения: {code}

Код действителен 5 минут.

Если вы не запрашивали этот код, просто проигнорируйте это письмо.

---
Tutor Bot
"""
        
        html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4CAF50;">{greeting}</h2>
        <p>Ваш код подтверждения:</p>
        <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; margin: 20px 0;">
            {code}
</div>
        <p style="color: #666; font-size: 14px;">Код действителен 5 минут.</p>
        <p style="color: #999; font-size: 12px; margin-top: 40px;">
            Если вы не запрашивали этот код, просто проигнорируйте это письмо.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Tutor Bot</p>
    </div>
</body>
</html>
"""
        
        # Прикрепляем текст и HTML
        part1 = MIMEText(text, 'plain', 'utf-8')
        part2 = MIMEText(html, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        
        # Отправляем
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return False
