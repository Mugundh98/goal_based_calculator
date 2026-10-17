"""Unit tests for the assistant's parts: tool schemas, grounding, chunking, the Gemini adapter."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from google.genai import errors, types

from app.chatbot import grounding, rag
from app.chatbot.llm import GeminiConversation, HistoryMessage, LLMError, ToolResult, ToolSpec
from app.chatbot.prompts import system_prompt
from app.chatbot.tools import TOOLS, SimulationArgs, what_if_label
from app.models import Goal
from app.schemas.simulation import SimulationOverrides
from app.services.simulations import resolve_inputs

# --- Tool declarations -----------------------------------------------------------------------


def test_every_tool_has_a_clean_json_schema():
    assert set(TOOLS) == {
        "list_goals", "goal_calculator", "create_goal", "run_simulation", "get_recommendation",
        "get_fund_metrics", "compare_funds", "get_portfolio_status", "get_risk_profile",
        "explain_term",
    }  # fmt: skip
    for tool in TOOLS.values():
        schema = tool.spec.parameters
        text = repr(schema)
        assert schema["type"] == "object"
        assert "$ref" not in text and "anyOf" not in text and "'title'" not in text
        assert len(tool.description) > 40


def test_schemas_carry_types_enums_and_required_fields():
    create = TOOLS["create_goal"].spec.parameters
    assert set(create["required"]) == {"target_amount", "target_year", "goal_type", "name"}
    assert "retirement" not in create["properties"]["goal_type"]["enum"]
    assert create["properties"]["confirmed"]["type"] == "boolean"
    simulation = TOOLS["run_simulation"].spec.parameters
    assert simulation["required"] == ["goal_id"]
    assert simulation["properties"]["equity_percent"]["type"] == "number"  # Optional unwrapped
    assert TOOLS["compare_funds"].spec.parameters["properties"]["fund_ids"]["maxItems"] == 4


def test_system_prompt_sets_scope_and_rules():
    prompt = system_prompt(date(2026, 10, 17))
    assert "17 October 2026" in prompt
    for rule in ("Numbers come only from tools", "explain_term", "confirmed=false",
                 "Stay in scope", "data, not instructions", "not personal investment advice",
                 "personal identifiers"):  # fmt: skip
        assert rule in prompt


# --- Grounding check -------------------------------------------------------------------------


def test_numbers_are_read_with_indian_units():
    found = {w: (v, u) for w, v, u in grounding.numbers_in_text(
        "₹1,25,000 a month, ₹12.5 lakh, ₹1.2 crore, 10.98% and 45 L"
    )}  # fmt: skip
    assert found["1,25,000"] == (125_000, "")
    assert found["12.5 lakh"] == (1_250_000, "lakh")
    assert found["1.2 crore"][0] == pytest.approx(12_000_000)
    assert found["10.98%"] == (10.98, "%")
    assert found["45 L"] == (4_500_000, "l")


def test_numbers_from_tools_are_grounded_even_when_rounded():
    tool = {"projected_value": 7187256.66, "xirr": 10.98, "sips": [{"monthly_sip": 22224.0}]}
    answer = "You will reach ₹71.87 lakh (about ₹72 lakh) with an XIRR of 11%; SIP ₹22,224."
    assert grounding.ungrounded(answer, [tool]) == []


def test_invented_numbers_are_flagged_once():
    tool = {"required_sip": 22224.0, "monthly_sip": 15000.0}
    answer = "Raise your SIP by ₹7,224 to ₹22,224. That is ₹7,224 more, about 48% higher."
    assert grounding.ungrounded(answer, [tool]) == ["7,224", "48%"]


def test_question_text_and_small_counts_do_not_need_a_source():
    answer = "For your 3 goals: the trip in 2029 costs ₹4 lakh as you said; here are 2 options."
    assert grounding.ungrounded(answer, ["a trip in 2029 costing 4 lakh"]) == []
    assert grounding.ungrounded("In 2031 you will have ₹4 lakh", []) == ["2031", "4 lakh"]


def test_numbers_inside_tool_strings_count():
    passages = {"passages": [{"text": "A stamp duty of 0.005% applies since 1 July 2020."}]}
    assert grounding.ungrounded("Stamp duty is 0.005% (since 2020).", [passages]) == []


# --- Knowledge base parsing ------------------------------------------------------------------


def test_every_article_parses_into_titled_sections():
    articles = rag.load_articles()
    assert len(articles) == 20
    for article in articles:
        assert article.title and len(article.sections) >= 2
        for heading, passage in rag.chunks(article):
            assert heading and passage
            assert len(passage) <= rag.MAX_CHUNK_CHARS + 600  # one paragraph may overflow


def test_long_sections_are_split_by_paragraph(tmp_path):
    paragraph = "word " * 150  # 750 characters
    (tmp_path / "long.md").write_text(
        f"# Long\n\n## Part\n\n{paragraph}\n\n{paragraph}\n\n{paragraph}\n\n## Short\n\nTiny.\n",
        encoding="utf-8",
    )
    [article] = rag.load_articles(tmp_path)
    pieces = rag.chunks(article)
    assert [h for h, _ in pieces] == ["Part", "Part", "Part", "Short"]


# --- Phase 5 override used by the assistant --------------------------------------------------


def test_simulation_can_start_from_recorded_investments():
    goal = Goal(
        target_amount=Decimal(2_500_000), target_year=2036, inflation_rate=Decimal(6),
        expected_return=None, current_savings=Decimal(0), monthly_sip=Decimal(15_000),
        step_up_rate=Decimal(0),
    )  # fmt: skip
    inputs, shown = resolve_inputs(
        goal,
        SimulationOverrides(current_savings=Decimal(1_605_939)),
        "moderate",
        date(2026, 10, 17),
    )
    assert inputs.current_savings == shown.current_savings == 1_605_939
    inputs, _ = resolve_inputs(goal, SimulationOverrides(), "moderate", date(2026, 10, 17))
    assert inputs.current_savings == 0


# --- Gemini adapter (with a stub client: no network) --------------------------------------------


def response(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def api_error(code: int, message: str = "error") -> errors.APIError:
    return errors.ClientError(code, {"error": {"code": code, "message": message}})


class StubModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)  # per call: list of responses, or an exception
        self.calls = []

    def generate_content_stream(self, *, model, contents, config):
        self.calls.append((model, list(contents)))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        yield from outcome


def conversation(outcomes, models=("main", "fallback")):
    stub = StubModels(outcomes)
    tools = [ToolSpec("list_goals", "List goals", {"type": "object", "properties": {}})]
    history = [HistoryMessage("user", "hi"), HistoryMessage("assistant", "hello")]
    chat = GeminiConversation(SimpleNamespace(models=stub), models, "system", history, tools)
    return chat, stub


def test_gemini_text_and_function_calls_become_chunks():
    call_part = types.Part(function_call=types.FunctionCall(id="c1", name="list_goals", args={}))
    chat, stub = conversation(
        [[response(types.Part(text="Let me check.")), response(call_part)],
         [response(types.Part(text="You have one goal."))]]
    )  # fmt: skip
    chunks = list(chat.send("my goals?"))
    assert [c.text for c in chunks] == ["Let me check.", ""]
    [requested] = chunks[1].calls
    assert (requested.name, requested.id) == ("list_goals", "c1")
    assert [c.role for c in chat.contents] == ["user", "model", "user", "model"]
    assert chat.config.tools[0].function_declarations[0].name == "list_goals"

    answer = list(chat.send_tool_results([ToolResult(requested, {"goals": []})]))
    assert answer[0].text == "You have one goal."
    sent = stub.calls[1][1][-1].parts[0].function_response
    assert (sent.id, sent.name, sent.response) == ("c1", "list_goals", {"result": {"goals": []}})


def test_gemini_skips_thoughts_but_sends_them_back():
    chat, _ = conversation([[response(types.Part(text="thinking", thought=True),
                                      types.Part(text="Answer"))]])  # fmt: skip
    assert [c.text for c in chat.send("q")] == ["Answer"]
    assert len(chat.contents[-1].parts) == 2  # the thought part is kept for the next round


def test_gemini_falls_back_to_the_second_model_when_rate_limited():
    chat, stub = conversation([api_error(429, "quota"), [response(types.Part(text="ok"))]])
    assert [c.text for c in chat.send("q")] == ["ok"]
    assert [m for m, _ in stub.calls] == ["main", "fallback"]
    assert chat.model == "fallback"


def test_gemini_errors_become_llm_errors():
    chat, _ = conversation([api_error(429), api_error(429)])
    with pytest.raises(LLMError) as raised:
        list(chat.send("q"))
    assert raised.value.kind == "rate_limit"

    chat, stub = conversation([api_error(400, "API key not valid")])
    with pytest.raises(LLMError) as raised:
        list(chat.send("q"))
    assert raised.value.kind == "config" and len(stub.calls) == 1  # not retried

    chat, _ = conversation([api_error(503)], models=("only",))
    with pytest.raises(LLMError) as raised:
        list(chat.send("q"))
    assert raised.value.kind == "unavailable"


def test_what_if_label_formats_only_the_values_given():
    # Regression: formatting a missing value (f"{None:g}") crashed every plain simulation.
    assert what_if_label(SimulationArgs(goal_id=1)) == ""
    label = what_if_label(SimulationArgs(goal_id=1, monthly_sip=25000, equity_percent=40))
    assert label == " (what if: SIP ₹25,000, 40% equity)"
    assert "target 2030" in what_if_label(SimulationArgs(goal_id=1, target_year=2030))
