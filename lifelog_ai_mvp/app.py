import os
import json
import sqlite3
import hashlib
import hmac
import secrets
from datetime import date, datetime, time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()
DB_PATH = Path("lifelog.db")
ASSET_ROOT = Path("lifelog_assets")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_ASSETS = {
    "png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "docx",
}

st.set_page_config(page_title="LifeLog AI", page_icon="📔", layout="wide")

# ---------- Validated day understanding ----------
class StructuredDay(BaseModel):
    date: str = Field(default_factory=lambda: date.today().isoformat())
    summary: str = ""
    events: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    mood: str = ""
    completed_tasks: list[str] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    future_plans: list[str] = Field(default_factory=list)
    important_moments: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)


class StructuredJournal(BaseModel):
    title: str = "Daily journal"
    opening: str = ""
    events: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    feelings: list[str] = Field(default_factory=list)
    reflection: str = ""
    gratitude: list[str] = Field(default_factory=list)
    closing: str = ""


class StructuredVlog(BaseModel):
    title: str = "A day in my life"
    hook: str = ""
    scenes: list[str] = Field(default_factory=list)
    voiceover: list[str] = Field(default_factory=list)
    b_roll: list[str] = Field(default_factory=list)
    closing: str = ""


def extract_pending_tasks(note):
    """Use lightweight NLP heuristics when no LLM is configured."""
    task_markers = (
        "need to ", "have to ", "must ", "should ", "remember to ",
        "plan to ", "going to ", "todo:", "to-do:",
    )
    completed_markers = ("finished ", "completed ", "did ", "already ")
    candidates = []
    for sentence in __import__("re").split(r"(?<=[.!?])\s+|[;\n]+", note):
        clean_sentence = " ".join(sentence.split()).strip(" -")
        lowered = clean_sentence.lower()
        if not clean_sentence or any(marker in lowered for marker in completed_markers):
            continue
        for marker in task_markers:
            marker_index = lowered.find(marker)
            if marker_index >= 0:
                task = clean_sentence[marker_index + len(marker):].strip(" .,!?:")
                if task and task not in candidates:
                    candidates.append(task[0].upper() + task[1:])
                break
    return candidates


def extract_completed_actions(note):
    """Extract explicitly completed actions for demo-mode segregation."""
    completed_markers = ("finished ", "completed ", "did ", "already ")
    actions = []
    for sentence in __import__("re").split(r"(?<=[.!?])\s+|[;\n]+", note):
        clean_sentence = " ".join(sentence.split()).strip(" -")
        lowered = clean_sentence.lower()
        for marker in completed_markers:
            marker_index = lowered.find(marker)
            if marker_index >= 0:
                action = clean_sentence[marker_index + len(marker):].strip(" .,!?:")
                if action and action not in actions:
                    actions.append(action[0].upper() + action[1:])
                break
    return actions


def normalize_structured_outputs(result, note):
    """Validate journals, vlogs, and task segregation returned by the model."""
    fallback_tasks = extract_pending_tasks(note)
    result.setdefault("structured_journal", {})
    result.setdefault("structured_vlog", {})
    try:
        journal = StructuredJournal.model_validate(result["structured_journal"])
    except ValidationError:
        journal = StructuredJournal(
            opening=result.get("journal", ""),
            reflection=result.get("reflection", ""),
            closing="End of today's record.",
        )
    try:
        vlog = StructuredVlog.model_validate(result["structured_vlog"])
    except ValidationError:
        vlog = StructuredVlog(
            hook="A short look at today's memory.",
            scenes=["Opening shot of the day", "Main moment from the note", "Closing reflection"],
            voiceover=[result.get("vlog_script", "")],
            closing="That is one moment I want to remember.",
        )
    result["structured_journal"] = journal.model_dump()
    result["structured_vlog"] = vlog.model_dump()
    structured = result.get("structured_day", {})
    if not isinstance(structured, dict):
        structured = {}
    llm_pending = structured.get("pending_tasks", result.get("tasks", []))
    pending_tasks = [
        str(task).strip() for task in llm_pending
        if str(task).strip()
    ]
    if not pending_tasks and fallback_tasks:
        pending_tasks = fallback_tasks
    structured["pending_tasks"] = pending_tasks
    if not structured.get("completed_tasks"):
        structured["completed_tasks"] = extract_completed_actions(note)
    result["structured_day"] = structured
    result["tasks"] = pending_tasks
    return result


def validate_day_result(result, note):
    """Validate and normalize the structured part of a generated result."""
    structured = result.get("structured_day", {})
    if not isinstance(structured, dict):
        structured = {}
    structured.setdefault("date", date.today().isoformat())
    structured.setdefault("summary", result.get("journal", "")[:240])
    structured.setdefault("pending_tasks", result.get("tasks", []))
    try:
        validated = StructuredDay.model_validate(structured)
    except ValidationError:
        validated = StructuredDay(
            date=date.today().isoformat(),
            summary=" ".join(note.split())[:240],
            pending_tasks=[str(task) for task in result.get("tasks", []) if str(task).strip()],
        )
    normalized = validated.model_dump()
    result["structured_day"] = normalized
    result["tasks"] = normalized["pending_tasks"]
    return normalize_structured_outputs(result, note)


# ---------- Storage ----------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                created_at TEXT NOT NULL,
                source_text TEXT NOT NULL,
                mode TEXT NOT NULL,
                result_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL,
                writing_style TEXT NOT NULL DEFAULT 'Reflective',
                journal_tone TEXT NOT NULL DEFAULT 'Warm',
                interests TEXT NOT NULL DEFAULT '',
                reminder_time TEXT NOT NULL DEFAULT '09:00',
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                memory_id INTEGER,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                memory_id INTEGER,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL,
                extracted_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            )
        """)
        memory_columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        if "user_id" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN user_id INTEGER")
        if "title" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN title TEXT NOT NULL DEFAULT 'Untitled memory'")
        if "tags" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
        if "memory_date" not in memory_columns:
            conn.execute("ALTER TABLE memories ADD COLUMN memory_date TEXT NOT NULL DEFAULT ''")
        task_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "due_date" not in task_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
        if "priority" not in task_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'Normal'")
        if "reminder_enabled" not in task_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN reminder_enabled INTEGER NOT NULL DEFAULT 0")
        conn.commit()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()
    return password_hash, salt

def create_user(name, email, password):
    password_hash, password_salt = hash_password(password)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?)",
                (name.strip(), email.strip().lower(), password_hash, password_salt,
                 datetime.now().isoformat(timespec="seconds")),
            )
            conn.commit()
            conn.execute(
                "INSERT INTO profiles (user_id, display_name) VALUES (?, ?)",
                (cursor.lastrowid, name.strip()),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None

def authenticate_user(email, password):
    with sqlite3.connect(DB_PATH) as conn:
        user = conn.execute(
            "SELECT id, name, email, password_hash, password_salt FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if not user:
        return None
    password_hash, _ = hash_password(password, user[4])
    if not hmac.compare_digest(password_hash, user[3]):
        return None
    return {"id": user[0], "name": user[1], "email": user[2]}

def save_memory(user_id, source_text, mode, result, title, tags, memory_date):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO memories (user_id, created_at, source_text, mode, result_json, title, tags, memory_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, datetime.now().isoformat(timespec="seconds"), source_text, mode,
             json.dumps(result, ensure_ascii=False), title.strip() or "Untitled memory",
             tags.strip(), memory_date),
        )
        memory_id = cursor.lastrowid
        for task in result.get("tasks", []):
            if str(task).strip():
                conn.execute(
                    "INSERT INTO tasks (user_id, memory_id, title, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, memory_id, str(task).strip(), datetime.now().isoformat(timespec="seconds")),
                )
        conn.commit()
        return memory_id

def load_memories(user_id, search_text="", memory_date="", limit=50):
    filters = ["user_id = ?"]
    params = [user_id]
    if search_text.strip():
        filters.append("(title LIKE ? OR tags LIKE ? OR source_text LIKE ? OR result_json LIKE ?)")
        term = f"%{search_text.strip()}%"
        params.extend([term, term, term, term])
    if memory_date:
        filters.append("memory_date = ?")
        params.append(memory_date)
    params.append(limit)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, created_at, source_text, mode, result_json, title, tags, memory_date "
            f"FROM memories WHERE {' AND '.join(filters)} ORDER BY id DESC LIMIT ?",
            params
        ).fetchall()
    return rows

def load_profile(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT display_name, writing_style, journal_tone, interests, reminder_time "
            "FROM profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row or ("", "Reflective", "Warm", "", "09:00")

def save_profile(user_id, display_name, writing_style, journal_tone, interests, reminder_time):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO profiles (user_id, display_name, writing_style, journal_tone, interests, reminder_time) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
            "display_name=excluded.display_name, writing_style=excluded.writing_style, "
            "journal_tone=excluded.journal_tone, interests=excluded.interests, reminder_time=excluded.reminder_time",
            (user_id, display_name.strip(), writing_style, journal_tone, interests.strip(), reminder_time),
        )
        conn.commit()

def load_tasks(user_id, include_completed=True, limit=50):
    query = "SELECT id, title, completed, created_at, due_date, priority, reminder_enabled FROM tasks WHERE user_id = ?"
    params = [user_id]
    if not include_completed:
        query += " AND completed = 0"
    query += " ORDER BY completed ASC, id DESC LIMIT ?"
    params.append(limit)
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchall()

def set_task_completed(user_id, task_id, completed):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?",
            (int(completed), task_id, user_id),
        )
        conn.commit()


def create_task(user_id, title, due_date=None, priority="Normal", reminder_enabled=False):
    clean_title = title.strip()
    if not clean_title:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO tasks (user_id, title, created_at, due_date, priority, reminder_enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, clean_title, datetime.now().isoformat(timespec="seconds"),
             due_date, priority, int(reminder_enabled)),
        )
        conn.commit()
    return True


def delete_task(user_id, task_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        conn.commit()


def update_task(user_id, task_id, title, due_date, priority, reminder_enabled):
    clean_title = title.strip()
    if not clean_title:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, due_date = ?, priority = ?, reminder_enabled = ? "
            "WHERE id = ? AND user_id = ?",
            (clean_title, due_date, priority, int(reminder_enabled), task_id, user_id),
        )
        conn.commit()
    return True


def asset_path(user_id, stored_name):
    user_dir = ASSET_ROOT / str(user_id)
    candidate = (user_dir / stored_name).resolve()
    if candidate.parent != user_dir.resolve():
        raise ValueError("Invalid asset path.")
    return candidate


def extract_asset_text(file_bytes, extension):
    if extension == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    if extension == "pdf":
        from pypdf import PdfReader
        import io
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(file_bytes)).pages).strip()
    if extension == "docx":
        from docx import Document
        import io
        document = Document(io.BytesIO(file_bytes))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    return ""


def save_asset(user_id, uploaded_file, memory_id=None):
    original_name = Path(uploaded_file.name).name
    extension = Path(original_name).suffix.lower().lstrip(".")
    file_bytes = uploaded_file.getvalue()
    if extension not in ALLOWED_ASSETS:
        raise ValueError("Unsupported file type. Use an image, PDF, TXT, or DOCX file.")
    if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Files must be non-empty and no larger than 25 MB.")
    stored_name = f"{secrets.token_hex(16)}.{extension}"
    path = asset_path(user_id, stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_bytes)
    asset_type = "image" if extension in {"png", "jpg", "jpeg", "gif", "webp"} else "document"
    status = "uploaded"
    extracted_text = ""
    if asset_type == "document":
        try:
            extracted_text = extract_asset_text(file_bytes, extension)
            status = "processed"
        except Exception as error:
            status = f"processing_failed: {error}"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO assets (user_id, memory_id, original_name, stored_name, asset_type, "
            "size_bytes, status, extracted_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, memory_id, original_name, stored_name, asset_type, len(file_bytes),
             status, extracted_text, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    return cursor.lastrowid, status, extracted_text


def load_assets(user_id, memory_id=None):
    query = ("SELECT id, original_name, stored_name, asset_type, size_bytes, status, "
             "extracted_text, created_at FROM assets WHERE user_id = ?")
    params = [user_id]
    if memory_id is not None:
        query += " AND memory_id = ?"
        params.append(memory_id)
    query += " ORDER BY id DESC"
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(query, params).fetchall()


def delete_asset(user_id, asset_id):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT stored_name FROM assets WHERE id = ? AND user_id = ?",
            (asset_id, user_id),
        ).fetchone()
        if not row:
            return False
        path = asset_path(user_id, row[0])
        conn.execute("DELETE FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id))
        conn.commit()
    if path.exists():
        path.unlink()
    return True

init_db()

# ---------- AI helpers ----------
def transcribe_audio(uploaded_file):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Add OPENAI_API_KEY to your .env file to enable audio transcription.")
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    suffix = Path(uploaded_file.name).suffix or ".wav"
    temp_path = Path(f"temp_voice_note{suffix}")
    try:
        temp_path.write_bytes(uploaded_file.getvalue())
        with temp_path.open("rb") as audio:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio)
        return transcript.text
    finally:
        if temp_path.exists():
            temp_path.unlink()

def demo_result(note, mode):
    """Fallback so the interface can be explored without an API key."""
    clean_note = " ".join(note.split())
    pending_tasks = extract_pending_tasks(note)
    completed_actions = extract_completed_actions(note)
    return {
        "journal": f"Today, I wanted to remember this: {clean_note}",
        "reflection": "What felt meaningful today? What challenged you? What is one thing you would like to carry into tomorrow?",
        "tasks": pending_tasks,
        "vlog_script": f"Today, {clean_note}",
        "social_caption": "A little memory from today ✨",
        "tomorrow_ideas": ["Choose one priority for tomorrow.", "Capture one small moment on video."],
        "structured_journal": {
            "title": f"{date.today().strftime('%B %d')} journal",
            "opening": f"Today I noticed: {clean_note}",
            "events": [],
            "achievements": [],
            "challenges": [],
            "feelings": [],
            "reflection": "What felt meaningful today?",
            "gratitude": [],
            "closing": "I will carry one useful lesson into tomorrow.",
        },
        "structured_vlog": {
            "title": "A moment from today",
            "hook": "Here is one moment I want to remember.",
            "scenes": ["Opening shot", "Main moment from today's note", "Closing shot"],
            "voiceover": [f"Today, {clean_note}"],
            "b_roll": ["Details of the setting", "Hands or objects connected to the moment"],
            "closing": "That is one moment I want to remember.",
        },
        "structured_day": {
            "date": date.today().isoformat(),
            "summary": clean_note[:240],
            "events": [],
            "achievements": [],
            "challenges": [],
            "mood": "",
            "completed_tasks": completed_actions,
            "pending_tasks": pending_tasks,
            "future_plans": [],
            "important_moments": [],
            "source_references": ["daily note"],
        },
    }

def generate_lifelog(note, mode):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return validate_day_result(demo_result(note, mode), note), "demo"

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    system_prompt = """
You are LifeLog AI, a supportive personal journaling assistant.
Use only details present in the user's note. Do not invent people, places, events, feelings, deadlines, or promises.
If something is unclear, say it is unclear. Treat the note as private personal content.
Return ONLY valid JSON with these keys:
journal (string), reflection (string), tasks (array of strings),
vlog_script (string), social_caption (string), tomorrow_ideas (array of strings).
Also return structured_journal with:
title, opening, events, achievements, challenges, feelings, reflection, gratitude, closing.
Also return structured_vlog with:
title, hook, scenes, voiceover, b_roll, closing.
Also include structured_day as an object with these keys:
date, summary, events, achievements, challenges, mood, completed_tasks,
pending_tasks, future_plans, important_moments, source_references.
Separate completed_tasks from pending_tasks. Extract completed actions when the user
explicitly says they finished or completed something. Extract a pending task only when the user
explicitly says they need to do something, must do it, should do it, plans to do it,
or otherwise describes an unfinished action. Never convert completed actions into tasks.
Do not invent due dates.
"""
    user_prompt = f"""
Selected generation mode: {mode}
Daily note:
{note}

Generate the LifeLog outputs. Match the selected mode in tone:
- Simple Journal: natural and concise
- Personal Persona: warm, reflective, first-person
- Structured Day: organized and factual
- Reflection: thoughtful but not overly dramatic
- Vlog Creator: visual, practical short-video script
- Social Media: concise caption suitable for a personal post
"""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    data = json.loads(content)
    defaults = demo_result(note, mode)
    for key, value in defaults.items():
        if key not in data or data[key] is None:
            data[key] = value
    return validate_day_result(data, note), "ai"


def generate_visual_prompt(memory_text, style):
    clean_text = " ".join(memory_text.split())
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return (
            f"A {style.lower()} personal memory illustration inspired only by: {clean_text}. "
            "No invented people, locations, or events; natural lighting and authentic details."
        ), "demo"
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.4,
        messages=[{
            "role": "user",
            "content": (
                "Write one concise image-generation prompt for a personal memory. "
                "Use only the supplied facts and do not infer identity, emotion, or location. "
                f"Visual style: {style}. Memory: {clean_text}"
            ),
        }],
    )
    return response.choices[0].message.content.strip(), "ai"

# ---------- Authentication ----------
def render_auth():
    st.title("📔 LifeLog AI")
    st.caption("A private space for the moments you want to remember.")
    sign_in_tab, register_tab = st.tabs(["Sign in", "Create account"])
    with sign_in_tab:
        with st.form("sign_in_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            user = authenticate_user(email, password)
            if user:
                st.session_state["lifelog_user"] = user
                st.rerun()
            st.error("We couldn't sign you in with those details.")
    with register_tab:
        with st.form("register_form"):
            name = st.text_input("Your name", placeholder="Alex Morgan")
            email = st.text_input("Email address", placeholder="you@example.com")
            password = st.text_input("Create a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create my account", type="primary", use_container_width=True)
        if submitted:
            if not name.strip() or not email.strip() or not password:
                st.error("Please complete every field.")
            elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                st.error("Enter a valid email address.")
            elif len(password) < 8:
                st.error("Your password must be at least 8 characters.")
            elif password != confirm_password:
                st.error("The passwords do not match.")
            else:
                user_id = create_user(name, email, password)
                if user_id:
                    st.session_state["lifelog_user"] = {
                        "id": user_id, "name": name.strip(), "email": email.strip().lower()
                    }
                    st.rerun()
                st.error("An account with that email already exists.")

if "lifelog_user" not in st.session_state:
    render_auth()
    st.stop()

# ---------- UI ----------
user = st.session_state["lifelog_user"]
profile = load_profile(user["id"])
display_name, writing_style, journal_tone, interests, reminder_time = profile
profile_name_parts = display_name.strip().split()
user_name_parts = user["name"].strip().split()
first_name = (profile_name_parts or user_name_parts or ["there"])[0]
st.title(f"📔 Welcome back, {first_name}")
st.caption("Your daily voice note, transformed into a journal, reflection, tasks, and creative memories.")

with st.sidebar:
    st.success(f"Signed in as {user['email']}")
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.header("Your daily memory")
    st.write("Start with a voice note or type what happened today.")
    mode = st.selectbox(
        "Choose a generation mode",
        ["Simple Journal", "Personal Persona", "Structured Day", "Reflection", "Vlog Creator", "Social Media"]
    )
    st.divider()
    st.caption("Privacy tip: use notes you are comfortable processing with the configured AI service.")

tab_dashboard, tab_create, tab_memories, tab_tasks, tab_visual, tab_profile, tab_admin, tab_about = st.tabs(
    ["⌂ Dashboard", "✨ Create today's memory", "🗂️ Saved memories", "✅ Tasks",
     "🎨 Visual memories", "⚙ Profile", "🛠️ Admin", "ℹ️ About"]
)

with tab_dashboard:
    memories = load_memories(user["id"])
    pending_tasks = load_tasks(user["id"], include_completed=False)
    completed_tasks = len(load_tasks(user["id"], include_completed=True)) - len(pending_tasks)
    st.subheader(f"{datetime.now().strftime('%A, %B %d')}")
    st.write("A clear place to collect what happened, what matters, and what comes next.")
    metric_one, metric_two, metric_three = st.columns(3)
    metric_one.metric("Memories", len(memories))
    metric_two.metric("Open tasks", len(pending_tasks))
    metric_three.metric("Completed tasks", completed_tasks)
    reminder_tasks = [
        task for task in pending_tasks
        if task[6] and task[4] and task[4] <= date.today().isoformat()
    ]
    if reminder_tasks:
        st.warning(
            "Reminders: " + "; ".join(task[1] for task in reminder_tasks[:5])
        )
    st.divider()
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("#### Recent memories")
        if memories:
            for _, created_at, source_text, saved_mode, result_json, title, tags, memory_date in memories[:5]:
                saved = json.loads(result_json)
                with st.container(border=True):
                    st.caption(f"{memory_date or created_at[:10]} · {saved_mode}")
                    st.markdown(f"**{title}**")
                    st.write(saved.get("journal", source_text)[:280])
        else:
            st.info("Your timeline is waiting for its first memory. Start with a note or voice recording.")
    with right:
        st.markdown("#### Next actions")
        if pending_tasks:
            for task_id, title, _, _, due_date, priority, reminder_enabled in pending_tasks[:5]:
                due_label = f" · due {due_date}" if due_date else ""
                st.write(f"• {title} ({priority}){due_label}")
        else:
            st.success("No open tasks. That is a lovely kind of empty.")
        st.markdown("#### Your writing preference")
        st.caption(f"{writing_style} writing · {journal_tone.lower()} tone")
        st.caption(f"Preferred reminder time: {reminder_time}")

with tab_create:
    st.subheader("1. Tell LifeLog about your day")
    title_col, date_col = st.columns([2, 1])
    with title_col:
        memory_title = st.text_input("Memory title", placeholder="e.g. Presentation day")
    with date_col:
        memory_date = st.date_input("Memory date", value=date.today())
    memory_tags = st.text_input("Tags (optional)", placeholder="e.g. college, project, friends")
    attachments = st.file_uploader(
        "Attach images or documents (optional)",
        type=sorted(ALLOWED_ASSETS),
        accept_multiple_files=True,
        help="Maximum 25 MB per file. Documents are extracted for review; images are stored privately.",
    )
    if attachments:
        for attachment in attachments:
            st.caption(f"{attachment.name} · {len(attachment.getvalue()) / 1024:.1f} KB")
    st.markdown("#### Record directly from your microphone")
    st.caption("Allow microphone access in your browser, record your note, then transcribe it into the editable note below.")
    recorded_audio = st.audio_input("Record a voice note", key="lifelog_microphone")
    if recorded_audio:
        st.audio(recorded_audio)
        if st.button("🎙️ Transcribe microphone recording", type="secondary"):
            with st.spinner("Transcribing your microphone recording..."):
                try:
                    st.session_state["lifelog_transcript"] = transcribe_audio(recorded_audio)
                    st.success("Transcription ready. You can edit it below.")
                except RuntimeError as error:
                    st.error(str(error))
                except (OSError, ValueError) as error:
                    st.error(f"Could not process the microphone recording: {error}")
    st.divider()
    st.markdown("#### Or upload an existing recording")
    uploaded = st.file_uploader("Upload a voice note (optional)", type=["wav", "mp3", "m4a", "webm", "mp4", "mpeg", "mpga"])
    if uploaded:
        st.audio(uploaded)
        if st.button("🎙️ Transcribe voice note", type="secondary"):
            with st.spinner("Transcribing your voice note..."):
                try:
                    st.session_state["lifelog_transcript"] = transcribe_audio(uploaded)
                    st.success("Transcription ready. You can edit it below.")
                except RuntimeError as error:
                    st.error(str(error))
                except (OSError, ValueError) as error:
                    st.error(f"Could not process the uploaded recording: {error}")

    note = st.text_area(
        "Daily note",
        value=st.session_state.get("lifelog_transcript", ""),
        height=180,
        placeholder="Example: I attended class, finished my assignment, felt nervous about the presentation, and need to message my teammate tomorrow..."
    )

    if st.button("✨ Generate my LifeLog", type="primary", use_container_width=True):
        if not note.strip():
            st.warning("Please type a daily note or transcribe a voice note first.")
        else:
            with st.spinner("Creating your LifeLog..."):
                try:
                    result, status = generate_lifelog(note.strip(), mode)
                    st.session_state["lifelog_result"] = result
                    st.session_state["lifelog_source"] = note.strip()
                    st.session_state["lifelog_mode"] = mode
                    st.session_state["lifelog_status"] = status
                    memory_id = save_memory(
                        user["id"], note.strip(), mode, result, memory_title,
                        memory_tags, memory_date.isoformat(),
                    )
                    for attachment in attachments or []:
                        try:
                            _, asset_status, extracted_text = save_asset(user["id"], attachment, memory_id)
                            if extracted_text:
                                st.session_state["lifelog_attachment_text"] = (
                                    st.session_state.get("lifelog_attachment_text", "")
                                    + f"\n\n[{attachment.name}]\n{extracted_text}"
                                )
                            st.success(f"{attachment.name}: {asset_status}")
                        except (ValueError, OSError, ImportError) as error:
                            st.error(f"{attachment.name}: {error}")
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.info("Check your API key and internet connection, or use the demo mode without an API key.")

    result = st.session_state.get("lifelog_result")
    if result:
        st.divider()
        if st.session_state.get("lifelog_status") == "demo":
            st.info("Demo mode: these are starter outputs. Add an API key to enable AI-generated results.")
        else:
            st.success("Your LifeLog is ready.")
        st.subheader("2. Your generated outputs")
        journal_tab, structured_tab, reflect_tab, tasks_tab, vlog_tab, social_tab, tomorrow_tab = st.tabs(
            ["📔 Journal", "🧭 Day understanding", "💭 Reflection", "✅ Tasks", "🎬 Vlog", "📱 Social", "🌅 Tomorrow"]
        )
        with journal_tab:
            journal = result.get("structured_journal", {})
            st.subheader(journal.get("title", "Daily journal"))
            st.markdown("**Opening**")
            st.write(journal.get("opening", result.get("journal", "")))
            for label, key in (
                ("Events", "events"), ("Achievements", "achievements"),
                ("Challenges", "challenges"), ("Feelings", "feelings"),
                ("Gratitude", "gratitude"),
            ):
                values = journal.get(key, [])
                if values:
                    st.markdown(f"**{label}**")
                    for value in values:
                        st.write(f"• {value}")
            st.markdown("**Reflection**")
            st.write(journal.get("reflection", result.get("reflection", "")))
            st.markdown("**Closing**")
            st.write(journal.get("closing", ""))
            journal_download = "\n\n".join([
                journal.get("title", "Daily journal"),
                f"Opening\n{journal.get('opening', '')}",
                f"Events\n" + "\n".join(f"- {item}" for item in journal.get("events", [])),
                f"Achievements\n" + "\n".join(f"- {item}" for item in journal.get("achievements", [])),
                f"Challenges\n" + "\n".join(f"- {item}" for item in journal.get("challenges", [])),
                f"Feelings\n" + "\n".join(f"- {item}" for item in journal.get("feelings", [])),
                f"Reflection\n{journal.get('reflection', '')}",
                f"Gratitude\n" + "\n".join(f"- {item}" for item in journal.get("gratitude", [])),
                f"Closing\n{journal.get('closing', '')}",
            ])
            st.download_button("Download structured journal", journal_download, file_name="lifelog_journal.txt")
        with structured_tab:
            structured = result.get("structured_day", {})
            st.write(structured.get("summary", ""))
            structured_columns = st.columns(2)
            structured_labels = [
                ("Events", "events"),
                ("Achievements", "achievements"),
                ("Challenges", "challenges"),
                ("Completed tasks", "completed_tasks"),
                ("Pending tasks", "pending_tasks"),
                ("Future plans", "future_plans"),
                ("Important moments", "important_moments"),
            ]
            for index, (label, key) in enumerate(structured_labels):
                with structured_columns[index % 2]:
                    values = structured.get(key, [])
                    st.markdown(f"**{label}**")
                    if values:
                        for value in values:
                            st.write(f"• {value}")
                    else:
                        st.caption("None identified")
            if structured.get("mood"):
                st.caption(f"User-described mood: {structured['mood']}")
        with reflect_tab:
            st.write(result.get("reflection", ""))
        with tasks_tab:
            structured_tasks = result.get("structured_day", {})
            pending_tasks = structured_tasks.get("pending_tasks", result.get("tasks", []))
            completed_tasks = structured_tasks.get("completed_tasks", [])
            st.markdown("**Pending tasks identified from your note**")
            if pending_tasks:
                for i, task in enumerate(pending_tasks):
                    st.checkbox(str(task), key=f"task_{i}_{hash(str(task))}")
            else:
                st.success("No pending tasks were identified.")
            st.markdown("**Completed actions**")
            if completed_tasks:
                for task in completed_tasks:
                    st.write(f"✓ {task}")
            else:
                st.caption("No completed actions were identified.")
            st.caption("Only explicit unfinished actions are placed in pending tasks.")
        with vlog_tab:
            vlog = result.get("structured_vlog", {})
            st.subheader(vlog.get("title", "A day in my life"))
            st.markdown("**Hook**")
            st.write(vlog.get("hook", ""))
            st.markdown("**Scenes**")
            for index, scene in enumerate(vlog.get("scenes", []), 1):
                st.write(f"{index}. {scene}")
            st.markdown("**Voice-over**")
            for line in vlog.get("voiceover", []):
                st.write(line)
            st.markdown("**B-roll suggestions**")
            for item in vlog.get("b_roll", []):
                st.write(f"• {item}")
            st.markdown("**Closing**")
            st.write(vlog.get("closing", ""))
            vlog_download = "\n\n".join([
                vlog.get("title", "A day in my life"),
                f"Hook\n{vlog.get('hook', '')}",
                "Scenes\n" + "\n".join(
                    f"{index}. {scene}" for index, scene in enumerate(vlog.get("scenes", []), 1)
                ),
                "Voice-over\n" + "\n".join(vlog.get("voiceover", [])),
                "B-roll\n" + "\n".join(f"- {item}" for item in vlog.get("b_roll", [])),
                f"Closing\n{vlog.get('closing', '')}",
            ])
            st.download_button("Download structured vlog", vlog_download, file_name="lifelog_vlog_script.txt")
        with social_tab:
            st.write(result.get("social_caption", ""))
            if st.button("Copy caption text", key="copy_caption"):
                st.code(result.get("social_caption", ""))
                st.caption("Select and copy the caption shown above.")
        with tomorrow_tab:
            for idea in result.get("tomorrow_ideas", []):
                st.write(f"• {idea}")

with tab_memories:
    st.subheader("Your recent saved memories")
    search_col, date_col = st.columns([2, 1])
    with search_col:
        memory_search = st.text_input("Search memories", placeholder="Search titles, tags, notes, or generated text")
    with date_col:
        filter_date = st.date_input("Filter by date", value=None)
    memories = load_memories(user["id"], memory_search, filter_date.isoformat() if filter_date else "")
    if not memories:
        st.info("No memories match your search.")
    else:
        for memory_id, created_at, source_text, saved_mode, result_json, title, tags, memory_date in memories:
            with st.expander(f"{memory_date or created_at[:10]} · {title}"):
                if tags:
                    st.caption(f"Tags: {tags}")
                st.markdown("**Original note**")
                st.write(source_text)
                saved = json.loads(result_json)
                st.markdown("**Journal entry**")
                st.write(saved.get("journal", ""))
                assets = load_assets(user["id"], memory_id)
                if assets:
                    st.markdown("**Attachments**")
                    for asset_id, name, stored_name, asset_type, size_bytes, status, extracted_text, asset_created in assets:
                        st.caption(f"{name} · {asset_type} · {status}")
                        if asset_type == "image":
                            path = asset_path(user["id"], stored_name)
                            if path.exists():
                                st.image(str(path), width=220)
                        if st.button("Delete attachment", key=f"delete_asset_{asset_id}"):
                            delete_asset(user["id"], asset_id)
                            st.rerun()
                st.download_button(
                    "Download this memory",
                    saved.get("journal", source_text),
                    file_name=f"{title.replace(' ', '_')}.txt",
                    key=f"download_memory_{memory_id}",
                )

with tab_tasks:
    st.subheader("Your task list")
    st.caption("Tasks come from your notes and remain suggestions until you confirm them here.")
    with st.form("manual_task_form"):
        manual_task = st.text_input("Add a task", placeholder="e.g. Message my teammate")
        manual_due_enabled = st.checkbox("Set a due date")
        manual_due = st.date_input("Due date", value=date.today()) if manual_due_enabled else None
        manual_priority = st.selectbox("Priority", ["Low", "Normal", "High"], index=1)
        manual_reminder = st.checkbox("Show reminder when the app is opened")
        if st.form_submit_button("Add task", type="primary"):
            if create_task(
                user["id"], manual_task,
                manual_due.isoformat() if manual_due else None,
                manual_priority, manual_reminder,
            ):
                st.success("Task added.")
                st.rerun()
            st.warning("Enter a task before adding it.")
    tasks = load_tasks(user["id"])
    if not tasks:
        st.info("No tasks yet. Generate a memory with an explicitly pending action to add one.")
    else:
        for task_id, title, completed, created_at, due_date, priority, reminder_enabled in tasks:
            task_col, delete_col = st.columns([8, 1])
            with task_col:
                checked = st.checkbox(title, value=bool(completed), key=f"saved_task_{task_id}")
                if checked != bool(completed):
                    set_task_completed(user["id"], task_id, checked)
                    st.rerun()
                st.caption(
                    f"Added {created_at.replace('T', ' ')} · {priority}"
                    + (f" · due {due_date}" if due_date else "")
                    + (" · reminder on" if reminder_enabled else "")
                )
                with st.expander("Edit task", expanded=False):
                    with st.form(f"edit_task_{task_id}"):
                        edited_title = st.text_input("Title", value=title)
                        edit_due_enabled = st.checkbox("Has due date", value=bool(due_date))
                        edit_due = st.date_input(
                            "Due date",
                            value=datetime.strptime(due_date, "%Y-%m-%d").date()
                            if due_date else date.today(),
                            key=f"edit_due_{task_id}",
                        ) if edit_due_enabled else None
                        edit_priority = st.selectbox(
                            "Priority", ["Low", "Normal", "High"],
                            index=["Low", "Normal", "High"].index(priority)
                            if priority in ["Low", "Normal", "High"] else 1,
                            key=f"edit_priority_{task_id}",
                        )
                        edit_reminder = st.checkbox(
                            "Show reminder when the app is opened",
                            value=bool(reminder_enabled),
                            key=f"edit_reminder_{task_id}",
                        )
                        if st.form_submit_button("Save task"):
                            update_task(
                                user["id"], task_id, edited_title,
                                edit_due.isoformat() if edit_due else None,
                                edit_priority, edit_reminder,
                            )
                            st.rerun()
            with delete_col:
                if st.button("🗑️", key=f"delete_task_{task_id}", help="Delete task"):
                    delete_task(user["id"], task_id)
                    st.rerun()

with tab_profile:
    st.subheader("Profile and personalization")
    st.caption("These preferences shape future generated writing. Optional fields can be left blank.")
    with st.form("profile_form"):
        edited_name = st.text_input("Display name", value=display_name)
        edited_style = st.selectbox(
            "Writing style", ["Concise", "Detailed", "Reflective", "Conversational"],
            index=["Concise", "Detailed", "Reflective", "Conversational"].index(writing_style)
            if writing_style in ["Concise", "Detailed", "Reflective", "Conversational"] else 2,
        )
        edited_tone = st.selectbox(
            "Journal tone", ["Warm", "Calm", "Honest", "Professional"],
            index=["Warm", "Calm", "Honest", "Professional"].index(journal_tone)
            if journal_tone in ["Warm", "Calm", "Honest", "Professional"] else 0,
        )
        edited_interests = st.text_input("Interests and goals", value=interests, placeholder="e.g. learning, health, creative work")
        edited_reminder = st.time_input("Preferred reminder time", value=datetime.strptime(reminder_time, "%H:%M").time())
        if st.form_submit_button("Save profile", type="primary"):
            save_profile(
                user["id"], edited_name, edited_style, edited_tone,
                edited_interests, edited_reminder.strftime("%H:%M"),
            )
            st.success("Profile preferences saved.")
            st.rerun()

with tab_visual:
    st.subheader("Visual memory studio")
    st.caption("Create an image prompt from saved facts. This MVP does not generate or upload images automatically.")
    visual_memories = load_memories(user["id"], limit=30)
    if visual_memories:
        visual_options = {
            f"{row[5]} · {row[7] or row[1][:10]}": row for row in visual_memories
        }
        selected_visual = st.selectbox("Choose a memory", list(visual_options))
        visual_style = st.selectbox("Visual style", ["Cinematic", "Watercolor", "Minimalist", "Photorealistic"])
        if st.button("Generate visual prompt", type="primary"):
            selected_row = visual_options[selected_visual]
            selected_result = json.loads(selected_row[4])
            try:
                prompt, prompt_status = generate_visual_prompt(
                    selected_result.get("journal", selected_row[2]), visual_style
                )
                st.session_state["visual_prompt"] = prompt
                st.caption(f"{prompt_status} prompt")
            except Exception as error:
                st.error(f"Could not create a visual prompt: {error}")
        if st.session_state.get("visual_prompt"):
            st.text_area("Visual prompt", value=st.session_state["visual_prompt"], height=140)
            st.download_button(
                "Download visual prompt",
                st.session_state["visual_prompt"],
                file_name="lifelog_visual_prompt.txt",
            )
    else:
        st.info("Save a memory first to create a visual prompt.")

with tab_admin:
    st.subheader("Administration and system health")
    admin_email = os.getenv("LIFELOG_ADMIN_EMAIL", "").strip().lower()
    if user["email"].lower() != admin_email:
        st.info("Admin monitoring is disabled for this account.")
    else:
        with sqlite3.connect(DB_PATH) as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            memory_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            failed_assets = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE status LIKE 'processing_failed:%'"
            ).fetchone()[0]
        metrics = st.columns(5)
        metrics[0].metric("Users", user_count)
        metrics[1].metric("Memories", memory_count)
        metrics[2].metric("Assets", asset_count)
        metrics[3].metric("Tasks", task_count)
        metrics[4].metric("Failed assets", failed_assets)
        st.success("Database is reachable. Private note content is not displayed in this view.")

with tab_about:
    st.subheader("What this first version includes")
    st.markdown("""
- Voice-note upload and speech-to-text (requires an API key)
- Editable transcript / typed daily note
- Selectable prompt modes
- Journal, reflection, task extraction, vlog script, social caption, and tomorrow ideas
- SQLite storage for generated memories

**Next:** improve structured extraction, add reminders, create a visual memory timeline, and optionally generate images.
""")
    st.warning("This is an early MVP. It is not a substitute for a secure private diary service; avoid entering highly sensitive information.")
