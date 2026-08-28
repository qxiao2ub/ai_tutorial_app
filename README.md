# Anish AI Tutorial App

**Author:** Anish Khandalkar  
**Mentor:** Dr. Qingyang Xiao

A Colab-friendly, GitHub-ready Streamlit prototype for a single-lecturer tutorial platform where **Anish** uploads lecture recordings, students watch videos, answer checkpoint quizzes, complete surveys, play reward-based mini-games, sign up for email/SMS updates, and message Anish for lecture help.

This repository is designed as a working educational MVP, not a production-grade LMS. Before using it with real students, add proper authentication, role-based permissions, consent workflows, encrypted storage for personal information, institutional privacy review, and an approved email/SMS provider.

## What is included

- Streamlit app with student and lecturer/admin modes
- Lecture upload and video playback
- Quiz checkpoints tied to lecture timestamps
- Survey templates and response capture
- Mini-games with reward points and badges
- Email/SMS signup storage for future communications
- Student-to-Anish messaging with AI-assisted draft hints
- SQLite database for local/Colab development
- AI analytics for:
  - watch time and engagement
  - subject preference modeling
  - at-risk student detection
  - strengths and weaknesses by subject
  - scikit-learn neural-network classifier
  - epsilon-greedy reinforcement-learning bandit for activity recommendations

## Deep-space UI integration

This version integrates the visual direction from the supplied **quantum-physics-tutoring-ui** package into the Streamlit application itself. The React/Tailwind reference design was translated to native Streamlit layout + CSS so there is **one deployable Streamlit app**, rather than a separate frontend that Streamlit Community Cloud cannot serve directly.

Integrated design elements include:

- deep-space navy dashboard theme
- cyan/violet AI accents and glow treatments
- branded author/mentor identity in the sidebar and header
- responsive learning-path hero and feature cards
- dark technical navigation, tabs, forms, metrics, tables, and expanders
- student rank/reward display driven by existing reward points
- custom styling for Lecturer/Admin, AI Analytics Lab, and Project README workspaces

The supplied visual assets are retained under `assets/ui/`, and integration notes are in `ui_reference/README.md`. No Node/Vite build is required for deployment.

## Quick start locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Default admin passcode for demo mode: `change-me`

Set a safer passcode before sharing:

```bash
export ANISH_ADMIN_PASSCODE="your-strong-passcode"
```

## Run in Google Colab

Open the companion notebook `Anish_AI_Tutorial_App_Colab.ipynb` provided with the downloadable artifacts, run the setup cells, and launch Streamlit through the localtunnel cell. Colab is useful for development demos, but it is not a permanent hosting platform.

## Deploy on Streamlit Community Cloud

1. Unzip this repository and upload/commit the **contents of this folder** to GitHub.
2. In Streamlit Community Cloud, create a new app and select your GitHub repository/branch.
3. Set the main file path to **`streamlit_app.py`**.
4. Optional but recommended: add `ANISH_ADMIN_PASSCODE` in the app's Secrets/settings instead of using the demo default.
5. Deploy. Streamlit will install the Python packages from `requirements.txt` and apply `.streamlit/config.toml` automatically.
6. For production use, replace local SQLite/upload storage with persistent managed services and add real authentication/privacy controls.

This repository intentionally has **no required frontend build step**. The supplied React UI was translated into the Streamlit layer so Community Cloud can run the app directly.

## Project structure

```text
ai_tutorial_app/
  streamlit_app.py          # Main Streamlit entry point
  requirements.txt          # Python dependencies
  README.md                 # Project guide
  .streamlit/
    config.toml             # Deep-space theme + Community Cloud config
  assets/ui/                # Visual assets from the supplied UI package
  data/                     # Seed JSON and local SQLite database location
  uploads/                  # Uploaded lecture videos during development
  ui_reference/
    README.md               # How the supplied React UI was adapted
  src/
    ai_models.py            # ML, DNN-style MLP, and analytics functions
    bandit.py               # Reinforcement learning recommendation bandit
    config.py               # Paths and settings
    database.py             # SQLite schema and data-access functions
    ui_theme.py             # Streamlit deep-space UI/CSS components
    utils.py                # Helper functions
  tests/
    test_smoke.py           # Basic database/AI smoke test
```

## Data and privacy notes

The app can collect names, emails, phone numbers, watch time, quiz answers, survey feedback, game scores, and messages. Treat all of this as sensitive educational data. The prototype includes a consent checkbox and stores data locally, but a real deployment should include:

- FERPA/GDPR/COPPA/organizational compliance review as applicable
- Clear consent language and data retention policies
- Ability to export/delete a student's data
- Encryption in transit and at rest
- Least-privilege admin access
- Audit logs
- Secure SMS/email opt-in and opt-out handling

## Project credits

- **Author and lecturer:** Anish Khandalkar
- **Mentor:** Dr. Qingyang Xiao


## Production roadmap

- Replace demo passcode with OAuth or SSO
- Move from local SQLite to Postgres/Supabase/Firebase
- Add background tasks for actual email/SMS sending
- Add a real video player event tracker through a Streamlit component or web frontend
- Add LLM-based tutoring with retrieval over Anish's lecture transcripts
- Add transcript generation and searchable lecture notes
- Add model monitoring, fairness checks, and human review for AI recommendations
