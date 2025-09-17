// static/js/main.js

// Подключаем обработчики для кнопок входа/регистрации
function setupAuthButtons() {
    const btnRegister = document.getElementById('btn-register');
    const btnLogin = document.getElementById('btn-login');

    if (btnRegister) {
        btnRegister.onclick = () => showForm('register-form');
    }
    if (btnLogin) {
        btnLogin.onclick = () => showForm('login-form');
    }
}

// Показать/скрыть формы
function showForm(formId) {
    const registerForm = document.getElementById('register-form');
    const loginForm = document.getElementById('login-form');

    if (registerForm) registerForm.style.display = 'none';
    if (loginForm) loginForm.style.display = 'none';

    if (formId) {
        const form = document.getElementById(formId);
        if (form) form.style.display = 'block';
    }
}

// Регистрация
document.addEventListener('DOMContentLoaded', () => {
    const submitRegister = document.getElementById('submit-register');
    if (submitRegister) {
        submitRegister.onclick = async () => {
            const username = document.getElementById('reg-username')?.value.trim();
            const email = document.getElementById('reg-email')?.value.trim();
            const password = document.getElementById('reg-password')?.value;

            if (!username || !email || !password) {
                showMessage('reg-message', 'Заполните все поля', 'error');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('username', username);
                formData.append('email', email);
                formData.append('password', password);

                const res = await fetch('/api/register', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) throw new Error('Сетевая ошибка');

                const data = await res.json();

                if (data.error) {
                    showMessage('reg-message', data.error, 'error');
                } else {
                    showMessage('reg-message', data.message, 'success');
                    document.getElementById('reg-username').value = '';
                    document.getElementById('reg-email').value = '';
                    document.getElementById('reg-password').value = '';
                    setTimeout(() => showForm('login-form'), 2000);
                }
            } catch (err) {
                showMessage('reg-message', 'Ошибка сети. Попробуйте позже.', 'error');
            }
        };
    }
});

// Вход
document.addEventListener('DOMContentLoaded', () => {
    const submitLogin = document.getElementById('submit-login');
    if (submitLogin) {
        submitLogin.onclick = async () => {
            const email = document.getElementById('login-email')?.value.trim();
            const password = document.getElementById('login-password')?.value;

            if (!email || !password) {
                showMessage('login-message', 'Заполните все поля', 'error');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('email', email);
                formData.append('password', password);

                const res = await fetch('/api/login', {
                    method: 'POST',
                    body: formData
                });

                if (!res.ok) throw new Error('Сетевая ошибка');

                const data = await res.json();

                if (data.error) {
                    showMessage('login-message', data.error, 'error');
                } else {
                    // Сохраняем имя пользователя в localStorage
                    localStorage.setItem('username', data.user.username);
                    showWelcome(data.user.username);
                    setupLogout();
                }
            } catch (err) {
                showMessage('login-message', 'Ошибка сети. Попробуйте позже.', 'error');
            }
        };
    }
});

// Показ сообщения
function showMessage(elementId, text, type = 'info') {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerText = text;
        el.className = type;
    }
}

// Показ приветствия
function showWelcome(username) {
    const welcomeEl = document.getElementById('welcome-username');
    const welcomeMsg = document.getElementById('welcome-message');
    const authButtons = document.getElementById('auth-buttons');

    if (welcomeEl) welcomeEl.innerText = username;
    if (welcomeMsg) welcomeMsg.style.display = 'block';
    if (authButtons) {
        authButtons.innerHTML = `
            <button id="btn-lk">ЛК</button>
            <button id="btn-logout">Выйти</button>
        `;
        setupLogout();
        setupLK(username);
    }
}

// Настройка кнопки выхода
function setupLogout() {
    const logoutBtn = document.getElementById('btn-logout');
    if (logoutBtn) {
        logoutBtn.onclick = async () => {
            // Отправляем запрос на сервер для выхода
            await fetch('/api/logout', { method: 'POST' });

            // Перезагружаем страницу
            location.reload();
        };
    }
}


document.addEventListener('DOMContentLoaded', async () => {
    setupAuthButtons();

    // Проверяем сессию на сервере
    try {
        const res = await fetch('/api/profile');
        if (res.ok) {
            const data = await res.json();
            // Получаем username из куки (можно добавить в ответ /api/profile)
            // Пока — заглушка:
            const username = "Mika"; // ← Замени на реальный способ
            showWelcome(username);
            setupLogout();
        }
    } catch (err) {
        console.log("Сессия не активна");
    }
});


function setupLK(username) {
    const btnLK = document.getElementById('btn-lk');
    if (btnLK) {
        btnLK.onclick = () => {
            window.location.href = `/static/personal.html?username=${username}`;
        };
    }
}