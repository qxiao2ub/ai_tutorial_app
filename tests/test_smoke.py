from pathlib import Path
import tempfile

from src.ai_models import build_engagement_dataset, train_all_models
from src.database import connect, init_db, seed_demo_data


def test_database_and_models_smoke():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        conn = connect(db)
        init_db(conn)
        seed_demo_data(conn)
        dataset = build_engagement_dataset(conn)
        assert not dataset.empty
        results = train_all_models(dataset)
        assert "mastery_dnn_mlp" in results
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(game_events)").fetchall()}
        assert "elapsed_seconds" in columns
        conn.close()


def test_usage_counter_never_returns_zero_on_service_failure(monkeypatch):
    from src import usage_counter

    monkeypatch.setattr(usage_counter, "_request_json", lambda url: None)
    count, remote_ok = usage_counter.increment_visit()
    assert count >= 1
    assert remote_ok is False


def test_usage_counter_floor_and_value_parsing(monkeypatch):
    from src import usage_counter

    monkeypatch.setattr(usage_counter, "_request_json", lambda url: {"value": 17})
    count, remote_ok = usage_counter.increment_visit()
    assert count == 17
    assert remote_ok is True


def test_streamlit_revision_requirements():
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    text = app.read_text(encoding="utf-8")
    assert "Watch-time logger" not in text
    assert "Log watch time" not in text
    assert "Message Anish" not in text
    assert "Start this quiz" in text
    assert 'st.fragment(run_every="1s")' in text
    assert "elapsed_seconds=final_elapsed" in text
