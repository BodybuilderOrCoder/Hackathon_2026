import json
import time
from datetime import datetime

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import OptimizationRun
from .services.optimizer import optimize


def run_once() -> bool:
    with SessionLocal() as db:
        job = db.scalar(select(OptimizationRun).where(OptimizationRun.status == "QUEUED").order_by(OptimizationRun.created_at).with_for_update(skip_locked=True))
        if not job: return False
        job.status="RUNNING";job.progress=5;job.started_at=datetime.utcnow();db.commit()
        try:
            config=json.loads(job.config_json)
            result=optimize(db,job.id,job.organization_id,job.created_by_id,config)
            job=db.get(OptimizationRun,job.id);job.status="SUCCEEDED";job.progress=100;job.result_json=json.dumps(result,ensure_ascii=False);job.finished_at=datetime.utcnow();db.commit()
        except Exception as exc:
            job=db.get(OptimizationRun,job.id);job.status="FAILED";job.error_message=str(exc)[:1500];job.finished_at=datetime.utcnow();db.commit()
        return True


def main():
    init_db()
    while True:
        if not run_once(): time.sleep(1)


if __name__ == "__main__": main()
