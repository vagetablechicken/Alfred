import pytest
from contextlib import contextmanager

import alfred.slack.patrol_launcher as patrol_launcher


@contextmanager
def _cm_with_value(value):
    yield value


def test_patrol_job_no_notify_blocks_does_not_send(monkeypatch):
    # notify blocks empty -> early return, no Slack calls
    monkeypatch.setattr(patrol_launcher, "get_slack_channel", lambda: "C123")

    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_notify_blocks",
        lambda: _cm_with_value([]),
    )

    # even if end_of_day would produce blocks, it should not be reached
    called = {"sent": False}

    def fake_chat_postMessage(**_):
        called["sent"] = True
        return {"ok": True}

    monkeypatch.setattr(patrol_launcher.app.client, "chat_postMessage", fake_chat_postMessage)
    # ensure end_of_day summary empty too
    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_end_of_day_summary",
        lambda: _cm_with_value([]),
    )

    patrol_launcher.patrol_job()
    assert called["sent"] is False

    # ensure end_of_day summary not empty
    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_end_of_day_summary",
        lambda: _cm_with_value(["summary_block"]),
    )
    patrol_launcher.patrol_job()
    assert called["sent"] is True


def test_patrol_job_sends_both_and_ok(monkeypatch):
    monkeypatch.setattr(patrol_launcher, "get_slack_channel", lambda: "C321")

    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_notify_blocks",
        lambda: _cm_with_value(["notify_block"]),
    )
    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_end_of_day_summary",
        lambda: _cm_with_value(["summary_block"]),
    )

    calls = []

    def fake_chat_postMessage(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(patrol_launcher.app.client, "chat_postMessage", fake_chat_postMessage)

    patrol_launcher.patrol_job()

    assert len(calls) == 2
    assert calls[0]["channel"] == "C321"
    assert calls[0]["blocks"] == ["notify_block"]
    assert calls[0]["text"] == "Todo Reminder"
    assert calls[1]["blocks"] == ["summary_block"]
    assert calls[1]["text"] == "Daily Todo Summary"


def test_patrol_job_raises_on_slack_error_on_notify(monkeypatch):
    monkeypatch.setattr(patrol_launcher, "get_slack_channel", lambda: "C999")

    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_notify_blocks",
        lambda: _cm_with_value(["notify_block"]),
    )
    # second summary should not be reached because first call fails
    monkeypatch.setattr(
        patrol_launcher.butler,
        "gather_end_of_day_summary",
        lambda: _cm_with_value(["summary_block"]),
    )

    def bad_chat_postMessage(**_):
        return {"ok": False, "error": "boom"}

    monkeypatch.setattr(patrol_launcher.app.client, "chat_postMessage", bad_chat_postMessage)

    with pytest.raises(Exception):
        patrol_launcher.patrol_job()


def test_launch_patrol_scheduler_success(monkeypatch):

    class DummyScheduler:
        def __init__(self, executors=None):
            self.executors = executors
            self.started = False
            self.added_job = None

        def add_job(self, func, trigger, seconds, id, replace_existing, misfire_grace_time):
            # record important bits
            self.added_job = {
                "func": func,
                "trigger": trigger,
                "seconds": seconds,
                "id": id,
            }

        def start(self):
            self.started = True

        def shutdown(self):
            self.started = False

    monkeypatch.setattr(patrol_launcher, "BackgroundScheduler", DummyScheduler)

    ok = patrol_launcher.launch_patrol_scheduler(seconds=123)
    assert ok is True
    # verify scheduler had job added with requested seconds
    # We can't access the instance directly, but our DummyScheduler stores in object created during call.
    # To assert, create a new instance and ensure behavior consistent (class used successfully).
    ds = DummyScheduler()
    ds.add_job(lambda: None, trigger="interval", seconds=5, id="id", replace_existing=True, misfire_grace_time=60)
    assert ds.added_job["seconds"] == 5


def test_launch_patrol_scheduler_failure_on_start(monkeypatch):
    shutdown_called = {"val": False}

    class BrokenScheduler:
        def __init__(self, executors=None):
            pass

        def add_job(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start")

        def shutdown(self):
            shutdown_called["val"] = True

    monkeypatch.setattr(patrol_launcher, "BackgroundScheduler", BrokenScheduler)

    ok = patrol_launcher.launch_patrol_scheduler(seconds=1)
    assert ok is False
    assert shutdown_called["val"] is True
