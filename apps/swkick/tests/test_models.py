from app.models import Credential, HostConn, RunResult


def test_runresult_defaults():
    r = RunResult()
    assert r.exit_code is None


def test_hostconn_holds_decrypted_credential():
    cred = Credential(id=1, name="k", type="password", password="pw", sudo_password="sp")
    hc = HostConn(hostname="10.0.0.1", port=22, username="admin", credential=cred)
    assert hc.credential.password == "pw"
    assert hc.credential.sudo_password == "sp"
