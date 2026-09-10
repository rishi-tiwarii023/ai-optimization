from src.adapters.http_proxy import proxy_environment


def test_proxy_environment_clears_no_proxy() -> None:
    env = proxy_environment("http://127.0.0.1:3128")
    assert env["HTTP_PROXY"] == "http://127.0.0.1:3128"
    assert env["NO_PROXY"] == ""
    assert env["no_proxy"] == ""


def test_proxy_environment_empty() -> None:
    assert proxy_environment("") == {}
    assert proxy_environment("  ") == {}
