from pathlib import Path

def test_no_duplicate_close_keys():
    src=Path("app.py").read_text(encoding="utf-8")
    assert "add_close_offset_" in src
    assert "close_action_" in src
    assert "key=f'close{a[\"id\"]}'" not in src

def test_no_pin_reset_magic_render():
    src=Path("app.py").read_text(encoding="utf-8")
    assert "st.success(msgm) if okm else st.info(msgm)" not in src
