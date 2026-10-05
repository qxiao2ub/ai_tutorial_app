from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai_models import (
    build_engagement_dataset,
    strength_weakness_summary,
    student_recommendations,
    train_all_models,
)
from src.bandit import bandit_summary, choose_arm, ensure_bandit_arms, update_arm
from src.config import ADMIN_PASSCODE, APP_NAME, LECTURER_NAME
from src.database import (
    add_game_event,
    add_lecture,
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
    save_uploaded_file,
    seed_demo_data,
)
from src.utils import from_json
from src.usage_counter import increment_visit
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

# Count one visit per Streamlit session, not once per widget rerun.
if "usage_counted" not in st.session_state:
    visit_count, remote_ok = increment_visit()
    st.session_state["usage_counted"] = True
    st.session_state["usage_count"] = visit_count
    st.session_state["usage_counter_remote_ok"] = remote_ok
else:
    visit_count = int(st.session_state.get("usage_count", 1))
    remote_ok = bool(st.session_state.get("usage_counter_remote_ok", False))

inject_theme()
render_app_header()

# Global usage counter: visible regardless of the selected workspace/page.
metric_col, note_col = st.columns([1, 3])
with metric_col:
    st.metric("👥 App uses", f"{visit_count:,}")
with note_col:
    if remote_ok:
        st.caption("Cumulative app visits • one increment per new Streamlit session • persistent outside the app database")
    else:
        st.caption("Cumulative visit counter is temporarily unavailable; the display is kept at a minimum of 1 so it never shows 0.")

with st.sidebar:
    render_sidebar_identity()
    st.markdown("### Navigation")
    role = st.radio(
        "Choose a workspace",
        ["Student", f"{LECTURER_NAME} Lecturer/Admin", "AI Analytics Lab", "Project README"],
    )
    st.divider()
    st.caption("Deep-space dashboard UI adapted from the supplied tutoring UI package. Usage counter is external/no-database and counts one visit per Streamlit session. Prototype note: replace demo passcode and SQLite before real deployment.")


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
                "I consent to local prototype storage of my quiz answers, survey responses, and game points.",
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

    selection_key = f"mini_game_selection:{game}:{subject}:{difficulty}"
    available_ids = set(quizzes["quiz_id"].tolist())
    saved_quiz_id = st.session_state.get(selection_key)
    if saved_quiz_id in available_ids:
        quiz = quizzes[quizzes["quiz_id"] == saved_quiz_id].iloc[0]
    else:
        quiz = quizzes.sample(1, random_state=None).iloc[0]
        st.session_state[selection_key] = quiz["quiz_id"]

    options = from_json(quiz["options_json"], [])
    game_key = f"{game}:{subject}:{difficulty}:{quiz['quiz_id']}"

    if st.session_state.get("active_game_key") != game_key:
        st.session_state.pop("game_started_at", None)
        st.session_state.pop("game_finished", None)
        st.session_state["active_game_key"] = game_key

    st.write(f"**{game}:** {quiz['question']}")

    if "game_started_at" not in st.session_state and not st.session_state.get("game_finished", False):
        if st.button("Start this quiz", use_container_width=True):
            st.session_state["game_started_at"] = time.time()
            st.session_state["game_finished"] = False
            st.rerun()
        st.caption("Start the quiz to begin the timer. The timer measures how long you spend on this activity.")
        return

    if st.session_state.get("game_finished", False):
        st.success("Quiz completed. Start another round to record a new timed attempt.")
        if st.button("Start another quiz", use_container_width=True):
            st.session_state.pop("game_finished", None)
            st.session_state.pop("game_started_at", None)
            st.session_state.pop(selection_key, None)
            st.rerun()
        return

    @st.fragment(run_every="1s")
    def timed_game_fragment():
        started_at = st.session_state.get("game_started_at")
        if started_at is None:
            return
        elapsed = max(0, int(time.time() - started_at))
        mins, secs = divmod(elapsed, 60)
        st.metric("Quiz timer", f"{mins:02d}:{secs:02d}")
        choice = st.radio("Your answer", options, key=f"game_answer_{game_key}")
        if st.button("Submit game answer", use_container_width=True, key=f"submit_{game_key}"):
            final_elapsed = max(0, int(time.time() - started_at))
            correct = choice == quiz["correct_answer"]
            base = {"easy": 8, "medium": 12, "hard": 18}[difficulty]
            speed_bonus = max(0, 10 - final_elapsed // 30)
            reward = base + (speed_bonus if correct else 0)
            score = 100 if correct else 20
            add_game_event(
                conn,
                student_id,
                game,
                subject,
                difficulty,
                score=score,
                reward_points=reward,
                elapsed_seconds=final_elapsed,
            )
            update_arm(
                conn,
                f"{subject}:{'flashcard_review' if game == 'Flashcard Recall' else 'speed_round' if game == 'Speed Round' else 'quiz_' + difficulty}",
                1.0 if correct else 0.2,
            )
            st.session_state["game_finished"] = True
            st.session_state["game_last_elapsed"] = final_elapsed
            st.session_state.pop("game_started_at", None)
            if correct:
                st.success(f"Correct. +{reward} points. Time: {final_elapsed} seconds.")
            else:
                st.warning(f"Review needed. Correct answer: {quiz['correct_answer']}. +{reward} effort points. Time: {final_elapsed} seconds.")
            st.caption(quiz["explanation"])
            st.rerun()

    timed_game_fragment()


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
        "Move between Anish's lectures, checkpoint quizzes, mini-games, surveys, signup options, and personalized AI recommendations.",
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
        tabs = st.tabs(["Watch + quizzes", "Mini-games", "Surveys", "Signup"])
        with tabs[0]:
            render_video_and_quizzes(student_id)
        with tabs[1]:
            render_mini_games(student_id)
        with tabs[2]:
            render_surveys(student_id)
        with tabs[3]:
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
        "Upload lecture recordings, build checkpoint assessments, manage communications, and monitor learning analytics.",
    )
    passcode = st.text_input("Admin passcode", type="password")
    if passcode != ADMIN_PASSCODE:
        st.info("Enter the admin passcode. Demo default is `change-me`; set ANISH_ADMIN_PASSCODE before sharing.")
        return
    tabs = st.tabs(["Dashboard", "Content Studio", "Communications", "AI Insights"])
    with tabs[0]:
        admin_dashboard()
    with tabs[1]:
        admin_content_studio()
    with tabs[2]:
        admin_communications()
    with tabs[3]:
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
