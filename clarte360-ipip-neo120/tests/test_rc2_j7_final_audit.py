from pathlib import Path


def test_completion_scopes_are_checked_before_feedback_and_completion_mutations():
    src = Path("app.py").read_text(encoding="utf-8")
    anchor = src.index("if st.session_state.stage=='feedback':")
    block = src[anchor:src.index("if st.session_state.stage=='completed':", anchor)]
    assert block.index("require_scope(c,'IPIP_RESULT_READ')") < block.index("save_feedback(")
    assert block.index("require_scope(c,'IPIP_STATUS')") < block.index("save_feedback(")
    assert block.index("save_feedback(") < block.index("generate_report(") < block.index("mark_completed(") < block.index("publish_event('TERMINE'")


def test_j7_build_increment_is_declared():
    src = Path("clarte360_ipip/version.py").read_text(encoding="utf-8")
    assert 'BUILD_INCREMENT = "RC2-J7"' in src
