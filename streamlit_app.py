from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai_models import (
    build_engagement_dataset,
    strength_weakness_summary,
    student_recommendations,
    suggest_reply,
    train_all_models,
)
from src.bandit import bandit_summary, choose_arm, ensure_bandit_arms, update_arm
from src.config import ADMIN_PASSCODE, APP_NAME, LECTURER_NAME
from src.database import (
    add_game_event,
    add_lecture,
    add_message,
    add_quiz,
    add_quiz_attempt,
    add_signup,
    add_survey,
    add_survey_response,
    connect,
    get_df,
    get_or_create_student,
    get_quizzes,
    get_rewards,
    get_surveys,
    init_db,
    list_lectures,
    log_watch_event,
    save_uploaded_file,
    seed_demo_data,
    update_message_status,
)
from src.utils import from_json
from src.ui_theme import (
    inject_theme,
    render_app_header,
    render_sidebar_identity,
    render_student_hero,
    render_workspace_banner,
)


st.set_page_config(page_title=APP_NAME, page_icon="🎓", layout="wide")


@st.cache_resource
def get_conn():
    conn = connect()
    init_db(conn)
    seed_demo_data(conn)
    subjects = list_lectures(conn)["subject"].dropna().unique().tolist()
    ensure_bandit_arms(conn, subjects or ["General"])
    return conn


conn = get_conn()

inject_theme()
render_app_header()

with st.sidebar:
    render_sidebar_identity()
    st.markdown("### Navigation")
    role = st.radio(
        "Choose a workspace",
        ["Student", f"{LECTURER_NAME} Lecturer/Admin", "AI Analytics Lab", "Project README"],
    )
    st.divider()
    st.caption("Deep-space dashboard UI adapted from the supplied tutoring UI package. Prototype note: replace demo passcode, SQLite, and manual video tracking before real deployment.")


def student_login() -> str | None:
    st.subheader("Student profile and consent")
    with st.form("student_login_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", value=st.session_state.get("student_name", "Demo Student"))
            email = st.text_input("Email", value=st.session_state.get("student_email", "demo.student@example.com"))
        with col2:
            phone = st.text_input("Phone for future text updates (optional)")
            consent = st.checkbox(
                "I consent to local prototype storage of my watch time, quiz answers, survey responses, game points, and messages.",
                value=True,
            )
        submitted = st.form_submit_button("Enter app")
    if submitted:
        if not name.strip() or not email.strip():
            st.error("Name and email are required for the prototype profile.")
            return None
        if not consent:
            st.error("Consent is required before logging educational analytics in this prototype.")
            return None
        student_id = get_or_create_student(conn, name, email, phone, consent=True)
        st.session_state["student_id"] = student_id
        st.session_state["student_name"] = name
        st.session_state["student_email"] = email
        st.success(f"Welcome, {name}.")
    return st.session_state.get("student_id")


def show_rewards(student_id: str) -> None:
    rewards = get_rewards(conn, student_id)
    badges = ", ".join(rewards["badges"]) if rewards["badges"] else "No badges yet"
    st.metric("Reward points", rewards["points"])
    st.caption(f"Badges: {badges}")


def select_lecture(label: str = "Choose a lecture"):
    lectures = list_lectures(conn)
    if lectures.empty:
        st.warning("No lectures have been created yet. Ask Anish to upload a lecture.")
        return None, lectures
    lectures["display"] = lectures["subject"] + " — " + lectures["title"]
    display = st.selectbox(label, lectures["display"].tolist())
    row = lectures[lectures["display"] == display].iloc[0]
    return row, lectures


def render_video_and_quizzes(student_id: str) -> None:
    row, _ = select_lecture()
    if row is None:
        return
    lecture_id = row["lecture_id"]
    st.markdown(f"### {row['title']}")
    st.write(row["description"] or "No description yet.")
    if row["video_path"] and Path(str(row["video_path"])).exists():
        st.video(str(row["video_path"]))
    elif row["video_path"] and str(row["video_path"]).startswith(("http://", "https://")):
        st.video(str(row["video_path"]))
    else:
        st.info("No video file is attached to this demo lecture yet. Anish can upload one in the admin Content Studio.")

    st.markdown("#### Watch-time logger")
    st.caption("Streamlit's built-in video player does not expose exact playback telemetry. This MVP logs self-reported watched minutes. A production version should use a custom video player component for exact play/pause/seek events.")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        watched_minutes = st.number_input("Minutes watched now", min_value=0.0, max_value=600.0, value=10.0, step=1.0)
    with col2:
        elapsed_minutes = st.number_input("Video position reached", min_value=0.0, max_value=600.0, value=min(float(row["duration_minutes"] or 0), 10.0), step=1.0)
    with col3:
        if st.button("Log watch time", use_container_width=True):
            log_watch_event(conn, student_id, lecture_id, "manual_log", int(elapsed_minutes * 60), int(watched_minutes * 60))
            st.success("Watch time logged.")

    st.markdown("#### Checkpoint quizzes")
    quizzes = get_quizzes(conn, lecture_id)
    if quizzes.empty:
        st.info("No quizzes for this lecture yet.")
        return
    for _, quiz in quizzes.iterrows():
        options = from_json(quiz["options_json"], [])
        minute = int(quiz["timestamp_seconds"] or 0) // 60
        with st.expander(f"Checkpoint at ~{minute} min | {quiz['difficulty'].title()}"):
            choice = st.radio(quiz["question"], options, key=f"quiz_{quiz['quiz_id']}")
            if st.button("Submit answer", key=f"submit_{quiz['quiz_id']}"):
                correct = choice == quiz["correct_answer"]
                points = 10 if correct else 2
                add_quiz_attempt(conn, student_id, quiz["quiz_id"], lecture_id, choice, correct, points=points)
                arm = f"{quiz['subject']}:quiz_{quiz['difficulty']}"
                update_arm(conn, arm, 1.0 if correct else 0.1)
                if correct:
                    st.success(f"Correct. +{points} points. {quiz['explanation']}")
                else:
                    st.error(f"Not quite. Correct answer: {quiz['correct_answer']}. {quiz['explanation']} +{points} effort points.")


def render_mini_games(student_id: str) -> None:
    st.subheader("Mini-games and rewards")
    lectures = list_lectures(conn)
    subjects = sorted(lectures["subject"].unique().tolist()) if not lectures.empty else ["General"]
    subject = st.selectbox("Subject", subjects)
    recommended_arm = choose_arm(conn, subject)
    st.info(f"AI/RL recommendation for next activity: **{recommended_arm.split(':', 1)[1].replace('_', ' ').title()}**")
    difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"], index=1)
    game = st.radio("Choose game", ["Quiz Blitz", "Flashcard Recall", "Speed Round"])

    quizzes = get_quizzes(conn)
    quizzes = quizzes[quizzes["subject"] == subject]
    if quizzes.empty:
        st.info("No quiz bank is available for this subject yet.")
        return
    quiz = quizzes.sample(1, random_state=None).iloc[0]
    options = from_json(quiz["options_json"], [])
    st.write(f"**{game}:** {quiz['question']}")
    choice = st.radio("Your answer", options, key=f"game_{game}_{quiz['quiz_id']}_{difficulty}")
    if st.button("Submit game answer"):
        correct = choice == quiz["correct_answer"]
        base = {"easy": 8, "medium": 12, "hard": 18}[difficulty]
        reward = base if correct else 3
        score = 100 if correct else 20
        add_game_event(conn, student_id, game, subject, difficulty, score=score, reward_points=reward)
        update_arm(conn, f"{subject}:{'flashcard_review' if game == 'Flashcard Recall' else 'speed_round' if game == 'Speed Round' else 'quiz_' + difficulty}", 1.0 if correct else 0.2)
        if correct:
            st.success(f"Correct. +{reward} points.")
        else:
            st.warning(f"Review needed. Correct answer: {quiz['correct_answer']}. +{reward} effort points.")
        st.caption(quiz["explanation"])


def render_surveys(student_id: str) -> None:
    st.subheader("Lecture surveys")
    row, _ = select_lecture("Choose lecture for feedback")
    if row is None:
        return
    surveys = get_surveys(conn, row["lecture_id"])
    if surveys.empty:
        st.info("No survey for this lecture yet.")
        return
    survey = surveys.iloc[0]
    questions = from_json(survey["questions_json"], [])
    with st.form(f"survey_{survey['survey_id']}"):
        satisfaction = st.slider("Overall satisfaction", 1, 5, 4)
        responses = {}
        for question in questions:
            responses[question] = st.text_area(question)
        submitted = st.form_submit_button("Submit survey")
    if submitted:
        add_survey_response(conn, student_id, survey["survey_id"], row["lecture_id"], responses, satisfaction_score=float(satisfaction))
        st.success("Thanks. Your feedback will help improve future sessions.")


def render_messages(student_id: str) -> None:
    st.subheader(f"Message {LECTURER_NAME}")
    row, _ = select_lecture("Optional lecture context")
    lecture_id = row["lecture_id"] if row is not None else None
    with st.form("message_form"):
        subject = st.text_input("Message subject", value="Question about the lecture")
        body = st.text_area("Your question or request for explanation")
        submitted = st.form_submit_button(f"Send to {LECTURER_NAME}")
    if body.strip():
        st.caption("AI draft hint for Anish")
        st.write(suggest_reply(conn, body, lecture_id))
    if submitted:
        if not body.strip():
            st.error("Please write a message first.")
        else:
            hint = suggest_reply(conn, body, lecture_id)
            add_message(conn, student_id, lecture_id, subject, body, ai_hint=hint)
            st.success("Message sent to the lecturer/admin inbox.")


def render_signup(student_id: str | None = None) -> None:
    st.subheader("Sign up for future communications")
    with st.form("signup_form"):
        name = st.text_input("Name", value=st.session_state.get("student_name", ""))
        email = st.text_input("Email", value=st.session_state.get("student_email", ""))
        phone = st.text_input("Phone")
        col1, col2 = st.columns(2)
        email_opt_in = col1.checkbox("Email updates", value=True)
        sms_opt_in = col2.checkbox("Text/SMS updates", value=False)
        notes = st.text_area("Topics or future sessions you care about")
        submitted = st.form_submit_button("Save signup")
    if submitted:
        if not email and not phone:
            st.error("Add at least an email or phone number.")
        else:
            add_signup(conn, name or "Student", email, phone, email_opt_in, sms_opt_in, notes)
            st.success("Signup saved.")


def student_workspace() -> None:
    render_workspace_banner(
        "Student Learning Path",
        "Your adaptive learning dashboard",
        "Move between Anish's lectures, checkpoint quizzes, mini-games, surveys, direct messages, and personalized AI recommendations.",
    )
    student_id = student_login()
    if not student_id:
        return
    rewards = get_rewards(conn, student_id)
    render_student_hero(st.session_state.get("student_name", "Student"), int(rewards.get("points", 0)))
    col1, col2 = st.columns([1, 3])
    with col1:
        show_rewards(student_id)
        recs = student_recommendations(conn, student_id)
        if not recs.empty:
            st.markdown("#### Personalized suggestions")
            st.dataframe(recs, use_container_width=True, hide_index=True)
    with col2:
        tabs = st.tabs(["Watch + quizzes", "Mini-games", "Surveys", f"Message {LECTURER_NAME}", "Signup"])
        with tabs[0]:
            render_video_and_quizzes(student_id)
        with tabs[1]:
            render_mini_games(student_id)
        with tabs[2]:
            render_surveys(student_id)
        with tabs[3]:
            render_messages(student_id)
        with tabs[4]:
            render_signup(student_id)


def admin_dashboard() -> None:
    st.subheader("Learning analytics dashboard")
    students = get_df(conn, "SELECT * FROM students")
    lectures = list_lectures(conn)
    watch = get_df(conn, "SELECT * FROM watch_events")
    attempts = get_df(conn, "SELECT * FROM quiz_attempts")
    signups = get_df(conn, "SELECT * FROM signups")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Students", len(students))
    c2.metric("Lectures", len(lectures))
    c3.metric("Quiz attempts", len(attempts))
    c4.metric("Communication signups", len(signups))

    dataset = build_engagement_dataset(conn)
    if dataset.empty:
        st.info("No engagement data yet.")
        return
    st.markdown("#### Engagement by student and subject")
    st.dataframe(dataset[["name", "subject", "watch_minutes", "quiz_accuracy", "survey_satisfaction", "game_points", "engagement_score", "at_risk"]], use_container_width=True, hide_index=True)

    by_subject = dataset.groupby("subject", as_index=False).agg(watch_minutes=("watch_minutes", "sum"), quiz_accuracy=("quiz_accuracy", "mean"), engagement_score=("engagement_score", "mean"))
    fig = px.bar(by_subject, x="subject", y="watch_minutes", title="Total watch minutes by subject")
    st.plotly_chart(fig, use_container_width=True)

    strongest, weakest = strength_weakness_summary(dataset)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Relative strengths")
        st.dataframe(strongest, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("#### Potential weaknesses")
        st.dataframe(weakest, use_container_width=True, hide_index=True)


def admin_content_studio() -> None:
    st.subheader("Content Studio")
    st.markdown("Upload a lecture recording, then add quiz checkpoints and surveys.")
    with st.form("lecture_form"):
        title = st.text_input("Lecture title")
        subject = st.text_input("Subject", value="Artificial Intelligence")
        description = st.text_area("Description")
        duration = st.number_input("Duration in minutes", min_value=0.0, value=30.0, step=1.0)
        video = st.file_uploader("Lecture recording", type=["mp4", "mov", "m4v"])
        submitted = st.form_submit_button("Save lecture")
    if submitted:
        video_path = save_uploaded_file(video) if video else ""
        lecture_id = add_lecture(conn, title, subject, description, video_path, duration)
        ensure_bandit_arms(conn, [subject])
        st.success(f"Lecture saved: {lecture_id}")

    st.divider()
    row, _ = select_lecture("Select lecture to add quiz/survey")
    if row is None:
        return
    with st.expander("Add quiz checkpoint", expanded=True):
        with st.form("quiz_form"):
            timestamp = st.number_input("Checkpoint timestamp in seconds", min_value=0, value=300, step=30)
            difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"], index=1)
            question = st.text_area("Question")
            options_raw = st.text_area("Options, one per line", value="Option A\nOption B\nOption C\nOption D")
            correct = st.text_input("Correct answer exactly as written in options")
            explanation = st.text_area("Explanation")
            save_quiz = st.form_submit_button("Save quiz")
        if save_quiz:
            options = [o.strip() for o in options_raw.splitlines() if o.strip()]
            if correct not in options:
                st.error("Correct answer must match one of the options.")
            else:
                add_quiz(conn, row["lecture_id"], row["subject"], question, options, correct, explanation, timestamp, difficulty)
                st.success("Quiz saved.")

    with st.expander("Add survey"):
        with st.form("survey_form"):
            title = st.text_input("Survey title", value=f"Feedback for {row['title']}")
            questions_raw = st.text_area("Survey questions, one per line", value="What was clearest?\nWhat was confusing?\nWhat should Anish add next?")
            save_survey = st.form_submit_button("Save survey")
        if save_survey:
            questions = [q.strip() for q in questions_raw.splitlines() if q.strip()]
            add_survey(conn, row["lecture_id"], title, questions)
            st.success("Survey saved.")


def admin_messages() -> None:
    st.subheader("Student messages")
    messages = get_df(
        conn,
        """
        SELECT m.message_id, m.created_at, s.name, l.title AS lecture, m.subject, m.body, m.ai_hint, m.status
        FROM messages m
        JOIN students s ON s.student_id = m.student_id
        LEFT JOIN lectures l ON l.lecture_id = m.lecture_id
        ORDER BY m.created_at DESC
        """,
    )
    if messages.empty:
        st.info("No messages yet.")
        return
    for _, msg in messages.iterrows():
        with st.expander(f"{msg['status'].upper()} | {msg['name']} | {msg['subject']}"):
            st.caption(f"Lecture: {msg['lecture'] or 'General'} | Created: {msg['created_at']}")
            st.write(msg["body"])
            st.markdown("**AI hint for Anish**")
            st.write(msg["ai_hint"] or "No hint available.")
            new_status = st.selectbox("Status", ["new", "in_review", "responded", "closed"], index=["new", "in_review", "responded", "closed"].index(msg["status"]), key=f"status_{msg['message_id']}")
            if st.button("Update status", key=f"update_{msg['message_id']}"):
                update_message_status(conn, msg["message_id"], new_status)
                st.success("Status updated. Refresh to see changes.")


def admin_communications() -> None:
    st.subheader("Future communications list")
    signups = get_df(conn, "SELECT name, email, phone, email_opt_in, sms_opt_in, notes, created_at FROM signups ORDER BY created_at DESC")
    if signups.empty:
        st.info("No signups yet.")
        return
    st.dataframe(signups, use_container_width=True, hide_index=True)
    st.markdown("#### Create a communication export")
    subject = st.text_input("Announcement subject", value="Upcoming session with Anish")
    body = st.text_area("Announcement body", value="Hi, Anish will host a new learning session soon. Reply with topics you want covered.")
    export = signups.copy()
    export["announcement_subject"] = subject
    export["announcement_body"] = body
    st.download_button(
        "Download CSV for email/SMS provider",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name="communications_outbox.csv",
        mime="text/csv",
    )
    st.caption("This prototype does not send live emails or SMS. Connect a compliant provider such as SendGrid/Mailchimp/Twilio after opt-in review.")


def admin_ai_insights() -> None:
    st.subheader("AI model training lab")
    dataset = build_engagement_dataset(conn)
    if dataset.empty:
        st.info("No data available yet.")
        return
    st.markdown("#### Feature table")
    st.dataframe(dataset, use_container_width=True, hide_index=True)
    st.caption("Labels are demo labels inferred from prototype behavior. Replace them with validated educational outcomes before using for decisions.")
    if st.button("Train ML, DNN/MLP, and at-risk models"):
        results = train_all_models(dataset)
        for key, result in results.items():
            with st.expander(result.name, expanded=True):
                st.write(f"Status: {result.status}")
                if result.accuracy is not None:
                    st.metric("Holdout accuracy", f"{result.accuracy:.2f}")
                    st.text(result.report)
                    st.dataframe(result.predictions, use_container_width=True, hide_index=True)
    st.markdown("#### Reinforcement learning bandit state")
    st.dataframe(bandit_summary(conn), use_container_width=True, hide_index=True)


def admin_workspace() -> None:
    render_workspace_banner(
        "Lecturer Command Center",
        f"{LECTURER_NAME} Lecturer / Admin workspace",
        "Upload lecture recordings, build checkpoint assessments, review student messages, manage communications, and monitor learning analytics.",
    )
    passcode = st.text_input("Admin passcode", type="password")
    if passcode != ADMIN_PASSCODE:
        st.info("Enter the admin passcode. Demo default is `change-me`; set ANISH_ADMIN_PASSCODE before sharing.")
        return
    tabs = st.tabs(["Dashboard", "Content Studio", "Messages", "Communications", "AI Insights"])
    with tabs[0]:
        admin_dashboard()
    with tabs[1]:
        admin_content_studio()
    with tabs[2]:
        admin_messages()
    with tabs[3]:
        admin_communications()
    with tabs[4]:
        admin_ai_insights()


def ai_lab_workspace() -> None:
    render_workspace_banner(
        "AI & Technology",
        "AI Analytics Lab",
        "Explore machine learning, neural-network modeling, strengths/weakness analysis, engagement signals, and reinforcement-learning activity recommendations.",
    )
    dataset = build_engagement_dataset(conn)
    if dataset.empty:
        st.info("Use the app first to generate watch, quiz, survey, and game data.")
        return
    st.markdown("This lab demonstrates the requested machine learning, deep-learning-style neural network, and reinforcement-learning pieces on the same education data.")
    st.dataframe(dataset, use_container_width=True, hide_index=True)
    strongest, weakest = strength_weakness_summary(dataset)
    col1, col2 = st.columns(2)
    col1.write("Strengths")
    col1.dataframe(strongest, use_container_width=True, hide_index=True)
    col2.write("Weaknesses")
    col2.dataframe(weakest, use_container_width=True, hide_index=True)
    if st.button("Train models in AI Lab"):
        for result in train_all_models(dataset).values():
            st.markdown(f"#### {result.name}")
            st.write(result.status)
            if result.accuracy is not None:
                st.metric("Holdout accuracy", f"{result.accuracy:.2f}")
                st.dataframe(result.predictions, use_container_width=True, hide_index=True)
    st.markdown("#### RL activity recommendations")
    st.dataframe(bandit_summary(conn), use_container_width=True, hide_index=True)


def readme_workspace() -> None:
    render_workspace_banner(
        "Project Documentation",
        "Architecture, workflow & deployment",
        "Review the application scope, AI pipeline, privacy notes, project structure, and Streamlit Community Cloud deployment steps.",
    )
    readme_path = Path(__file__).parent / "README.md"
    st.markdown(readme_path.read_text(encoding="utf-8"))


if role == "Student":
    student_workspace()
elif role == f"{LECTURER_NAME} Lecturer/Admin":
    admin_workspace()
elif role == "AI Analytics Lab":
    ai_lab_workspace()
else:
    readme_workspace()
