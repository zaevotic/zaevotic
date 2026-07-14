document.addEventListener("DOMContentLoaded", () => {
  /* ── Custom Cursor Logic ───────────────────────────────────────────────── */
  const ccDot = document.getElementById('cc-dot');
  const ccRing = document.getElementById('cc-ring');
  const ccFocus = document.getElementById('cc-focus');
  
  if (ccDot && window.matchMedia("(pointer: fine)").matches) {
    let mouseX = -100, mouseY = -100;
    let ringX = -100, ringY = -100;
    let mode = 'idle';
    let isMouseDown = false;
    
    function lerp(start, end, amt) {
      return (1 - amt) * start + amt * end;
    }
    
    function animateCursor() {
      ringX = lerp(ringX, mouseX, 0.15);
      ringY = lerp(ringY, mouseY, 0.15);
      
      const scaleDot = isMouseDown ? 1.5 : 1;
      const scaleRing = isMouseDown ? 0.8 : 1;
      
      if (mode === 'idle') {
        ccDot.style.opacity = '1';
        ccRing.style.opacity = '1';
        ccFocus.style.opacity = '0';
        
        ccDot.style.transform = `translate(calc(${mouseX}px - 50%), calc(${mouseY}px - 50%)) scale(${scaleDot})`;
        ccRing.style.transform = `translate(calc(${ringX}px - 50%), calc(${ringY}px - 50%)) scale(${scaleRing})`;
      } else if (mode === 'focus') {
        ccDot.style.opacity = '0';
        ccRing.style.opacity = '0';
        ccFocus.style.opacity = '1';
      }
      
      requestAnimationFrame(animateCursor);
    }
    requestAnimationFrame(animateCursor);
    
    const INTERACTIVE_SELECTOR = 'a, button, input, textarea, select, [role="button"], .tab, .jentry, .filter';
    let lastTarget = null;
    
    function applyTarget(el) {
      if (!el) {
        mode = 'idle';
        lastTarget = null;
        return;
      }
      const PAD = 6;
      const rect = el.getBoundingClientRect();
      const w = rect.width + PAD * 2;
      const h = rect.height + PAD * 2;
      const x = rect.left - PAD;
      const y = rect.top - PAD;
      
      ccFocus.style.width = `${w}px`;
      ccFocus.style.height = `${h}px`;
      ccFocus.style.transform = `translate(${x}px, ${y}px) scale(${isMouseDown ? 1.06 : 1})`;
      
      mode = 'focus';
      lastTarget = el;
    }
    
    window.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      
      const target = e.target;
      const el = target.closest ? target.closest(INTERACTIVE_SELECTOR) : null;
      if (el !== lastTarget) {
        applyTarget(el);
      }
    });
    
    window.addEventListener('mousedown', () => {
      isMouseDown = true;
      document.body.classList.add('cursor-down');
      if (mode === 'focus' && lastTarget) applyTarget(lastTarget);
    });
    window.addEventListener('mouseup', () => {
      isMouseDown = false;
      document.body.classList.remove('cursor-down');
      if (mode === 'focus' && lastTarget) applyTarget(lastTarget);
    });
  }

  /* ── Tab Indicator Logic ───────────────────────────────────────────────── */
  const tabs = document.querySelectorAll('.tab-link');
  const indicator = document.querySelector('.tab-indicator');
  
  function updateIndicator(activeTab) {
    if (!activeTab || !indicator) return;
    indicator.style.width = `${activeTab.offsetWidth}px`;
    indicator.style.transform = `translateX(${activeTab.offsetLeft}px)`;
  }

  // Init indicator
  const activeTab = document.querySelector('.tab-link.active');
  updateIndicator(activeTab);

  tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      if (tab.classList.contains('active')) return;
      
      // Shake animation
      tab.classList.remove('shake');
      // trigger reflow
      void tab.offsetWidth;
      tab.classList.add('shake');
      
      setTimeout(() => {
        tab.classList.remove('shake');
      }, 300);
    });
  });

  window.addEventListener('resize', () => {
    updateIndicator(document.querySelector('.tab-link.active'));
  });

  /* ── Progress Bar Animation ────────────────────────────────────────────── */
  const progressBar = document.querySelector('.cs-progress-bar');
  const progressText = document.querySelector('.cs-progress-labels span:last-child');
  
  if (progressBar && progressText) {
    const target = 67;
    const duration = 1500; // ms
    const startTime = performance.now();

    function easeOutQuart(x) {
      return 1 - Math.pow(1 - x, 4);
    }

    function animateProgress(time) {
      let elapsed = time - startTime;
      let rawProgress = Math.min(elapsed / duration, 1);
      let eased = easeOutQuart(rawProgress);
      let currentVal = Math.floor(eased * target);
      
      progressBar.style.width = `${eased * target}%`;
      progressText.textContent = `${currentVal}%`;

      if (rawProgress < 1) {
        requestAnimationFrame(animateProgress);
      } else {
        progressText.textContent = `${target}%`;
      }
    }
    requestAnimationFrame(animateProgress);
  }

  /* ── Matrix Glitch Logic ───────────────────────────────────────────────── */
  const canvas = document.getElementById('matrix-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  const glitchColors = ['#b6182b', '#ff2436', '#c47c2e', '#5c1018'];
  const characters = 'ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ01';
  const lettersAndSymbols = Array.from(characters);
  
  const fontSize = 16;
  const charWidth = 10;
  const charHeight = 20;
  
  let letters = [];
  let grid = { columns: 0, rows: 0 };
  let activeLetters = new Set();
  let animationFrameId;
  let lastGlitchTime = Date.now();
  
  function getRandomChar() {
    return lettersAndSymbols[Math.floor(Math.random() * lettersAndSymbols.length)];
  }
  
  function getRandomColor() {
    return glitchColors[Math.floor(Math.random() * glitchColors.length)];
  }
  
  function hexToRgb(hex) {
    const shorthandRegex = /^#?([a-f\d])([a-f\d])([a-f\d])$/i;
    hex = hex.replace(shorthandRegex, (m, r, g, b) => r + r + g + g + b + b);
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }
  
  function interpolateColor(start, end, factor) {
    const r = Math.round(start.r + (end.r - start.r) * factor);
    const g = Math.round(start.g + (end.g - start.g) * factor);
    const b = Math.round(start.b + (end.b - start.b) * factor);
    return `rgb(${r}, ${g}, ${b})`;
  }
  
  function calculateGrid(width, height) {
    return {
      columns: Math.ceil(width / charWidth),
      rows: Math.ceil(height / charHeight)
    };
  }
  
  function initializeLetters(columns, rows) {
    grid = { columns, rows };
    const totalLetters = columns * rows;
    letters = Array.from({ length: totalLetters }, () => ({
      char: getRandomChar(),
      color: getRandomColor(),
      targetColor: getRandomColor(),
      colorProgress: 1
    }));
    activeLetters.clear();
  }
  
  function resizeCanvas() {
    const parent = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;
    const rect = parent.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    
    const newGrid = calculateGrid(rect.width, rect.height);
    initializeLetters(newGrid.columns, newGrid.rows);
    drawLetters();
  }
  
  function drawLetters() {
    if (letters.length === 0) return;
    const { width, height } = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    ctx.font = `${fontSize}px monospace`;
    ctx.textBaseline = 'top';
    
    letters.forEach((letter, index) => {
      const x = (index % grid.columns) * charWidth;
      const y = Math.floor(index / grid.columns) * charHeight;
      ctx.fillStyle = letter.color;
      ctx.fillText(letter.char, x, y);
    });
  }
  
  function drawLetter(index) {
    const letter = letters[index];
    const x = (index % grid.columns) * charWidth;
    const y = Math.floor(index / grid.columns) * charHeight;
    ctx.clearRect(x, y, charWidth, charHeight);
    ctx.fillStyle = letter.color;
    ctx.fillText(letter.char, x, y);
  }
  
  function updateLetters() {
    if (letters.length === 0) return;
    const updateCount = Math.max(1, Math.floor(letters.length * 0.05));
    for (let i = 0; i < updateCount; i++) {
      const index = Math.floor(Math.random() * letters.length);
      const letter = letters[index];
      if (!letter) continue;
      
      letter.char = getRandomChar();
      letter.targetColor = getRandomColor();
      letter.colorProgress = 0;
      activeLetters.add(index);
    }
  }
  
  function handleSmoothTransitions() {
    for (const index of activeLetters) {
      const letter = letters[index];
      if (letter.colorProgress < 1) {
        letter.colorProgress += 0.05;
        if (letter.colorProgress >= 1) {
          letter.colorProgress = 1;
          activeLetters.delete(index);
        }
        
        const startRgb = hexToRgb(letter.color);
        const endRgb = hexToRgb(letter.targetColor);
        if (startRgb && endRgb) {
          letter.color = interpolateColor(startRgb, endRgb, letter.colorProgress);
          drawLetter(index);
        }
      }
    }
  }
  
  function animate() {
    const now = Date.now();
    if (now - lastGlitchTime >= 50) {
      updateLetters();
      lastGlitchTime = now;
    }
    handleSmoothTransitions();
    animationFrameId = requestAnimationFrame(animate);
  }
  
  resizeCanvas();
  animate();
  
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      cancelAnimationFrame(animationFrameId);
      resizeCanvas();
      animate();
    }, 100);
  });
});
