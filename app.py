#!/usr/bin/env python3
"""
Produkční backend aplikace Projekt čtvrtletí pro českou OSM komunitu
S reálným propojením na OSM API pro sledování changesetů s tagem #projektctvrtleti
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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'produkce-osm-projekt-ctvrtleti-2026-tajny-klic')
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

# Načtení výchozích dat (už jsme dostali od uživatele)
provided_data = {
    "chat_messages": [
        {
            "user": "turistka123",
            "text": "Dokončila jsem mapování turistických rozcestníků v Krkonoších.",
            "timestamp": "2025-12-31T22:08:59.008730"
        },
        {
            "user": "turistka123",
            "text": "Dokončila jsem mapování turistických rozcestníků v Krkonoších.",
            "timestamp": "2025-12-31T22:11:12.000605"
        },
        {
            "user": "mapomat",
            "text": "Právě jsem zmapoval 5 nových cyklostezek v Praze!",
            "timestamp": "2025-12-31T22:16:41.985738"
        },
        {
            "user": "Thisík",
            "text": "Testovací zpráva",
            "timestamp": "2025-12-31T22:20:08.569725"
        },
        {
            "user": "MoudrýEditátor36",
            "text": "Funguje?",
            "timestamp": "2025-12-31T22:20:24.803822"
        },
        {
            "user": "Thisík",
            "text": "JJ",
            "timestamp": "2025-12-31T22:20:32.631943"
        },
        {
            "user": "Thisík",
            "text": ":)",
            "timestamp": "2025-12-31T22:24:30.429998"
        },
        {
            "user": "RychlýEditátor11",
            "text": "😉",
            "timestamp": "2025-12-31T22:24:48.405515"
        },
        {
            "user": "Ondřej Lopatka",
            "text": "Zaprvé, tohle by se dalo napojit na náš OSM chat? Ale jestli to chcete nechat pro projekt měsíce tak asi jo.",
            "timestamp": "2026-01-01T08:31:48.305618"
        },
        {
            "user": "Ondřej Lopatka",
            "text": "Zadruhé, ta village_green by podle mě šla docela dobře přemapovat pomocí nějakého hromadného editu z overpass hledání",
            "timestamp": "2026-01-01T08:33:14.149370"
        },
        {
            "user": "Ondřej Lopatka",
            "text": "Ale určitě by to bylo vhodné, protože já jsem mapoval okolní zeleň právě jako village green, protože jsem tagy opisoval, místo abych četl wiki",
            "timestamp": "2026-01-01T08:34:12.362743"
        },
        {
            "user": "Thisík",
            "text": "Přesně, ta village_green by šla krásně přes overpass a JOSM",
            "timestamp": "2026-01-01T10:13:46.617609"
        },
        {
            "user": "Thisík",
            "text": "Napojit na OSM chat by to možná šlo, ale zatím bych to asi nechal takto, jestli souhlasíte.",
            "timestamp": "2026-01-01T10:14:08.492441"
        },
        {
            "user": "Ondřej Lopatka",
            "text": "Udělal bych to tak, aby se mapovalo klidně od 1. každého měsíce až do posledního dne a aby se mezitím klidně celý měsíc hlasovalo o tématu na další měsíc, co myslíš?",
            "timestamp": "2026-01-01T15:37:15.624698"
        },
        {
            "user": "Thisík",
            "text": "Ano, to je jasné, ale teď, jak jsem to vytvářel až v noci 31.12, tak jsem to udělal takto. Postupně samozřejmě najedeme na ten systém, jak říkáš Ty.",
            "timestamp": "2026-01-01T19:31:24.419996"
        },
        {
            "user": "Amunak",
            "text": "Budu rád když se projdou staré poznámky, ale pozor na to, že fakt že je poznámka stará, ještě neznamená že je neaktuální. Nedávno mi takhle mermomocí zavíral \"starou\" poznámku jeden němec, ale poznámka byla o tom že se na to místo má jít někdo podívat a zkontrolovat to, ne zavírat to od počítače. Takže bych v první fázi prošel fakt jen to co se jednoznačně může vyhodit, nebo zapracovat poznámky o úpravách pokud to půjde, ale jinak je to o tom taky vyjít do terénu a ty věci začít zkoumat.",
            "timestamp": "2026-01-02T14:28:37.619510"
        },
        {
            "user": "Thisík",
            "text": "Na dobíjecí stanice pro elektromobily přece budou nějaká opendata, ne?",
            "timestamp": "2026-01-02T20:36:40.370224"
        },
        {
            "user": "Ondřej Lopatka",
            "text": "Já počítám s tím že vyřešení starých poznámek bude z velké části potřeba jít do terénu",
            "timestamp": "2026-01-03T14:30:14.695442"
        }
    ],
    "project_ideas": [
        {
            "id": 1767216366889,
            "title": "Zařazování zastávek a stanic správně do IDSa opravovat staré tagy.",
            "description": "Zařazování zastávek a stanic správně do IDS příslušných krajů a opravovat zastaralé/chybné tagy, kde chybí bus=yes a podobně. +mapování nových terminálu, který je teď docela dost.",
            "author": "Thisík",
            "votes": 5,
            "created_at": "2025-12-31T22:26:06.889908",
            "winning": False
        },
        {
            "id": 1767218003305,
            "title": "village_green není veřejná zeleň",
            "description": "village_green je zatravněná náves v anglických vesnicích, ne veřejná zeleň. Pro tu je na místě tráva, křoví apod.",
            "author": "PilnýKartograf65",
            "votes": 3,
            "created_at": "2025-12-31T22:53:23.305822",
            "winning": False
        },
        {
            "id": 1767218173150,
            "title": "Uzavření starých poznámek",
            "description": "V mapě jsou mnoho let staré poznámky, kterým se nikdo nevěnuje.",
            "author": "PřesnýObjevitel0",
            "votes": 25,
            "created_at": "2025-12-31T22:56:13.150691",
            "winning": True  # Vítězný nápad pro Q1 2026
        },
        {
            "id": 1767279191529,
            "title": "Mapování chodníků a přechodů pro chodce",
            "description": "Doplnění chodníků a mapování chodníků podél silnic jako samostatných cest pro lepší přehlednost v mapě. Spousta chodníků je nezmapována, některé jsou pouze jako tag u samotné cesty, takže se nevykreslují. \nZároveň by se daly mapovat i přechody, které jsou často tagovány špatně místo značeného přechodu jako přechod.",
            "author": "Ondřej Lopatka",
            "votes": 8,
            "created_at": "2026-01-01T15:53:11.529577",
            "winning": False
        },
        {
            "id": 1767287427772,
            "title": "Dobíjecí stanice pro elektromobily",
            "description": "V OSM chybí kvantum dobíjecích stanic pro elektromobily.",
            "author": "NadšenýObjevitel78",
            "votes": 7,
            "created_at": "2026-01-01T18:10:27.772281",
            "winning": False
        },
        {
            "id": 1767294983190,
            "title": "Revize a opravy nesprávně užívaných značek",
            "description": "Provést kontrolu dat z pohledu správnosti užitých atributů. Uživatel Ernout Meillet opakovaně upozorňoval českou komunitu OSM na nesprávně užívané značky. Viz samostatná vlákna talk cz osm od strpna 2025.",
            "author": "PřesnýEditátor72",
            "votes": 3,
            "created_at": "2026-01-01T20:16:23.190919",
            "winning": False
        },
        {
            "id": 1767349871457,
            "title": "Povrchy dálnic a silnic první třídy",
            "description": "Chybí nám jak větší části dálnic tak i spousta silnic první třídy. Neměl by být problém mapovat to i z ortofota (a teda hlavně by to všechno měl být asfalt).",
            "author": "ZkušenýEditátor24",
            "votes": 1,
            "created_at": "2026-01-02T11:31:11.457919",
            "winning": False
        }
    ],
    "user_votes": {
        "user_sl4oamv6b_mjuit45o": [
            "1767216366889",
            "1767218173150"
        ],
        "user_p9q73k9li_mjujrctg": [
            1767218003305,
            1767218173150
        ],
        "user_16kytczud_mjvjk7nj": [
            1767279191529
        ],
        "user_2fqvtu6gc_mjvkyjuc": [
            "1767279191529",
            "1767218173150"
        ],
        "user_tvupej30s_mjvlxl37": [
            "1767218003305"
        ],
        "user_bbou34s6p_mjvohnhx": [
            "1767218173150"
        ],
        "user_m0u3c7y50_mjvp7i5p": [
            "1767218173150",
            1767287427772
        ],
        "user_hdsoii2dh_mjvptvwu": [
            "1767218173150"
        ],
        "user_auowvjj5x_mjvqnc8w": [
            "1767216366889"
        ],
        "user_b856oeail_mjvtjb1y": [
            "1767218173150",
            1767294983190
        ],
        "user_a99xzkvgq_mjvt9dkz": [
            "1767218173150",
            "1767279191529"
        ],
        "user_n5jti3vwl_mjvv8t2m": [
            "1767287427772"
        ],
        "user_agwazkv9c_mjvx4jsv": [
            "1767218173150",
            "1767279191529"
        ],
        "user_54y01wp5h_mjvx8fj1": [
            "1767279191529"
        ],
        "user_n71eg01m7_mjvxcp7z": [
            "1767218173150"
        ],
        "user_oat4iepb8_mjvym1o5": [
            "1767279191529"
        ],
        "user_6dgkzfzty_mjw1p316": [
            "1767218173150",
            "1767279191529"
        ],
        "user_o23s3gfcn_mjulxld0": [
            "1767218173150"
        ],
        "user_ndx7qyxuc_mjvdpurr": [
            "1767218173150",
            "1767216366889"
        ],
        "user_cagtkicf9_mjw48cbb": [
            "1767218173150",
            "1767218003305"
        ],
        "user_z6dg03phu_mjwbs4rl": [
            "1767218173150",
            "1767287427772"
        ],
        "user_jkbmboxp5_mjwkra5j": [
            "1767216366889",
            "1767218173150"
        ],
        "user_3d9ise6n4_mjwlpano": [
            "1767279191529",
            "1767218173150"
        ],
        "user_pwbbpeu1l_mjwmiwnn": [
            "1767218173150"
        ],
        "user_q482ua9gg_mjwqf1y0": [
            1767349871457,
            "1767294983190"
        ],
        "user_79laizviw_mjwvcinz": [
            "1767218173150"
        ],
        "user_0oqw59ga4_mjww3rb0": [
            "1767218173150",
            "1767287427772"
        ],
        "user_uzfjkxns5_mjwwqpyn": [
            "1767218173150",
            "1767287427772"
        ],
        "user_ndtkaua1z_mjwxsgea": [
            "1767218173150",
            "1767294983190"
        ],
        "user_tp3wzzp1h_mjvssvh3": [
            "1767216366889",
            "1767218173150"
        ],
        "user_vgsagrywn_mjx2xw4n": [
            "1767218173150",
            "1767287427772"
        ],
        "user_vc56xvoxb_mjx34gb1": [
            "1767218173150"
        ],
        "user_h6pil8gh9_mjxaoe2p": [
            "1767287427772"
        ]
    }
}

# Inicializace globálních proměnných s poskytnutými daty
chat_messages = provided_data['chat_messages']
project_ideas = provided_data['project_ideas']
user_votes = provided_data['user_votes']
osm_stats_cache = {
    'data': None,
    'last_updated': None,
    'expires_at': None
}

# Aktuální projekt - vítězný nápad pro Q1 2026
current_project = {
    'id': 1767218173150,
    'title': 'Uzavření starých poznámek',
    'description': 'V mapě jsou mnoho let staré poznámky, kterým se nikdo nevěnuje.',
    'start_date': '2026-01-03',
    'end_date': '2026-04-01',
    'author': 'PřesnýObjevitel0',
    'votes': 25,
    'quarter': 'Q1-2026'
}

# Cesta k souboru s daty
DATA_FILE = 'osm_project_data_quarterly.json'
CONFIG_FILE = 'osm_project_config_quarterly.json'

# Načtení dat ze souboru (pokud existuje)
def load_data():
    global chat_messages, project_ideas, user_votes
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chat_messages = data.get('chat_messages', provided_data['chat_messages'])
            project_ideas = data.get('project_ideas', provided_data['project_ideas'])
            user_votes = data.get('user_votes', provided_data['user_votes'])
            logger.info(f"Data načtena ze souboru: {len(chat_messages)} zpráv, {len(project_ideas)} nápadů")
    except FileNotFoundError:
        logger.info("Soubor s daty neexistuje, používám výchozí data...")
        save_data()

# Uložení dat do souboru
def save_data():
    data = {
        'chat_messages': chat_messages[-200:],
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

# OSM API funkce pro získání changesetů s tagem #projektctvrtleti
def fetch_changesets_from_osm():
    """Získává changesety s tagem #projektctvrtleti z OSM API"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # Čtvrtletí = 90 dní
        
        logger.info(f"OSM API dotaz pro čtvrtletí: od {start_date.date()} do {end_date.date()}")
        
        url = "https://api.openstreetmap.org/api/0.6/changesets"
        
        # Použijeme bbox pro ČR
        params = {
            'bbox': '12.09,48.55,18.87,51.06',
            'time': f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}",
        }
        
        headers = {
            'User-Agent': 'OSM-Projekt-Ctvrtleti/1.0 (Czech OSM Community; https://openstreetmap.cz)'
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
                
                # Hledáme #projektctvrtleti v tagu 'hashtags'
                hashtags = tags.get('hashtags', '')
                comment = tags.get('comment', '')
                
                # Hledáme v hashtags i comment
                search_text = f"{hashtags} {comment}".lower()
                
                if '#projektctvrtleti' in search_text or '#projektčtvrtletí' in search_text:
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
        
        logger.info(f"Načteno {len(changesets)} changesetů s #projektctvrtleti")
        
        # Debug výpis
        for cs in changesets[:5]:
            logger.info(f"  - ID {cs['id']}: {cs.get('user', 'Unknown')} - Hashtags: {cs.get('hashtags', 'None')}")
        
        return changesets
        
    except Exception as e:
        logger.error(f"Chyba při získávání changesetů z OSM: {e}", exc_info=True)
        return []

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
        
        # Parse created_at
        created_at = changeset.get('created_at')
        if created_at:
            try:
                # OSM API vrací UTC čas
                if created_at.endswith('Z'):
                    created_at = created_at[:-1] + '+00:00'
                
                created_dt = datetime.fromisoformat(created_at)
                created_date = created_dt.date()
                
                # Today
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
            
            # Kontrola konce čtvrtletí
            check_quarter_end()
            
        except Exception as e:
            logger.error(f"Chyba v periodických úlohách: {e}")
        
        time.sleep(30)

def check_quarter_end():
    """Kontrola, zda nekončí čtvrtletí"""
    global current_project
    
    now = datetime.now()
    
    # Pokud je 2.4.2026 00:00, vyhlásit vítěze pro Q2
    if now >= datetime(2026, 4, 2, 0, 0, 0):
        # Najít vítězný nápad pro Q2
        if project_ideas:
            # Vyfiltrujeme nápady, které nebyly vítězné
            available_ideas = [idea for idea in project_ideas if not idea.get('winning', False)]
            if available_ideas:
                winning_idea = max(available_ideas, key=lambda x: x.get('votes', 0))
                
                # Označit jako vítězný
                for idea in project_ideas:
                    idea['winning'] = (idea['id'] == winning_idea['id'])
                
                current_project = {
                    'id': winning_idea['id'],
                    'title': winning_idea['title'],
                    'description': winning_idea['description'],
                    'start_date': '2026-04-02',
                    'end_date': '2026-07-01',
                    'author': winning_idea['author'],
                    'votes': winning_idea['votes'],
                    'quarter': 'Q2-2026'
                }
                
                # Oznámit v chatu
                system_message = {
                    'user': 'Systém',
                    'text': f'🎉 Vyhlášen vítězný projekt pro letní čtvrtletí 2026: "{winning_idea["title"]}"! Mapování probíhá od 2.4. do 1.7.2026.',
                    'timestamp': now.isoformat()
                }
                chat_messages.append(system_message)
                socketio.emit('chat_message', system_message)
                logger.info(f"Vyhlášen vítězný projekt pro Q2: {winning_idea['title']}")

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

@app.route('/api/current-project')
def get_current_project():
    """API endpoint pro získání aktuálního projektu"""
    return jsonify(current_project)

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
        
        # Kontrola počtu hlasů (max 2 na čtvrtletí)
        user_vote_count = len(user_votes.get(user_id, []))
        if user_vote_count >= 2:
            return jsonify({'error': 'Již jste použili všechny hlasy pro toto čtvrtletí'}), 400
        
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
    print("PRODUKČNÍ APLIKACE - Projekt čtvrtletí pro českou OSM komunitu")
    print(f"Čas spuštění: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"Načteno: {len(chat_messages)} zpráv v chatu, {len(project_ideas)} nápadů")
    print(f"Aktuální projekt (Q1 2026): {current_project['title']}")
    print(f"Období: {current_project['start_date']} - {current_project['end_date']}")
    print("=" * 70)
    print("Aplikace běží na http://0.0.0.0:4040")
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