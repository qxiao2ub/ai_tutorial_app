from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "watch_minutes",
    "watch_sessions",
    "quiz_attempts",
    "quiz_accuracy",
    "survey_satisfaction",
    "game_points",
]


@dataclass
class ModelResult:
    name: str
    status: str
    accuracy: float | None
    report: str
    predictions: pd.DataFrame


def _read(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)


def build_engagement_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    students = _read(conn, "SELECT student_id, name, email FROM students")
    lectures = _read(conn, "SELECT lecture_id, subject, title FROM lectures")
    if students.empty or lectures.empty:
        return pd.DataFrame(columns=["student_id", "name", "subject"] + FEATURE_COLUMNS)

    watch = _read(
        conn,
        """
        SELECT w.student_id, l.subject,
               SUM(w.session_seconds) / 60.0 AS watch_minutes,
               COUNT(*) AS watch_sessions
        FROM watch_events w
        JOIN lectures l ON l.lecture_id = w.lecture_id
        GROUP BY w.student_id, l.subject
        """,
    )
    quiz = _read(
        conn,
        """
        SELECT qa.student_id, q.subject,
               COUNT(*) AS quiz_attempts,
               AVG(qa.correct) AS quiz_accuracy
        FROM quiz_attempts qa
        JOIN quizzes q ON q.quiz_id = qa.quiz_id
        GROUP BY qa.student_id, q.subject
        """,
    )
    surveys = _read(
        conn,
        """
        SELECT sr.student_id, l.subject,
               AVG(sr.satisfaction_score) AS survey_satisfaction
        FROM survey_responses sr
        JOIN lectures l ON l.lecture_id = sr.lecture_id
        GROUP BY sr.student_id, l.subject
        """,
    )
    games = _read(
        conn,
        """
        SELECT student_id, subject, SUM(reward_points) AS game_points
        FROM game_events
        GROUP BY student_id, subject
        """,
    )

    subjects = lectures[["subject"]].drop_duplicates()
    base = students.assign(key=1).merge(subjects.assign(key=1), on="key").drop(columns="key")
    for frame, keys in [(watch, ["student_id", "subject"]), (quiz, ["student_id", "subject"]), (surveys, ["student_id", "subject"]), (games, ["student_id", "subject"])] :
        if not frame.empty:
            base = base.merge(frame, on=keys, how="left")

    for col in FEATURE_COLUMNS:
        if col not in base:
            base[col] = 0
        base[col] = base[col].fillna(0)

    # Labels for demo ML. In production, labels should be validated by Anish or based on explicit outcomes.
    base["preferred_subject"] = 0
    for sid, group in base.groupby("student_id"):
        if group["watch_minutes"].max() > 0:
            idx = group["watch_minutes"].idxmax()
            base.loc[idx, "preferred_subject"] = 1

    base["at_risk"] = ((base["watch_minutes"] < base["watch_minutes"].median()) & (base["quiz_accuracy"] < 0.55)).astype(int)
    base["mastery"] = ((base["quiz_accuracy"] >= 0.70) & (base["watch_minutes"] >= base["watch_minutes"].median())).astype(int)
    base["engagement_score"] = (
        base["watch_minutes"].rank(pct=True) * 0.35
        + base["quiz_accuracy"].rank(pct=True) * 0.35
        + base["game_points"].rank(pct=True) * 0.15
        + base["survey_satisfaction"].rank(pct=True) * 0.15
    ).round(3)
    return base


def strength_weakness_summary(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if dataset.empty:
        empty = pd.DataFrame(columns=["subject", "quiz_accuracy", "watch_minutes", "students", "interpretation"])
        return empty, empty
    by_subject = (
        dataset.groupby("subject", as_index=False)
        .agg(
            quiz_accuracy=("quiz_accuracy", "mean"),
            watch_minutes=("watch_minutes", "mean"),
            students=("student_id", "nunique"),
            engagement_score=("engagement_score", "mean"),
        )
        .sort_values("quiz_accuracy", ascending=False)
    )
    by_subject["quiz_accuracy"] = by_subject["quiz_accuracy"].round(3)
    by_subject["watch_minutes"] = by_subject["watch_minutes"].round(1)
    by_subject["engagement_score"] = by_subject["engagement_score"].round(3)
    strongest = by_subject.head(3).copy()
    weakest = by_subject.tail(3).sort_values("quiz_accuracy").copy()
    strongest["interpretation"] = "Relative strength: keep challenging students with higher-level practice."
    weakest["interpretation"] = "Potential weakness: add review clips, simpler examples, or more checkpoint questions."
    return strongest, weakest


def _train_classifier(dataset: pd.DataFrame, label: str, model, name: str) -> ModelResult:
    if dataset.empty or len(dataset) < 8:
        return ModelResult(name, "Need at least 8 student-subject rows before training.", None, "", pd.DataFrame())
    y = dataset[label].astype(int)
    if y.nunique() < 2:
        return ModelResult(name, f"Need both positive and negative examples for {label}.", None, "", pd.DataFrame())
    X = dataset[FEATURE_COLUMNS].astype(float)
    test_size = 0.30 if len(dataset) >= 12 else 0.25
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, dataset.index, test_size=test_size, random_state=42, stratify=y if y.value_counts().min() >= 2 else None
    )
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    proba = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_test)[:, 1]
    report = classification_report(y_test, pred, zero_division=0)
    pred_df = dataset.loc[idx_test, ["student_id", "name", "subject"] + FEATURE_COLUMNS].copy()
    pred_df[f"actual_{label}"] = y_test.values
    pred_df[f"predicted_{label}"] = pred
    if proba is not None:
        pred_df[f"prob_{label}"] = np.round(proba, 3)
    return ModelResult(name, "trained", float(accuracy_score(y_test, pred)), report, pred_df)


def train_all_models(dataset: pd.DataFrame) -> dict[str, ModelResult]:
    models = {
        "preference_logistic_regression": _train_classifier(
            dataset,
            "preferred_subject",
            Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=42))]),
            "Subject preference logistic regression",
        ),
        "at_risk_random_forest": _train_classifier(
            dataset,
            "at_risk",
            RandomForestClassifier(n_estimators=120, min_samples_leaf=2, random_state=42),
            "At-risk random forest",
        ),
        "mastery_dnn_mlp": _train_classifier(
            dataset,
            "mastery",
            Pipeline([("scale", StandardScaler()), ("clf", MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=700, random_state=42))]),
            "Deep-neural-network style MLP mastery classifier",
        ),
    }
    return models


def student_recommendations(conn: sqlite3.Connection, student_id: str) -> pd.DataFrame:
    dataset = build_engagement_dataset(conn)
    if dataset.empty:
        return pd.DataFrame(columns=["subject", "recommendation", "reason"])
    student = dataset[dataset["student_id"] == student_id].copy()
    if student.empty:
        return pd.DataFrame(columns=["subject", "recommendation", "reason"])
    rows = []
    for _, row in student.sort_values("quiz_accuracy").iterrows():
        if row["quiz_attempts"] == 0:
            rec = "Try the first checkpoint quiz."
            reason = "No quiz attempts yet."
        elif row["quiz_accuracy"] < 0.55:
            rec = "Review the lecture segment and play an easy practice game."
            reason = f"Quiz accuracy is {row['quiz_accuracy']:.0%}."
        elif row["watch_minutes"] < student["watch_minutes"].median():
            rec = "Watch more of Anish's lecture before moving to harder questions."
            reason = f"Watch time is {row['watch_minutes']:.1f} minutes."
        else:
            rec = "Move to medium or hard challenge questions."
            reason = "Engagement and accuracy look solid."
        rows.append({"subject": row["subject"], "recommendation": rec, "reason": reason})
    return pd.DataFrame(rows)


def suggest_reply(conn: sqlite3.Connection, question: str, lecture_id: str | None = None) -> str:
    if not question.strip():
        return ""
    terms = {t.lower().strip(".,?!;:") for t in question.split() if len(t) > 3}
    if not terms:
        return "Ask Anish to clarify the exact lecture timestamp or concept."
    query = "SELECT question, explanation FROM quizzes"
    params: tuple[Any, ...] = ()
    if lecture_id:
        query += " WHERE lecture_id = ?"
        params = (lecture_id,)
    quiz_df = _read(conn, query, params)
    best_score = 0
    best = None
    for _, row in quiz_df.iterrows():
        haystack = f"{row['question']} {row['explanation']}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score > best_score:
            best_score = score
            best = row
    if best is not None and best_score > 0:
        return (
            "Possible Anish reply draft: "
            + str(best["explanation"])
            + " Please connect this back to the lecture example and ask the student where they got stuck."
        )
    return "Possible Anish reply draft: Ask the student for the lecture timestamp, restate the concept, and give one short example before assigning one practice question."
