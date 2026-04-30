document.addEventListener('DOMContentLoaded', () => {
    // ── THREE.JS BACKGROUND ENGINE ────────────────────────────
    const initThree = () => {
        const canvas = document.getElementById('three-canvas');
        if (!canvas) return;
        const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.z = 5;
        const geometry = new THREE.IcosahedronGeometry(1, 0);
        const material = new THREE.MeshPhongMaterial({ color: 0x00ffcc, wireframe: true, transparent: true, opacity: 0.1 });
        const shapes = [];
        for (let i = 0; i < 20; i++) {
            const mesh = new THREE.Mesh(geometry, material);
            mesh.position.set((Math.random() - 0.5) * 20, (Math.random() - 0.5) * 20, (Math.random() - 0.5) * 20);
            scene.add(mesh);
            shapes.push(mesh);
        }
        const animate = () => {
            requestAnimationFrame(animate);
            shapes.forEach(s => { s.rotation.x += 0.001; s.rotation.y += 0.002; });
            renderer.render(scene, camera);
        };
        animate();
    };

    // ── DASHBOARD LOGIC ───────────────────────────────────────
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const syncBtn = document.getElementById('syncBtn');
    const globalMonthInput = document.getElementById('globalMonth');
    const monthLabels = document.querySelectorAll('.active-month-label');
    const summaryContainer = document.getElementById('summary-container');
    const goalsContainer = document.getElementById('goals-container');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');
    
    const incomeVal = document.getElementById('incomeVal');
    const expenseVal = document.getElementById('expenseVal');
    const healthVal = document.getElementById('healthVal');

    const urlParams = new URLSearchParams(window.location.search);
    let currentMonth = urlParams.get('month') || "2025-02";
    const autoSync = urlParams.get('autosync') === 'true';

    // Set initial value
    globalMonthInput.value = currentMonth;

    function updateMonthDisplay() {
        currentMonth = globalMonthInput.value;
        monthLabels.forEach(lbl => lbl.textContent = currentMonth);
        fetchSummary();
        chatHistory = ""; // Reset context for new month
    }

    globalMonthInput.addEventListener('change', updateMonthDisplay);

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`panel-${target}`).classList.add('active');
            if (target === 'summary') fetchSummary();
            if (target === 'goals') fetchGoals();
        });
    });

    function appendMessage(text, type = 'system') {
        const msg = document.createElement('div');
        msg.className = `message ${type}`;
        msg.innerHTML = `<p>${text.replace(/\n/g, '<br>')}</p>`;
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function fetchSummary() {
        summaryContainer.innerHTML = `<div class="loader">Accessing ${currentMonth} Data...</div>`;
        try {
            const response = await fetch(`/api/summary/${currentMonth}`);
            const data = await response.json();
            if (data.length === 0) {
                summaryContainer.innerHTML = '<div class="loader">No datasets found.</div>';
                return;
            }
            let totalIncome = 0, totalExpense = 0, html = '';
            data.forEach(item => {
                const isIncome = item.category.toLowerCase().includes('income');
                if (isIncome) totalIncome += item.actual;
                else totalExpense += item.actual;
                const pct = Math.min((item.actual / item.planned) * 100, 100) || 0;
                html += `<div class="card"><div class="card-header"><div class="card-title">${item.category}</div><div class="main-stat">$${item.actual.toLocaleString()}</div></div><div class="progress-bar-container"><div class="progress-bar-fill" style="width: ${pct}%"></div></div></div>`;
            });
            summaryContainer.innerHTML = html;
            incomeVal.textContent = `$${Math.round(totalIncome).toLocaleString()}`;
            expenseVal.textContent = `$${Math.round(totalExpense).toLocaleString()}`;
            healthVal.textContent = `$${Math.round(totalIncome - totalExpense).toLocaleString()}`;
            healthVal.className = (totalIncome - totalExpense) >= 0 ? 'pos' : 'neg';
        } catch (error) {
            summaryContainer.innerHTML = `<div class="loader">Error loading Summary.</div>`;
        }
    }

    async function fetchGoals() {
        goalsContainer.innerHTML = '<div class="loader">Syncing Targets...</div>';
        try {
            const response = await fetch('/api/goals');
            const data = await response.json();
            let html = '';
            data.forEach(goal => {
                const pct = Math.min((goal.current_amount / goal.target_amount) * 100, 100);
                html += `<div class="card"><div class="card-header"><div class="card-title">${goal.name}</div><div class="main-stat">$${goal.current_amount.toLocaleString()}</div></div><div class="progress-bar-container"><div class="progress-bar-fill" style="width: ${pct}%"></div></div></div>`;
            });
            goalsContainer.innerHTML = html;
        } catch (error) {
            goalsContainer.innerHTML = `<div class="loader">Error loading targets.</div>`;
        }
    }

    let chatHistory = "";
    async function handleChat() {
        const text = userInput.value.trim();
        if (!text) return;
        appendMessage(text, 'user');
        userInput.value = '';
        const core = document.getElementById('ai-core-portal');
        core.style.animation = 'pulseCore 0.5s infinite ease-in-out';
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: text, history: chatHistory, month: currentMonth })
            });
            const data = await response.json();
            if (response.ok) {
                appendMessage(data.response, 'system');
                chatHistory += `User: ${text}\nAI: ${data.response}\n`;
            }
        } catch (error) {
            appendMessage("Neural link interrupted.", "system");
        } finally {
            core.style.animation = 'pulseCore 3s infinite ease-in-out';
        }
    }

    async function handleSync() {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '✨ SYNCING...';
        appendMessage(`Initiating Atomic Sync for ${currentMonth}...`, "system");
        try {
            const bResponse = await fetch('/api/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ month: currentMonth })
            });
            const pResponse = await fetch('/api/sync/profiles', { method: 'POST' });
            if (bResponse.ok && pResponse.ok) {
                appendMessage(`✅ Monthly Sheet "${currentMonth}" updated and verified.`, "system");
                fetchSummary();
            }
        } catch (error) {
            appendMessage("❌ Sync Error: " + error.message, "system");
        } finally {
            syncBtn.disabled = false;
            syncBtn.innerHTML = '✨ TRIGGER ATOMIC SYNC';
        }
    }

    sendBtn.addEventListener('click', handleChat);
    userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleChat(); });
    syncBtn.addEventListener('click', handleSync);
    
    initThree();
    updateMonthDisplay();

    if (autoSync) {
        setTimeout(handleSync, 1000);
    }
});
