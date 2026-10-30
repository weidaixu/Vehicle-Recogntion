from backend.deepseek_client import call_deepseek


def test_v4_tool_call_disables_thinking_mode():
    captured = {}

    def transport(payload):
        captured.update(payload)
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}

    call_deepseek(
        [{"role": "user", "content": "识别图片"}],
        [{"type": "function", "function": {"name": "classify_car"}}],
        tool_choice={"type": "function", "function": {"name": "classify_car"}},
        transport=transport,
    )

    assert captured["thinking"] == {"type": "disabled"}
