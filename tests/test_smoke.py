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
        conn.close()
