from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_DIR, DB_PATH, UPLOAD_DIR
from .utils import now_iso, safe_filename, stable_id, to_json


def connect(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS students(
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            consent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lectures(
            lecture_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            video_path TEXT,
            duration_minutes REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quizzes(
            quiz_id TEXT PRIMARY KEY,
            lecture_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            timestamp_seconds INTEGER DEFAULT 0,
            difficulty TEXT DEFAULT 'medium',
            question TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts(
            attempt_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            quiz_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            selected_answer TEXT NOT NULL,
            correct INTEGER NOT NULL,
            points INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY(quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS surveys(
            survey_id TEXT PRIMARY KEY,
            lecture_id TEXT NOT NULL,
            title TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS survey_responses(
            response_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            survey_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            responses_json TEXT NOT NULL,
            satisfaction_score REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY(survey_id) REFERENCES surveys(survey_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS watch_events(
            event_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            lecture_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            elapsed_seconds INTEGER DEFAULT 0,
            session_seconds INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages(
            message_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            lecture_id TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            ai_hint TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE,
            FOREIGN KEY(lecture_id) REFERENCES lectures(lecture_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS signups(
            signup_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            email_opt_in INTEGER DEFAULT 0,
            sms_opt_in INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS game_events(
            event_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            game_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            difficulty TEXT DEFAULT 'medium',
            score REAL DEFAULT 0,
            reward_points INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rewards(
            student_id TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0,
            badges_json TEXT DEFAULT '[]',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bandit_state(
            arm TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            value REAL DEFAULT 0.0,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def get_df(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)


def get_or_create_student(conn: sqlite3.Connection, name: str, email: str, phone: str = "", consent: bool = False) -> str:
    student_id = stable_id("stu", email or name, name)
    conn.execute(
        """
        INSERT INTO students(student_id, name, email, phone, consent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            name=excluded.name,
            email=excluded.email,
            phone=excluded.phone,
            consent=excluded.consent
        """,
        (student_id, name.strip(), email.strip().lower(), phone.strip(), int(consent), now_iso()),
    )
    conn.execute(
        "INSERT OR IGNORE INTO rewards(student_id, points, badges_json, updated_at) VALUES (?, 0, '[]', ?)",
        (student_id, now_iso()),
    )
    conn.commit()
    return student_id


def add_points(conn: sqlite3.Connection, student_id: str, points: int) -> None:
    row = conn.execute("SELECT points, badges_json FROM rewards WHERE student_id = ?", (student_id,)).fetchone()
    if row is None:
        current, badges = 0, []
    else:
        current = int(row["points"])
        try:
            badges = json.loads(row["badges_json"] or "[]")
        except Exception:
            badges = []
    total = current + int(points)
    for threshold, badge in [(25, "Starter"), (75, "Persistent Learner"), (150, "Quiz Master"), (300, "Subject Champion")]:
        if total >= threshold and badge not in badges:
            badges.append(badge)
    conn.execute(
        """
        INSERT INTO rewards(student_id, points, badges_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET points=excluded.points, badges_json=excluded.badges_json, updated_at=excluded.updated_at
        """,
        (student_id, total, to_json(badges), now_iso()),
    )
    conn.commit()


def get_rewards(conn: sqlite3.Connection, student_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT points, badges_json FROM rewards WHERE student_id = ?", (student_id,)).fetchone()
    if row is None:
        return {"points": 0, "badges": []}
    try:
        badges = json.loads(row["badges_json"] or "[]")
    except Exception:
        badges = []
    return {"points": int(row["points"]), "badges": badges}


def add_lecture(conn: sqlite3.Connection, title: str, subject: str, description: str = "", video_path: str = "", duration_minutes: float = 0) -> str:
    lecture_id = stable_id("lec", title, subject, str(duration_minutes))
    conn.execute(
        """
        INSERT OR REPLACE INTO lectures(lecture_id, title, subject, description, video_path, duration_minutes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (lecture_id, title.strip(), subject.strip(), description.strip(), video_path, float(duration_minutes or 0), now_iso()),
    )
    conn.commit()
    return lecture_id


def add_quiz(
    conn: sqlite3.Connection,
    lecture_id: str,
    subject: str,
    question: str,
    options: list[str],
    correct_answer: str,
    explanation: str = "",
    timestamp_seconds: int = 0,
    difficulty: str = "medium",
) -> str:
    quiz_id = stable_id("quiz", lecture_id, question, str(timestamp_seconds))
    conn.execute(
        """
        INSERT OR REPLACE INTO quizzes(quiz_id, lecture_id, subject, timestamp_seconds, difficulty, question, options_json, correct_answer, explanation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (quiz_id, lecture_id, subject, int(timestamp_seconds or 0), difficulty, question.strip(), to_json(options), correct_answer, explanation, now_iso()),
    )
    conn.commit()
    return quiz_id


def add_survey(conn: sqlite3.Connection, lecture_id: str, title: str, questions: list[str]) -> str:
    survey_id = stable_id("survey", lecture_id, title)
    conn.execute(
        """
        INSERT OR REPLACE INTO surveys(survey_id, lecture_id, title, questions_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (survey_id, lecture_id, title.strip(), to_json(questions), now_iso()),
    )
    conn.commit()
    return survey_id


def log_watch_event(
    conn: sqlite3.Connection,
    student_id: str,
    lecture_id: str,
    event_type: str,
    elapsed_seconds: int = 0,
    session_seconds: int = 0,
) -> str:
    event_id = stable_id("watch", student_id, lecture_id, event_type, now_iso(), str(random.random()))
    conn.execute(
        """
        INSERT INTO watch_events(event_id, student_id, lecture_id, event_type, elapsed_seconds, session_seconds, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, student_id, lecture_id, event_type, int(elapsed_seconds or 0), int(session_seconds or 0), now_iso()),
    )
    conn.commit()
    return event_id


def add_quiz_attempt(
    conn: sqlite3.Connection,
    student_id: str,
    quiz_id: str,
    lecture_id: str,
    selected_answer: str,
    correct: bool,
    points: int = 0,
) -> str:
    attempt_id = stable_id("attempt", student_id, quiz_id, selected_answer, now_iso(), str(random.random()))
    conn.execute(
        """
        INSERT INTO quiz_attempts(attempt_id, student_id, quiz_id, lecture_id, selected_answer, correct, points, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (attempt_id, student_id, quiz_id, lecture_id, selected_answer, int(correct), int(points), now_iso()),
    )
    if points:
        add_points(conn, student_id, points)
    conn.commit()
    return attempt_id


def add_survey_response(
    conn: sqlite3.Connection,
    student_id: str,
    survey_id: str,
    lecture_id: str,
    responses: dict[str, Any],
    satisfaction_score: float | None = None,
) -> str:
    response_id = stable_id("surveyresp", student_id, survey_id, now_iso(), str(random.random()))
    conn.execute(
        """
        INSERT INTO survey_responses(response_id, student_id, survey_id, lecture_id, responses_json, satisfaction_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (response_id, student_id, survey_id, lecture_id, to_json(responses), satisfaction_score, now_iso()),
    )
    conn.commit()
    return response_id


def add_game_event(
    conn: sqlite3.Connection,
    student_id: str,
    game_name: str,
    subject: str,
    difficulty: str,
    score: float,
    reward_points: int,
) -> str:
    event_id = stable_id("game", student_id, game_name, subject, now_iso(), str(random.random()))
    conn.execute(
        """
        INSERT INTO game_events(event_id, student_id, game_name, subject, difficulty, score, reward_points, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, student_id, game_name, subject, difficulty, float(score), int(reward_points), now_iso()),
    )
    if reward_points:
        add_points(conn, student_id, reward_points)
    conn.commit()
    return event_id


def add_message(conn: sqlite3.Connection, student_id: str, lecture_id: str | None, subject: str, body: str, ai_hint: str = "") -> str:
    message_id = stable_id("msg", student_id, lecture_id or "", subject, body, now_iso(), str(random.random()))
    conn.execute(
        """
        INSERT INTO messages(message_id, student_id, lecture_id, subject, body, ai_hint, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'new', ?)
        """,
        (message_id, student_id, lecture_id, subject.strip(), body.strip(), ai_hint, now_iso()),
    )
    conn.commit()
    return message_id


def update_message_status(conn: sqlite3.Connection, message_id: str, status: str) -> None:
    conn.execute("UPDATE messages SET status = ? WHERE message_id = ?", (status, message_id))
    conn.commit()


def add_signup(
    conn: sqlite3.Connection,
    name: str,
    email: str = "",
    phone: str = "",
    email_opt_in: bool = False,
    sms_opt_in: bool = False,
    notes: str = "",
) -> str:
    signup_id = stable_id("signup", email or phone or name, name)
    conn.execute(
        """
        INSERT INTO signups(signup_id, name, email, phone, email_opt_in, sms_opt_in, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(signup_id) DO UPDATE SET
            name=excluded.name,
            email=excluded.email,
            phone=excluded.phone,
            email_opt_in=excluded.email_opt_in,
            sms_opt_in=excluded.sms_opt_in,
            notes=excluded.notes
        """,
        (signup_id, name.strip(), email.strip().lower(), phone.strip(), int(email_opt_in), int(sms_opt_in), notes.strip(), now_iso()),
    )
    conn.commit()
    return signup_id


def save_uploaded_file(uploaded_file) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(uploaded_file.name)
    target = UPLOAD_DIR / filename
    with open(target, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(target)


def list_lectures(conn: sqlite3.Connection) -> pd.DataFrame:
    return get_df(conn, "SELECT * FROM lectures ORDER BY subject, title")


def get_quizzes(conn: sqlite3.Connection, lecture_id: str | None = None) -> pd.DataFrame:
    if lecture_id:
        return get_df(conn, "SELECT * FROM quizzes WHERE lecture_id = ? ORDER BY timestamp_seconds", (lecture_id,))
    return get_df(conn, "SELECT * FROM quizzes ORDER BY subject, timestamp_seconds")


def get_surveys(conn: sqlite3.Connection, lecture_id: str | None = None) -> pd.DataFrame:
    if lecture_id:
        return get_df(conn, "SELECT * FROM surveys WHERE lecture_id = ? ORDER BY created_at", (lecture_id,))
    return get_df(conn, "SELECT * FROM surveys ORDER BY created_at")


def seed_demo_data(conn: sqlite3.Connection) -> None:
    existing = conn.execute("SELECT COUNT(*) AS n FROM lectures").fetchone()["n"]
    if existing:
        return

    lectures = [
        {
            "title": "AI Foundations with Anish",
            "subject": "Artificial Intelligence",
            "duration": 28,
            "description": "A beginner-friendly overview of supervised learning, deep learning, and reinforcement learning.",
            "quizzes": [
                (300, "easy", "Which learning setup uses labeled examples?", ["Supervised learning", "Reinforcement learning", "Clustering", "Random search"], "Supervised learning", "Supervised learning trains on input-output pairs."),
                (900, "medium", "What does a reward signal guide in reinforcement learning?", ["The agent's action choices", "Only database schema", "The video file format", "The email signup form"], "The agent's action choices", "Rewards tell the agent which actions are useful over time."),
                (1500, "hard", "Why should model recommendations be reviewed by a lecturer?", ["To prevent unfair or misleading decisions", "To make videos longer", "To remove quizzes", "To skip consent"], "To prevent unfair or misleading decisions", "Human review catches data quality, bias, and context issues."),
            ],
        },
        {
            "title": "Python for Data Learning",
            "subject": "Python",
            "duration": 35,
            "description": "A practical lecture on Python data structures, pandas, and simple analytics for education data.",
            "quizzes": [
                (420, "easy", "Which Python library is commonly used for tabular data?", ["pandas", "sqlite3 only", "turtle", "calendar"], "pandas", "pandas DataFrames are useful for tabular analytics."),
                (1200, "medium", "What is a DataFrame row often used to represent in this app?", ["One event or record", "Only a video pixel", "An email server", "A phone carrier"], "One event or record", "Each row can represent a student, quiz attempt, watch event, or survey response."),
                (1800, "hard", "Why is a stable student ID better than raw email in model features?", ["It reduces exposure of personal data", "It makes quizzes impossible", "It stops SQLite", "It removes consent"], "It reduces exposure of personal data", "Pseudonymous IDs reduce unnecessary exposure of direct identifiers."),
            ],
        },
        {
            "title": "Calculus Review Sprint",
            "subject": "Calculus",
            "duration": 32,
            "description": "A concise review of limits, derivatives, and interpretation of rates of change.",
            "quizzes": [
                (360, "easy", "What does a derivative describe?", ["Rate of change", "A database table", "A survey form", "A text message"], "Rate of change", "A derivative measures how a function changes locally."),
                (1020, "medium", "If quiz accuracy is low in derivatives, what should the app recommend?", ["Review and targeted practice", "Skip all math", "Delete the lecture", "Disable surveys"], "Review and targeted practice", "The app should suggest extra practice in weak concepts."),
                (1560, "hard", "What is a useful sign that a student may need support?", ["Low watch time plus low quiz accuracy", "A high badge count", "Opting into email", "Opening the app once"], "Low watch time plus low quiz accuracy", "Combining engagement and performance gives a stronger support signal."),
            ],
        },
    ]

    lecture_ids: dict[str, str] = {}
    for lecture in lectures:
        lecture_id = add_lecture(
            conn,
            title=lecture["title"],
            subject=lecture["subject"],
            description=lecture["description"],
            video_path="",
            duration_minutes=lecture["duration"],
        )
        lecture_ids[lecture["subject"]] = lecture_id
        for timestamp, difficulty, question, options, answer, explanation in lecture["quizzes"]:
            add_quiz(conn, lecture_id, lecture["subject"], question, options, answer, explanation, timestamp, difficulty)
        add_survey(
            conn,
            lecture_id,
            f"Feedback for {lecture['subject']}",
            [
                "What was the clearest part of the lecture?",
                "What topic should Anish explain again?",
                "How can the quiz or mini-game be improved?",
            ],
        )

    # Simulated demo students and interactions.
    demo_students = [
        ("Ava", "ava@example.com", "Artificial Intelligence", 0.95),
        ("Ben", "ben@example.com", "Python", 0.80),
        ("Chloe", "chloe@example.com", "Calculus", 0.55),
        ("Dev", "dev@example.com", "Artificial Intelligence", 0.65),
        ("Eli", "eli@example.com", "Python", 0.45),
        ("Fatima", "fatima@example.com", "Calculus", 0.88),
        ("Grace", "grace@example.com", "Python", 0.73),
        ("Hugo", "hugo@example.com", "Artificial Intelligence", 0.38),
    ]
    rng = random.Random(42)
    for name, email, preferred, ability in demo_students:
        sid = get_or_create_student(conn, name, email, consent=True)
        for subject, lecture_id in lecture_ids.items():
            base_minutes = rng.randint(6, 30)
            if subject == preferred:
                base_minutes += rng.randint(10, 24)
            if ability < 0.5:
                base_minutes = max(3, base_minutes - rng.randint(4, 12))
            log_watch_event(conn, sid, lecture_id, "manual_log", elapsed_seconds=base_minutes * 60, session_seconds=base_minutes * 60)
            quizzes = conn.execute("SELECT * FROM quizzes WHERE lecture_id = ?", (lecture_id,)).fetchall()
            for quiz in quizzes:
                correct_prob = min(0.95, max(0.15, ability + (0.1 if subject == preferred else -0.05)))
                is_correct = rng.random() < correct_prob
                options = json.loads(quiz["options_json"])
                selected = quiz["correct_answer"] if is_correct else rng.choice([o for o in options if o != quiz["correct_answer"]])
                add_quiz_attempt(conn, sid, quiz["quiz_id"], lecture_id, selected, is_correct, points=10 if is_correct else 2)
            add_game_event(conn, sid, "Quiz Blitz", subject, "medium", score=ability * 100, reward_points=int(ability * 15))
            survey = conn.execute("SELECT * FROM surveys WHERE lecture_id = ?", (lecture_id,)).fetchone()
            add_survey_response(
                conn,
                sid,
                survey["survey_id"],
                lecture_id,
                {
                    "clearest": f"The examples in {subject}.",
                    "review": "More step-by-step explanations.",
                    "improve": "Add more checkpoint questions.",
                },
                satisfaction_score=round(ability * 5, 1),
            )
    conn.commit()
