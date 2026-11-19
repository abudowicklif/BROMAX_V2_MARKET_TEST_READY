
from bromax.storage import Store
from bromax.models import Tick

def _signal(predicted):
    return {"signal_id":f"s{predicted}","symbol":"R_100","generation":1,"snapshot_sequence":10,
            "target_sequence":11,"created_at":"2026-01-01T00:00:00+00:00",
            "predicted_digit":predicted,"probabilities":[.1]*10,"status":"PENDING",
            "verifier_reason":"test","model_version":"test"}

def test_pending_signal_invalidated_on_generation_change(tmp_path):
    store=Store(str(tmp_path/"test.sqlite3"))
    store.create_signal(_signal(3))
    store.invalidate_generation("R_100",1,"reconnected")
    assert store.signals("R_100")[0]["status"]=="INVALIDATED"
    store.close()

def test_abstention_is_not_counted_as_miss(tmp_path):
    store=Store(str(tmp_path/"test.sqlite3"))
    store.create_signal(_signal(None))
    tick=Tick("R_100",11,1,123,"2026-01-01T00:00:01+00:00","1.2","1.2",1,2)
    store.resolve_signal("sNone",tick)
    row=store.signals("R_100")[0]
    assert row["outcome"]=="ABSTAIN"
    assert row["status"]=="RESOLVED"
    store.close()
