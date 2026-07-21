# Anish AI Tutorial App

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

## GitHub deployment path

1. Unzip this folder.
2. Create a new GitHub repository.
3. Commit these files.
4. Deploy with Streamlit Community Cloud or another hosting platform.
5. Replace SQLite with a managed database for production.
6. Add real user authentication and privacy controls.

## Project structure

```text
anish_ai_tutorial_app/
  streamlit_app.py          # Main Streamlit user interface
  requirements.txt          # Python dependencies
  README.md                 # Project guide
  data/                     # Seed JSON and local SQLite database location
  uploads/                  # Uploaded lecture videos during development
  src/
    ai_models.py            # ML, DNN-style MLP, and analytics functions
    bandit.py               # Reinforcement learning recommendation bandit
    config.py               # Paths and settings
    database.py             # SQLite schema and data-access functions
    utils.py                # Helper functions
  tests/
    test_smoke.py           # Basic import and database smoke test
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

## Production roadmap

- Replace demo passcode with OAuth or SSO
- Move from local SQLite to Postgres/Supabase/Firebase
- Add background tasks for actual email/SMS sending
- Add a real video player event tracker through a Streamlit component or web frontend
- Add LLM-based tutoring with retrieval over Anish's lecture transcripts
- Add transcript generation and searchable lecture notes
- Add model monitoring, fairness checks, and human review for AI recommendations
