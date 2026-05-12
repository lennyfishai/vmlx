import base64

from vmlx_engine.omni_multimodal import (
    OmniMultimodalDispatcher,
    _build_omni_turn_prompt_with_thinking,
    _decode_data_url,
)


class _FakeTokenizer:
    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        rail = "<think></think>" if kwargs.get("enable_thinking") is False else "<think>\n"
        return f"rendered:{messages[-1]['content']}:{rail}"


def test_omni_prompt_builder_forwards_enable_thinking_false_on_first_turn():
    tok = _FakeTokenizer()

    prompt = _build_omni_turn_prompt_with_thinking(
        tok,
        "Describe the image directly.",
        n_image_tokens=2,
        is_first=True,
        enable_thinking=False,
    )

    assert tok.calls[0][0][0]["role"] == "system"
    assert "Answer directly" in tok.calls[0][0][0]["content"]
    assert tok.calls[0][0][1]["role"] == "user"
    assert "<img><image><image></img>" in tok.calls[0][0][1]["content"]
    assert tok.calls[0][1]["enable_thinking"] is False
    assert prompt.endswith("<think></think>")


def test_omni_prompt_builder_forwards_enable_thinking_false_on_followup_turn():
    tok = _FakeTokenizer()

    _build_omni_turn_prompt_with_thinking(
        tok,
        "Now answer directly.",
        is_first=False,
        enable_thinking=False,
    )

    assert tok.calls[0][1]["enable_thinking"] is False


def test_omni_dispatcher_sets_thinking_flag_on_first_session_turn(tmp_path):
    class _FakeSession:
        def __init__(self):
            self.reset_count = 0

        def reset(self):
            self.reset_count += 1

        def turn(self, **kwargs):
            return "direct answer"

    dispatcher = OmniMultimodalDispatcher.__new__(OmniMultimodalDispatcher)
    dispatcher.bundle_path = "/fake"
    dispatcher._session = _FakeSession()
    dispatcher._lock = __import__("threading").Lock()
    dispatcher._last_signature = None
    dispatcher._scratch_dir = tmp_path

    dispatcher.chat(
        [{"role": "user", "content": "Describe directly."}],
        enable_thinking=False,
    )

    assert dispatcher._session._vmlx_enable_thinking is False


def test_omni_dispatcher_resets_when_prior_turn_media_changes(tmp_path):
    class _FakeSession:
        def __init__(self):
            self.reset_count = 0

        def reset(self):
            self.reset_count += 1

        def turn(self, **kwargs):
            return "direct answer"

    def audio_part(raw: bytes):
        return {
            "type": "input_audio",
            "input_audio": {
                "data": base64.b64encode(raw).decode("ascii"),
                "format": "wav",
            },
        }

    def first_turn(raw: bytes):
        return [
            {
                "role": "user",
                "content": [
                    audio_part(raw),
                    {"type": "text", "text": "same words"},
                ],
            }
        ]

    def followup_with_prior_media(raw: bytes):
        return [
            first_turn(raw)[0],
            {"role": "assistant", "content": "prior answer"},
            {"role": "user", "content": "continue"},
        ]

    dispatcher = OmniMultimodalDispatcher.__new__(OmniMultimodalDispatcher)
    dispatcher.bundle_path = "/fake"
    dispatcher._session = _FakeSession()
    dispatcher._lock = __import__("threading").Lock()
    dispatcher._last_signature = None
    dispatcher._scratch_dir = tmp_path

    dispatcher.chat(first_turn(b"audio-a"))
    assert dispatcher._session.reset_count == 1

    dispatcher.chat(followup_with_prior_media(b"audio-b"))
    assert dispatcher._session.reset_count == 2


def test_omni_decode_data_url_maps_mpeg4_audio_to_m4a():
    raw, ext = _decode_data_url(
        "data:audio/mp4;base64," + base64.b64encode(b"fake").decode("ascii")
    )

    assert raw == b"fake"
    assert ext == ".m4a"
