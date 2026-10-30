from tools.go20_demo_seed import launch_context


def test_go20_demo_launch_token_respects_max_ttl():
    ctx = launch_context()
    assert 0 < (ctx.exp - ctx.iat) <= 900
