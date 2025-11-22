import threading
from sqlalchemy import select

from alfred.task.vault.models import TodoTemplate
from alfred.task.vault import get_vault

# test db in config.test.yaml, if you want to test with other db, change the config.test.yaml path


def test_write_and_read_basic():
    # simple write
    vault = get_vault()
    with vault.db as session:
        template = TodoTemplate(
            user_id="1", content="t1", cron="* * * * *", ddl_offset="5m", run_once=False
        )
        session.add(template)

    with vault.db as session:
        rows = session.execute(select(TodoTemplate)).scalars().all()
    assert rows and len(rows) == 1


def test_context_transaction_commit():
    vault = get_vault()
    with vault.db as session:
        session.add(
            TodoTemplate(
                user_id="2",
                content="t2",
                cron="* * * * *",
                ddl_offset="5m",
                run_once=False,
            )
        )
        session.add(
            TodoTemplate(
                user_id="3",
                content="t3",
                cron="* * * * *",
                ddl_offset="5m",
                run_once=False,
            )
        )

    with vault.db as session:
        rows = (
            session.execute(select(TodoTemplate).order_by(TodoTemplate.id))
            .scalars()
            .all()
        )
    assert rows and len(rows) == 2


def test_context_transaction_rollback_on_error():
    vault = get_vault()
    try:
        with vault.db as session:
            session.add(
                TodoTemplate(
                    user_id="4",
                    content="t4",
                    cron="* * * * *",
                    ddl_offset="5m",
                    run_once=False,
                )
            )
            # cause an error: flush with invalid data or explicit raise
            # SQLAlchemy usually flushes on commit, so we can force an error
            raise Exception("Force rollback")
    except Exception:
        pass

    with vault.db as session:
        rows = session.execute(select(TodoTemplate)).scalars().all()
    # transaction should have been rolled back
    assert not rows


def test_concurrent_writes():
    vault = get_vault()
    def worker(i):
        for j in range(10):
            with vault.db as session:
                session.add(
                    TodoTemplate(
                        user_id=str(i),
                        content=f"t{i}-{j}",
                        cron="* * * * *",
                        ddl_offset="5m",
                        run_once=False,
                    )
                )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with vault.db as session:
        rows = session.execute(select(TodoTemplate)).scalars().all()
    assert rows and len(rows) == 4 * 10


def test_fetch_all():
    # insert sample data
    vault = get_vault()
    with vault.db as session:
        session.add(
            TodoTemplate(
                user_id="1",
                content="t1",
                cron="* * * * *",
                ddl_offset="5m",
                run_once=False,
            )
        )
        session.add(
            TodoTemplate(
                user_id="2",
                content="t2",
                cron="* * * * *",
                ddl_offset="10m",
                run_once=True,
            )
        )

    with vault.db as session:
        all_data = session.execute(select(TodoTemplate)).scalars().all()
    assert all_data and len(all_data) == 2
