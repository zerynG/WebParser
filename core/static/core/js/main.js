// Основной JavaScript для главной страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Sports Parser loaded successfully!');

    // Анимация появления карточек
    const cards = document.querySelectorAll('.nav-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';

        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // Обновление времени в реальном времени
    function updateTime() {
        const now = new Date();
        const timeElement = document.querySelector('.status-value');
        if (timeElement && timeElement.textContent === '-') {
            timeElement.textContent = now.toLocaleString('ru-RU');
        }
    }

    updateTime();
    setInterval(updateTime, 60000); // Обновлять каждую минуту
});