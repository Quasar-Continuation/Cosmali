document.addEventListener('DOMContentLoaded', () => {
    const spaceBackground = document.getElementById('spaceBackground');

    // twinkling stars
    function createStars(count = 150) {
        for (let i = 0; i < count; i++) {
            const star = document.createElement('div');
            star.className = 'star';
        
            const size = Math.random() * 1.5 + 0.5;
            star.style.width = `${size}px`;
            star.style.height = `${size}px`;
            star.style.top = `${Math.random() * 100}vh`;
            star.style.left = `${Math.random() * 100}vw`;
            star.style.animationDuration = `${Math.random() * 5 + 3}s`;
            star.style.animationDelay = `${Math.random() * 5}s`;
        
            spaceBackground.appendChild(star);
        }
    }

    // shooting stars from top-right to bottom-left
    function createShootingStar() {
        const star = document.createElement('div');
        star.className = 'shooting-star';
        
        // calc diagonal distance to ensure star travels across screen
        const distance = Math.sqrt(
            Math.pow(window.innerWidth, 2) + 
            Math.pow(window.innerHeight, 2)
        ) * 1.2;
        
        // duration based on distance (faster for longer distances)
        const duration = distance / 1000; // pixels per second
        
        // start position - top right area (off screen)
        const startX = window.innerWidth + 50;
        const startY = -50;
        
        star.style.setProperty('--distance', `${distance}px`);
        star.style.animationDuration = `${duration}s`;
        star.style.left = `${startX}px`;
        star.style.top = `${startY}px`;
        
        spaceBackground.appendChild(star);
        
        // remove the star after animation completes
        setTimeout(() => {
            star.remove();
        }, duration * 1000);
    }

    createStars();
    
    // create shooting stars at random intervals
    function startShootingStars() {
        // initial delay
        let delay = Math.random() * 3000 + 2000;
        
        const createWithDelay = () => {
            createShootingStar();
            delay = Math.random() * 3000 + 2000; // 2-5 seconds random (I absolutely hate how random delays are done in js because its the same as java)
            setTimeout(createWithDelay, delay); // I'm a D1 java hater fuck AP Comp Sci
        };
        
        setTimeout(createWithDelay, delay);
    }
    
    startShootingStars();
    
    // adjust stars on resize
    window.addEventListener('resize', () => {
        document.querySelectorAll('.shooting-star').forEach(star => star.remove());
    });
});