# app/utils/db_events.py
from sqlalchemy import event
from .logger import DBLogger
import time

def setup_db_events(db):
    @event.listens_for(db.engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())
        DBLogger.debug("SQL: %s" % statement)
        DBLogger.debug("Parameters: %r" % (parameters,))

    @event.listens_for(db.engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info['query_start_time'].pop(-1)
        DBLogger.debug("Query Time: %.3f" % total)
        # Log slower queries with more detail
        if total > 0.5:  # Log queries taking more than 500ms
            DBLogger.warning(f"Slow Query ({total:.3f}s): {statement}")
        else:
            DBLogger.info(f"SQL: {statement}")