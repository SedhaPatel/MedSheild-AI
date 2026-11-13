"""Behaviour of the built-in (offline) scan assistant and the chat endpoint around it."""

import pytest
from fastapi.testclient import TestClient

from medshield.api.app import create_app
from medshield.config import Settings, get_settings
from medshield.ml.offline_assistant import answer, detect_topics, is_heatmap_question, suggest_follow_ups

PREDS = [
    {"pathology": "Pneumonia", "probability": 0.91, "triage_urgency": "STAT_CRITICAL"},
    {"pathology": "Cardiomegaly", "probability": 0.01, "triage_urgency": "ROUTINE"},
    {"pathology": "Pleural Effusion", "probability": 0.11, "triage_urgency": "ROUTINE"},
    {"pathology": "Pneumothorax", "probability": 0.05, "triage_urgency": "ROUTINE"},
    {"pathology": "Atelectasis", "probability": 0.14, "triage_urgency": "ROUTINE"},
]
HEATMAP = {"has_heatmap": True, "peak_zone": "mid zone of the right lung", "secondary_zone": "", "focus_percentage": 19.4}


def ask(question, history=None, preds=PREDS):
    text, info = answer(question, preds, "Pneumonia", heatmap_analysis=HEATMAP, conversation_history=history)
    return text, info


def headings(text):
    return [line.strip("*") for line in text.splitlines() if line.startswith("**") and line.endswith("**")]


@pytest.mark.parametrize("question, condition", [
    ("Does the patient have lung cancer?", "lung cancer"),
    ("Can it detect tuberculosis?", "tuberculosis"),
    ("Is there COVID?", "COVID-19"),
    ("Any rib fractures?", "fractures"),
])
def test_out_of_scope_conditions_are_declined_honestly(question, condition):
    text, _ = ask(question)
    assert headings(text)[0] == "Not something this tool checks"
    assert condition in text
    assert "only reports five findings" in text


@pytest.mark.parametrize("question", ["What is the patient's name?", "How old is the patient?", "What's the MRN?"])
def test_identity_questions_are_refused(question):
    text, _ = ask(question)
    assert headings(text) == ["Patient details aren't available"]
    assert "de-identified" in text


def test_greeting_and_thanks_are_brief_and_do_not_dump_results():
    hi, _ = ask("hi")
    thanks, _ = ask("thanks!")
    for reply in (hi, thanks):
        assert "0." not in reply and "- Pneumonia" not in reply   # no scores or findings list
    assert len(hi) < 250 and len(thanks) < 150


def test_multiple_topics_are_answered_in_one_reply():
    text, _ = ask("Explain the heatmap and next steps")
    assert headings(text) == ["Where the heatmap is focused", "Suggested next steps"]


def test_comparison_answers_each_named_finding_in_order():
    text, _ = ask("Compare pneumonia and atelectasis")
    assert headings(text) == ["Pneumonia: positive", "Atelectasis: negative"]


def test_definition_questions_explain_the_term_and_give_the_result():
    text, _ = ask("What is atelectasis?")
    assert "partial collapse of lung tissue" in text
    assert "negative, score 0.14" in text


def test_why_stat_explains_the_priority_rule():
    text, _ = ask("Why is it STAT?")
    assert headings(text) == ["Why this scan is STAT"]
    assert "pneumonia at 0.91" in text and "0.70" in text
    assert "isn't a measure of how ill the patient is" in text


def test_score_question_identifies_which_finding_a_number_belongs_to():
    text, _ = ask("What does 0.91 mean?")
    assert "0.91 is the model's score for Pneumonia" in text
    assert "doesn't mean a 91% chance" in text


def test_laterality_question_explains_whole_image_scores():
    text, _ = ask("Is the left lung okay?")
    assert "Left or right" in headings(text)
    assert "doesn't say which side" in text


@pytest.mark.parametrize("question", ["What did the model look at?", "Where is it?", "Which side is affected?"])
def test_location_questions_request_a_heatmap(question):
    assert is_heatmap_question(question)


def test_short_follow_ups_use_the_previous_answer():
    first, _ = ask("Is there pneumonia?")
    history = [{"role": "user", "content": "Is there pneumonia?"}, {"role": "assistant", "content": first}]
    follow, info = ask("Why?", history)
    assert info["follow_up_of"] == "finding:Pneumonia"
    assert headings(follow) == ["More about pneumonia"]
    assert "can be confused with" in follow


def test_suggestions_skip_topics_already_covered_in_the_conversation():
    history = []
    seen = []
    for question in ["Is there pneumonia?", "Why?", "tell me more", "Where is the heatmap focused?"]:
        text, info = ask(question, history)
        asked = [t["content"] for t in history if t["role"] == "user"] + [question]
        suggestions = suggest_follow_ups(info, PREDS, asked_before=asked, history=history)
        assert len(suggestions) == 3
        seen.append(suggestions)
        history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
    assert "What is pneumonia?" not in seen[1]          # covered by "More about pneumonia"
    assert "Why is it STAT?" not in seen[2]             # covered by the STAT section
    assert "Where is the heatmap focused?" not in seen[3]


def test_plain_language_answer_counts_as_having_defined_the_finding():
    first, _ = ask("Explain the result in simple terms")
    history = [{"role": "user", "content": "Explain the result in simple terms"}, {"role": "assistant", "content": first}]
    _, info = ask("Why is it STAT?", history)
    suggestions = suggest_follow_ups(info, PREDS, asked_before=["Why is it STAT?"], history=history)
    assert "What is pneumonia?" not in suggestions


def test_detected_findings_follow_question_order():
    assert detect_topics("Is there effusion or pneumothorax?")["findings"] == ["Pleural Effusion", "Pneumothorax"]


# --- Chat endpoint -----------------------------------------------------------------------------

def _client(tmp_path, pepper):
    settings = Settings(storage_path=str(tmp_path / "enc"), require_mtls=False, secret_pepper=pepper,
                        chat_provider="gemini", gemini_api_key="")
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_chat_returns_suggestions_and_reuses_cached_model_results(tmp_path, monkeypatch):
    import medshield.api.routes.dashboard as dashboard

    client = _client(tmp_path, b"offline-assistant-cache-pepper")
    uid = client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_01_pneumonia"}).json()[
        "anonymous_study_instance_uid"]

    calls = {"predict": 0, "heatmap": 0}
    real_predict, real_heatmap = dashboard._dashboard_engine.predict, dashboard._dashboard_engine.generate_heatmap_image

    def counting_predict(ds):
        calls["predict"] += 1
        return real_predict(ds)

    def counting_heatmap(ds, pathology):
        calls["heatmap"] += 1
        return real_heatmap(ds, pathology)

    monkeypatch.setattr(dashboard._dashboard_engine, "predict", counting_predict)
    monkeypatch.setattr(dashboard._dashboard_engine, "generate_heatmap_image", counting_heatmap)

    for question in ["Where is the heatmap focused?", "Where is the heatmap focused?", "How reliable is this result?"]:
        resp = client.post("/api/chat", json={"scan_id": uid, "user_message": question})
        assert resp.status_code == 200, resp.text
        assert resp.json()["suggested_questions"]

    assert calls["predict"] == 1      # model ran once for three questions
    assert calls["heatmap"] == 1      # heatmap computed once, then reused


def test_question_about_one_finding_gets_that_findings_heatmap(tmp_path, monkeypatch):
    import medshield.api.routes.dashboard as dashboard

    client = _client(tmp_path, b"offline-assistant-target-pepper")
    uid = client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_01_pneumonia"}).json()[
        "anonymous_study_instance_uid"]
    requested = []
    real_heatmap = dashboard._dashboard_engine.generate_heatmap_image
    monkeypatch.setattr(dashboard._dashboard_engine, "generate_heatmap_image",
                        lambda ds, pathology: requested.append(pathology) or real_heatmap(ds, pathology))

    resp = client.post("/api/chat", json={
        "scan_id": uid, "user_message": "Where does the model see atelectasis?", "target_pathology": "Pneumonia"})
    assert resp.status_code == 200
    assert requested == ["Atelectasis"]
    assert "for atelectasis, the heatmap" in resp.json()["answer"].lower()


def test_erasing_a_study_evicts_its_cached_chat_results(tmp_path):
    import medshield.api.routes.dashboard as dashboard

    client = _client(tmp_path, b"offline-assistant-evict-pepper")
    uid = client.post("/api/v1/dashboard/analyze", data={"sample_id": "patient_02_effusion"}).json()[
        "anonymous_study_instance_uid"]
    assert client.post("/api/chat", json={"scan_id": uid, "user_message": "Where is the heatmap focused?"}).status_code == 200
    assert any(key[0] == uid for key in dashboard._chat_cache)

    assert client.post(f"/api/v1/dashboard/shred/{uid}").status_code == 200
    assert not any(key[0] == uid for key in dashboard._chat_cache)
    assert client.post("/api/chat", json={"scan_id": uid, "user_message": "Is there pneumonia?"}).status_code == 410
