// Algorithmic Particle Wave Animation for Login Page
// Inspired by Apple's aesthetic minimalism

class ParticleWave {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.particleCount = 80;
        this.connectionDistance = 150;
        this.mouse = { x: null, y: null, radius: 120 };

        this.resize();
        this.init();
        this.animate();

        window.addEventListener('resize', () => this.resize());
        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.x;
            this.mouse.y = e.y;
        });
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    init() {
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            const x = Math.random() * this.canvas.width;
            const y = Math.random() * this.canvas.height;
            const size = Math.random() * 2 + 1;
            const speedX = (Math.random() - 0.5) * 0.5;
            const speedY = (Math.random() - 0.5) * 0.5;

            this.particles.push({
                x: x,
                y: y,
                size: size,
                baseX: x,
                baseY: y,
                speedX: speedX,
                speedY: speedY,
                density: (Math.random() * 30) + 1
            });
        }
    }

    drawParticle(particle) {
        this.ctx.fillStyle = 'rgba(0, 113, 227, 0.5)';
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        this.ctx.closePath();
        this.ctx.fill();
    }

    connectParticles() {
        for (let a = 0; a < this.particles.length; a++) {
            for (let b = a; b < this.particles.length; b++) {
                const dx = this.particles[a].x - this.particles[b].x;
                const dy = this.particles[a].y - this.particles[b].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < this.connectionDistance) {
                    const opacity = 1 - (distance / this.connectionDistance);
                    this.ctx.strokeStyle = `rgba(0, 113, 227, ${opacity * 0.15})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[a].x, this.particles[a].y);
                    this.ctx.lineTo(this.particles[b].x, this.particles[b].y);
                    this.ctx.stroke();
                }
            }
        }
    }

    updateParticles() {
        for (let i = 0; i < this.particles.length; i++) {
            let particle = this.particles[i];

            // Mouse interaction
            if (this.mouse.x != null && this.mouse.y != null) {
                const dx = this.mouse.x - particle.x;
                const dy = this.mouse.y - particle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const forceDirectionX = dx / distance;
                const forceDirectionY = dy / distance;
                const maxDistance = this.mouse.radius;
                const force = (maxDistance - distance) / maxDistance;
                const directionX = forceDirectionX * force * particle.density;
                const directionY = forceDirectionY * force * particle.density;

                if (distance < this.mouse.radius) {
                    particle.x -= directionX;
                    particle.y -= directionY;
                } else {
                    if (particle.x !== particle.baseX) {
                        const dx = particle.x - particle.baseX;
                        particle.x -= dx / 10;
                    }
                    if (particle.y !== particle.baseY) {
                        const dy = particle.y - particle.baseY;
                        particle.y -= dy / 10;
                    }
                }
            }

            // Gentle drift
            particle.x += particle.speedX;
            particle.y += particle.speedY;

            // Boundary check
            if (particle.x < 0 || particle.x > this.canvas.width) {
                particle.speedX = -particle.speedX;
            }
            if (particle.y < 0 || particle.y > this.canvas.height) {
                particle.speedY = -particle.speedY;
            }
        }
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw gradient background
        const gradient = this.ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#fbfbfd');
        gradient.addColorStop(1, '#f5f5f7');
        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Update and draw particles
        this.updateParticles();
        this.connectParticles();

        for (let i = 0; i < this.particles.length; i++) {
            this.drawParticle(this.particles[i]);
        }

        requestAnimationFrame(() => this.animate());
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('particleCanvas')) {
        new ParticleWave('particleCanvas');
    }
});
