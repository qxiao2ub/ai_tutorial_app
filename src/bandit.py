from __future__ import annotations

import math
import random
import sqlite3
from dataclasses import dataclass

from .utils import now_iso

DEFAULT_ACTIVITIES = [
    "quiz_easy",
    "quiz_medium",
    "quiz_hard",
    "flashcard_review",
    "speed_round",
    "video_rewatch",
]


@dataclass
class BanditArm:
    arm: str
    count: int
    value: float


def ensure_bandit_arms(conn: sqlite3.Connection, subjects: list[str] | None = None) -> None:
    subjects = subjects or ["General"]
    for subject in subjects:
        for activity in DEFAULT_ACTIVITIES:
            arm = f"{subject}:{activity}"
            conn.execute(
                """
                INSERT OR IGNORE INTO bandit_state(arm, count, value, updated_at)
                VALUES (?, 0, 0.0, ?)
                """,
                (arm, now_iso()),
            )
    conn.commit()


def load_arms(conn: sqlite3.Connection, subject: str | None = None) -> list[BanditArm]:
    if subject:
        rows = conn.execute(
            "SELECT arm, count, value FROM bandit_state WHERE arm LIKE ? ORDER BY arm",
            (f"{subject}:%",),
        ).fetchall()
    else:
        rows = conn.execute("SELECT arm, count, value FROM bandit_state ORDER BY arm").fetchall()
    return [BanditArm(row["arm"], int(row["count"]), float(row["value"])) for row in rows]


def choose_arm(conn: sqlite3.Connection, subject: str = "General", epsilon: float = 0.15) -> str:
    ensure_bandit_arms(conn, [subject])
    arms = load_arms(conn, subject)
    if not arms:
        ensure_bandit_arms(conn, [subject])
        arms = load_arms(conn, subject)
    if random.random() < epsilon:
        return random.choice(arms).arm
    total_count = sum(max(a.count, 1) for a in arms)
    # UCB-style exploration on top of incremental average reward.
    scored = []
    for arm in arms:
        exploration = math.sqrt(2 * math.log(total_count + 1) / max(arm.count, 1))
        scored.append((arm.value + exploration, arm.arm))
    return max(scored)[1]


def update_arm(conn: sqlite3.Connection, arm: str, reward: float) -> None:
    row = conn.execute("SELECT count, value FROM bandit_state WHERE arm = ?", (arm,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO bandit_state(arm, count, value, updated_at) VALUES (?, 0, 0.0, ?)",
            (arm, now_iso()),
        )
        count, value = 0, 0.0
    else:
        count, value = int(row["count"]), float(row["value"])
    new_count = count + 1
    new_value = value + (float(reward) - value) / new_count
    conn.execute(
        "UPDATE bandit_state SET count = ?, value = ?, updated_at = ? WHERE arm = ?",
        (new_count, new_value, now_iso(), arm),
    )
    conn.commit()


def bandit_summary(conn: sqlite3.Connection):
    import pandas as pd

    return pd.read_sql_query(
        "SELECT arm, count, ROUND(value, 3) AS estimated_reward FROM bandit_state ORDER BY estimated_reward DESC, count DESC",
        conn,
    )
