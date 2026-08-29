from core.state_store import StateStore


def test_active_printer_and_notifications_survive_close_and_reopen(tmp_path):
    path = tmp_path / "state.json"

    store = StateStore(path=path)
    store.set_active_printer(chat_id=1, printer_name="k1c")
    store.mark_notified("k1c", "cube.gcode:complete")
    store.close()

    reopened = StateStore(path=path)
    assert reopened.get_active_printer(chat_id=1) == "k1c"
    assert reopened.was_notified("k1c", "cube.gcode:complete")
    reopened.close()


def test_mark_notified_keeps_only_the_latest_event_per_printer(tmp_path):
    """Bounds sent_notifications' growth: unbounded rows would make every
    read/write of state.json (including the one on every Telegram update)
    progressively slower over the bot's lifetime."""
    store = StateStore(path=tmp_path / "state.json")

    store.mark_notified("k1c", "cube.gcode:complete")
    store.mark_notified("k1c", "vase.gcode:paused")

    assert not store.was_notified("k1c", "cube.gcode:complete")
    assert store.was_notified("k1c", "vase.gcode:paused")
    assert len(store._sent_notifications.all()) == 1
    store.close()


def test_mark_notified_tracks_each_printer_independently(tmp_path):
    store = StateStore(path=tmp_path / "state.json")

    store.mark_notified("k1c", "cube.gcode:complete")
    store.mark_notified("ender3", "vase.gcode:complete")

    assert store.was_notified("k1c", "cube.gcode:complete")
    assert store.was_notified("ender3", "vase.gcode:complete")
    assert len(store._sent_notifications.all()) == 2
    store.close()
