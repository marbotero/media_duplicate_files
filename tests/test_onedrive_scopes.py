from providers.onedrive import GRAPH_SCOPES


def test_graph_scopes_do_not_include_reserved_scope():
    assert "offline_access" not in GRAPH_SCOPES
    assert set(GRAPH_SCOPES) == {"Files.Read.All", "User.Read"}
