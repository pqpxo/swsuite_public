from app.notify import newly_updated_hosts


def test_host_with_new_updates_is_reported():
    prev = {"web-01": 0, "db-01": 0}
    new = {"web-01": 5, "db-01": 0}
    assert newly_updated_hosts(prev, new) == ["web-01"]


def test_same_pending_set_not_reported_again():
    prev = {"web-01": 5}
    new = {"web-01": 5}
    assert newly_updated_hosts(prev, new) == []


def test_brand_new_host_with_updates_reported():
    prev = {}
    new = {"new-host": 3}
    assert newly_updated_hosts(prev, new) == ["new-host"]


def test_count_increase_reported():
    prev = {"web-01": 2}
    new = {"web-01": 9}
    assert newly_updated_hosts(prev, new) == ["web-01"]
