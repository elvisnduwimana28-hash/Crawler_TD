import time
import sqlite3
import urllib.robotparser
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import re
from collections import defaultdict

# Configuration cible (Un site de football riche sémantiquement)
TARGET_URL = "https://elvis-nduwimana-portofolio.vercel.app/"
USER_AGENT = "Mozilla/5.0 (Indexeur-Football-Bot; +http://monsite.com/bot)"

# ==========================================
# ÉTAPE 4 : PERSISTANCE & SÉCURITÉ (Backend)
# ==========================================
def setup_database():
    """Initialise le Modèle (MVC) avec SQLite et prévient les injections SQL."""
    conn = sqlite3.connect('index_crawler.db')
    cursor = conn.cursor()
    # Création de la table pour stocker l'URL, le mot-clé et la fréquence pondérée
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS index_seo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            mot_cle TEXT NOT NULL,
            frequence_ponderee INTEGER NOT NULL
        )
    ''')
    conn.commit()
    return conn

def save_to_db(conn, url, word_scores):
    """Sauvegarde sécurisée utilisant des requêtes paramétrées."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM index_seo WHERE url = ?", (url,)) # Nettoyage préalable
    
    # Insertion sécurisée (sanitisation stricte par le driver SQLite)
    for word, score in word_scores.items():
        cursor.execute(
            "INSERT INTO index_seo (url, mot_cle, frequence_ponderee) VALUES (?, ?, ?)",
            (url, word, score)
        )
    conn.commit()

# ==========================================
# ÉTAPE 1 : ARCHITECTURE DU ROBOT (Crawler)
# ==========================================
def check_robots_txt(url):
    """Vérifie le standard d'exclusion des robots (RES)."""
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    robots_url = f"{base_url}/robots.txt"
    
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        # Vérifie si notre bot (User-agent) a le droit de crawler
        return rp.can_fetch(USER_AGENT, url)
    except Exception as e:
        print(f"[-] Impossible de lire robots.txt : {e}")
        return True # Par défaut, on continue si le fichier est absent

def get_words(text):
    """Nettoie et extrait les mots (minimum 3 lettres), en ignorant les stop-words basiques."""
    if not text: return []
    words = re.findall(r'\b[a-zA-Zà-ÿÀ-Ÿ]+\b', text.lower())
    stop_words = {'les', 'des', 'est', 'sur', 'pour', 'par', 'avec', 'dans', 'une', 'qui', 'que'}
    return [w for w in words if len(w) > 2 and w not in stop_words]

# ==========================================
# ÉTAPE 2 & 3 : EXTRACTION SÉMANTIQUE & POIDS
# ==========================================
def analyze_page(url):
    """Télécharge la page et calcule la fréquence pondérée des balises SEO critiques."""
    print(f"[*] Vérification de {url}...")
    
    if not check_robots_txt(url):
        print("[-] Crawl interdit par le fichier robots.txt (Directive Disallow).")
        return None

    # Implémentation du Rate Limiting (anti DoS)
    print("[*] Rate limiting : attente de 2 secondes...")
    time.sleep(2)
    
    headers = {'User-Agent': USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[-] Erreur de connexion : {e}")
        return None

    # L'utilisation de utf-8 est critique pour les caractères internationaux (ex: accents)
    response.encoding = 'utf-8' 
    soup = BeautifulSoup(response.text, 'html.parser')
    scores = defaultdict(int)

    # Grille de pondération SEO
    weights = {
        'title': 10, 'meta_keywords': 8, 'meta_description': 7,
        'h1': 6, 'h2': 5, 'h3': 4, 'h4': 3, 'h5': 2, 'h6': 1, 'alt': 1
    }

    # Extraction Sémantique
    if soup.title and soup.title.string:
        for w in get_words(soup.title.string): scores[w] += weights['title']
            
    for meta in soup.find_all('meta'):
        name = (meta.get('name') or meta.get('property', '')).lower()
        content = meta.get('content', '')
        if 'keywords' in name:
            for w in get_words(content): scores[w] += weights['meta_keywords']
        elif 'description' in name:
            for w in get_words(content): scores[w] += weights['meta_description']

    for i in range(1, 7):
        tag_name = f'h{i}'
        for tag in soup.find_all(tag_name):
            for w in get_words(tag.get_text()): scores[w] += weights[tag_name]

    for img in soup.find_all('img'):
        if img.get('alt'):
            for w in get_words(img.get('alt')): scores[w] += weights['alt']

    return scores

def display_cloud(scores, limit=15):
    """Affiche un tableau imitant un nuage de mots-clés."""
    if not scores: return
    print("\n" + "="*50)
    print(f"{'MOT CLÉ (Thèmes du site) ':<30} | {'FRÉQUENCE PONDÉRÉE'}")
    print("="*50)
    
    # Tri décroissant selon le score calculé
    top_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    for word, score in top_words:
        print(f"{word.capitalize():<30} | {score}")
    print("="*50)

if __name__ == "__main__":
    db_conn = setup_database()
    
    mots_cles_calcules = analyze_page(TARGET_URL)
    
    if mots_cles_calcules:
        save_to_db(db_conn, TARGET_URL, mots_cles_calcules)
        print("\n[+] Données sauvegardées en base (Modèle MVC) avec sanitisation.")
        display_cloud(mots_cles_calcules)
        
    db_conn.close()