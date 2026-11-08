"""Career Finder - Recherche de stage à Marrakech (IA & IT) - version Streamlit."""
import hashlib
import os
import sqlite3
import datetime as dt

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Career Finder", page_icon="🎯", layout="wide")

DB = "career_finder.db"
SECTORS = ["Informatique", "IA", "Marketing", "Commerce", "Autre"]
STATUSES = ["À contacter", "Envoyée", "Entretien", "Offre reçue", "Refusée"]
CONTRACTS = ["Stage", "CDI", "CDD", "Freelance", "Alternance"]
INTERN_TYPES = ["PFE", "Stage d'initiation", "Stage d'été", "Stage technique"]
MAX_CV = 10
MAX_CV_BYTES = 5 * 1024 * 1024

st.markdown(
    """
<style>
.block-container {padding-top: 2rem;}
div[data-testid="stSidebar"] {border-right: 1px solid #1f2a44;}
.badge {background:#0f766e; color:#d1fae5; padding:2px 10px; border-radius:12px; font-size:.8rem;}
.muted {color:#8b9ab8; font-size:.9rem;}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------- Base de données


def get_conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def q(sql, params=()):
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def ex(sql, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def init_db():
    with get_conn() as c:
        c.executescript(
            """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, salt TEXT, pwd TEXT, role TEXT);
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, address TEXT, sector TEXT,
            phone TEXT, email TEXT, website TEXT, maps TEXT, rating REAL,
            lat REAL, lng REAL, favorite INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS offers(
            id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, company TEXT,
            intern_type TEXT, contract TEXT, link TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS applications(
            id INTEGER PRIMARY KEY, user_id INTEGER, company TEXT, position TEXT,
            date TEXT, status TEXT, comment TEXT);
        CREATE TABLE IF NOT EXISTS cvs(
            id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, filename TEXT,
            data BLOB, size INTEGER, is_default INTEGER DEFAULT 0, created TEXT);
        CREATE TABLE IF NOT EXISTS profiles(
            user_id INTEGER PRIMARY KEY, skills TEXT, sectors TEXT, keywords TEXT, level TEXT);
        """
        )


init_db()

# ----------------------------------------------------------------- Authentification


def hash_pwd(pwd, salt):
    return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 100_000).hex()


def register(username, pwd):
    if len(username) < 3 or len(pwd) < 6:
        return "Pseudo ≥ 3 caractères et mot de passe ≥ 6 caractères."
    if q("SELECT id FROM users WHERE username=?", (username,)):
        return "Ce pseudo existe déjà."
    role = "admin" if not q("SELECT id FROM users LIMIT 1") else "user"
    salt = os.urandom(8).hex()
    ex("INSERT INTO users(username,salt,pwd,role) VALUES(?,?,?,?)",
       (username, salt, hash_pwd(pwd, salt), role))
    return None


def login(username, pwd):
    u = q("SELECT * FROM users WHERE username=?", (username,))
    if u and u[0]["pwd"] == hash_pwd(pwd, u[0]["salt"]):
        st.session_state.user = u[0]
        return True
    return False


def auth_screen():
    st.markdown("## 🎯 Career Finder")
    st.caption("Marrakech · IA & IT")
    t1, t2 = st.tabs(["Connexion", "Créer un compte"])
    with t1:
        with st.form("login"):
            u = st.text_input("Pseudo")
            p = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", type="primary"):
                if login(u.strip(), p):
                    st.rerun()
                else:
                    st.error("Identifiants incorrects.")
    with t2:
        with st.form("register"):
            u = st.text_input("Pseudo", key="ru")
            p = st.text_input("Mot de passe", type="password", key="rp")
            if st.form_submit_button("Créer mon compte"):
                err = register(u.strip(), p)
                if err:
                    st.error(err)
                else:
                    login(u.strip(), p)
                    st.rerun()


if "user" not in st.session_state:
    auth_screen()
    st.stop()

USER = st.session_state.user
UID = USER["id"]

# ----------------------------------------------------------------- Helpers métier


def get_profile():
    r = q("SELECT * FROM profiles WHERE user_id=?", (UID,))
    if r:
        return r[0]
    return {"skills": "", "sectors": "", "keywords": "", "level": ""}


def compute_score(c, profile):
    """Score d'opportunité (0-100) d'une entreprise."""
    s = min((c.get("rating") or 0) / 5, 1) * 40
    s += 20 if c.get("website") else 0
    s += 15 if c.get("email") else 0
    s += 10 if c.get("phone") else 0
    kws = [k.strip().lower() for k in (profile.get("keywords") or "").split(",") if k.strip()]
    kws += [k.strip().lower() for k in (profile.get("skills") or "").split(",") if k.strip()]
    text = f"{c.get('name','')} {c.get('address','')} {c.get('sector','')}".lower()
    if any(k in text for k in kws):
        s += 15
    return int(min(100, round(s)))


def companies_df():
    rows = q("SELECT * FROM companies WHERE user_id=?", (UID,))
    prof = get_profile()
    for r in rows:
        r["score"] = compute_score(r, prof)
    df = pd.DataFrame(rows)
    return df.sort_values("score", ascending=False) if not df.empty else df


def default_cv():
    r = q("SELECT * FROM cvs WHERE user_id=? ORDER BY is_default DESC, id LIMIT 1", (UID,))
    return r[0] if r else None


def add_application(company, position="Stage", status="À contacter", comment=""):
    ex("INSERT INTO applications(user_id,company,position,date,status,comment) VALUES(?,?,?,?,?,?)",
       (UID, company, position, dt.date.today().isoformat(), status, comment))


# ----------------------------------------------------------------- Navigation

PAGES = {
    "🏠 Accueil": "home",
    "🏢 Entreprises": "companies",
    "📄 Offres": "offers",
    "🗺️ Carte": "map",
    "📨 Candidatures": "apps",
    "📎 Mes CV": "cvs",
    "👤 Profil & Matching": "profile",
    "📊 Statistiques": "stats",
    "🗄️ Collecte & Import": "import",
}

with st.sidebar:
    st.markdown("### 🎯 Career Finder")
    st.caption("Marrakech · IA & IT")
    if "page" not in st.session_state:
        st.session_state.page = "🏠 Accueil"
    page = st.radio("Navigation", list(PAGES), key="page", label_visibility="collapsed")
    st.divider()
    st.markdown(f"**{USER['username']}** · `{USER['role']}`")
    if st.button("Se déconnecter", use_container_width=True):
        del st.session_state["user"]
        st.rerun()


def goto(p):
    st.session_state.page = p


# ----------------------------------------------------------------- Pages


def page_home():
    st.title(f"Bonjour {USER['username']} 👋")
    st.caption("Voici où en est ta recherche de stage à Marrakech.")
    df = companies_df()
    n_comp = len(df)
    n_mail = int(df["email"].fillna("").ne("").sum()) if n_comp else 0
    n_off = q("SELECT COUNT(*) n FROM offers WHERE user_id=?", (UID,))[0]["n"]
    apps = q("SELECT * FROM applications WHERE user_id=?", (UID,))
    n_sent = sum(1 for a in apps if a["status"] != "À contacter")
    prof = get_profile()

    steps = [
        ("Enregistre ton CV (PDF)", default_cv() is not None, "📎 Mes CV", "Ajouter"),
        ("Renseigne tes compétences", bool(prof["skills"]), "👤 Profil & Matching", "Profil"),
        ("Récupère des entreprises (Google Places ou Excel)", n_comp > 0, "🗄️ Collecte & Import", "Importer"),
        ("Ajoute des e-mails de contact", n_mail > 0, "🏢 Entreprises", "Voir les entreprises"),
        ("Envoie ton premier CV", n_sent > 0, "📨 Candidatures", "Postuler"),
    ]
    done = sum(1 for s in steps if s[1])
    with st.container(border=True):
        st.subheader(f"🚀 Pour bien démarrer · {done}/5")
        st.progress(done / 5)
        for i, (label, ok, target, btn) in enumerate(steps, 1):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{'✅' if ok else f'**{i}.**'} " + (f"~~{label}~~" if ok else label))
            if not ok:
                c2.button(btn, key=f"step{i}", on_click=goto, args=(target,))

    k = st.columns(5)
    k[0].metric("🏢 Entreprises", n_comp)
    k[1].metric("📄 Offres", n_off)
    k[2].metric("✉️ Avec e-mail", n_mail)
    k[3].metric("📤 CV envoyés", n_sent)
    k[4].metric("📨 Candidatures", len(apps))


def company_form(prefix, c=None):
    c = c or {}
    col1, col2 = st.columns(2)
    name = col1.text_input("Nom", c.get("name", ""), key=f"{prefix}n")
    sector = col2.selectbox("Secteur", SECTORS,
                            index=SECTORS.index(c["sector"]) if c.get("sector") in SECTORS else 0, key=f"{prefix}s")
    address = st.text_input("Adresse", c.get("address", "") or "", key=f"{prefix}a")
    col3, col4, col5 = st.columns(3)
    phone = col3.text_input("Téléphone", c.get("phone", "") or "", key=f"{prefix}p")
    email = col4.text_input("E-mail", c.get("email", "") or "", key=f"{prefix}e")
    website = col5.text_input("Site web", c.get("website", "") or "", key=f"{prefix}w")
    return dict(name=name, sector=sector, address=address, phone=phone, email=email, website=website)


def page_companies():
    st.title("🏢 Entreprises")
    st.caption("Entreprises IA & IT de Marrakech, classées par score d'opportunité.")
    df = companies_df()

    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 1, 1])
        search = c1.text_input("Recherche", placeholder="Nom ou adresse…")
        sector = c2.selectbox("Secteur", ["Tous les secteurs"] + SECTORS)
        min_score = c3.slider("Score minimum", 0, 100, 0)
        only_mail = c4.checkbox("Avec e-mail")
        only_fav = c5.checkbox("Favoris")

    with st.expander("➕ Ajouter une entreprise"):
        with st.form("add_company", clear_on_submit=True):
            data = company_form("new")
            if st.form_submit_button("Enregistrer", type="primary") and data["name"]:
                ex("INSERT INTO companies(user_id,name,sector,address,phone,email,website) VALUES(?,?,?,?,?,?,?)",
                   (UID, data["name"], data["sector"], data["address"], data["phone"], data["email"], data["website"]))
                st.rerun()

    if df.empty:
        st.info("Aucune entreprise. Va dans « Collecte & Import » ou ajoute-en une.")
        return
    f = df.copy()
    if search:
        s = search.lower()
        f = f[f["name"].fillna("").str.lower().str.contains(s) | f["address"].fillna("").str.lower().str.contains(s)]
    if sector != "Tous les secteurs":
        f = f[f["sector"] == sector]
    f = f[f["score"] >= min_score]
    if only_mail:
        f = f[f["email"].fillna("") != ""]
    if only_fav:
        f = f[f["favorite"] == 1]
    st.write(f"**{len(f)}** entreprise(s) trouvée(s)")

    per_page = 15
    pages = max(1, -(-len(f) // per_page))
    pg = st.number_input("Page", 1, pages, 1) if pages > 1 else 1
    cv = default_cv()

    for _, r in f.iloc[(pg - 1) * per_page: pg * per_page].iterrows():
        with st.container(border=True):
            a, b, c, d = st.columns([0.4, 4, 2, 3])
            if a.button("⭐" if r["favorite"] else "☆", key=f"fav{r['id']}"):
                ex("UPDATE companies SET favorite=? WHERE id=?", (0 if r["favorite"] else 1, int(r["id"])))
                st.rerun()
            b.markdown(f"**{r['name']}**")
            if r["address"]:
                b.markdown(f"<span class='muted'>{r['address']}</span>", unsafe_allow_html=True)
            b.markdown(f"<span class='badge'>{r['sector']}</span>", unsafe_allow_html=True)
            c.markdown(f"**Score {r['score']}**")
            c.progress(r["score"] / 100)
            if r["rating"]:
                c.caption(f"⭐ {r['rating']}")
            if r["phone"]:
                c.caption(f"📞 {r['phone']}")
            c.caption(f"✉️ {r['email']}" if r["email"] else "✉️ —")
            links = []
            if r["website"]:
                links.append(f"[🌐 Site]({r['website']})")
            if r["maps"]:
                links.append(f"[📍 Maps]({r['maps']})")
            d.markdown(" · ".join(links) if links else "—")
            bc = d.columns(3)
            if cv:
                bc[0].download_button("CV", cv["data"], cv["filename"], "application/pdf", key=f"cv{r['id']}")
            if bc[1].button("Suivre", key=f"fol{r['id']}"):
                add_application(r["name"])
                st.toast(f"{r['name']} ajoutée aux candidatures")
            if bc[2].button("🗑️", key=f"del{r['id']}"):
                ex("DELETE FROM companies WHERE id=?", (int(r["id"]),))
                st.rerun()
            with st.expander("✏️ Modifier"):
                with st.form(f"edit{r['id']}"):
                    data = company_form(f"e{r['id']}", r.to_dict())
                    if st.form_submit_button("Mettre à jour"):
                        ex("UPDATE companies SET name=?,sector=?,address=?,phone=?,email=?,website=? WHERE id=?",
                           (*data.values(), int(r["id"])))
                        st.rerun()


def page_offers():
    st.title("📄 Offres de stage et d'emploi")
    st.caption("Opportunités professionnelles à Marrakech.")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        search = c1.text_input("Recherche", placeholder="Titre, entreprise…")
        t = c2.selectbox("Type de stage", ["Tous les types"] + INTERN_TYPES)
        ct = c3.selectbox("Contrat", ["Tous les contrats"] + CONTRACTS)
    with st.expander("➕ Ajouter une offre"):
        with st.form("add_offer", clear_on_submit=True):
            a, b = st.columns(2)
            title = a.text_input("Titre *")
            company = b.text_input("Entreprise")
            c, d = st.columns(2)
            it = c.selectbox("Type de stage", INTERN_TYPES)
            co = d.selectbox("Contrat", CONTRACTS)
            link = st.text_input("Lien")
            if st.form_submit_button("Enregistrer", type="primary") and title:
                ex("INSERT INTO offers(user_id,title,company,intern_type,contract,link,created) VALUES(?,?,?,?,?,?,?)",
                   (UID, title, company, it, co, link, dt.date.today().isoformat()))
                st.rerun()
    rows = q("SELECT * FROM offers WHERE user_id=? ORDER BY id DESC", (UID,))
    if search:
        rows = [r for r in rows if search.lower() in f"{r['title']} {r['company']}".lower()]
    if t != "Tous les types":
        rows = [r for r in rows if r["intern_type"] == t]
    if ct != "Tous les contrats":
        rows = [r for r in rows if r["contract"] == ct]
    st.write(f"**{len(rows)}** offre(s) trouvée(s)")
    if not rows:
        st.info("Aucune offre. Ajoute-en une ou importe un fichier depuis « Collecte & Import ».")
    for r in rows:
        with st.container(border=True):
            a, b = st.columns([6, 1])
            a.markdown(f"**{r['title']}** — {r['company'] or '—'}")
            a.markdown(f"<span class='badge'>{r['intern_type']}</span> <span class='badge'>{r['contract']}</span>",
                       unsafe_allow_html=True)
            if r["link"]:
                a.markdown(f"[Voir l'offre]({r['link']})")
            if b.button("🗑️", key=f"do{r['id']}"):
                ex("DELETE FROM offers WHERE id=?", (r["id"],))
                st.rerun()


def page_map():
    st.title("🗺️ Carte")
    st.caption("Localisation des entreprises collectées.")
    df = companies_df()
    c1, c2 = st.columns([1, 2])
    sector = c1.selectbox("Secteur", ["Tous les secteurs"] + SECTORS)
    min_score = c2.slider("Score minimum", 0, 100, 0)
    if df.empty:
        st.info("Aucune entreprise collectée.")
        return
    f = df[df["score"] >= min_score]
    if sector != "Tous les secteurs":
        f = f[f["sector"] == sector]
    f = f.dropna(subset=["lat", "lng"])
    st.write(f"**{len(f)}** entreprise(s) affichée(s)")
    if f.empty:
        st.warning("Aucune coordonnée. Importe des données avec colonnes lat/lng ou utilise Google Places.")
    else:
        # Centre la carte sur Marrakech si possible
        f = f[(f["lat"].between(-90, 90)) & (f["lng"].between(-180, 180))]
        st.map(f.rename(columns={"lng": "lon"}), latitude="lat", longitude="lon", size=60)


def page_apps():
    st.title("📨 Suivi des candidatures")
    st.caption("Ajoute et suis tes candidatures auprès des entreprises.")
    with st.container(border=True):
        with st.form("add_app", clear_on_submit=True):
            st.subheader("➕ Ajouter une candidature")
            a, b = st.columns(2)
            company = a.text_input("Entreprise *", placeholder="Nom de l'entreprise")
            position = b.text_input("Poste *", "Stage")
            c, d = st.columns(2)
            date = c.date_input("Date", dt.date.today())
            status = d.selectbox("Statut", STATUSES)
            comment = st.text_area("Commentaire", placeholder="Ex : CV envoyé par e-mail…")
            if st.form_submit_button("💾 Enregistrer la candidature", type="primary") and company and position:
                ex("INSERT INTO applications(user_id,company,position,date,status,comment) VALUES(?,?,?,?,?,?)",
                   (UID, company, position, date.isoformat(), status, comment))
                st.rerun()

    apps = q("SELECT * FROM applications WHERE user_id=? ORDER BY id DESC", (UID,))
    cols = st.columns(len(STATUSES))
    for col, st_name in zip(cols, STATUSES):
        items = [a for a in apps if a["status"] == st_name]
        with col:
            st.markdown(f"**{st_name.upper()}** `{len(items)}`")
            for a in items:
                with st.container(border=True):
                    st.markdown(f"**{a['position']}**")
                    st.caption(f"{a['company']} · {a['date']}")
                    if a["comment"]:
                        st.caption(a["comment"])
                    new = st.selectbox("Statut", STATUSES, index=STATUSES.index(a["status"]),
                                       key=f"st{a['id']}", label_visibility="collapsed")
                    if new != a["status"]:
                        ex("UPDATE applications SET status=? WHERE id=?", (new, a["id"]))
                        st.rerun()
                    if st.button("🗑️", key=f"da{a['id']}"):
                        ex("DELETE FROM applications WHERE id=?", (a["id"],))
                        st.rerun()


def page_cvs():
    st.title("📎 Mes CV")
    cvs = q("SELECT id,name,filename,size,is_default,created FROM cvs WHERE user_id=? ORDER BY is_default DESC,id", (UID,))
    st.caption(f"Enregistre tes CV (PDF) et choisis celui à envoyer à chaque entreprise. — **{len(cvs)} / {MAX_CV} CV**")
    with st.container(border=True):
        with st.form("add_cv", clear_on_submit=True):
            st.subheader("➕ Ajouter un CV")
            a, b = st.columns(2)
            name = a.text_input("Nom du CV", placeholder="Ex. CV Intelligence Artificielle")
            file = b.file_uploader("Fichier PDF (5 Mo maximum)", type=["pdf"])
            default = st.checkbox("Utiliser comme CV par défaut")
            if st.form_submit_button("Enregistrer le CV", type="primary"):
                if len(cvs) >= MAX_CV:
                    st.error("Limite de 10 CV atteinte.")
                elif not name or not file:
                    st.error("Nom et fichier requis.")
                elif file.size > MAX_CV_BYTES:
                    st.error("Fichier trop volumineux (5 Mo max).")
                else:
                    if default or not cvs:
                        ex("UPDATE cvs SET is_default=0 WHERE user_id=?", (UID,))
                        default = True
                    ex("INSERT INTO cvs(user_id,name,filename,data,size,is_default,created) VALUES(?,?,?,?,?,?,?)",
                       (UID, name, file.name, file.getvalue(), file.size, int(default), dt.date.today().isoformat()))
                    st.rerun()

    cols = st.columns(3)
    for i, cv in enumerate(cvs):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"📕 **{cv['name']}**")
                if cv["is_default"]:
                    st.markdown("<span class='badge'>⭐ Par défaut</span>", unsafe_allow_html=True)
                st.caption(f"{cv['filename']} · {cv['size']//1024} Ko · ajouté le {cv['created']}")
                full = q("SELECT data FROM cvs WHERE id=?", (cv["id"],))[0]["data"]
                st.download_button("⬇️ Télécharger", full, cv["filename"], "application/pdf", key=f"dl{cv['id']}")
                new = st.text_input("Renommer", cv["name"], key=f"rn{cv['id']}", label_visibility="collapsed")
                b1, b2, b3 = st.columns(3)
                if b1.button("✏️", key=f"rb{cv['id']}", help="Renommer") and new:
                    ex("UPDATE cvs SET name=? WHERE id=?", (new, cv["id"]))
                    st.rerun()
                if not cv["is_default"] and b2.button("⭐", key=f"df{cv['id']}", help="Par défaut"):
                    ex("UPDATE cvs SET is_default=0 WHERE user_id=?", (UID,))
                    ex("UPDATE cvs SET is_default=1 WHERE id=?", (cv["id"],))
                    st.rerun()
                if b3.button("🗑️", key=f"dc{cv['id']}"):
                    ex("DELETE FROM cvs WHERE id=?", (cv["id"],))
                    st.rerun()


def page_profile():
    st.title("👤 Profil & Matching")
    st.caption("Renseigne tes compétences pour classer les entreprises selon ton profil.")
    p = get_profile()
    with st.form("profile"):
        skills = st.text_input("Compétences (séparées par des virgules)", p["skills"] or "",
                               placeholder="Python, Machine Learning, SQL, React…")
        sectors = st.multiselect("Secteurs visés", SECTORS, [s for s in (p["sectors"] or "").split(",") if s in SECTORS])
        keywords = st.text_input("Mots-clés d'entreprises", p["keywords"] or "", placeholder="IA, data, web, cloud…")
        level = st.selectbox("Niveau", ["Bac+2", "Bac+3", "Bac+4", "Bac+5"],
                             index=["Bac+2", "Bac+3", "Bac+4", "Bac+5"].index(p["level"]) if p["level"] in
                             ["Bac+2", "Bac+3", "Bac+4", "Bac+5"] else 2)
        if st.form_submit_button("💾 Enregistrer", type="primary"):
            ex("INSERT OR REPLACE INTO profiles(user_id,skills,sectors,keywords,level) VALUES(?,?,?,?,?)",
               (UID, skills, ",".join(sectors), keywords, level))
            st.success("Profil enregistré.")
            st.rerun()

    st.subheader("🎯 Meilleures correspondances")
    df = companies_df()
    if df.empty:
        st.info("Aucune entreprise à classer.")
        return
    prof = get_profile()
    pref = [s for s in (prof["sectors"] or "").split(",") if s]
    df = df.copy()
    df["match"] = df.apply(lambda r: min(100, r["score"] + (10 if r["sector"] in pref else 0)), axis=1)
    top = df.sort_values("match", ascending=False).head(20)
    st.dataframe(top[["name", "sector", "address", "email", "match"]].rename(
        columns={"name": "Entreprise", "sector": "Secteur", "address": "Adresse", "email": "E-mail", "match": "Match"}),
        use_container_width=True, hide_index=True,
        column_config={"Match": st.column_config.ProgressColumn("Match", min_value=0, max_value=100, format="%d")})


def page_stats():
    st.title("📊 Statistiques")
    df = companies_df()
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("🏢 Entreprises par secteur")
        if df.empty:
            st.caption("Pas encore de données.")
        else:
            st.bar_chart(df["sector"].value_counts())
    with c2.container(border=True):
        st.subheader("📈 Distribution des scores")
        if df.empty:
            st.caption("Pas encore de données.")
        else:
            st.bar_chart(pd.cut(df["score"], [-1, 20, 40, 60, 80, 100],
                                labels=["0-20", "21-40", "41-60", "61-80", "81-100"]).value_counts().sort_index())
    c3, c4 = st.columns(2)
    with c3.container(border=True):
        st.subheader("📋 Offres par type de contrat")
        offers = pd.DataFrame(q("SELECT contract FROM offers WHERE user_id=?", (UID,)))
        if offers.empty:
            st.caption("Pas encore de données.")
        else:
            st.bar_chart(offers["contract"].value_counts())
    with c4.container(border=True):
        st.subheader("🌐 Présence numérique des entreprises")
        if df.empty:
            st.caption("Pas encore de données.")
        else:
            has = lambda col: int(df[col].fillna("").ne("").sum())
            st.bar_chart(pd.Series({"Avec e-mail": has("email"), "Sans e-mail": len(df) - has("email"),
                                    "Avec site web": has("website"), "Sans site web": len(df) - has("website")}))
    with st.container(border=True):
        st.subheader("📨 Candidatures par statut")
        apps = pd.DataFrame(q("SELECT status FROM applications WHERE user_id=?", (UID,)))
        if apps.empty:
            st.caption("Pas encore de données.")
        else:
            st.bar_chart(apps["status"].value_counts().reindex(STATUSES).fillna(0))


COLMAP = {
    "name": ["name", "nom", "entreprise", "company", "title"],
    "address": ["address", "adresse"],
    "phone": ["phone", "telephone", "téléphone", "tel"],
    "email": ["email", "e-mail", "mail"],
    "website": ["website", "site", "site web", "url"],
    "maps": ["maps", "google maps", "maps_url"],
    "rating": ["rating", "note"],
    "sector": ["sector", "secteur"],
    "lat": ["lat", "latitude"],
    "lng": ["lng", "lon", "longitude"],
}


def import_companies(df):
    df.columns = [str(c).strip().lower() for c in df.columns]
    found = {k: next((c for c in v if c in df.columns), None) for k, v in COLMAP.items()}
    if not found["name"]:
        return 0, "Colonne « nom » introuvable."
    n = 0
    for _, r in df.iterrows():
        g = lambda k: (None if not found[k] or pd.isna(r[found[k]]) else r[found[k]])
        if not g("name"):
            continue
        sec = g("sector") if g("sector") in SECTORS else "Informatique"
        ex("INSERT INTO companies(user_id,name,address,sector,phone,email,website,maps,rating,lat,lng) "
           "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
           (UID, str(g("name")), g("address"), sec, g("phone"), g("email"), g("website"), g("maps"),
            float(g("rating")) if g("rating") else None, float(g("lat")) if g("lat") else None,
            float(g("lng")) if g("lng") else None))
        n += 1
    return n, None


def google_places(api_key, query, max_results=20):
    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={"X-Goog-Api-Key": api_key, "Content-Type": "application/json",
                 "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
                                     "places.websiteUri,places.rating,places.location,places.googleMapsUri"},
        json={"textQuery": query, "pageSize": max_results}, timeout=30)
    r.raise_for_status()
    return r.json().get("places", [])


def page_import():
    st.title("🗄️ Collecte & Import")
    t1, t2, t3 = st.tabs(["📍 Google Places", "📥 Import Excel/CSV", "⚠️ Données"])
    with t1:
        st.caption("Récupère automatiquement des entreprises via l'API Google Places (clé requise).")
        key = st.text_input("Clé API Google Places", type="password", value=os.getenv("GOOGLE_PLACES_API_KEY", ""))
        query = st.text_input("Recherche", "entreprise informatique intelligence artificielle Marrakech")
        sector = st.selectbox("Secteur à attribuer", SECTORS)
        if st.button("Lancer la collecte", type="primary"):
            if not key:
                st.error("Clé API requise.")
            else:
                try:
                    places = google_places(key, query)
                    existing = {c["name"].lower() for c in q("SELECT name FROM companies WHERE user_id=?", (UID,))}
                    n = 0
                    for p in places:
                        nm = p.get("displayName", {}).get("text", "")
                        if not nm or nm.lower() in existing:
                            continue
                        loc = p.get("location", {})
                        ex("INSERT INTO companies(user_id,name,address,sector,phone,website,maps,rating,lat,lng) "
                           "VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (UID, nm, p.get("formattedAddress"), sector, p.get("nationalPhoneNumber"),
                            p.get("websiteUri"), p.get("googleMapsUri"), p.get("rating"),
                            loc.get("latitude"), loc.get("longitude")))
                        n += 1
                    st.success(f"{n} entreprise(s) ajoutée(s).")
                except Exception as e:
                    st.error(f"Erreur API : {e}")
    with t2:
        st.caption("Colonnes reconnues : nom, adresse, téléphone, email, site, note, secteur, lat, lng.")
        kind = st.radio("Type de données", ["Entreprises", "Offres"], horizontal=True)
        f = st.file_uploader("Fichier", type=["csv", "xlsx"])
        if f is not None:
            df = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
            st.dataframe(df.head(10), use_container_width=True)
            if st.button("Importer", type="primary"):
                if kind == "Entreprises":
                    n, err = import_companies(df)
                    st.error(err) if err else st.success(f"{n} entreprise(s) importée(s).")
                else:
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    tc = next((c for c in ["title", "titre", "poste"] if c in df.columns), None)
                    if not tc:
                        st.error("Colonne « titre » introuvable.")
                    else:
                        n = 0
                        for _, r in df.iterrows():
                            ex("INSERT INTO offers(user_id,title,company,intern_type,contract,link,created) "
                               "VALUES(?,?,?,?,?,?,?)",
                               (UID, str(r[tc]), str(r.get("company", r.get("entreprise", "")) or ""),
                                INTERN_TYPES[0], "Stage", str(r.get("link", r.get("lien", "")) or ""),
                                dt.date.today().isoformat()))
                            n += 1
                        st.success(f"{n} offre(s) importée(s).")
    with t3:
        df = companies_df()
        if not df.empty:
            st.download_button("⬇️ Exporter les entreprises (CSV)", df.to_csv(index=False).encode("utf-8"),
                               "entreprises.csv", "text/csv")
        if st.button("🗑️ Supprimer toutes mes entreprises"):
            ex("DELETE FROM companies WHERE user_id=?", (UID,))
            st.rerun()


{
    "home": page_home, "companies": page_companies, "offers": page_offers, "map": page_map,
    "apps": page_apps, "cvs": page_cvs, "profile": page_profile, "stats": page_stats, "import": page_import,
}[PAGES[page]]()
