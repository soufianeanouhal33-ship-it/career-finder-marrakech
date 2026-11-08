# Guide de contribution

Merci de contribuer à Career Finder Marrakech ! Ce guide décrit les meilleures pratiques pour contribuer au projet.

## Structure du code

### Frontend (static)

Le frontend est livré sous forme de code JavaScript vanilla sans framework. Toutes les interactions sont codées en pure JS avec une architecture simple anti-poison basée sur `localStorage`.

- **Structure des fichiers**
  - `frontend/static/index.html` - HTML principal, routeur de vue (hash-based)
  - `frontend/static/js/` - JavaScript modulaire : `core.js` (noyau), `pages-a.js` (pages principales), `pages-b.js` (dialogues modaux)
  - `frontend/static/css/` - Styles CSS en une seule feuille (source de vérité pour l'interface utilisateur)

- **Nommage des fichiers**
  - Le cas snake_case est préféré pour tous les nouveaux fichiers (ex. `auth-helper.js`, `ui-utils.js`)
  - Les noms descriptifs et concis sont obligatoires

- **Organisation des fichiers**
  - Fichiers regroupés par fonctionnalité (auth, utils, api, ui)
  - Pas de dépendances npm ou bundlers externes (léger, fonctionne partout)

### Backend (FastAPI)

- **Structure des fichiers**
  - `backend/main.py` - FastAPI principal, routes d'API
  - `backend/database.py` - Accès SQLite, schéma, fonctions CRUD
  - `backend/mailer.py` - Envoi d'e-mails via SMTP
  - `backend/security.py` - JWT, hachage de mots de passe, rate limiting

- **Organisation des fichiers**
  - Services spécialisés (modules séparés pour les préoccupations distinctes)
  - Imports absolus, pas de fichiers __pycache__ dans le dépôt

### Pipeline (collecte et nettoyage de données)

- **Modules**
  - `google_places.py` - API Google Places, pagination, nettoyage
  - `excel_importer.py` - Lecture Excel/CSV, détection de colonnes, nettoyage
  - `cleaner.py` - Lignes de nettoyage en chaîne, scoring par secteur
  - `sectors.py` - Tableau de correspondance des secteurs, utilitaires de normalisation

- **Conventions**
  - Utilisez pandas pour les traitements tabulaire ; les grands ensembles de données restent en mémoire (ML local)
  - Chaque script est une application autonome avec un `main()`
  - Pas de processus en arrière-plan ; tout est synchrone ou asynchrone explicite

## Workflow de développement

### Commencer un nouveau fichier

1. **Choisissez un emplacement approprié** :
   - Frontend : `frontend/static/js/`
   - Backend : `backend/`
   - Données : `pipeline/`

2. **Commencez par la structure**

```javascript
// Exemple : frontend/static/js/auth-helper.js
"use strict";

/** Helper pour l'authentification et la gestion des sessions */

/** @typedef {object} AuthState */

/** @type {AuthState} */
const authState = {
  token: null,
  user: null,
};

/** @param {string} token */
function setToken(token) {
  authState.token = token;
  localStorage.setItem("auth_token", token);
}

export { authState, setToken };
```

3. **Écrivez des tests unitaires** (si approprié)
4. **Validez le nouveau code localement**
5. **Créez une branche** avec un nom descriptif (ex. `feature/employes-recherche-ajoutee`)
6. **Envoyez la branche** et créez une Pull Request

### Révision du code et normes de qualité

- **Règles du moteur**
  - **Taille maximale des lignes** : 100 caractères
  - **Semi-colons** : Requis (Style JS avec points-virgules)
  - **Cas de code** : snake_case pour les variables et les fonctions, PascalCase pour les classes
  - **Nommage des fichiers** : snake_case (sauf index.html)

- **Normes spécifiques**
  - **Sécurité** : Toutes les données issues de l'API sont échappées (`esc()`) avant injection HTML
  - **Accessibilité** : Utilisez aria-* et tabindex pour toutes les interfaces utilisateur modales/focales
  - **Performance** : Debounce de la recherche (250 ms), limite de pagination (100 éléments par page)
  - **Tests** : Tests unitaires pour les helpers du backend, tests d'intégration pour les APIs

### Processus de fusion de Pull Requests (PR)

1. **Révision de la PR**
   - Un relecteur désigné vérifie le code, la sécurité, les tests et l'accessibilité
   - Tests d'intégration automatisés (si disponibles)
   - Informations de débogage, instructions de déploiement ajoutées dans la description

2. **Préparation pour la fusion**
   - Titre de la PR concis + description claire du problème et de la solution
   - Incluez les numéros de problèmes/GitHub dans la description de la PR
   - Ajoutez des captures d'écran pour les changements d'interface utilisateur (si elles changent significativement l'interface)

3. **Conditions de fusion**
   - Toutes les vérifications CI doivent passer (linting, tests, packaging)
   - Problèmes de sécurité critiques bloqués, mais les avertissements de qualité de code nécessitent une attention

### Version et étiquetage

- **Étiquettes principales**
  - `bug` - Problèmes de sécurité, bugs fonctionnels
  - `feature` - Nouvelles fonctionnalités, améliorations de l'interface utilisateur
  - `improvement` - Nettoyage du code, performance, qualité de l'interface utilisateur
  - `documentation` - Mises à jour de README, guides, commentaires
  - `testing` - Couverture de tests, ajout de tests

- **Étiquettes de version**
  - Suivez le style sémantique de versionning (SemVer) basé sur l'état du dépôt de base (stable/major)

## Commande /help pour obtenir de l'aide

Si vous avez besoin d'aide pour le développement, de conseils ou pour savoir quelles tâches prioriser, utilisez simplement la commande `/help` dans la conversation. Elle vous guidera vers la documentation pertinente, vous suggérera des tâches courantes et vous aidera à comprendre la base de code.

## Conventions de base de code non négociables

1. **Sécurité**
   - Les données issues de l'API doivent toujours être échappées (`esc()`) avant injection HTML
   - Toutes les opérations sensibles sont limitées par utilisateur et temps
   - Pas de `innerHTML` sur du contenu utilisateur brut ; utilisez `textContent` ou des fragments DOM sûrs

2. **Performance**
   - La pagination et le debounce sont obligatoires pour les listes volumineuses
   - Les cartes sensibles aux événements sont limitées à ~100 éléments par page
   - Les images et scripts lourds sont chargés à la demande (lazy loading)

3. **Accessibilité**
   - Toutes les interfaces modales ont un `role="dialog"` et des boutons de fermeture
   - Skip links pour le contenu principal (`#view`)
   - Utilisez des rôles ARIA appropriés et un contraste suffisant

4. **Compatibilité**
   - Fonctionne sur les navigateurs modernes (Chrome, Firefox, Safari, Edge)
   - CSS adaptatif intégré (mobile/tablette/desktop)
   - Pas de dépendance aux frameworks ou transpilation

## Questions fréquentes

### "Puis-je utiliser un framework frontend ?"
Non. Ce projet est délibérément livré sous forme de code JavaScript vanilla pour réduire la complexité et améliorer les performances. Si vous avez besoin d'un framework, envisagez un dépôt séparé pour une version avancée.

### "Où sont les packages.json et la gestion des dépendances ?"
Toutes les dépendances sont gérées par un `requirements.txt` et des commandes pip explicites. Le frontend n'a aucune dépendance, ce qui en fait un produit léger.

### "Puis-je ajouter des hooks pour une nouvelle fonctionnalité ?"
Oui, mais vous devez suivre nos hooks et conventions. Les commandes `/help` ou `/config` peuvent vous guider vers les bonnes étapes.

## Guide de démarrage rapide pour les nouveaux contributeurs

1. **Lisez la documentation principale** (`docs/`) pour comprendre le domaine métier
2. **Choisissez une tâche** depuis notre liste de `issues` (étiquette : `good-first-issue`, `help-wanted`)
3. **Faites un tuto** - choisissez un fichier, ajoutez un commentaire, demandez-moi des instructions spécifiques
4. **Faites vos premiers pas** avec un problème de documentation ou un bug simple
5. **Construisez progressivement** des compétences en écrivant des helpers réutilisables

## Support et ressources

- **Slack/Teams** : Joignez-vous à notre communauté de développeurs pour des questions en temps réel
- **GitHub Issues** : Rapports de bugs et demandes de fonctionnalités
- **Discord** : Discussions informelles, partage de conseils, débriefings de code

N'hésitez pas à demander `/help` pour plus de conseils sur un nouveau fichier ou une nouvelle fonctionnalité. Nous mettons tout en œuvre pour rendre la collaboration fluide et agréable ! 🎉