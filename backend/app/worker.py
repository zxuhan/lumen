from arq.connections import RedisSettings

from app.config import get_settings
from app.tasks import TASKS

settings = get_settings()


class WorkerSettings:
    """ARQ worker entry point. Register new async tasks in app.tasks.TASKS."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = TASKS
    max_jobs = 4
    job_timeout = 300
    keep_result = 3600
