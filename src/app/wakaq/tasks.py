import inspect
from datetime import timedelta

from loguru import logger
from wakaq import WakaQ, CronTask

from app.flask.main import create_app
from app.modules.search.backend import SearchBackend

Q_DEFAULT = 'default-lowest-priority-queue'

wakaq = WakaQ(
    queues=[
        Q_DEFAULT,
    ],

    # concurrency="cores*4",
    concurrency=2,
    async_concurrency=0,
    soft_timeout=30,  # seconds
    hard_timeout=timedelta(minutes=1),
    max_retries=3,
    max_mem_percent=98,
    max_tasks_per_worker=5000,

    schedules=[
        CronTask(schedule='* * * * *', task_name='index', queue=Q_DEFAULT),
    ],
    #scheduler_log_file="logs/scheduler.log",
    #worker_log_file="logs/worker.log",
)

global_app = None


@wakaq.wrap_tasks_with
async def custom_task_decorator(fn, args, kwargs):
    global global_app
    if global_app is None:
        global_app = create_app()

    with global_app.app_context():
        if inspect.iscoroutinefunction(fn):
            await fn(*args, **kwargs)
        else:
            fn(*args, **kwargs)


@wakaq.task
def index():
    print("Indexing...")
    logger.info("Indexing...")

    backend = SearchBackend()
    backend.index_all()
