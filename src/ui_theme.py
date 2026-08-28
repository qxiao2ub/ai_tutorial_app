from __future__ import annotations

import html

import streamlit as st

from src.config import APP_NAME, AUTHOR_NAME, MENTOR_NAME


DEEP_SPACE_CSS = r"""
<style>
:root {
  --space-bg: #07111f;
  --space-bg-2: #0a1628;
  --space-card: rgba(15, 29, 49, 0.92);
  --space-card-soft: rgba(16, 34, 56, 0.76);
  --space-border: rgba(148, 163, 184, 0.16);
  --space-text: #e7eef8;
  --space-muted: #8ea0b8;
  --accent-cyan: #22d3ee;
  --accent-cyan-2: #67e8f9;
  --accent-violet: #8b5cf6;
  --accent-green: #34d399;
  --accent-amber: #fbbf24;
}

html, body, [class*="css"] {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.stApp {
  color: var(--space-text);
  background:
    radial-gradient(circle at 77% 4%, rgba(34, 211, 238, 0.10), transparent 28rem),
    radial-gradient(circle at 25% 18%, rgba(139, 92, 246, 0.08), transparent 31rem),
    linear-gradient(135deg, #07111f 0%, #081426 48%, #06101d 100%);
}

[data-testid="stHeader"] {
  background: rgba(7, 17, 31, 0.70);
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  backdrop-filter: blur(14px);
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #07111f 0%, #091526 58%, #07111f 100%);
  border-right: 1px solid rgba(148, 163, 184, 0.10);
}

[data-testid="stSidebar"] > div:first-child {
  padding-top: 1.6rem;
}

[data-testid="stSidebar"] hr,
hr {
  border-color: rgba(148, 163, 184, 0.13) !important;
}

.block-container {
  max-width: 1280px;
  padding-top: 2.2rem;
  padding-bottom: 4rem;
}

h1, h2, h3, h4 {
  letter-spacing: -0.025em;
  color: #f8fbff !important;
}

p, label, .stCaption, [data-testid="stCaptionContainer"] {
  color: #a6b5c9;
}

/* Buttons */
.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {
  border-radius: 999px !important;
  border: 1px solid rgba(34, 211, 238, 0.35) !important;
  background: linear-gradient(135deg, rgba(34, 211, 238, 0.18), rgba(139, 92, 246, 0.16)) !important;
  color: #ecfeff !important;
  font-weight: 700 !important;
  min-height: 2.7rem;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.02), 0 12px 30px rgba(0,0,0,0.18);
  transition: all 160ms ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px);
  border-color: rgba(103, 232, 249, 0.70) !important;
  box-shadow: 0 0 26px rgba(34, 211, 238, 0.12), 0 14px 36px rgba(0,0,0,0.22);
}

/* Inputs */
[data-baseweb="input"] > div,
[data-baseweb="textarea"] > div,
[data-baseweb="select"] > div,
.stNumberInput > div > div,
.stTextInput > div > div,
.stTextArea > div > div {
  background: rgba(8, 20, 36, 0.88) !important;
  border-color: rgba(148, 163, 184, 0.16) !important;
  border-radius: 12px !important;
}

input, textarea {
  color: #e7eef8 !important;
}

/* Radio navigation */
[data-testid="stSidebar"] [role="radiogroup"] {
  gap: 0.35rem;
}
[data-testid="stSidebar"] [role="radiogroup"] label {
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 0.55rem 0.65rem;
  transition: all 140ms ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  background: rgba(255,255,255,0.035);
  border-color: rgba(148, 163, 184, 0.10);
}
[data-testid="stSidebar"] [data-baseweb="radio"] div:first-child {
  border-color: rgba(148, 163, 184, 0.45);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.35rem;
  background: rgba(7, 17, 31, 0.50);
  padding: 0.35rem;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.10);
}
.stTabs [data-baseweb="tab"] {
  border-radius: 10px;
  color: #92a5bd;
  font-weight: 650;
  padding-left: 1rem;
  padding-right: 1rem;
}
.stTabs [aria-selected="true"] {
  background: rgba(34, 211, 238, 0.09);
  color: #c9f8ff !important;
}
.stTabs [data-baseweb="tab-highlight"] {
  background-color: var(--accent-cyan) !important;
}

/* Metric / cards / expanders */
[data-testid="stMetric"] {
  background: linear-gradient(145deg, rgba(16, 34, 56, 0.86), rgba(9, 23, 41, 0.88));
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  box-shadow: 0 16px 34px rgba(0,0,0,0.14);
}
[data-testid="stMetricValue"] {
  color: #f8fbff;
}
[data-testid="stMetricLabel"] {
  color: #8294ad;
}

[data-testid="stExpander"] {
  background: linear-gradient(145deg, rgba(15, 29, 49, 0.86), rgba(8, 20, 36, 0.90));
  border: 1px solid rgba(148, 163, 184, 0.12) !important;
  border-radius: 16px !important;
  overflow: hidden;
}

[data-testid="stDataFrame"], [data-testid="stTable"] {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.10);
}

[data-testid="stAlert"] {
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.13);
}

/* Custom UI adapted from the supplied deep-space React design */
.aai-brand-shell {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.13);
  border-radius: 26px;
  padding: 1.55rem 1.7rem;
  margin-bottom: 1.4rem;
  background:
    radial-gradient(circle at 92% 10%, rgba(34, 211, 238, 0.15), transparent 14rem),
    radial-gradient(circle at 72% 115%, rgba(139, 92, 246, 0.18), transparent 18rem),
    linear-gradient(135deg, rgba(18, 38, 62, 0.96), rgba(8, 20, 36, 0.94));
  box-shadow: 0 24px 65px rgba(0,0,0,0.18);
}
.aai-brand-shell::after {
  content: "";
  position: absolute;
  width: 280px;
  height: 280px;
  right: -90px;
  bottom: -170px;
  border: 1px solid rgba(34, 211, 238, 0.25);
  border-radius: 50%;
  box-shadow: 0 0 0 45px rgba(255,255,255,0.018), 0 0 0 90px rgba(34,211,238,0.018);
}
.aai-brand-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}
.aai-logo-orb {
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-weight: 900;
  font-size: 1.1rem;
  color: #04131c;
  background: linear-gradient(135deg, #67e8f9, #22d3ee 48%, #8b5cf6 115%);
  box-shadow: 0 0 28px rgba(34, 211, 238, 0.22);
}
.aai-kicker {
  color: #67e8f9;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.70rem;
  font-weight: 800;
  margin-bottom: 0.3rem;
}
.aai-brand-title {
  color: #ffffff;
  font-size: clamp(1.65rem, 3.2vw, 2.7rem);
  font-weight: 850;
  line-height: 1.05;
  letter-spacing: -0.04em;
  margin: 0;
}
.aai-brand-subtitle {
  margin-top: 0.7rem;
  max-width: 790px;
  color: #9fb0c5;
  font-size: 0.96rem;
  line-height: 1.55;
}
.aai-credit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 1rem;
}
.aai-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid rgba(148,163,184,0.16);
  border-radius: 999px;
  background: rgba(255,255,255,0.035);
  color: #dce7f5;
  padding: 0.38rem 0.72rem;
  font-size: 0.78rem;
  font-weight: 650;
}
.aai-chip.cyan { border-color: rgba(34,211,238,0.24); color: #b8f4fb; }
.aai-chip.violet { border-color: rgba(139,92,246,0.28); color: #ddd2ff; }

.aai-sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0.2rem 0 0.8rem;
}
.aai-sidebar-dot {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #22d3ee, #8b5cf6);
  box-shadow: 0 0 20px rgba(34,211,238,.25);
}
.aai-sidebar-name {
  color: white;
  font-weight: 850;
  letter-spacing: 0.08em;
  font-size: 0.95rem;
}
.aai-sidebar-card {
  background: linear-gradient(145deg, rgba(34,211,238,.07), rgba(139,92,246,.08));
  border: 1px solid rgba(148,163,184,.13);
  border-radius: 14px;
  padding: 0.8rem 0.85rem;
  margin-bottom: 1.05rem;
}
.aai-sidebar-card .label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: #6fe9f8;
  font-weight: 800;
  margin-bottom: 0.35rem;
}
.aai-sidebar-card .person {
  color: #e8f2ff;
  font-size: 0.82rem;
  line-height: 1.65;
}

.aai-hero {
  position: relative;
  overflow: hidden;
  min-height: 220px;
  border-radius: 24px;
  border: 1px solid rgba(148,163,184,.12);
  background:
    radial-gradient(circle at 94% 72%, rgba(34,211,238,.16), transparent 18rem),
    linear-gradient(145deg, rgba(15,32,54,.95), rgba(7,18,32,.96));
  padding: 1.6rem 1.7rem;
  margin: 0.8rem 0 1.2rem;
}
.aai-hero::before, .aai-hero::after {
  content: "";
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(34,211,238,.18);
  pointer-events: none;
}
.aai-hero::before { width: 230px; height: 230px; right: -55px; bottom: -85px; }
.aai-hero::after { width: 160px; height: 160px; right: -20px; bottom: -50px; border-color: rgba(139,92,246,.17); }
.aai-hero .eyebrow {
  display: inline-block;
  padding: .32rem .60rem;
  border-radius: 999px;
  border: 1px solid rgba(34,211,238,.22);
  background: rgba(34,211,238,.08);
  color: #67e8f9;
  font-size: .66rem;
  text-transform: uppercase;
  letter-spacing: .12em;
  font-weight: 800;
}
.aai-hero h2 {
  margin: .65rem 0 .45rem;
  max-width: 720px;
  font-size: clamp(1.55rem, 3vw, 2.35rem);
  color: white !important;
}
.aai-hero p {
  max-width: 720px;
  margin: 0;
  color: #9bacc1;
}
.aai-hero .statrow {
  display: flex;
  flex-wrap: wrap;
  gap: .55rem;
  margin-top: 1rem;
}
.aai-hero .stat {
  color: #dbe8f7;
  border: 1px solid rgba(148,163,184,.13);
  background: rgba(255,255,255,.03);
  border-radius: 10px;
  padding: .45rem .65rem;
  font-size: .76rem;
}

.aai-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0,1fr));
  gap: 0.9rem;
  margin: 0.5rem 0 1.35rem;
}
.aai-feature-card {
  border-radius: 18px;
  border: 1px solid rgba(148,163,184,.12);
  background: linear-gradient(145deg, rgba(15,31,52,.90), rgba(9,22,38,.90));
  padding: 1rem 1.05rem;
  min-height: 132px;
  box-shadow: 0 15px 32px rgba(0,0,0,.12);
}
.aai-feature-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(34,211,238,.09);
  border: 1px solid rgba(34,211,238,.17);
  margin-bottom: .65rem;
}
.aai-feature-card:nth-child(2) .aai-feature-icon { background: rgba(139,92,246,.10); border-color: rgba(139,92,246,.20); }
.aai-feature-card:nth-child(3) .aai-feature-icon { background: rgba(52,211,153,.09); border-color: rgba(52,211,153,.18); }
.aai-feature-card h4 { margin: 0 0 .32rem; font-size: .96rem; }
.aai-feature-card p { margin: 0; color: #8397b1; font-size: .80rem; line-height: 1.5; }

.aai-workspace-banner {
  border: 1px solid rgba(148,163,184,.12);
  background: linear-gradient(145deg, rgba(15,31,52,.90), rgba(8,20,36,.90));
  border-radius: 20px;
  padding: 1rem 1.15rem;
  margin: .45rem 0 1rem;
}
.aai-workspace-banner .kicker { color: #67e8f9; font-size: .68rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
.aai-workspace-banner h3 { margin: .25rem 0 .25rem; font-size: 1.35rem; }
.aai-workspace-banner p { margin: 0; color: #8fa2ba; font-size: .86rem; }

@media (max-width: 900px) {
  .aai-card-grid { grid-template-columns: 1fr; }
  .aai-brand-shell { padding: 1.25rem 1.2rem; }
  .aai-brand-row { gap: .75rem; }
  .aai-logo-orb { width: 42px; height: 42px; flex-basis: 42px; border-radius: 13px; }
}
</style>
"""


def inject_theme() -> None:
    st.markdown(DEEP_SPACE_CSS, unsafe_allow_html=True)


def render_app_header() -> None:
    st.markdown(
        f"""
        <div class="aai-brand-shell">
          <div class="aai-brand-row">
            <div class="aai-logo-orb">AI</div>
            <div>
              <div class="aai-kicker">AI-powered learning dashboard</div>
              <div class="aai-brand-title">{html.escape(APP_NAME)}</div>
              <div class="aai-brand-subtitle">
                Learn through Anish's lecture recordings, checkpoint quizzes, surveys, reward-based mini-games,
                direct messaging, and adaptive AI learning analytics.
              </div>
              <div class="aai-credit-row">
                <span class="aai-chip cyan">Author &amp; Lecturer · {html.escape(AUTHOR_NAME)}</span>
                <span class="aai-chip violet">Mentor · {html.escape(MENTOR_NAME)}</span>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_identity() -> None:
    st.markdown(
        f"""
        <div class="aai-sidebar-brand">
          <div class="aai-sidebar-dot"></div>
          <div class="aai-sidebar-name">ANISH AI</div>
        </div>
        <div class="aai-sidebar-card">
          <div class="label">Project Team</div>
          <div class="person"><strong>Author / Lecturer</strong><br>{html.escape(AUTHOR_NAME)}</div>
          <div class="person" style="margin-top:.45rem"><strong>Mentor</strong><br>{html.escape(MENTOR_NAME)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_student_hero(student_name: str, points: int = 0) -> None:
    name = html.escape(student_name or "Student")
    if points >= 300:
        rank = "Nova Tier"
    elif points >= 150:
        rank = "Quark Tier"
    elif points >= 50:
        rank = "Neutron Tier"
    else:
        rank = "Photon Tier"
    st.markdown(
        f"""
        <div class="aai-hero">
          <span class="eyebrow">Learning Path · Up Next</span>
          <h2>Welcome back, {name}. Keep building momentum.</h2>
          <p>Continue a lecture, answer checkpoint questions, play a mini-game, or use your personalized recommendations to choose the best next activity.</p>
          <div class="statrow">
            <span class="stat">Current Rank · <strong>{rank}</strong></span>
            <span class="stat">Reward Points · <strong>{int(points)}</strong></span>
            <span class="stat">AI Mode · <strong>Adaptive</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="aai-card-grid">
          <div class="aai-feature-card">
            <div class="aai-feature-icon">▶</div>
            <h4>Lecture Library</h4>
            <p>Watch Anish's recordings and answer timestamped checkpoint quizzes while you learn.</p>
          </div>
          <div class="aai-feature-card">
            <div class="aai-feature-icon">✦</div>
            <h4>Challenge & Rewards</h4>
            <p>Practice with mini-games, earn points and badges, and identify topics that need more review.</p>
          </div>
          <div class="aai-feature-card">
            <div class="aai-feature-icon">AI</div>
            <h4>Adaptive Analytics</h4>
            <p>Machine learning, neural-network models, and reinforcement learning turn activity data into next-step recommendations.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_workspace_banner(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="aai-workspace-banner">
          <div class="kicker">{html.escape(kicker)}</div>
          <h3>{html.escape(title)}</h3>
          <p>{html.escape(description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
