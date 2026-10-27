# LifeLog AI — MVP

LifeLog AI turns a daily note or voice note into a journal entry, reflection, possible pending tasks, a short vlog script, a social caption, and ideas for tomorrow. Each user has a local account and private memory history.

## 1. Requirements

- Python 3.10 or newer
- Internet connection for AI generation/transcription
- An API key for AI features (optional for exploring demo mode)

## 2. Open the project

Extract the ZIP, open the `lifelog_ai_mvp` folder in VS Code, then open its terminal.

## 3. Create a virtual environment

### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation, use Command Prompt:
```bat
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

## 4. Configure the API key (optional)

1. Copy `.env.example` and rename the copy to `.env`.
2. Open `.env` and replace `your_api_key_here` with your API key.
3. Do not share your `.env` file or upload it to GitHub.

Without a key, you can still try the interface in demo mode. Audio transcription and AI-generated results require a key and may incur API charges.

## 5. Run the app

```bash
streamlit run app.py
```

Streamlit will show a local URL, usually `http://localhost:8501`.

## Current MVP features

- Local account registration and sign-in
- Salted password hashing for local authentication
- User-specific SQLite memory history
- Typed daily note
- Browser microphone recording and transcription
- Voice-note upload and transcription
- Selectable generation mode
- Validated structured day understanding (events, achievements, challenges, plans, and tasks)
- Journal, reflection, tasks, vlog script, caption, tomorrow ideas
- Searchable, titled, tagged SQLite memory history with date filtering
- Manual task creation, completion, and deletion
- Private image and document uploads with PDF/TXT/DOCX text extraction
- Task due dates, priorities, and in-app reminder indicators
- Visual memory prompt studio
- Restricted admin health and usage metrics

## Known limitations

- Accounts and journal data are stored only in the local SQLite database; this is not production-grade account security.
- Reminders are not scheduled yet; tasks are only displayed.
- Reminders currently appear when the app is opened; an external scheduler is required for closed-app delivery.
- Memory editing and external reminder delivery are planned next.
- The visual studio creates prompts but does not call an image-generation service.
- Set `LIFELOG_ADMIN_EMAIL` to enable the restricted admin metrics tab for one account.
- Image generation and a visual timeline are planned for later phases.
- Demo mode is only for testing the interface and does not perform real AI reasoning.
- The app stores memories in a local SQLite database. Treat personal notes carefully.
