document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const username = urlParams.get('username');
    if (username) document.getElementById('username').value = username;

    document.getElementById('personal-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        
        try {
            const response = await fetch('/api/personal', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            document.getElementById('message').textContent = result.message || result.error;
        } catch {
            document.getElementById('message').textContent = 'Ошибка сети';
        }
    });
});