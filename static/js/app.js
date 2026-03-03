// Константы
const API_URL = '';
const TIME_SLOTS = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00'];
const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const DAY_NAMES = {
    'monday': 'Понедельник',
    'tuesday': 'Вторник',
    'wednesday': 'Среда',
    'thursday': 'Четверг',
    'friday': 'Пятница',
    'saturday': 'Суббота',
    'sunday': 'Воскресенье'
};

// Глобальные переменные
let scheduleData = {};
let studentsData = [];
let currentModalData = null;

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initModals();
    loadDashboard();
    loadSettings();
});

// === Навигация ===
function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const pages = document.querySelectorAll('.page');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const pageName = link.dataset.page;
            
            navLinks.forEach(l => l.classList.remove('active'));
            pages.forEach(p => p.classList.remove('active'));
            
            link.classList.add('active');
            document.getElementById(pageName).classList.add('active');
            
            if (pageName === 'dashboard') {
                loadDashboard();
            } else if (pageName === 'schedule') {
                loadSchedule();
            } else if (pageName === 'students') {
                loadStudents();
            }
        });
    });
}

// === Личный кабинет ===
async function loadDashboard() {
    try {
        const response = await fetch(`${API_URL}/api/dashboard/stats`);
        const data = await response.json();
        
        document.getElementById('lessonsPerDay').textContent = data.lessons.per_day_avg;
        document.getElementById('lessonsPerWeek').textContent = data.lessons.per_week;
        document.getElementById('lessonsPerMonth').textContent = data.lessons.per_month;
        document.getElementById('incomePerWeek').textContent = formatMoney(data.income.per_week);
        document.getElementById('incomePerMonth').textContent = formatMoney(data.income.per_month);
        document.getElementById('studentsCount').textContent = data.students_count;
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function formatMoney(amount) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0
    }).format(amount);
}

// === Расписание ===
async function loadSchedule() {
    try {
        const response = await fetch(`${API_URL}/api/schedule/week`);
        const data = await response.json();
        scheduleData = data.schedule;
        
        renderScheduleTable();
    } catch (error) {
        console.error('Error loading schedule:', error);
        showError('Ошибка загрузки расписания');
    }
}

function renderScheduleTable() {
    const tbody = document.getElementById('scheduleBody');
    tbody.innerHTML = '';
    
    TIME_SLOTS.forEach(time => {
        const row = document.createElement('tr');
        
        const timeCell = document.createElement('td');
        timeCell.className = 'time-cell';
        timeCell.textContent = time;
        row.appendChild(timeCell);
        
        DAYS.forEach(day => {
            const cell = document.createElement('td');
            cell.className = 'lesson-cell';
            
            const dayLessons = scheduleData[day] || [];
            const lesson = dayLessons.find(l => l.time === time);
            
            if (lesson) {
                const badge = document.createElement('div');
                badge.className = 'lesson-badge';
                badge.textContent = lesson.student_name;
                cell.appendChild(badge);
                
                cell.addEventListener('click', () => openLessonModal(day, time, lesson));
            } else {
                cell.classList.add('empty');
                cell.addEventListener('click', () => openLessonModal(day, time, null));
            }
            
            row.appendChild(cell);
        });
        
        tbody.appendChild(row);
    });
}

// === Модальные окна ===
function initModals() {
    const lessonModal = document.getElementById('lessonModal');
    const editStudentModal = document.getElementById('editStudentModal');
    
    // Закрытие модалок
    document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
        el.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-close') || e.target.classList.contains('modal-overlay')) {
                closeModal();
            }
        });
    });
    
    document.getElementById('addLessonForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await addLesson();
    });
    
    document.getElementById('editStudentForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveStudentPrice();
    });
}

async function openLessonModal(day, time, lesson) {
    const modal = document.getElementById('lessonModal');
    const existingLesson = document.getElementById('existingLesson');
    const newLesson = document.getElementById('newLesson');
    
    currentModalData = { day, time, lesson };
    
    if (lesson) {
        document.getElementById('modalTitle').textContent = 'Информация об уроке';
        document.getElementById('lessonStudent').textContent = lesson.student_name;
        document.getElementById('lessonDay').textContent = DAY_NAMES[day];
        document.getElementById('lessonTime').textContent = time;
        
        existingLesson.style.display = 'block';
        newLesson.style.display = 'none';
        
        document.getElementById('deleteBtn').onclick = () => deleteLesson(lesson.student_id, day, time);
    } else {
        document.getElementById('modalTitle').textContent = 'Добавить урок';
        document.getElementById('newLessonDay').textContent = DAY_NAMES[day];
        document.getElementById('newLessonTime').textContent = time;
        
        existingLesson.style.display = 'none';
        newLesson.style.display = 'block';
        
        await loadStudentsForSelect();
    }
    
    modal.classList.add('active');
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('active');
    });
    currentModalData = null;
}

async function loadStudentsForSelect() {
    try {
        const response = await fetch(`${API_URL}/api/students`);
        const data = await response.json();
        
        const select = document.getElementById('studentSelect');
        select.innerHTML = '<option value="">Выберите ученика</option>';
        
        data.students.forEach(student => {
            const option = document.createElement('option');
            option.value = student.user_id;
            option.textContent = student.name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading students:', error);
    }
}

async function addLesson() {
    const studentId = document.getElementById('studentSelect').value;
    
    if (!studentId) {
        alert('Выберите ученика');
        return;
    }
    
    const { day, time } = currentModalData;
    
    try {
        const response = await fetch(`${API_URL}/api/students/${studentId}/schedule/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ day, time })
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
            showSuccess('Урок добавлен');
        } else {
            const error = await response.json();
            alert('Ошибка: ' + (error.detail || 'Не удалось добавить урок'));
        }
    } catch (error) {
        console.error('Error adding lesson:', error);
        alert('Ошибка при добавлении урока');
    }
}

async function deleteLesson(studentId, day, time) {
    if (!confirm('Удалить этот урок?')) return;
    
    try {
        const response = await fetch(`${API_URL}/api/students/${studentId}/schedule?day=${day}&time=${time}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
            showSuccess('Урок удален');
        } else {
            alert('Ошибка при удалении урока');
        }
    } catch (error) {
        console.error('Error deleting lesson:', error);
        alert('Ошибка при удалении урока');
    }
}

// === Ученики ===
async function loadStudents() {
    const tbody = document.getElementById('studentsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #94a3b8;">Загрузка...</td></tr>';
    
    try {
        const response = await fetch(`${API_URL}/api/students`);
        const data = await response.json();
        studentsData = data.students;
        
        if (studentsData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #94a3b8;">Пока нет учеников</td></tr>';
            return;
        }
        
        renderStudentsTable();
    } catch (error) {
        console.error('Error loading students:', error);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem; color: #ef4444;">Ошибка загрузки</td></tr>';
    }
}

function renderStudentsTable() {
    const tbody = document.getElementById('studentsTableBody');
    tbody.innerHTML = '';
    
    studentsData.forEach(student => {
        const row = createStudentRow(student);
        tbody.appendChild(row);
    });
}

function createStudentRow(student) {
    const row = document.createElement('tr');
    const price = student.lesson_price || 1000;
    
    // Конвертируем часовой пояс в МСК
    const tzOffset = student.timezone_offset;
    const mskOffset = 3;
    const diffFromMsk = tzOffset - mskOffset;
    let tzDisplay;
    
    if (diffFromMsk === 0) {
        tzDisplay = 'МСК';
    } else if (diffFromMsk > 0) {
        tzDisplay = `МСК+${diffFromMsk}`;
    } else {
        tzDisplay = `МСК${diffFromMsk}`;
    }
    
    row.innerHTML = `
        <td>
            <div class="student-name-cell">
                <div class="student-avatar-small">${student.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}</div>
                <span>${student.name}</span>
            </div>
        </td>
        <td>${student.username ? '@' + student.username : '—'}</td>
        <td>${student.lessons_count}</td>
        <td class="price-cell">${formatMoney(price)}</td>
        <td>${tzDisplay}</td>
        <td>
            <div class="table-actions">
                <button class="action-btn action-btn-settings" onclick="toggleStudentMenuTable(event, ${student.user_id})" title="Настройки">
                    ⚙️
                </button>
                <div class="student-menu-table" id="menu-table-${student.user_id}" style="display: none;">
                    <button class="menu-item menu-item-edit" onclick="openEditStudentModal(${student.user_id}, '${student.name}', ${price}); closeAllMenus();">
                        ✏️ Изменить цену
                    </button>
                    <button class="menu-item menu-item-delete" onclick="deleteStudent(${student.user_id}, '${student.name}'); closeAllMenus();">
                        🗑️ Удалить
                    </button>
                </div>
            </div>
        </td>
    `;
    
    return row;
}

async function openEditStudentModal(userId, name, price) {
    document.getElementById('editStudentId').value = userId;
    document.getElementById('editStudentName').value = name;
    document.getElementById('editStudentPrice').value = price;
    
    document.getElementById('editStudentModal').classList.add('active');
}

async function saveStudentPrice() {
    const userId = document.getElementById('editStudentId').value;
    const price = parseInt(document.getElementById('editStudentPrice').value);
    
    try {
        const response = await fetch(`${API_URL}/api/students/${userId}/price?price=${price}`, {
            method: 'PUT'
        });
        
        if (response.ok) {
            closeModal();
            await loadStudents();
            await loadDashboard();
            showSuccess('Цена обновлена');
        } else {
            alert('Ошибка при обновлении цены');
        }
    } catch (error) {
        console.error('Error updating price:', error);
        alert('Ошибка при обновлении цены');
    }
}

async function deleteStudent(userId, name) {
    if (!confirm(`Удалить ученика "${name}"?\n\nВсе его уроки также будут удалены.`)) return;
    
    try {
        const response = await fetch(`${API_URL}/api/students/${userId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadStudents();
            await loadSchedule();
            await loadDashboard();
            showSuccess(`Ученик "${name}" удален`);
        } else {
            alert('Ошибка при удалении ученика');
        }
    } catch (error) {
        console.error('Error deleting student:', error);
        alert('Ошибка при удалении ученика');
    }
}

// === Настройки ===
async function loadSettings() {
    try {
        const response = await fetch(`${API_URL}/api/settings`);
        const data = await response.json();
        
        document.getElementById('adminTimezone').value = data.settings.admin_timezone;
        document.getElementById('reminderMinutes').value = data.settings.reminder_minutes_before || 60;
        document.getElementById('reportMinutes').value = data.settings.homework_check_minutes_before;
        document.getElementById('dailyTime').value = data.settings.admin_daily_reminder_time;
        document.getElementById('defaultPrice').value = data.settings.default_lesson_price || 1000;
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

document.getElementById('settingsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const settings = {
        admin_timezone: parseInt(document.getElementById('adminTimezone').value),
        reminder_minutes_before: parseInt(document.getElementById('reminderMinutes').value),
        homework_check_minutes_before: parseInt(document.getElementById('reportMinutes').value),
        admin_daily_reminder_time: document.getElementById('dailyTime').value,
        default_lesson_price: parseInt(document.getElementById('defaultPrice').value)
    };
    
    try {
        const response = await fetch(`${API_URL}/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showSuccess('Настройки сохранены! Перезапустите бота для применения изменений.');
        } else {
            alert('Ошибка при сохранении настроек');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Ошибка при сохранении настроек');
    }
});

// === Уведомления ===
function showSuccess(message) {
    alert('✅ ' + message);
}

function showError(message) {
    alert('❌ ' + message);
}

// === Меню настроек ученика ===
function toggleStudentMenu(event, userId) {
    event.stopPropagation();
    
    const menu = document.getElementById(`menu-${userId}`);
    const isVisible = menu.style.display === 'block';
    
    closeAllMenus();
    
    if (!isVisible) {
        menu.style.display = 'block';
    }
}

function toggleStudentMenuTable(event, userId) {
    event.stopPropagation();
    
    const menu = document.getElementById(`menu-table-${userId}`);
    const isVisible = menu.style.display === 'block';
    
    closeAllMenus();
    
    if (!isVisible) {
        menu.style.display = 'block';
    }
}

function closeAllMenus() {
    document.querySelectorAll('.student-menu, .student-menu-table').forEach(menu => {
        menu.style.display = 'none';
    });
}

// Закрываем меню при клике вне его
document.addEventListener('click', (e) => {
    if (!e.target.closest('.student-settings-btn') && 
        !e.target.closest('.action-btn-settings') && 
        !e.target.closest('.student-menu') && 
        !e.target.closest('.student-menu-table')) {
        closeAllMenus();
    }
});
