# Career Finder Marrakech

Une application complète de recherche d'emploi pour le marché de Marrakech, spécifiquement ciblant les entreprises IA & IT.

## Qu'est-ce que c'est ?

Career Finder Marrakech est une plateforme tout-en-un qui aide les professionnels à trouver des opportunités d'emploi dans le secteur des technologies à Marrakech. Il combine la recherche d'entreprises, la gestion de candidatures et les fonctionnalités d'analyse des données pour simplifier votre recherche d'emploi.

### Points forts principaux

- **📊 Base de données d'entreprises enrichie** - Entreprises IA & IT vérifiées de Marrakech collectées via Google Places et importées via Excel
- **🎯 Système de scoring intelligent** - Score de pertinence 0-100 basé sur les compétences et l'analyse sectorielle
- **📧 Envoi automatique de CV** - Envoie des CV par e-mail aux entreprises cibles avec suivi des candidatures
- **🗺️ Carte interactive** - Visualisez l'emplacement des entreprises avec Google Maps
- **📈 Tableaux de bord avancés** - Suivez votre progression, les tendances du marché et les statistiques de candidature
- **🔐 Interface d'administration robuste** - Ajoutez/modifiez des entreprises, importez des offres, gérez les utilisateurs

## Fonctionnalités

### Pour les candidats

1. **Recherche d'entreprises** - Filtrez par secteur, score minimum, mots-clés
2. **Envoi de CV** - Envoyez votre CV par e-mail avec un message personnalisé
3. **Suivi des candidatures** - Suivez l'état de vos candidatures (À contacter → Refusée)
4. **Matching IA** - Obtenez des recommandations d'entreprises basées sur vos compétences
5. **Gestion de CV** - Téléversez et gérez plusieurs CV PDF

### Pour l'administration

1. **Gestion des entreprises** - Ajoutez/modifiez des entreprises IA/IT marrachéennes
2. **Importation de données en masse** - Importez via Google Places ou Excel
3. **Gestion des offres** - Ajoutez des offres de stage/offre d'emploi et liez-les aux entreprises
4. **Rapports et analyses** - Exportez des données et générez des insights
5. **Contrôle d'accès** - System d'authentification admin/utilisateur

## Technologies utilisées

- **Frontend** : HTML5, CSS3 (moderne, design réactif), JavaScript (ES2022+, vanilla)
- **Backend** : FastAPI (Python), SQLite (base de données)
- **APIs** : Google Places API, Google Maps JavaScript API
- **Traitement de fichiers** : Pandas, Openpyxl (Excel), BeautifulSoup (web scraping)
- **Email** : SMTP avec configuration flexible

## Démarrage rapide

### Prérequis

- Python 3.8+
- Pip

### Installation

```bash
# Clonez ce dépôt
cd /chemin/vers/votre/projet

# Créez un environnement virtuel (optionnel mais recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
# venv\\Scripts\\activate  # Windows

# Installez les dépendances
pip install -r requirements.txt

# Configurez l'environnement (voir .env.example)
cp .env.example .env
# Modifier GOOGLE_MAPS_API_KEY, variables SMTP, etc.

# Configurez la base de données (les migrations sont gérées automatiquement)
# Le moteur SQLite est utilisé ; la base de données par défaut est ubicada dans le dossier backend/

# Démarrez le serveur FastAPI
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Dans un terminal séparé, démarrez le serveur de fichiers statiques
# Le backend FastAPI sert automatiquement le dossier frontend/static/
```

### Accéder à l'interface utilisateur

- **Local** : http://localhost:8000/
- **Depuis un autre appareil** : http://votre-ip:8000/

## Configuration

### Variables d'environnement principales

- `GOOGLE_MAPS_API_KEY` - Clé API Google Places/Maps
- `SMTP_*` - Paramètres du serveur SMTP (optionnel)
- `ALLOW_REGISTRATION` - Activer/désactiver les inscriptions d'utilisateurs (défaut : true)
- `CORS_ORIGINS` - Origines autorisées pour le frontend (séparées par des virgules)

### Structure du répertoire

```
projet-principale-career-finder-marrakech-2/
├── backend/
│   ├── main.py              # Serveur FastAPI principal
│   ├── database.py         # Opérations SQLite
│   ├── mailer.py           # Fonctions d'envoi d'e-mails
│   └── security.py         # JWT, mots de passe, rate limiting
├── frontend/static/         # Frontend statique (servi par le backend)
│   ├── index.html
│   ├── css/
│   ├── js/
│   │   ├── core.js
│   │   ├── pages-a.js
│   │   └── pages-b.js
│   └── img/
├── pipeline/                # Modules de collecte et nettoyage de données
│   ├── google_places.py    # Collecte Google Places
│   ├── excel_importer.py   # Import Excel / CSV
│   ├── cleaner.py          # Nettoyages + scoring
│   ├── sectors.py          # Liste des secteurs IT/IA
│   └── scraper_trabajo.py  # Web scraping optionnel
├── tests/                   # Tests unitaires et d'intégration
├── Dockerfile               # Image Docker (optionnel)
├── docker-compose.yml       # Environnement complet Docker
├── requirements.txt         # Dépendances Python
└── .env.example            # Exemple de .env
```

## Utilisation

### Utilisateur authentifié

1. **Connexion / Inscription** - Créez un compte ou connectez-vous
2. **Tableau de bord** - Visualisez votre progression et les opportunités clés
3. **Recherche d'entreprises** - Trouvez des entreprises basées sur le secteur, le score, les mots-clés
4. **Postulez** - Envoyez votre CV, suivez vos candidatures
5. **Profil** - Configurez les compétences, téléversez des CV, obtenez des suggestions de matching

### Admin

1. **Connexion** - Connectez-vous avec des droits d'admin (modifiez backend/database.py si nécessaire)
2. **Administration** - Utilisez les onglets :
   - **Entreprises** - Ajoutez/modifiez des entreprises IA/IT
   - **Offres** - Ajoutez des offres de stage/offre d'emploi
   - **Données** - Importez des données via Google Places ou Excel
   - **Statistiques** - Visualisez les analyses et exportez des données
3. **Rapports** - Exportez des données brutes vs nettoyées, suivis complet des candidatures

## Tests

```bash
# Tests unitaires (Python)
python -m pytest tests/ -v

# Exemples de tests d'intégration (à automatiser avec Docker Compose)
# À exécuter après avoir démarré le serveur FastAPI
```

## Maintenance et opérations

### Répertoire de stockage des CV

Les PDF de CV sont stockés dans `backend/cvs/` (nom d'utilisateur comme sous-dossier).

### Sauvegarde de la base de données

La base de données SQLite est située dans `backend/data.db`. Exportez via les API d'exportation du backend ou utilisez SQLite standard.

### Journalisation des envois d'e-mails

L'envoi d'e-mails est basé sur SMTP ; vérifiez les journaux du serveur SMTP pour les tentatives.

### Améliorations possibles (roadmap)

1. **Système de fichiers complet** - Rôle multi-utilisateurs (recruteurs), CV public/visibilité privée
2. **Matching IA avancé** - Analyse de CV + mots-clés d'entreprises, prédiction de score
3. **Intégration mobile** - Application mobile PWA
4. **Optimisation SEO** - Tarification dynamique, suggestions de mots-clés
5. **Analytique avancée** - Heatmaps des secteurs, tendances salariales, temps moyen de réponse

## Licence

Propriétaire - utilisez selon les besoins du projet.

## Support

Pour les modifications du code, reportez-vous aux fichiers CHANGELOG ou CONVENTIONS spécifiques à chaque module.