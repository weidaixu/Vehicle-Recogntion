import json
import pytest
from backend.deepseek_client import generate_design_language, FIELDS

def test_design_language_schema_with_fake_transport():
    body={k:f"value-{k}" for k in FIELDS}
    fake=lambda payload:{"choices":[{"message":{"content":json.dumps(body,ensure_ascii=False)}}]}
    result=generate_design_language({"id":"0000","name_from_new":"江铃_凯运"},transport=fake)
    assert list(result)==FIELDS
def test_design_language_rejects_bad_schema():
    fake=lambda payload:{"choices":[{"message":{"content":"{}"}}]}
    try: generate_design_language({"id":"0000"},transport=fake)
    except ValueError: return
    raise AssertionError("invalid schema was accepted")

def test_design_language_requests_json_output():
    body={k:f"value-{k}" for k in FIELDS}
    captured={}
    def fake(payload):
        captured.update(payload)
        return {"choices":[{"message":{"content":json.dumps(body)}}]}
    generate_design_language({"id":"0000"},transport=fake)
    assert captured["response_format"] == {"type":"json_object"}
    assert captured["thinking"] == {"type":"disabled"}
    assert captured["max_tokens"] >= 2400

def test_design_language_explains_empty_content():
    fake=lambda payload:{"choices":[{"message":{"content":None}}]}
    with pytest.raises(RuntimeError,match="未返回有效文本"):
        generate_design_language({"id":"0000"},transport=fake)
