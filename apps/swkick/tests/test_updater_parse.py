from app.updater import parse_upgradable


def test_parses_package_names():
    output = (
        "Listing...\n"
        "curl/jammy-updates 7.81.0-1ubuntu1.15 amd64 [upgradable from: 7.81.0-1ubuntu1.14]\n"
        "libssl3/jammy-updates 3.0.2-0ubuntu1.15 amd64 [upgradable from: 3.0.2-0ubuntu1.10]\n"
    )
    assert parse_upgradable(output) == ["curl", "libssl3"]


def test_empty_when_no_updates():
    assert parse_upgradable("Listing...\n") == []


def test_ignores_blank_lines():
    assert parse_upgradable("Listing...\n\n\n") == []
