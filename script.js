// Produkční aplikace Projekt čtvrtletí pro českou OSM komunitu
document.addEventListener('DOMContentLoaded', function() {
    // Inicializace Socket.io - připojení k backendu
    const socket = io(window.location.origin, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
    });
    
    // Aktualizace data a času v patičce
    function updateDateTime() {
        const now = new Date();
        const dateTimeElement = document.getElementById('currentDateTime');
        const options = { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        dateTimeElement.textContent = now.toLocaleDateString('cs-CZ', options);
    }
    
    updateDateTime();
    setInterval(updateDateTime, 1000);
    
    // Navigace
    const navLinks = document.querySelectorAll('.nav-link');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navMenu = document.querySelector('.nav-menu');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            // Odstranit aktivní třídu ze všech odkazů
            navLinks.forEach(l => l.classList.remove('active'));
            // Přidat aktivní třídu aktuálnímu odkazu
            this.classList.add('active');
            
            // Scrollovat k cílovému elementu
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 100,
                    behavior: 'smooth'
                });
            }
            
            // Skrýt mobilní menu
            if (window.innerWidth <= 768) {
                navMenu.classList.remove('active');
            }
        });
    });
    
    mobileMenuBtn.addEventListener('click', function() {
        navMenu.classList.toggle('active');
    });
    
    // Zavřít menu při kliknutí mimo něj
    document.addEventListener('click', function(e) {
        if (!e.target.closest('nav') && !e.target.closest('.mobile-menu-btn')) {
            navMenu.classList.remove('active');
        }
    });
    
    // Správa hlasování - maximálně 2 hlasy na čtvrtletí
    let userVotes = JSON.parse(localStorage.getItem('osmProjectVotes')) || { 
        ideas: {}, 
        remaining: 2,
        userId: generateUserId(),
        quarter: 'Q1-2026' // Aktuální čtvrtletí
    };
    
    // Pokud je nové čtvrtletí, resetovat hlasy
    const currentQuarter = getCurrentQuarter();
    if (userVotes.quarter !== currentQuarter) {
        userVotes = {
            ideas: {},
            remaining: 2,
            userId: userVotes.userId || generateUserId(),
            quarter: currentQuarter
        };
    }
    
    const remainingVotesElement = document.getElementById('remainingVotes');
    const ideasContainer = document.getElementById('ideasContainer');
    const addIdeaBtn = document.getElementById('addIdeaBtn');
    const ideaTitleInput = document.getElementById('ideaTitle');
    const ideaDescriptionInput = document.getElementById('ideaDescription');
    
    // Generování unikátního ID uživatele
    function generateUserId() {
        return 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
    }
    
    // Získání aktuálního čtvrtletí
    function getCurrentQuarter() {
        const now = new Date();
        const month = now.getMonth() + 1; // 1-12
        const year = now.getFullYear();
        
        if (month >= 1 && month <= 3) return `Q1-${year}`;
        if (month >= 4 && month <= 6) return `Q2-${year}`;
        if (month >= 7 && month <= 9) return `Q3-${year}`;
        return `Q4-${year}`;
    }
    
    // Aktualizace zbývajících hlasů
    function updateRemainingVotes() {
        remainingVotesElement.textContent = userVotes.remaining;
        localStorage.setItem('osmProjectVotes', JSON.stringify(userVotes));
    }
    
    // Načtení nápadů z backendu
    let ideas = [];
    
    function loadIdeas() {
        ideasContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Načítám nápady...</div>';
        
        fetch('/api/ideas')
            .then(response => response.json())
            .then(data => {
                ideas = data;
                renderIdeas();
            })
            .catch(error => {
                console.error('Chyba při načítání nápadů:', error);
                ideasContainer.innerHTML = '<div class="state-empty"><i class="fas fa-exclamation-circle"></i><p>Nepodařilo se načíst nápady</p></div>';
            });
    }
    
    // Aktualizace uživatelských hlasů v nápadcích
    function updateUserVotesInIdeas() {
        ideas.forEach(idea => {
            idea.userVoted = userVotes.ideas[idea.id] || false;
        });
    }
    
    // Vyrenderování nápadů
    function renderIdeas() {
        updateUserVotesInIdeas();
        
        if (ideas.length === 0) {
            ideasContainer.innerHTML = '<div class="state-empty"><i class="fas fa-lightbulb"></i><p>Zatím nejsou žádné nápady. Buďte první!</p></div>';
            return;
        }
        
        ideasContainer.innerHTML = '';
        
        // Seřadit nápady podle počtu hlasů (sestupně)
        const sortedIdeas = [...ideas].sort((a, b) => b.votes - a.votes);
        
        sortedIdeas.forEach(idea => {
            const ideaElement = document.createElement('div');
            ideaElement.className = `idea-item fade-in ${idea.winning ? 'winning' : ''}`;
            ideaElement.innerHTML = `
                <div class="idea-header">
                    <div class="idea-title">${escapeHtml(idea.title)}</div>
                    <div class="idea-votes">${idea.votes} hlasů</div>
                </div>
                <div class="idea-description">${escapeHtml(idea.description)}</div>
                <div class="idea-footer">
                    <div class="idea-author">
                        <i class="fas fa-user"></i>
                        ${escapeHtml(idea.author || 'Anonymní')} | 
                        <i class="fas fa-clock"></i> ${formatDate(idea.created_at)}
                    </div>
                    <button class="btn btn-small vote-btn ${idea.userVoted ? 'voted' : ''} ${userVotes.remaining === 0 && !idea.userVoted ? 'disabled' : ''}" 
                            data-id="${idea.id}" ${idea.userVoted || userVotes.remaining === 0 ? 'disabled' : ''}>
                        <i class="fas fa-thumbs-up"></i>
                        ${idea.userVoted ? 'Hlasováno' : 'Hlasovat'}
                    </button>
                </div>
            `;
            ideasContainer.appendChild(ideaElement);
        });
        
        // Přidání event listenerů na tlačítka hlasování
        document.querySelectorAll('.vote-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const ideaId = this.getAttribute('data-id');
                voteForIdea(ideaId);
            });
        });
    }
    
    // Pomocná funkce pro escapování HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Formátování data
    function formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString('cs-CZ', { 
            day: '2-digit', 
            month: '2-digit', 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    // Hlasování pro nápad
    function voteForIdea(ideaId) {
        if (userVotes.remaining <= 0) return;
        
        const idea = ideas.find(i => i.id == ideaId);
        if (!idea || idea.userVoted) return;
        
        fetch('/api/vote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                idea_id: ideaId,
                user_id: userVotes.userId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Aktualizovat lokální data
                idea.votes = data.votes;
                idea.userVoted = true;
                
                // Aktualizovat uživatelské hlasy
                userVotes.ideas[ideaId] = true;
                userVotes.remaining--;
                
                // Uložit a znovu vykreslit
                updateRemainingVotes();
                renderIdeas();
                
                // Oznámit přes socket
                socket.emit('vote_update', { ideaId, votes: data.votes });
            } else {
                alert('Chyba při hlasování: ' + (data.error || 'Neznámá chyba'));
            }
        })
        .catch(error => {
            console.error('Chyba při hlasování:', error);
            alert('Nepodařilo se odeslat hlas. Zkontrolujte připojení.');
        });
    }
    
    // Přidání nového nápadu
    addIdeaBtn.addEventListener('click', function() {
        const title = ideaTitleInput.value.trim();
        const description = ideaDescriptionInput.value.trim();
        
        if (!title || !description) {
            alert('Prosím vyplňte název i popis nápadu.');
            return;
        }
        
        if (title.length < 5) {
            alert('Název projektu musí mít alespoň 5 znaků.');
            return;
        }
        
        if (description.length < 10) {
            alert('Popis projektu musí mít alespoň 10 znaků.');
            return;
        }
        
        const username = document.getElementById('usernameInput').value.trim() || 'Anonymní';
        
        fetch('/api/idea', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                description: description,
                author: username
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Přidat nápad do seznamu
                ideas.push(data.idea);
                
                // Automaticky hlasovat pro vlastní nápad (pokud máme hlasy)
                if (userVotes.remaining > 0) {
                    voteForIdea(data.idea.id);
                }
                
                // Vyčistit formulář
                ideaTitleInput.value = '';
                ideaDescriptionInput.value = '';
                
                // Zobrazit potvrzení
                showNotification('Nápad byl úspěšně přidán!', 'success');
            } else {
                alert('Chyba při přidávání nápadu: ' + (data.error || 'Neznámá chyba'));
            }
        })
        .catch(error => {
            console.error('Chyba při přidávání nápadu:', error);
            alert('Nepodařilo se přidat nápad. Zkontrolujte připojení.');
        });
    });
    
    // Statistiky - inicializace grafu
    let changesetsChart = null;
    
    function initChart(statsData) {
        const ctx = document.getElementById('changesetsChart').getContext('2d');
        
        if (changesetsChart) {
            changesetsChart.destroy();
        }
        
        // Data pro graf (posledních 30 dní)
        const labels = [];
        const data = [];
        
        const today = new Date();
        for (let i = 29; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('cs-CZ', { day: '2-digit', month: '2-digit' }));
            data.push(statsData.daily_stats && statsData.daily_stats[i] ? statsData.daily_stats[i] : 0);
        }
        
        const chartData = {
            labels: labels,
            datasets: [{
                label: 'Changesety s #projektctvrtleti',
                data: data,
                backgroundColor: 'rgba(44, 120, 115, 0.2)',
                borderColor: 'rgba(44, 120, 115, 1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        };
        
        changesetsChart = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            display: true
                        },
                        ticks: {
                            stepSize: 5
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Changesety: ${context.parsed.y}`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Leaderboard
    const leaderboardContainer = document.getElementById('leaderboardContainer');
    
    function renderLeaderboard(leaderboardData) {
        if (!leaderboardData || leaderboardData.length === 0) {
            leaderboardContainer.innerHTML = '<div class="state-empty"><i class="fas fa-user-friends"></i><p>Zatím žádná data</p></div>';
            return;
        }
        
        leaderboardContainer.innerHTML = '';
        
        leaderboardData.forEach((item, index) => {
            const leaderboardItem = document.createElement('div');
            leaderboardItem.className = 'leaderboard-item fade-in';
            leaderboardItem.innerHTML = `
                <div class="leaderboard-rank">${index + 1}</div>
                <div class="leaderboard-user">
                    <i class="fas fa-user"></i>
                    ${escapeHtml(item.user)}
                </div>
                <div class="leaderboard-score">${item.changesets} changesetů</div>
            `;
            leaderboardContainer.appendChild(leaderboardItem);
        });
    }
    
    // Načtení statistik z backendu
    function loadStats() {
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                updateStatsDisplay(data);
                initChart(data);
                renderLeaderboard(data.leaderboard);
            })
            .catch(error => {
                console.error('Chyba při načítání statistik:', error);
            });
    }
    
    // Aktualizace zobrazení statistik
    function updateStatsDisplay(stats) {
        document.getElementById('totalChangesets').textContent = stats.total_changesets || 0;
        document.getElementById('totalContributors').textContent = stats.total_contributors || 0;
        document.getElementById('changesetsToday').textContent = stats.changesets_today || 0;
        document.getElementById('changesetsWeek').textContent = stats.changesets_week || 0;
        
        const lastUpdate = stats.last_updated ? new Date(stats.last_updated) : new Date();
        document.getElementById('lastUpdate').textContent = lastUpdate.toLocaleTimeString('cs-CZ', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    // Chat - správa zpráv
    const messagesContainer = document.getElementById('messagesContainer');
    const messageInput = document.getElementById('messageInput');
    const sendMessageBtn = document.getElementById('sendMessageBtn');
    const usernameInput = document.getElementById('usernameInput');
    const onlineCountElement = document.getElementById('onlineCount');
    
    // Nastavení uživatelského jména z localStorage
    const savedUsername = localStorage.getItem('osmChatUsername');
    if (savedUsername) {
        usernameInput.value = savedUsername;
    } else {
        // Generovat náhodné uživatelské jméno
        const adjectives = ['Veselý', 'Rychlý', 'Moudrý', 'Šikovný', 'Pilný', 'Zkušený', 'Nadšený', 'Přesný'];
        const nouns = ['Mapper', 'Kartograf', 'Surveyor', 'Editátor', 'Dobrovolník', 'Přispěvatel', 'Nadšenec', 'Objevitel'];
        const randomAdj = adjectives[Math.floor(Math.random() * adjectives.length)];
        const randomNoun = nouns[Math.floor(Math.random() * nouns.length)];
        const randomNumber = Math.floor(Math.random() * 100);
        usernameInput.value = `${randomAdj}${randomNoun}${randomNumber}`;
    }
    
    // Uložení uživatelského jména při změně
    usernameInput.addEventListener('change', function() {
        localStorage.setItem('osmChatUsername', this.value.trim());
    });
    
    // Přidání zprávy do chatu
    function addMessage(message, isOwn = false, isSystem = false) {
        const messageElement = document.createElement('div');
        const messageClass = isSystem ? 'system' : (isOwn ? 'own' : 'other');
        
        const time = message.timestamp ? 
            new Date(message.timestamp).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' }) : 
            new Date().toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' });
        
        messageElement.className = `message ${messageClass} fade-in`;
        messageElement.innerHTML = `
            ${!isSystem ? `<div class="message-header">
                <div class="message-user">
                    <i class="fas fa-user"></i>
                    ${escapeHtml(message.user)}
                </div>
                <div class="message-time">${time}</div>
            </div>` : ''}
            <div class="message-content">${escapeHtml(message.text)}</div>
            ${isSystem ? `<div class="message-time">${time}</div>` : ''}
        `;
        
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Odeslání zprávy
    function sendMessage() {
        const text = messageInput.value.trim();
        const username = usernameInput.value.trim();
        
        if (!text) return;
        
        if (!username) {
            alert('Prosím zadejte přezdívku pro chat.');
            usernameInput.focus();
            return;
        }
        
        // Uložit uživatelské jméno
        localStorage.setItem('osmChatUsername', username);
        
        const message = {
            user: username,
            text: text,
            timestamp: new Date().toISOString()
        };
        
        // Přidat zprávu lokálně
        addMessage(message, true);
        
        // Odeslat přes socket.io
        socket.emit('chat_message', message);
        
        // Vyčistit vstup
        messageInput.value = '';
        messageInput.focus();
    }
    
    sendMessageBtn.addEventListener('click', sendMessage);
    
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Socket.io eventy
    socket.on('connect', function() {
        console.log('Připojeno k serveru');
        addMessage({
            user: 'Systém',
            text: 'Vítejte v komunitním chatu Projekt čtvrtletí! Diskutujte o mapování, ptejte se na radu nebo sdílejte své úspěchy.'
        }, false, true);
    });
    
    socket.on('connect_error', function(error) {
        console.error('Chyba připojení:', error);
        addMessage({
            user: 'Systém',
            text: 'Chyba připojení k serveru. Zkuste obnovit stránku.'
        }, false, true);
    });
    
    socket.on('user_count', function(count) {
        onlineCountElement.textContent = count;
    });
    
    socket.on('chat_message', function(message) {
        const currentUser = usernameInput.value.trim();
        const isOwn = message.user === currentUser;
        addMessage(message, isOwn, false);
    });
    
    socket.on('new_idea', function(idea) {
        // Přidat nápad do seznamu (jen pokud tam ještě není)
        const existingIdea = ideas.find(i => i.id === idea.id);
        if (!existingIdea) {
            ideas.push(idea);
            renderIdeas();
            
            // Zobrazit upozornění v chatu
            addMessage({
                user: 'Systém',
                text: `Byl přidán nový nápad: "${idea.title}"`
            }, false, true);
        }
    });
    
    socket.on('vote_update', function(data) {
        // Aktualizovat počet hlasů u nápadu
        const idea = ideas.find(i => i.id == data.ideaId);
        if (idea) {
            idea.votes = data.votes;
            renderIdeas();
        }
    });
    
    socket.on('stats_update', function(stats) {
        // Aktualizovat statistiky
        updateStatsDisplay(stats);
        initChart(stats);
        renderLeaderboard(stats.leaderboard);
    });
    
    // Zobrazení notifikace
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} fade-in`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
    
    // Přidání stylů pro notifikace
    const style = document.createElement('style');
    style.textContent = `
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 9999;
            max-width: 400px;
            border-left: 4px solid var(--primary-color);
        }
        .notification-success {
            border-left-color: var(--success-color);
        }
        .notification i {
            font-size: 1.2rem;
        }
        .notification-success i {
            color: var(--success-color);
        }
        .fade-out {
            opacity: 0;
            transform: translateY(-10px);
            transition: opacity 0.3s, transform 0.3s;
        }
    `;
    document.head.appendChild(style);
    
    // Periodická aktualizace statistik
    setInterval(loadStats, 60000); // každou minutu
    
    // Načtení inicializačních dat
    loadIdeas();
    loadStats();
    updateRemainingVotes();
});