import time

import schedule

from app.flask.main import create_app
from app.modules.search.backend import SearchBackend


def index():
    print("Indexing...")
    app = create_app()
    with app.app_context():
        backend = SearchBackend()
        backend.index_all()


def scheduler():
    print("Starting scheduler")
    schedule.every().hour.do(index)

    while True:
        print("Scheduling")
        schedule.run_pending()
        time.sleep(60)
