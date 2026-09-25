import React from 'react';
import ReactDOM from 'react-dom/client';
import { I18nProvider } from './i18n/context';
import App from './App';
import './index.css';

// ── Cosmic background (canvas starfield) ──
(function cosmic() {
  const c = document.createElement('canvas');
  c.id = 'cosmic-bg';
  document.body.prepend(c);
  const ctx = c.getContext('2d')!;
  const stars: Array<{x:number;y:number;r:number;o:number;s:number;p:number}> = [];
  function resize() { c.width = window.innerWidth; c.height = window.innerHeight; }
  resize(); window.addEventListener('resize', resize);
  for (let i = 0; i < 60; i++) {
    stars.push({
      x: Math.random() * 2000, y: Math.random() * 2000,
      r: Math.random() * 1.2 + 0.3,
      o: Math.random() * 0.5 + 0.1,
      s: Math.random() * 0.3 + 0.05,
      p: Math.random() * Math.PI * 2,
    });
  }
  let t = 0;
  // Theme-responsive star colors
  const getStarColor = () => {
    const theme = document.documentElement.getAttribute('data-theme');
    return theme === 'light'
      ? { r: 0, g: 152, b: 199, a: 0.35 }   // light: muted cyan
      : { r: 0, g: 229, b: 255, a: 0.5 };    // dark: bright cyan
  };

  function draw() {
    const col = getStarColor();
    t += 0.003;
    ctx.clearRect(0, 0, c.width, c.height);
    for (const s of stars) {
      const px = (s.x + Math.sin(t * s.s + s.p) * 20 + c.width) % c.width;
      const py = (s.y + Math.cos(t * s.s + s.p) * 12 + c.height) % c.height;
      const alpha = col.a + Math.sin(t * 2 + s.p) * 0.08;
      ctx.beginPath();
      ctx.arc(px, py, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${col.r},${col.g},${col.b},${Math.max(0, alpha)})`;
      ctx.fill();
    }
    requestAnimationFrame(draw);
  }
  draw();
})();

// HUD effects
const scanlines = document.createElement('div'); scanlines.className = 'scanlines'; document.body.appendChild(scanlines);
const vignette = document.createElement('div'); vignette.className = 'vignette-overlay'; document.body.appendChild(vignette);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </React.StrictMode>,
);
