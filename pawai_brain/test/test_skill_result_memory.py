from pawai_brain.capability.skill_result_memory import SkillResultMemory


def test_starts_empty():
    m = SkillResultMemory()
    assert m.recent() == []


def test_add_and_recall_in_order():
    m = SkillResultMemory()
    m.add({"name": "self_introduce", "status": "completed", "ts": 1.0, "detail": ""})
    m.add({"name": "show_status", "status": "completed", "ts": 2.0, "detail": ""})
    items = m.recent()
    assert len(items) == 2
    assert items[0]["name"] == "self_introduce"
    assert items[1]["name"] == "show_status"


def test_maxlen_5_evicts_oldest():
    m = SkillResultMemory(maxlen=5)
    for i in range(7):
        m.add({"name": f"skill_{i}", "status": "completed", "ts": float(i), "detail": ""})
    items = m.recent()
    assert len(items) == 5
    assert items[0]["name"] == "skill_2"  # oldest two evicted
    assert items[-1]["name"] == "skill_6"


def test_recent_returns_copy_not_reference():
    m = SkillResultMemory()
    m.add({"name": "x", "status": "completed", "ts": 1.0, "detail": ""})
    items = m.recent()
    items.append({"hacked": True})
    assert len(m.recent()) == 1


def test_thread_safe_basic():
    """Smoke check that lock is used."""
    import threading
    m = SkillResultMemory()

    def writer(start):
        for i in range(50):
            m.add({"name": f"s{start+i}", "status": "completed", "ts": float(i), "detail": ""})

    threads = [threading.Thread(target=writer, args=(i*100,)) for i in range(4)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(m.recent()) == 5  # maxlen still respected
