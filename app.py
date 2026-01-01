#!/usr/bin/env python3
"""
Produkční backend aplikace Projekt měsíce pro českou OSM komunitu
S reálným propojením na OSM API pro sledování changesetů s tagem #projektmesice
"""

import os
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Konfigurace loggingu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Konfigurace aplikace
app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'produkce-osm-projekt-mesice-2026-tajny-klic')
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Konfigurace session pro requests
session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Globální proměnné pro správu dat
connected_users = 0
chat_messages = []
project_ideas = []
user_votes = {}
osm_stats_cache = {
    'data': None,
    'last_updated': None,
    'expires_at': None
}
current_project = None

# Cesta k souboru s daty
DATA_FILE = 'osm_project_data.json'
CONFIG_FILE = 'osm_project_config.json'

# Načtení dat ze souboru
def load_data():
    global chat_messages, project_ideas, user_votes, current_project
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chat_messages = data.get('chat_messages', [])
            project_ideas = data.get('project_ideas', [])
            user_votes = data.get('user_votes', {})
            logger.info(f"Data načtena: {len(chat_messages)} zpráv, {len(project_ideas)} nápadů")
    except FileNotFoundError:
        logger.info("Soubor s daty neexistuje, vytvářím nový...")
        save_data()
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            current_project = config.get('current_project')
    except FileNotFoundError:
        logger.info("Konfigurační soubor neexistuje, vytvářím nový...")
        save_config()

# Uložení dat do souboru
def save_data():
    data = {
        'chat_messages': chat_messages[-200:],  # Ukládáme pouze posledních 200 zpráv
        'project_ideas': project_ideas,
        'user_votes': user_votes,
        'last_updated': datetime.now().isoformat()
    }
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Data uložena")
    except Exception as e:
        logger.error(f"Chyba při ukládání dat: {e}")

def save_config():
    config = {
        'current_project': current_project,
        'last_updated': datetime.now().isoformat()
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info("Konfigurace uložena")
    except Exception as e:
        logger.error(f"Chyba při ukládání konfigurace: {e}")

# OSM API funkce pro získání changesetů s tagem #projektmesice
def fetch_changesets_from_osm():
    """Získává changesety s tagem #projektmesice z OSM API - SPRÁVNÁ VERZE"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"OSM API dotaz: od {start_date.date()} do {end_date.date()}")
        
        url = "https://api.openstreetmap.org/api/0.6/changesets"
        
        # Použijeme bbox pro ČR
        params = {
            'bbox': '12.09,48.55,18.87,51.06',
            'time': f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}",
        }
        
        headers = {
            'User-Agent': 'OSM-Projekt-Mesice/1.0 (Czech OSM Community; https://openstreetmap.cz)'
        }
        
        response = session.get(url, params=params, headers=headers, timeout=60)
        
        if response.status_code != 200:
            logger.error(f"Chyba OSM API: {response.status_code}")
            return []
        
        # Parse XML response
        import xml.etree.ElementTree as ET
        changesets = []
        
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            logger.error(f"Chyba parsování XML: {e}")
            return []
        
        for changeset in root.findall('changeset'):
            try:
                # Získat všechny tagy
                tags = {}
                for tag in changeset.findall('tag'):
                    k = tag.get('k', '')
                    v = tag.get('v', '')
                    if k and v:
                        tags[k] = v
                
                # HLAVNÍ ZMĚNA: Hledáme #projektmesice v tagu 'hashtags', ne 'comment'!
                hashtags = tags.get('hashtags', '')
                comment = tags.get('comment', '')
                
                # Hledáme v hashtags i comment (pro jistotu)
                search_text = f"{hashtags} {comment}".lower()
                
                if '#projektmesice' in search_text:
                    changeset_data = {
                        'id': changeset.get('id'),
                        'user': changeset.get('user'),
                        'uid': changeset.get('uid'),
                        'created_at': changeset.get('created_at'),
                        'closed_at': changeset.get('closed_at'),
                        'tags': tags,
                        'hashtags': hashtags,
                        'comment': comment
                    }
                    changesets.append(changeset_data)
                    
            except Exception as e:
                logger.warning(f"Chyba při parsování changesetu: {e}")
                continue
        
        logger.info(f"Načteno {len(changesets)} changesetů s #projektmesice")
        
        # Debug výpis
        for cs in changesets[:5]:
            logger.info(f"  - ID {cs['id']}: {cs.get('user', 'Unknown')} - Hashtags: {cs.get('hashtags', 'None')}")
        
        return changesets
        
    except Exception as e:
        logger.error(f"Chyba při získávání changesetů z OSM: {e}", exc_info=True)
        return []

def fetch_from_overpass_api(start_date, end_date):
    """Fallback metoda pomocí Overpass API - opravená pro hashtags"""
    try:
        # Formát data pro Overpass
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Overpass API query - hledáme změny s hashtags obsahující #projektmesice
        query = f"""
        [out:json][timeout:90];
        (
          node["hashtags"~"#projektmesice"](changed:"{start_str}","{end_str}");
          way["hashtags"~"#projektmesice"](changed:"{start_str}","{end_str}");
          relation["hashtags"~"#projektmesice"](changed:"{start_str}","{end_str}");
        );
        out meta;
        >;
        out skel qt;
        """
        
        url = "https://overpass-api.de/api/interpreter"
        headers = {
            'User-Agent': 'OSM-Projekt-Mesice/1.0 (Czech OSM Community)'
        }
        
        response = session.post(url, data={'data': query}, headers=headers, timeout=120)
        
        if response.status_code != 200:
            logger.error(f"Overpass API chyba: {response.status_code}")
            return []
        
        data = response.json()
        changesets_dict = {}
        
        for element in data.get('elements', []):
            changeset_id = element.get('changeset')
            if changeset_id:
                if changeset_id not in changesets_dict:
                    changesets_dict[changeset_id] = {
                        'id': changeset_id,
                        'user': element.get('user'),
                        'uid': element.get('uid'),
                        'created_at': element.get('timestamp') + 'Z' if element.get('timestamp') else None,
                        'tags': element.get('tags', {})
                    }
        
        changesets = list(changesets_dict.values())
        logger.info(f"Overpass API našel {len(changesets)} changesetů")
        return changesets
        
    except Exception as e:
        logger.error(f"Chyba Overpass API: {e}")
        return []

def parse_changesets_old_method(xml_text):
    """Starší metoda parsování jako fallback"""
    changesets = []
    lines = xml_text.split('\n')
    current_changeset = None
    in_changeset = False
    
    for line in lines:
        line = line.strip()
        if '<changeset' in line:
            # Extract attributes
            import re
            attrs = re.findall(r'(\w+)="([^"]*)"', line)
            current_changeset = dict(attrs)
            current_changeset['tags'] = {}
            in_changeset = True
        elif '<tag' in line and in_changeset:
            attrs = re.findall(r'(\w+)="([^"]*)"', line)
            if attrs and len(attrs) >= 2:
                current_changeset['tags'][attrs[0][1]] = attrs[1][1]
        elif '</changeset>' in line and in_changeset:
            if current_changeset:
                # Check if comment contains #projektmesice (case insensitive)
                comment = current_changeset.get('tags', {}).get('comment', '')
                comment = comment + current_changeset.get('tags', {}).get('Comment', '')
                if '#projektmesice' in comment.lower():
                    changesets.append(current_changeset)
            current_changeset = None
            in_changeset = False
    
    return changesets

def calculate_statistics(changesets):
    """Vypočítá statistiky ze changesetů"""
    if not changesets:
        return {
            'total_changesets': 0,
            'total_contributors': 0,
            'changesets_today': 0,
            'changesets_week': 0,
            'leaderboard': [],
            'daily_stats': [0] * 30,
            'last_updated': datetime.now().isoformat()
        }
    
    # Unikátní uživatelé
    users = set()
    for c in changesets:
        user = c.get('user')
        if user:
            users.add(user)
    
    # Changesety dnes a tento týden
    today = datetime.now().date()
    week_ago = datetime.now() - timedelta(days=7)
    
    changesets_today = 0
    changesets_week = 0
    user_counts = {}
    daily_counts = {}
    
    for changeset in changesets:
        user = changeset.get('user')
        if user:
            user_counts[user] = user_counts.get(user, 0) + 1
        
        # Parse created_at - robustněji
        created_at = changeset.get('created_at')
        if created_at:
            try:
                # OSM API vrací UTC čas, např.: 2026-01-01T10:30:00Z
                # Odstranit 'Z' a převést na datetime
                if created_at.endswith('Z'):
                    created_at = created_at[:-1] + '+00:00'
                
                created_dt = datetime.fromisoformat(created_at)
                created_date = created_dt.date()
                
                # Today (s ohledem na timezone)
                if created_date == today:
                    changesets_today += 1
                
                # This week
                if created_dt >= week_ago:
                    changesets_week += 1
                
                # Daily stats za posledních 30 dní
                days_ago = (datetime.now().date() - created_date).days
                if 0 <= days_ago < 30:
                    daily_counts[days_ago] = daily_counts.get(days_ago, 0) + 1
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Chyba parsování data {created_at}: {e}")
                continue
    
    # Create leaderboard
    leaderboard = [{'user': user, 'changesets': count} 
                   for user, count in sorted(user_counts.items(), 
                                           key=lambda x: x[1], 
                                           reverse=True)[:10]]
    
    # Create daily stats for last 30 days
    daily_stats = []
    for i in range(29, -1, -1):
        daily_stats.append(daily_counts.get(i, 0))
    
    logger.info(f"Statistiky: {len(changesets)} changesetů, {len(users)} uživatelů, dnes: {changesets_today}")
    
    return {
        'total_changesets': len(changesets),
        'total_contributors': len(users),
        'changesets_today': changesets_today,
        'changesets_week': changesets_week,
        'leaderboard': leaderboard,
        'daily_stats': daily_stats,
        'last_updated': datetime.now().isoformat()
    }

def update_osm_stats():
    """Aktualizace statistik z OSM API"""
    try:
        changesets = fetch_changesets_from_osm()
        stats = calculate_statistics(changesets)
        
        osm_stats_cache['data'] = stats
        osm_stats_cache['last_updated'] = datetime.now()
        osm_stats_cache['expires_at'] = datetime.now() + timedelta(minutes=5)
        
        logger.info(f"Statistiky aktualizovány: {stats['total_changesets']} changesetů, {stats['total_contributors']} uživatelů")
        
        # Broadcast update via WebSocket
        socketio.emit('stats_update', stats)
        
        return stats
    except Exception as e:
        logger.error(f"Chyba při aktualizaci statistik: {e}")
        return None

# Periodické úlohy
def periodic_tasks():
    """Spouští periodické úlohy v pozadí"""
    while True:
        try:
            # Aktualizace statistik každých 5 minut
            update_osm_stats()
            
            # Ukládání dat každých 30 sekund
            save_data()
            
            # Kontrola konce hlasování a vyhlášení vítěze
            check_voting_period()
            
        except Exception as e:
            logger.error(f"Chyba v periodických úlohách: {e}")
        
        time.sleep(30)  # Spát 30 sekund

def check_voting_period():
    """Kontrola, zda nekončí hlasování nebo projekt"""
    global current_project
    
    now = datetime.now()
    
    # Pokud je 6.1.2026 00:00, vyhlásit vítěze
    if now >= datetime(2026, 1, 6, 0, 0, 0) and current_project is None:
        # Najít vítězný nápad
        if project_ideas:
            winning_idea = max(project_ideas, key=lambda x: x.get('votes', 0))
            current_project = {
                'id': winning_idea['id'],
                'title': winning_idea['title'],
                'description': winning_idea['description'],
                'start_date': '2026-01-06',
                'end_date': '2026-02-06'
            }
            save_config()
            
            # Oznámit v chatu
            system_message = {
                'user': 'Systém',
                'text': f'🎉 Vyhlášen vítězný projekt: "{winning_idea["title"]}"! Začínáme mapovat od dneška do 6.2.2026.',
                'timestamp': now.isoformat()
            }
            chat_messages.append(system_message)
            socketio.emit('chat_message', system_message)
            logger.info(f"Vyhlášen vítězný projekt: {winning_idea['title']}")

# Flask routes
@app.route('/')
def index():
    """Hlavní stránka aplikace"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Soubory statického obsahu"""
    return send_from_directory('.', path)

@app.route('/api/stats')
def get_stats():
    """API endpoint pro získání statistik"""
    # Zkontrolovat cache
    if (osm_stats_cache['data'] and osm_stats_cache['expires_at'] and 
        datetime.now() < osm_stats_cache['expires_at']):
        return jsonify(osm_stats_cache['data'])
    
    # Jinak aktualizovat
    stats = update_osm_stats()
    if stats:
        return jsonify(stats)
    else:
        return jsonify(calculate_statistics([]))

@app.route('/api/ideas')
def get_ideas():
    """API endpoint pro získání nápadů"""
    return jsonify(project_ideas)

@app.route('/api/vote', methods=['POST'])
def vote_for_idea():
    """API endpoint pro hlasování pro nápad"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Žádná data'}), 400
        
        idea_id = data.get('idea_id')
        user_id = data.get('user_id')
        
        if not idea_id or not user_id:
            return jsonify({'error': 'Chybějící idea_id nebo user_id'}), 400
        
        # Najít nápad
        idea = None
        for i in project_ideas:
            if str(i.get('id')) == str(idea_id):
                idea = i
                break
        
        if not idea:
            return jsonify({'error': 'Nápad nebyl nalezen'}), 404
        
        # Kontrola, zda uživatel již hlasoval pro tento nápad
        if user_id in user_votes and idea_id in user_votes[user_id]:
            return jsonify({'error': 'Už jste hlasovali pro tento nápad'}), 400
        
        # Kontrola počtu hlasů (max 2 na období)
        user_vote_count = len(user_votes.get(user_id, []))
        if user_vote_count >= 2:
            return jsonify({'error': 'Již jste použili všechny hlasy pro toto období'}), 400
        
        # Přidat hlas
        idea['votes'] = idea.get('votes', 0) + 1
        
        # Uložit hlas uživatele
        if user_id not in user_votes:
            user_votes[user_id] = []
        user_votes[user_id].append(idea_id)
        
        # Broadcast update
        socketio.emit('vote_update', {'ideaId': idea_id, 'votes': idea['votes']})
        
        return jsonify({'success': True, 'votes': idea['votes']})
        
    except Exception as e:
        logger.error(f"Chyba při hlasování: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/idea', methods=['POST'])
def add_idea():
    """API endpoint pro přidání nového nápadu"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Žádná data'}), 400
        
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        author = data.get('author', 'Anonymní').strip()
        
        if not title or not description:
            return jsonify({'error': 'Chybějící název nebo popis'}), 400
        
        if len(title) < 5:
            return jsonify({'error': 'Název musí mít alespoň 5 znaků'}), 400
        
        if len(description) < 10:
            return jsonify({'error': 'Popis musí mít alespoň 10 znaků'}), 400
        
        # Vytvořit nový nápad
        new_idea = {
            'id': int(time.time() * 1000),
            'title': title,
            'description': description,
            'author': author or 'Anonymní',
            'votes': 0,
            'created_at': datetime.now().isoformat(),
            'winning': False
        }
        
        project_ideas.append(new_idea)
        
        # Broadcast via WebSocket
        socketio.emit('new_idea', new_idea)
        
        return jsonify({'success': True, 'idea': new_idea})
        
    except Exception as e:
        logger.error(f"Chyba při přidávání nápadu: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/current-project')
def get_current_project():
    """API endpoint pro získání aktuálního projektu"""
    return jsonify(current_project or {})

@app.route('/api/debug/osm-test')
def debug_osm_test():
    """Debug endpoint pro testování OSM API s hashtags"""
    import requests
    
    # Testovací dotaz - stejný jako v aplikaci
    test_url = "https://api.openstreetmap.org/api/0.6/changesets"
    params = {
        'bbox': '12.09,48.55,18.87,51.06',
        'time': '2025-12-01,2026-01-01',
    }
    
    response = requests.get(test_url, params=params, timeout=30, 
                           headers={'User-Agent': 'OSM-Projekt-Mesice-Debug'})
    
    # Analyzujeme response
    import xml.etree.ElementTree as ET
    changesets_with_hashtags = []
    
    if response.status_code == 200:
        try:
            root = ET.fromstring(response.text)
            for changeset in root.findall('changeset'):
                tags = {}
                for tag in changeset.findall('tag'):
                    k = tag.get('k')
                    v = tag.get('v')
                    if k and v:
                        tags[k] = v
                
                if 'hashtags' in tags:
                    changesets_with_hashtags.append({
                        'id': changeset.get('id'),
                        'user': changeset.get('user'),
                        'hashtags': tags['hashtags'],
                        'created_at': changeset.get('created_at')
                    })
        except Exception as e:
            error = str(e)
    else:
        error = f"Status: {response.status_code}"
    
    return jsonify({
        'url': response.url,
        'status': response.status_code,
        'size': len(response.text),
        'changesets_with_hashtags': changesets_with_hashtags,
        'preview': response.text[:500] if response.status_code == 200 else response.text
    })
    
# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Zpracování připojení nového klienta"""
    global connected_users
    connected_users += 1
    
    # Odeslat aktuální počet připojených uživatelů
    emit('user_count', connected_users, broadcast=True)
    
    # Odeslat posledních 50 zpráv z chatu
    for message in chat_messages[-50:]:
        emit('chat_message', message)
    
    logger.info(f"Uživatel připojen. Celkem uživatelů: {connected_users}")

@socketio.on('disconnect')
def handle_disconnect():
    """Zpracování odpojení klienta"""
    global connected_users
    connected_users -= 1
    
    # Odeslat aktualizovaný počet připojených uživatelů
    emit('user_count', connected_users, broadcast=True)
    
    logger.info(f"Uživatel odpojen. Celkem uživatelů: {connected_users}")

@socketio.on('chat_message')
def handle_chat_message(data):
    """Zpracování zprávy v chatu"""
    try:
        if not isinstance(data, dict):
            return
        
        user = str(data.get('user', '')).strip()[:50]
        text = str(data.get('text', '')).strip()[:500]
        
        if not user or not text:
            return
        
        # Přidat časovou značku
        message = {
            'user': user,
            'text': text,
            'timestamp': datetime.now().isoformat()
        }
        
        # Uložit zprávu (maximálně 200)
        chat_messages.append(message)
        if len(chat_messages) > 200:
            chat_messages.pop(0)
        
        # Odeslat všem připojeným klientům
        emit('chat_message', message, broadcast=True, include_self=False)
        
    except Exception as e:
        logger.error(f"Chyba při zpracování zprávy: {e}")

@socketio.on('vote_update')
def handle_vote_update(data):
    """Broadcast aktualizace hlasů"""
    emit('vote_update', data, broadcast=True, include_self=False)

# Hlavní funkce
if __name__ == '__main__':
    # Načtení existujících dat
    load_data()
    
    # Spuštění vlákna pro periodické úlohy
    tasks_thread = threading.Thread(target=periodic_tasks, daemon=True)
    tasks_thread.start()
    
    # První aktualizace statistik
    update_osm_stats()
    
    print("=" * 70)
    print("PRODUKČNÍ APLIKACE - Projekt měsíce pro českou OSM komunitu")
    print(f"Čas spuštění: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"Načteno: {len(chat_messages)} zpráv v chatu, {len(project_ideas)} nápadů")
    print(f"Aktuální projekt: {current_project['title'] if current_project else 'Žádný (probíhá hlasování)'}")
    print("=" * 70)
    print("Aplikace běží na http://0.0.0.0:4040")
    print("Pro produkci použijte gunicorn nebo uWSGI")
    print("Ukončete stiskem Ctrl+C")
    print("=" * 70)
    
    # Spuštění aplikace
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=4040, 
        debug=False, 
        allow_unsafe_werkzeug=True,
        log_output=True
    )