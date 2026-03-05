// Константы
const API_URL = '';
const MONTH_NAMES = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

// Глобальные переменные
let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let lessonsData = [];
let studentsData = [];
let currentModalData = null;
let adminTimezone = 3; // Часовой пояс репетитора (по умолчанию МСК)

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    initNavigation();
    initModals();
    loadDashboard();
    loadSettings();
});

// === Авторизация ===
function checkAuth() {
    const token = localStorage.getItem('auth_token');
    if (!token) {
        window.location.href = '/login';
    }
}

function logout() {
    if (confirm('Вы уверены, что хотите выйти?')) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
    }
}

// Добавляем токен ко всем запросам
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('auth_token');
    
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    
    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    
    return response;
}

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
            } else if (pageName === 'today') {
                loadToday();
            } else if (pageName === 'templates') {
                loadTemplates();
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
        const response = await fetchWithAuth(`${API_URL}/api/dashboard/stats`);
        const data = await response.json();
        
        document.getElementById('monthLessons').textContent = data.month_lessons;
        document.getElementById('monthCompleted').textContent = data.month_completed;
        document.getElementById('monthPending').textContent = data.month_pending;
        document.getElementById('monthIncome').textContent = formatMoney(data.month_income);
        document.getElementById('monthExpected').textContent = formatMoney(data.month_expected);
        
        document.getElementById('yearLessons').textContent = data.year_lessons;
        document.getElementById('yearCompleted').textContent = data.year_completed;
        document.getElementById('yearIncome').textContent = formatMoney(data.year_income);
        
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

// === Сегодня ===
async function loadToday() {
    try {
        const today = new Date();
        const dateStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        
        const dayNames = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
        const dayName = dayNames[today.getDay()];
        document.getElementById('todayDate').textContent = `${formatDateRu(dateStr)}, ${dayName}`;
        
        const response = await fetchWithAuth(`${API_URL}/api/lessons/month/${today.getFullYear()}/${today.getMonth() + 1}`);
        const data = await response.json();
        
        const todayLessons = data.lessons.filter(l => l.date === dateStr);
        todayLessons.sort((a, b) => a.time.localeCompare(b.time));
        
        const tbody = document.getElementById('todayTableBody');
        
        if (todayLessons.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 2rem; color: #94a3b8;">Сегодня уроков нет</td></tr>';
            return;
        }
        
        tbody.innerHTML = '';
        
        todayLessons.forEach(lesson => {
            const row = document.createElement('tr');
            if (lesson.is_moved) {
                row.style.borderLeft = '4px solid #f59e0b';
            }
            if (lesson.completed) {
                row.style.background = '#f0fdf4';
                row.style.borderLeft = '4px solid var(--success)';
            }
            
            const actions = [];
            if (!lesson.completed) {
                actions.push(`<button class="btn btn-success btn-sm" onclick="completeLessonQuick('${lesson.id}')">Отметить</button>`);
                actions.push(`<button class="btn btn-secondary btn-sm" onclick="openMoveLessonModalQuick('${lesson.id}', '${lesson.student_name}', '${lesson.date}', '${lesson.time}')">Перенести</button>`);
            } else {
                actions.push(`<button class="btn btn-icon btn-sm" onclick="uncompleteLessonQuick('${lesson.id}')" title="Отменить выполнение">↻</button>`);
            }
            
            row.innerHTML = `
                <td style="font-weight: 600; font-size: 1.125rem;">${formatTimeRange(lesson.time)}</td>
                <td>
                    ${lesson.student_name}
                    ${lesson.is_moved && !lesson.completed ? '<span style="color: #f59e0b; font-size: 0.75rem; margin-left: 0.5rem;">Перенесен</span>' : ''}
                </td>
                <td class="price-cell">${formatMoney(lesson.price)}</td>
                <td>
                    ${lesson.completed ? 
                        '<span style="color: var(--success); font-weight: 600;">Выполнен</span>' : 
                        '<span style="color: var(--text-secondary);">Запланирован</span>'
                    }
                </td>
                <td style="display: flex; gap: 0.5rem;">
                    ${actions.join('')}
                </td>
            `;
            
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading today:', error);
    }
}

async function completeLessonQuick(lessonId) {
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${lessonId}/complete`, {
            method: 'POST'
        });
        
        if (response.ok) {
            await loadToday();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error completing lesson:', error);
    }
}

async function uncompleteLessonQuick(lessonId) {
    if (!confirm('Отменить выполнение урока?')) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${lessonId}/uncomplete`, {
            method: 'POST'
        });
        
        if (response.ok) {
            await loadToday();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error uncompleting lesson:', error);
    }
}

// === Расписание ===
function previousMonth() {
    currentMonth--;
    if (currentMonth < 1) {
        currentMonth = 12;
        currentYear--;
    }
    loadSchedule();
}

function nextMonth() {
    currentMonth++;
    if (currentMonth > 12) {
        currentMonth = 1;
        currentYear++;
    }
    loadSchedule();
}

async function loadSchedule() {
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/month/${currentYear}/${currentMonth}`);
        const data = await response.json();
        lessonsData = data.lessons;
        
        renderCalendar();
    } catch (error) {
        console.error('Error loading schedule:', error);
    }
}

function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    const monthTitle = document.getElementById('currentMonth');
    
    monthTitle.textContent = `${MONTH_NAMES[currentMonth - 1]} ${currentYear}`;
    
    grid.innerHTML = '';
    
    // Добавляем заголовки дней недели
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    dayNames.forEach(dayName => {
        const headerDiv = document.createElement('div');
        headerDiv.className = 'calendar-day-header';
        headerDiv.textContent = dayName;
        grid.appendChild(headerDiv);
    });
    
    // Получаем первый день месяца и количество дней
    const firstDay = new Date(currentYear, currentMonth - 1, 1);
    const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    
    // Получаем день недели первого дня (0 = воскресенье, нужно конвертировать в понедельник = 0)
    let firstDayOfWeek = firstDay.getDay();
    firstDayOfWeek = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1; // Конвертируем: Пн=0, Вс=6
    
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    
    // Добавляем пустые ячейки до первого дня месяца
    for (let i = 0; i < firstDayOfWeek; i++) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'calendar-day empty';
        grid.appendChild(emptyDiv);
    }
    
    // Рендерим все дни месяца
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(currentYear, currentMonth - 1, day);
        const dayOfWeek = date.getDay();
        
        const dateStr = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        
        const dayDiv = document.createElement('div');
        dayDiv.className = 'calendar-day';
        
        // Выходные
        if (dayOfWeek === 0 || dayOfWeek === 6) {
            dayDiv.classList.add('weekend');
        }
        
        if (dateStr === todayStr) {
            dayDiv.classList.add('today');
        }
        
        if (dateStr < todayStr) {
            dayDiv.classList.add('past');
        }
        
        const dayNameShort = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'][dayOfWeek];
        
        dayDiv.innerHTML = `
            <div class="day-number">${day} <span class="day-name-mobile">${dayNameShort}</span></div>
            <div class="day-lessons" id="lessons-${dateStr}"></div>
            ${dateStr >= todayStr ? '<div class="add-lesson-hint">+</div>' : ''}
        `;
        
        // Только для текущих и будущих дней разрешаем добавление уроков
        if (dateStr >= todayStr) {
            dayDiv.addEventListener('click', (e) => {
                if (!e.target.closest('.lesson-item')) {
                    openAddLessonModal(dateStr);
                }
            });
        }
        
        grid.appendChild(dayDiv);
        
        // Добавляем уроки для этого дня
        const dayLessons = lessonsData.filter(l => l.date === dateStr);
        const lessonsContainer = dayDiv.querySelector('.day-lessons');
        
        dayLessons.forEach(lesson => {
            const lessonDiv = document.createElement('div');
            lessonDiv.className = 'lesson-item';
            if (lesson.is_moved) {
                lessonDiv.classList.add('moved');
            }
            if (lesson.completed) {
                lessonDiv.classList.add('completed');
            }
            
            lessonDiv.innerHTML = `
                <span class="lesson-time">${formatTimeRange(lesson.time)}</span>
                <span class="lesson-student">${lesson.student_name}</span>
                ${lesson.is_moved ? '<span class="lesson-moved-badge">↻</span>' : ''}
            `;
            
            // Только для текущих и будущих дней разрешаем клик на урок
            if (dateStr >= todayStr) {
                lessonDiv.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openLessonModal(lesson);
                });
            }
            
            lessonsContainer.appendChild(lessonDiv);
        });
    }
}

// === Модальные окна ===
function initModals() {
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

async function openAddLessonModal(date) {
    const modal = document.getElementById('lessonModal');
    const existingLesson = document.getElementById('existingLesson');
    const newLesson = document.getElementById('newLesson');
    
    currentModalData = { date, isNew: true };
    
    document.getElementById('modalTitle').textContent = 'Добавить урок';
    document.getElementById('newLessonDate').textContent = formatDateWithDay(date);
    
    existingLesson.style.display = 'none';
    newLesson.style.display = 'block';
    
    await loadStudentsForSelect();
    
    modal.classList.add('active');
}

async function openLessonModal(lesson) {
    const modal = document.getElementById('lessonModal');
    const existingLesson = document.getElementById('existingLesson');
    const newLesson = document.getElementById('newLesson');
    
    currentModalData = { lesson };
    
    document.getElementById('modalTitle').textContent = 'Информация об уроке';
    document.getElementById('lessonStudent').textContent = lesson.student_name;
    document.getElementById('lessonDate').textContent = formatDateWithDay(lesson.date);
    document.getElementById('lessonTime').textContent = formatTimeRange(lesson.time);
    document.getElementById('lessonPrice').textContent = formatMoney(lesson.price);
    document.getElementById('lessonStatus').textContent = lesson.completed ? 'Выполнен' : 'Запланирован';
    
    const completeBtn = document.getElementById('completeBtn');
    if (lesson.completed) {
        completeBtn.style.display = 'block';
        completeBtn.textContent = 'Отменить выполнение';
        completeBtn.className = 'btn btn-secondary btn-block';
        completeBtn.onclick = () => uncompleteLesson(lesson.id);
    } else {
        completeBtn.style.display = 'block';
        completeBtn.textContent = 'Отметить выполненным';
        completeBtn.className = 'btn btn-success btn-block';
        completeBtn.onclick = () => completeLesson(lesson.id);
    }
    
    document.getElementById('moveBtn').onclick = () => openMoveLessonModal(lesson);
    document.getElementById('deleteBtn').onclick = () => deleteLesson(lesson.id);
    
    existingLesson.style.display = 'block';
    newLesson.style.display = 'none';
    
    modal.classList.add('active');
}

function openMoveLessonModal(lesson) {
    closeModal();
    
    const modal = document.getElementById('moveLessonModal');
    currentModalData = { lesson };
    
    // Показываем информацию об уроке
    const info = document.getElementById('moveLessonInfo');
    info.innerHTML = `
        <div class="move-info-box">
            <strong>${lesson.student_name}</strong><br>
            <span style="color: var(--text-secondary);">Текущее время: ${formatDateWithDay(lesson.date)} в ${formatTimeRange(lesson.time)}</span>
        </div>
    `;
    
    // Устанавливаем минимальную дату (сегодня)
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('moveDatePicker').min = today;
    document.getElementById('moveDatePicker').value = '';
    
    // Очищаем поля
    document.getElementById('availableSlots').innerHTML = '<div class="slots-loading">Выберите дату</div>';
    document.getElementById('manualTimeInput').value = '';
    document.getElementById('manualTimeResult').innerHTML = '';
    
    modal.classList.add('active');
}

async function openMoveLessonModalQuick(lessonId, studentName, date, time) {
    const lesson = {
        id: lessonId,
        student_name: studentName,
        date: date,
        time: time
    };
    openMoveLessonModal(lesson);
}

// Обработчик выбора даты для переноса
document.getElementById('moveDatePicker')?.addEventListener('change', async (e) => {
    const date = e.target.value;
    if (!date) return;
    
    await loadAvailableSlots(date);
});

async function loadAvailableSlots(date) {
    const container = document.getElementById('availableSlots');
    container.innerHTML = '<div class="slots-loading">Загрузка...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/available-slots/${date}`);
        const data = await response.json();
        
        container.innerHTML = '';
        
        data.slots.forEach(slot => {
            const slotDiv = document.createElement('div');
            slotDiv.className = `slot-item ${slot.available ? 'slot-available' : 'slot-busy'}`;
            
            if (slot.available) {
                slotDiv.innerHTML = `
                    <div class="slot-time">${formatTimeRange(slot.time)}</div>
                    <div class="slot-status">Свободно</div>
                `;
                slotDiv.onclick = () => selectSlot(date, slot.time);
            } else {
                slotDiv.innerHTML = `
                    <div class="slot-time">${formatTimeRange(slot.time)}</div>
                    <div class="slot-status">Занято${slot.student_name ? ': ' + slot.student_name : ''}</div>
                `;
            }
            
            container.appendChild(slotDiv);
        });
    } catch (error) {
        console.error('Error loading slots:', error);
        container.innerHTML = '<div class="slots-error">Ошибка загрузки</div>';
    }
}

async function selectSlot(date, time) {
    if (!currentModalData || !currentModalData.lesson) return;
    
    if (!confirm(`Перенести урок на ${formatDateWithDay(date)} в ${time}?`)) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${currentModalData.lesson.id}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                new_date: date,
                new_time: time
            })
        });
        
        if (response.ok) {
            closeModal();
            await loadToday();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error moving lesson:', error);
        alert('Ошибка переноса урока');
    }
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('active');
    });
    currentModalData = null;
}


function formatDate(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function formatDateRu(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function formatDateWithDay(dateStr) {
    const date = new Date(dateStr + 'T00:00:00');
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const dayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
    const dayName = dayNames[date.getDay()];
    return `${day}.${month}.${year} (${dayName})`;
}

function formatTimeRange(startTime) {
    // Урок длится 1 час
    const [hours, minutes] = startTime.split(':').map(Number);
    const endHours = (hours + 1) % 24;
    const endTime = `${String(endHours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
    return `${startTime} - ${endTime}`;
}

async function loadStudentsForSelect() {
    try {
        const response = await fetchWithAuth(`${API_URL}/api/students`);
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
    const studentId = parseInt(document.getElementById('studentSelect').value);
    const time = document.getElementById('lessonTimeInput').value;
    
    if (!studentId || !time) {
        return;
    }
    
    const { date } = currentModalData;
    
    // Получаем цену ученика
    const student = studentsData.find(s => s.user_id === studentId);
    const price = student ? student.lesson_price : 1000;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                date: date,
                time: time,
                price: price
            })
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
        } else if (response.status === 409) {
            const error = await response.json();
            alert('Ошибка: ' + error.detail);
        }
    } catch (error) {
        console.error('Error adding lesson:', error);
        alert('Ошибка при добавлении урока');
    }
}

async function completeLesson(lessonId) {
    if (!confirm('Отметить урок как выполненный?')) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${lessonId}/complete`, {
            method: 'POST'
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error completing lesson:', error);
    }
}

async function uncompleteLesson(lessonId) {
    if (!confirm('Отменить выполнение урока?')) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${lessonId}/uncomplete`, {
            method: 'POST'
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error uncompleting lesson:', error);
    }
}


async function deleteLesson(lessonId) {
    if (!confirm('Удалить урок?')) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${lessonId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            closeModal();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error deleting lesson:', error);
    }
}

// === Ученики ===
async function loadStudents() {
    const tbody = document.getElementById('studentsTableBody');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #94a3b8;">Загрузка...</td></tr>';
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/students`);
        const data = await response.json();
        studentsData = data.students;
        
        if (studentsData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #94a3b8;">Пока нет учеников</td></tr>';
            return;
        }
        
        renderStudentsTable();
        
        // Запускаем обновление времени
        startStudentTimeUpdates();
    } catch (error) {
        console.error('Error loading students:', error);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #ef4444;">Ошибка загрузки</td></tr>';
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
    
    // Конвертируем часовой пояс относительно часового пояса репетитора
    const tzOffset = student.timezone_offset;
    const diffFromAdmin = tzOffset - adminTimezone;
    let tzDisplay;
    
    if (diffFromAdmin === 0) {
        tzDisplay = 'UTC' + (adminTimezone >= 0 ? '+' : '') + adminTimezone;
    } else if (diffFromAdmin > 0) {
        tzDisplay = `UTC${adminTimezone >= 0 ? '+' : ''}${adminTimezone}+${diffFromAdmin}`;
    } else {
        tzDisplay = `UTC${adminTimezone >= 0 ? '+' : ''}${adminTimezone}${diffFromAdmin}`;
    }
    
    // Получаем текущее время ученика
    const studentTime = getCurrentTimeForStudent(tzOffset);
    
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
        <td class="student-time-cell" data-timezone="${tzOffset}" data-user-id="${student.user_id}">${studentTime}</td>
        <td>
            <div class="table-actions">
                <button class="action-btn action-btn-settings" onclick="toggleStudentMenuTable(event, ${student.user_id})" title="Настройки">
                    ⋮
                </button>
                <div class="student-menu-table" id="menu-table-${student.user_id}" style="display: none;">
                    <button class="menu-item menu-item-edit" onclick="openEditStudentModal(${student.user_id}, '${student.name}', ${price}); closeAllMenus();">
                        Изменить цену
                    </button>
                    <button class="menu-item menu-item-delete" onclick="deleteStudent(${student.user_id}, '${student.name}'); closeAllMenus();">
                        Удалить
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
        const response = await fetchWithAuth(`${API_URL}/api/students/${userId}/price`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ price: price })
        });
        
        if (response.ok) {
            closeModal();
            await loadStudents();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error updating price:', error);
    }
}

async function deleteStudent(userId, name) {
    if (!confirm(`Удалить ученика "${name}"?\n\nВсе его уроки также будут удалены.`)) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/students/${userId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadStudents();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error deleting student:', error);
    }
}

// === Шаблоны расписания ===
const DAY_NAMES = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];

async function loadTemplates() {
    try {
        const response = await fetchWithAuth(`${API_URL}/api/recurring`);
        const data = await response.json();
        
        const grid = document.getElementById('templatesGrid');
        grid.innerHTML = '';
        
        // Создаем 7 колонок для всех дней недели
        for (let day = 0; day < 7; day++) {
            const dayDiv = document.createElement('div');
            dayDiv.className = 'template-day';
            
            dayDiv.innerHTML = `
                <div class="template-day-header">${DAY_NAMES[day]}</div>
                <div class="template-lessons" id="templates-day-${day}"></div>
                <button class="template-add-btn" onclick="openAddTemplateModal(${day})">+</button>
            `;
            
            grid.appendChild(dayDiv);
            
            // Добавляем шаблоны для этого дня
            const dayTemplates = data.templates.filter(t => t.day_of_week === day);
            dayTemplates.sort((a, b) => a.time.localeCompare(b.time));
            
            const lessonsContainer = dayDiv.querySelector('.template-lessons');
            
            dayTemplates.forEach(template => {
                const templateDiv = document.createElement('div');
                templateDiv.className = 'template-item';
                
                templateDiv.innerHTML = `
                    <span class="template-time">${formatTimeRange(template.time)}</span>
                    <span class="template-student">${template.student_name}</span>
                    <button class="template-delete" onclick="deleteTemplate('${template.id}', event)">×</button>
                `;
                
                lessonsContainer.appendChild(templateDiv);
            });
        }
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

async function openAddTemplateModal(dayOfWeek = null) {
    const modal = document.getElementById('addTemplateModal');
    
    // Если передан день недели - устанавливаем его
    if (dayOfWeek !== null) {
        document.getElementById('templateDaySelect').value = dayOfWeek;
    }
    
    // Загружаем учеников
    try {
        const response = await fetchWithAuth(`${API_URL}/api/students`);
        const data = await response.json();
        
        const select = document.getElementById('templateStudentSelect');
        select.innerHTML = '<option value="">Выберите ученика</option>';
        
        data.students.forEach(student => {
            const option = document.createElement('option');
            option.value = student.user_id;
            option.textContent = student.name;
            option.dataset.price = student.lesson_price;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading students:', error);
    }
    
    modal.classList.add('active');
}

document.getElementById('addTemplateForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const studentSelect = document.getElementById('templateStudentSelect');
    const studentId = parseInt(studentSelect.value);
    const dayOfWeek = parseInt(document.getElementById('templateDaySelect').value);
    const time = document.getElementById('templateTimeInput').value;
    const price = parseInt(studentSelect.selectedOptions[0]?.dataset.price || 1000);
    
    if (!studentId || !time) {
        return;
    }
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/recurring`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: studentId,
                day_of_week: dayOfWeek,
                time: time,
                price: price
            })
        });
        
        if (response.ok) {
            closeModal();
            await loadTemplates();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error creating template:', error);
    }
});

async function deleteTemplate(templateId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    const deleteFuture = confirm(
        'Удалить постоянный урок?\n\n' +
        'Нажмите OK чтобы удалить урок И все будущие уроки в календаре\n' +
        'Нажмите Отмена чтобы удалить только постоянный урок (уроки в календаре останутся)'
    );
    
    try {
        const url = deleteFuture 
            ? `${API_URL}/api/recurring/${templateId}?delete_future=true`
            : `${API_URL}/api/recurring/${templateId}`;
            
        const response = await fetchWithAuth(url, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.deleted_lessons > 0) {
                alert(`Удалено: постоянный урок + ${data.deleted_lessons} будущих уроков`);
            }
            await loadTemplates();
            await loadSchedule();
        }
    } catch (error) {
        console.error('Error deleting template:', error);
    }
}

// === Настройки ===
async function loadSettings() {
    try {
        const response = await fetchWithAuth(`${API_URL}/api/settings`);
        const data = await response.json();
        
        adminTimezone = data.settings.admin_timezone || 3;
        
        document.getElementById('adminTimezone').value = adminTimezone;
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
        const response = await fetchWithAuth(`${API_URL}/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            // Обновляем глобальную переменную
            adminTimezone = settings.admin_timezone;
            
            // Перезагружаем данные для обновления отображения
            await loadStudents();
            
            alert('Настройки сохранены');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('Ошибка сохранения настроек');
    }
});
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


// === Ручной ввод времени для переноса ===
async function checkManualTime() {
    const date = document.getElementById('moveDatePicker').value;
    const time = document.getElementById('manualTimeInput').value;
    const resultDiv = document.getElementById('manualTimeResult');
    
    if (!date) {
        resultDiv.innerHTML = '<div class="manual-time-error">Сначала выберите дату</div>';
        return;
    }
    
    if (!time) {
        resultDiv.innerHTML = '<div class="manual-time-error">Введите время</div>';
        return;
    }
    
    resultDiv.innerHTML = '<div class="manual-time-loading">Проверка...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/check-time/${date}/${time}`);
        const data = await response.json();
        
        if (data.available) {
            resultDiv.innerHTML = `
                <div class="manual-time-success">
                    ✓ Время ${formatTimeRange(time)} свободно
                    <button class="btn btn-success btn-sm" onclick="selectManualTime('${date}', '${time}')">
                        Перенести на это время
                    </button>
                </div>
            `;
        } else {
            const conflictsList = data.conflicts.map(c => 
                `<li>${c.time} - ${c.student_name}</li>`
            ).join('');
            
            resultDiv.innerHTML = `
                <div class="manual-time-error">
                    ✗ Время ${formatTimeRange(time)} занято:<br>
                    <ul style="margin: 0.5rem 0; padding-left: 1.5rem;">
                        ${conflictsList}
                    </ul>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error checking time:', error);
        resultDiv.innerHTML = '<div class="manual-time-error">Ошибка проверки времени</div>';
    }
}

async function selectManualTime(date, time) {
    if (!currentModalData || !currentModalData.lesson) return;
    
    if (!confirm(`Перенести урок на ${formatDateWithDay(date)} в ${formatTimeRange(time)}?`)) return;
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/lessons/${currentModalData.lesson.id}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                new_date: date,
                new_time: time
            })
        });
        
        if (response.ok) {
            closeModal();
            await loadToday();
            await loadSchedule();
            await loadDashboard();
        }
    } catch (error) {
        console.error('Error moving lesson:', error);
        alert('Ошибка переноса урока');
    }
}


// === История работы ===
async function openHistoryModal() {
    const modal = document.getElementById('historyModal');
    const container = document.getElementById('historyContainer');
    
    container.innerHTML = '<div class="history-loading">Загрузка...</div>';
    modal.classList.add('active');
    
    try {
        const response = await fetchWithAuth(`${API_URL}/api/dashboard/history`);
        const data = await response.json();
        
        if (data.history.length === 0) {
            container.innerHTML = '<div class="history-empty">История пока пуста</div>';
            return;
        }
        
        renderHistory(data.history);
    } catch (error) {
        console.error('Error loading history:', error);
        container.innerHTML = '<div class="history-error">Ошибка загрузки истории</div>';
    }
}

function renderHistory(history) {
    const container = document.getElementById('historyContainer');
    
    const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
    
    // Группируем по годам
    const byYear = {};
    history.forEach(item => {
        if (!byYear[item.year]) {
            byYear[item.year] = [];
        }
        byYear[item.year].push(item);
    });
    
    container.innerHTML = '';
    
    // Сортируем годы (новые первые)
    const years = Object.keys(byYear).sort((a, b) => b - a);
    
    years.forEach(year => {
        const yearDiv = document.createElement('div');
        yearDiv.className = 'history-year';
        
        const yearHeader = document.createElement('h3');
        yearHeader.className = 'history-year-header';
        yearHeader.textContent = `${year} год`;
        yearDiv.appendChild(yearHeader);
        
        const monthsGrid = document.createElement('div');
        monthsGrid.className = 'history-months-grid';
        
        byYear[year].forEach(item => {
            const monthCard = document.createElement('div');
            monthCard.className = 'history-month-card';
            
            monthCard.innerHTML = `
                <div class="history-month-name">${monthNames[item.month - 1]}</div>
                <div class="history-month-stats">
                    <div class="history-stat">
                        <span class="history-stat-label">Уроков:</span>
                        <span class="history-stat-value">${item.total_lessons}</span>
                    </div>
                    <div class="history-stat">
                        <span class="history-stat-label">Проведено:</span>
                        <span class="history-stat-value">${item.completed_lessons}</span>
                    </div>
                    <div class="history-stat">
                        <span class="history-stat-label">Доход:</span>
                        <span class="history-stat-value history-stat-money">${formatMoney(item.completed_income)}</span>
                    </div>
                </div>
            `;
            
            monthsGrid.appendChild(monthCard);
        });
        
        yearDiv.appendChild(monthsGrid);
        container.appendChild(yearDiv);
    });
}


// === Время учеников ===
function getCurrentTimeForStudent(timezoneOffset) {
    const now = new Date();
    
    // Получаем UTC время
    const utcTime = now.getTime() + (now.getTimezoneOffset() * 60000);
    
    // Добавляем смещение часового пояса ученика
    const studentTime = new Date(utcTime + (timezoneOffset * 3600000));
    
    const hours = String(studentTime.getHours()).padStart(2, '0');
    const minutes = String(studentTime.getMinutes()).padStart(2, '0');
    
    return `${hours}:${minutes}`;
}

function updateAllStudentTimes() {
    // Обновляем время для всех учеников в таблице
    const timeCells = document.querySelectorAll('.student-time-cell');
    
    timeCells.forEach(cell => {
        const timezone = parseInt(cell.dataset.timezone);
        cell.textContent = getCurrentTimeForStudent(timezone);
    });
}

let studentTimeInterval = null;

function startStudentTimeUpdates() {
    // Останавливаем предыдущий интервал если есть
    if (studentTimeInterval) {
        clearInterval(studentTimeInterval);
    }
    
    // Первое обновление сразу
    updateAllStudentTimes();
    
    // Вычисляем сколько миллисекунд до следующей минуты
    const now = new Date();
    const msUntilNextMinute = (60 - now.getSeconds()) * 1000 - now.getMilliseconds();
    
    // Запускаем первое обновление в начале следующей минуты
    setTimeout(() => {
        updateAllStudentTimes();
        
        // Затем обновляем каждую минуту
        studentTimeInterval = setInterval(updateAllStudentTimes, 60000);
    }, msUntilNextMinute);
}
