"""Career Finder Marrakech - interface Streamlit (remplace FastAPI + frontend/static)."""
import io
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="Career Finder Marrakech", page_icon="🎯", layout="wide")

# --- Secrets Streamlit -> variables d'environnement (AVANT d'importer backend.security) ---
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, (str, int, float, bool)):
            os.environ.setdefault(_k, str(_v))
except Exception:
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from backend.database import (  # noqa: E402
    CONTRATS, MAX_CVS_PER_USER, TYPES_STAGE, add_cv, count_emails_since, create_user,
    delete_cv, delete_offer, delete_opportunity, get_connection, get_cv, get_opportunities_for_user,
    get_offer_owner, get_opportunity, get_opportunity_owner, get_profile, get_user, init_db,
    insert_manual_opportunity, insert_offer, last_email_to, list_cvs, list_offers, log_email,
    toggle_favorite, update_cv, update_opportunity_fields, upsert_offers, upsert_opportunities,
    upsert_profile,
)
from backend.mailer import (  # noqa: E402
    MAX_CV_BYTES, MailError, build_cv_message, is_valid_email, safe_filename, send_message,
    smtp_configured,
)
from backend.security import LoginRateLimiter, hash_password, verify_password  # noqa: E402
from pipeline.cleaner import clean_and_score_places  # noqa: E402
from pipeline.excel_importer import clean_excel_opportunities  # noqa: E402
from pipeline.google_places import fetch_it_companies_google  # noqa: E402
from pipeline.sectors import SECTEURS  # noqa: E402

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LENGTH = 8
STATUTS = ["À contacter", "Envoyée", "Entretien", "Offre reçue", "Refusée"]
MAX_CV_PER_HOUR = int(os.getenv("MAX_CV_PER_HOUR", "10"))
MAX_CV_PER_DAY = int(os.getenv("MAX_CV_PER_DAY", "30"))
CV_RESEND_DELAY_DAYS = 7
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")


@st.cache_resource
def _setup():
    init_db()
    return LoginRateLimiter(max_attempts=5, window=300)


limiter = _setup()


# ---------------------------------------------------------------- utilitaires
def user_applications(username: str) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM applications WHERE user=? ORDER BY date_ajout DESC", conn, params=(username,))
    conn.close()
    return df


def compute_match_score(profile_skills, mots_cles, score_opportunite) -> float:
    a = {s.strip().lower() for s in (profile_skills or "").split(",") if s.strip()}
    b = {s.strip().lower() for s in (mots_cles or "").split(",") if s.strip()}
    kw = round(100 * len(a & b) / len(a), 1) if a and b else 0.0
    return min(round(0.6 * kw + 0.4 * (score_opportunite or 0), 1), 100.0)


def run_sql(sql: str, params=()):
    conn = get_connection()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def df_to_xlsx(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, d in sheets.items():
            d.to_excel(w, sheet_name=name[:31], index=False)
    return buf.getvalue()


# ---------------------------------------------------------------- authentification
def login_screen():
    st.title("🎯 Career Finder")
    st.caption("Marrakech · IA & IT")
    tab_in, tab_up = st.tabs(["Connexion", "Inscription"])

    with tab_in:
        with st.form("login"):
            u = st.text_input("Nom d'utilisateur").strip()
            p = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter", type="primary")
        if ok:
            key = u.lower()
            if limiter.is_blocked(key):
                st.error("Trop de tentatives. Réessaie dans quelques minutes.")
            else:
                user = get_user(u)
                stored = user["password_hash"] if user else "scrypt$AAAA$AAAA"
                if not verify_password(p, stored) or user is None:
                    limiter.register_failure(key)
                    st.error("Identifiants incorrects.")
                else:
                    limiter.reset(key)
                    st.session_state.user = {"username": user["username"], "is_admin": bool(user["is_admin"])}
                    st.rerun()

    with tab_up:
        with st.form("register"):
            u = st.text_input("Nom d'utilisateur (3-32 caractères)", key="ru").strip()
            p = st.text_input("Mot de passe (8 caractères min.)", type="password", key="rp")
            ok = st.form_submit_button("Créer mon compte")
        if ok:
            if not USERNAME_RE.match(u):
                st.error("Nom d'utilisateur : 3 à 32 caractères (lettres, chiffres, . _ -).")
            elif len(p) < MIN_PASSWORD_LENGTH:
                st.error(f"Mot de passe : {MIN_PASSWORD_LENGTH} caractères minimum.")
            else:
                try:
                    user = create_user(u, hash_password(p))
                    st.session_state.user = {"username": user["username"], "is_admin": user["is_admin"]}
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


if "user" not in st.session_state:
    login_screen()
    st.stop()

ME = st.session_state.user["username"]
IS_ADMIN = st.session_state.user["is_admin"]

# ---------------------------------------------------------------- navigation
PAGES = ["🏠 Accueil", "🏢 Entreprises", "📄 Offres", "🗺️ Carte", "📨 Candidatures",
         "📎 Mes CV", "👤 Profil & Matching", "📊 Statistiques", "🗄️ Collecte & Import"]

with st.sidebar:
    st.header("🎯 Career Finder")
    st.caption("Marrakech · IA & IT")
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.divider()
    st.write(f"**{ME}**" + (" · admin" if IS_ADMIN else ""))
    if st.button("Se déconnecter", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------------- Accueil
def page_accueil():
    st.title(f"Bonjour {ME} 👋")
    st.caption("Voici où en est ta recherche de stage à Marrakech.")
    opps = get_opportunities_for_user(ME)
    apps = user_applications(ME)
    offers = list_offers()
    prof = get_profile(ME)
    n = len(opps)
    n_mail = int((opps["email"].fillna("").str.strip() != "").sum()) if n else 0
    n_cv_sent = int(opps["cv_envoye_le"].notna().sum()) if n else 0

    steps = [
        ("Enregistre ton CV (PDF)", len(list_cvs(ME)) > 0),
        ("Renseigne tes compétences", bool((prof.get("skills") or "").strip())),
        ("Récupère des entreprises (Google Places ou Excel)", n > 0),
        ("Ajoute des e-mails de contact", n_mail > 0),
        ("Envoie ton premier CV", n_cv_sent > 0),
    ]
    done = sum(1 for _, ok in steps if ok)
    st.subheader(f"🚀 Pour bien démarrer · {done}/5")
    st.progress(done / 5)
    for label, ok in steps:
        st.write(("✅ ~~" + label + "~~") if ok else ("⬜ " + label))

    c = st.columns(5)
    c[0].metric("Entreprises", n)
    c[1].metric("Offres", len(offers))
    c[2].metric("Avec e-mail", n_mail)
    c[3].metric("CV envoyés", n_cv_sent)
    c[4].metric("Candidatures", len(apps))


# ---------------------------------------------------------------- Envoi de CV
def send_cv_ui(opp: dict):
    st.markdown("##### ✉️ Envoyer mon CV")
    if not smtp_configured():
        st.info("L'envoi d'e-mails n'est pas configuré (secrets SMTP_HOST et SMTP_FROM manquants).")
        return
    to_email = (opp.get("email") or "").strip()
    if not is_valid_email(to_email):
        st.warning("Cette entreprise n'a pas d'adresse e-mail valide. Ajoute-la ci-dessus.")
        return
    cvs = list_cvs(ME)
    if not cvs:
        st.warning("Enregistre d'abord un CV dans « Mes CV ».")
        return
    with st.form(f"sendcv_{opp['id']}"):
        cv_choice = st.selectbox("CV à envoyer", cvs, format_func=lambda c: c["label"] + (" (défaut)" if c["is_default"] else ""))
        subject = st.text_input("Objet", f"Candidature spontanée pour un stage - {opp['nom']}")
        message = st.text_area("Message", f"Bonjour,\n\nJe vous adresse ma candidature spontanée pour un stage au sein de {opp['nom']}.\nVous trouverez mon CV en pièce jointe.\n\nCordialement,\n{ME}", height=180)
        reply_to = st.text_input("Ton e-mail (réponse)")
        force = st.checkbox("Renvoyer même si déjà envoyé récemment")
        go = st.form_submit_button("Envoyer", type="primary")
    if not go:
        return
    if not subject.strip() or not message.strip():
        st.error("L'objet et le message sont obligatoires.")
        return
    if reply_to.strip() and not is_valid_email(reply_to.strip()):
        st.error("Ton adresse de réponse est invalide.")
        return
    if count_emails_since(ME, 1) >= MAX_CV_PER_HOUR or count_emails_since(ME, 24) >= MAX_CV_PER_DAY:
        st.error("Limite d'envois atteinte. Réessaie plus tard.")
        return
    prev = last_email_to(ME, opp["id"])
    if prev and not force:
        sent_at = datetime.strptime(prev, "%Y-%m-%d %H:%M:%S")
        if datetime.now(timezone.utc).replace(tzinfo=None) - sent_at < timedelta(days=CV_RESEND_DELAY_DAYS):
            st.error(f"Tu as déjà envoyé ton CV le {sent_at:%d/%m/%Y}. Coche « Renvoyer » pour confirmer.")
            return
    saved = get_cv(ME, cv_choice["id"], with_content=True)
    msg = build_cv_message(to_email=to_email, subject=subject.strip(), body=message.strip(),
                           cv_bytes=saved["content"], cv_filename=saved["filename"], reply_to=reply_to.strip())
    try:
        send_message(msg)
    except MailError as e:
        st.error(str(e))
        return
    log_email(ME, opp["id"], to_email, subject.strip())
    run_sql("""INSERT INTO applications (user, company, poste, statut, date_candidature, remarque, opportunity_id)
               VALUES (?, ?, 'Candidature spontanée', 'Envoyée', ?, ?, ?)""",
            (ME, opp["nom"], date.today().isoformat(), f"CV « {saved['label']} » envoyé à {to_email}", opp["id"]))
    st.success(f"CV envoyé à {to_email} ✅")


# ---------------------------------------------------------------- Entreprises
def page_entreprises():
    st.title("🏢 Entreprises")
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    q = c1.text_input("Recherche (nom, mots-clés)")
    secteurs = c2.multiselect("Secteur", SECTEURS)
    min_score = c3.number_input("Score min", 0, 100, 0)
    fav_only = c4.checkbox("Favoris")
    df = get_opportunities_for_user(ME, int(min_score), fav_only)
    if q:
        mask = df["nom"].fillna("").str.contains(q, case=False) | df["mots_cles"].fillna("").str.contains(q, case=False)
        df = df[mask]
    if secteurs:
        df = df[df["secteur"].isin(secteurs)]

    st.caption(f"{len(df)} entreprise(s)")
    show = df[["nom", "secteur", "score_opportunite", "note", "email", "telephone", "site_web", "favori", "cv_envoye_le"]]
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export CSV", df.to_csv(index=False).encode("utf-8-sig"), "opportunites.csv", "text/csv")

    if df.empty:
        return
    st.divider()
    rows = df.to_dict("records")
    opp = st.selectbox("Choisir une entreprise", rows, format_func=lambda r: f"{r['nom']} ({r['score_opportunite']})")
    st.subheader(opp["nom"])
    st.write(f"📍 {opp.get('adresse') or '—'}  ·  Secteur : {opp.get('secteur')}  ·  Score : {opp.get('score_opportunite')}")
    if opp.get("google_maps_url"):
        st.link_button("Ouvrir dans Google Maps", opp["google_maps_url"])

    cols = st.columns(2)
    if cols[0].button("★ Retirer des favoris" if opp["favori"] else "☆ Ajouter aux favoris", key=f"fav{opp['id']}"):
        toggle_favorite(ME, opp["id"])
        st.rerun()
    can_edit = IS_ADMIN or opp.get("added_by") == ME
    if can_edit and cols[1].button("🗑️ Supprimer", key=f"del{opp['id']}"):
        delete_opportunity(opp["id"])
        st.rerun()

    if can_edit:
        with st.form(f"edit{opp['id']}"):
            e = st.text_input("E-mail", opp.get("email") or "")
            t = st.text_input("Téléphone", opp.get("telephone") or "")
            w = st.text_input("Site web", opp.get("site_web") or "")
            s = st.selectbox("Secteur", SECTEURS, index=SECTEURS.index(opp["secteur"]) if opp.get("secteur") in SECTEURS else 0)
            if st.form_submit_button("Enregistrer"):
                e = e.strip().lower()
                if e and not is_valid_email(e):
                    st.error("Adresse e-mail invalide")
                else:
                    update_opportunity_fields(opp["id"], {"email": e, "telephone": t, "site_web": w, "secteur": s})
                    st.success("Enregistré")
                    st.rerun()
    send_cv_ui(get_opportunity(opp["id"]))

    with st.expander("➕ Ajouter une entreprise manuellement"):
        with st.form("manual_opp"):
            nom = st.text_input("Nom *")
            email = st.text_input("E-mail")
            sect = st.selectbox("Secteur", SECTEURS, key="msect")
            adr = st.text_input("Adresse")
            tel = st.text_input("Téléphone")
            site = st.text_input("Site web")
            if st.form_submit_button("Ajouter"):
                if not nom.strip():
                    st.error("Le nom est obligatoire")
                elif email.strip() and not is_valid_email(email.strip()):
                    st.error("E-mail invalide")
                else:
                    try:
                        insert_manual_opportunity({"nom": nom.strip(), "email": email.strip().lower(), "secteur": sect,
                                                   "adresse": adr, "telephone": tel, "site_web": site}, added_by=ME)
                        st.success("Entreprise ajoutée")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))


# ---------------------------------------------------------------- Offres
def page_offres():
    st.title("📄 Offres de stage / d'emploi")
    c1, c2, c3 = st.columns(3)
    q = c1.text_input("Recherche")
    contrat = c2.selectbox("Contrat", [""] + CONTRATS)
    tstage = c3.selectbox("Type de stage", [""] + TYPES_STAGE)
    df = list_offers(q.strip(), contrat, tstage)
    st.caption(f"{len(df)} offre(s)")
    if not df.empty:
        st.dataframe(df[["titre", "entreprise", "contrat", "type_stage", "ville", "date_publication", "url"]],
                     use_container_width=True, hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("Lien")})
        offer = st.selectbox("Supprimer une offre", df.to_dict("records"),
                             format_func=lambda r: f"{r['titre']} - {r['entreprise']}")
        if st.button("🗑️ Supprimer cette offre"):
            exists, owner = get_offer_owner(offer["id"])
            if IS_ADMIN or owner == ME:
                delete_offer(offer["id"])
                st.rerun()
            else:
                st.error("Tu ne peux supprimer que les offres que tu as ajoutées.")

    with st.expander("➕ Ajouter une offre"):
        with st.form("new_offer"):
            titre = st.text_input("Titre *")
            ent = st.text_input("Entreprise")
            ct = st.selectbox("Contrat", CONTRATS, key="oc")
            ts = st.selectbox("Type de stage", TYPES_STAGE, key="ot")
            ville = st.text_input("Ville", "Marrakech")
            pub = st.date_input("Date de publication", date.today())
            url = st.text_input("Lien (http/https)")
            desc = st.text_area("Description")
            if st.form_submit_button("Ajouter"):
                if url.strip() and not re.match(r"^https?://", url.strip(), re.I):
                    st.error("Le lien doit commencer par http:// ou https://")
                else:
                    try:
                        insert_offer({"titre": titre, "entreprise": ent, "contrat": ct, "type_stage": ts, "ville": ville,
                                      "date_publication": pub.isoformat(), "url": url, "description": desc}, added_by=ME)
                        st.success("Offre ajoutée")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

    with st.expander("📥 Importer des offres (CSV / Excel)"):
        up = st.file_uploader("Fichier", type=["csv", "xlsx"], key="offers_up")
        if up and st.button("Importer"):
            try:
                raw = pd.read_csv(up, sep=None, engine="python", encoding="utf-8-sig") if up.name.lower().endswith(".csv") else pd.read_excel(up)
            except Exception as e:
                st.error(f"Fichier illisible : {e}")
                return
            lower = {str(c).strip().lower(): c for c in raw.columns}
            pick = lambda *names: next((lower[n] for n in names if n in lower), None)  # noqa: E731
            ctitre = pick("titre", "title", "intitulé", "intitule", "poste")
            if ctitre is None:
                st.error("Colonne du titre introuvable (titre, intitulé ou poste).")
                return
            m = {"entreprise": pick("entreprise", "company", "société", "societe"), "contrat": pick("contrat", "contract"),
                 "type_stage": pick("type_stage", "type de stage"), "ville": pick("ville", "city"),
                 "date_publication": pick("date_publication", "date"), "url": pick("url", "lien", "link"),
                 "description": pick("description")}
            rows = []
            for _, r in raw.iterrows():
                d = {"titre": str(r[ctitre]).strip(), "source": "Import fichier"}
                for k, c in m.items():
                    d[k] = "" if c is None or pd.isna(r[c]) else str(r[c]).strip()
                rows.append(d)
            rep = upsert_offers(rows, added_by=ME)
            st.success(f"{rep['ajoutees']} ajoutée(s), {rep['ignorees']} ignorée(s)")


# ---------------------------------------------------------------- Carte
def page_carte():
    st.title("🗺️ Carte")
    df = get_opportunities_for_user(ME)
    geo = df.dropna(subset=["latitude", "longitude"])[["latitude", "longitude"]]
    if geo.empty:
        st.info("Aucune entreprise géolocalisée.")
    else:
        st.map(geo)
        st.caption(f"{len(geo)} entreprise(s) affichée(s)")


# ---------------------------------------------------------------- Candidatures
def page_candidatures():
    st.title("📨 Candidatures")
    apps = user_applications(ME)
    if apps.empty:
        st.info("Aucune candidature pour le moment.")
    else:
        st.dataframe(apps[["id", "company", "poste", "statut", "date_candidature", "remarque"]],
                     use_container_width=True, hide_index=True)
        st.subheader("Modifier / supprimer")
        a = st.selectbox("Candidature", apps.to_dict("records"), format_func=lambda r: f"#{r['id']} · {r['company']} · {r['poste']}")
        c1, c2 = st.columns(2)
        new_st = c1.selectbox("Statut", STATUTS, index=STATUTS.index(a["statut"]) if a["statut"] in STATUTS else 0)
        rem = c2.text_input("Remarque", a.get("remarque") or "")
        b1, b2 = st.columns(2)
        if b1.button("Enregistrer", type="primary"):
            run_sql("UPDATE applications SET statut=?, remarque=? WHERE id=? AND user=?", (new_st, rem, a["id"], ME))
            st.rerun()
        if b2.button("🗑️ Supprimer"):
            run_sql("DELETE FROM applications WHERE id=? AND user=?", (a["id"], ME))
            st.rerun()

    with st.expander("➕ Nouvelle candidature"):
        with st.form("new_app"):
            company = st.text_input("Entreprise *")
            poste = st.text_input("Poste *")
            statut = st.selectbox("Statut", STATUTS)
            d = st.date_input("Date", date.today())
            rem = st.text_input("Remarque")
            if st.form_submit_button("Enregistrer"):
                if company.strip() and poste.strip():
                    run_sql("""INSERT INTO applications (user, company, poste, statut, date_candidature, remarque)
                               VALUES (?, ?, ?, ?, ?, ?)""", (ME, company.strip(), poste.strip(), statut, d.isoformat(), rem))
                    st.rerun()
                else:
                    st.error("Entreprise et poste obligatoires")


# ---------------------------------------------------------------- Mes CV
def page_cv():
    st.title("📎 Mes CV")
    cvs = list_cvs(ME)
    st.caption(f"{len(cvs)}/{MAX_CVS_PER_USER} CV enregistrés")
    for cv in cvs:
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        c1.write(f"**{cv['label']}** {'⭐ (défaut)' if cv['is_default'] else ''}  \n{cv['filename']} · {cv['size_bytes'] // 1024} Ko")
        full = get_cv(ME, cv["id"], with_content=True)
        c2.download_button("Télécharger", full["content"], safe_filename(cv["filename"]), "application/pdf", key=f"dl{cv['id']}")
        if not cv["is_default"] and c3.button("Par défaut", key=f"def{cv['id']}"):
            update_cv(ME, cv["id"], make_default=True)
            st.rerun()
        if c4.button("🗑️", key=f"rm{cv['id']}"):
            delete_cv(ME, cv["id"])
            st.rerun()
    st.divider()
    with st.form("add_cv", clear_on_submit=True):
        label = st.text_input("Nom du CV (ex. « CV IA »)", max_chars=60)
        f = st.file_uploader("Fichier PDF (5 Mo max)", type=["pdf"])
        make_def = st.checkbox("Définir comme CV par défaut")
        if st.form_submit_button("Enregistrer", type="primary"):
            data = f.getvalue() if f else b""
            if not label.strip():
                st.error("Donne un nom à ce CV.")
            elif not data.startswith(b"%PDF"):
                st.error("Le CV doit être un PDF valide.")
            elif len(data) > MAX_CV_BYTES:
                st.error("CV trop volumineux (5 Mo maximum).")
            else:
                try:
                    add_cv(ME, re.sub(r"\s+", " ", label).strip(), safe_filename(f.name), data, make_def)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


# ---------------------------------------------------------------- Profil & Matching
def page_profil():
    st.title("👤 Profil & Matching")
    prof = get_profile(ME)
    with st.form("profile"):
        skills = st.text_input("Compétences (séparées par des virgules)", prof.get("skills") or "",
                               placeholder="python, machine learning, sql")
        exp = st.number_input("Années d'expérience", 0.0, 50.0, float(prof.get("experience_years") or 0.0), 0.5)
        bio = st.text_area("Bio", prof.get("bio") or "")
        if st.form_submit_button("Enregistrer", type="primary"):
            upsert_profile({"user": ME, "skills": skills, "experience_years": exp, "bio": bio,
                            "cv_filename": prof.get("cv_filename", "")})
            st.success("Profil enregistré")
            st.rerun()

    st.subheader("🎯 Entreprises qui te correspondent")
    df = get_opportunities_for_user(ME)
    if df.empty:
        st.info("Aucune entreprise dans la base.")
        return
    df["match_score"] = df.apply(lambda r: compute_match_score(prof.get("skills", ""), r.get("mots_cles", ""), r.get("score_opportunite", 0)), axis=1)
    mn = st.slider("Score de matching minimum", 0, 100, 0)
    df = df[df["match_score"] >= mn].sort_values("match_score", ascending=False)
    st.dataframe(df[["nom", "secteur", "match_score", "score_opportunite", "mots_cles", "email"]],
                 use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- Statistiques
def page_stats():
    st.title("📊 Statistiques")
    df = get_opportunities_for_user(ME)
    apps = user_applications(ME)
    offers = list_offers()
    c = st.columns(4)
    c[0].metric("Entreprises", len(df))
    c[1].metric("Score moyen", round(df["score_opportunite"].mean(), 1) if len(df) else 0)
    c[2].metric("Favoris", int(df["favori"].sum()) if len(df) else 0)
    c[3].metric("Candidatures", len(apps))
    if len(df):
        st.subheader("Entreprises par secteur")
        st.bar_chart(df["secteur"].value_counts())
    if not apps.empty:
        st.subheader("Candidatures par statut")
        st.bar_chart(apps["statut"].value_counts())
    if not offers.empty:
        a, b = st.columns(2)
        a.subheader("Offres par contrat")
        a.bar_chart(offers["contrat"].value_counts())
        b.subheader("Offres par type de stage")
        b.bar_chart(offers["type_stage"].value_counts())
    if len(df):
        has_mail = df["email"].fillna("").str.strip() != ""
        st.subheader("Présence numérique")
        st.bar_chart(pd.Series({"Avec e-mail": int(has_mail.sum()), "Sans e-mail": int((~has_mail).sum())}))
    opps_all = get_opportunities_for_user(ME)
    st.download_button("⬇️ Export Excel complet",
                       df_to_xlsx({"Opportunites": opps_all, "Candidatures": apps}),
                       "resultats_analyse_et_suivi.xlsx")


# ---------------------------------------------------------------- Collecte & Import
def page_collecte():
    st.title("🗄️ Collecte & Import")
    st.subheader("Google Places")
    key = st.text_input("Clé Google Maps (optionnelle si définie dans les secrets)", type="password")
    c1, c2, c3 = st.columns(3)
    query = c1.text_input("Requête", "Intelligence Artificielle OR Informatique")
    location = c2.text_input("Position (lat,lng)", "31.6295,-7.9811")
    radius = c3.number_input("Rayon (m)", 500, 50000, 10000, 500)
    if st.button("Lancer la collecte", type="primary"):
        k = key or GOOGLE_API_KEY
        if not k:
            st.error("Aucune clé Google Maps fournie.")
        else:
            with st.spinner("Collecte en cours..."):
                try:
                    raw = fetch_it_companies_google(k, location=location, radius=int(radius), query=query)
                    if not raw:
                        st.warning("Aucun résultat renvoyé par Google Places.")
                    else:
                        n = upsert_opportunities(clean_and_score_places(raw), added_by=ME)
                        st.success(f"{n} entreprise(s) enregistrée(s)")
                except Exception as e:
                    st.error(f"Erreur de collecte : {e}")

    st.divider()
    st.subheader("Import Excel d'entreprises")
    f = st.file_uploader("Fichier Excel", type=["xlsx", "xls"], key="excel_up")
    only_it = st.checkbox("Garder seulement IT / IA", True)
    if f and st.button("Nettoyer et importer"):
        try:
            df, report, _ = clean_excel_opportunities(io.BytesIO(f.getvalue()), only_it_ai=only_it)
            report["opportunites_ajoutees"] = upsert_opportunities(df, added_by=ME)
            st.success("Import terminé")
            st.json(report)
        except Exception as e:
            st.error(f"Erreur de lecture du fichier Excel : {e}")


{
    "🏠 Accueil": page_accueil, "🏢 Entreprises": page_entreprises, "📄 Offres": page_offres,
    "🗺️ Carte": page_carte, "📨 Candidatures": page_candidatures, "📎 Mes CV": page_cv,
    "👤 Profil & Matching": page_profil, "📊 Statistiques": page_stats, "🗄️ Collecte & Import": page_collecte,
}[page]()
