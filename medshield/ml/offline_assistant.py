"""
Rule-based scan assistant used when no external model is configured (or the external model fails).

It answers only from the model's scores and the Grad-CAM heatmap analysis. A question is split into
one or more topics (e.g. a specific finding, the heatmap, next steps), and each topic gets a short
section. Out-of-scope conditions and patient-identity questions are answered honestly instead of
falling back to a generic summary.
"""

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

THRESHOLD = 0.5
BORDERLINE_LOW, BORDERLINE_HIGH = 0.4, 0.6
STAT_SCORE = 0.7

FINDINGS = ("Pneumonia", "Cardiomegaly", "Pleural Effusion", "Pneumothorax", "Atelectasis")

FINDING_PATTERNS: Dict[str, str] = {
    "Pneumothorax": r"\b(?:pneumothorax|tension|air\s*leak|collapsed\s+lung)\b",
    "Pneumonia": r"\b(?:pneumonia|consolidation|infiltrates?|infection|infected)\b",
    "Cardiomegaly": r"\b(?:cardiomegaly|heart|cardiac|enlarged\s+heart)\b",
    "Pleural Effusion": r"\b(?:effusions?|fluid|pleural|costophrenic)\b",
    "Atelectasis": r"\b(?:atelectasis|volume\s+loss|collapse)\b",
}

DEFINITIONS: Dict[str, Dict[str, str]] = {
    "Pneumonia": {
        "what": "an infection that inflames the air sacs of the lung, which can fill with fluid or pus",
        "looks_like": "a cloudy or hazy patch where the lung should look dark",
        "lookalikes": "atelectasis, fluid in the lungs (edema) or a pleural effusion",
    },
    "Cardiomegaly": {
        "what": "an enlarged heart",
        "looks_like": "a heart shadow wider than about half the width of the chest",
        "lookalikes": "magnification on bedside (AP) films, fluid around the heart, or a raised diaphragm",
    },
    "Pleural Effusion": {
        "what": "fluid collecting between the lung and the chest wall",
        "looks_like": "a white, curved fluid level that blunts the lower corners of the chest",
        "lookalikes": "pleural thickening, a raised diaphragm or lower-lobe pneumonia",
    },
    "Pneumothorax": {
        "what": "air between the lung and the chest wall, which can make part of the lung collapse",
        "looks_like": "a thin white line at the lung edge with no lung markings beyond it",
        "lookalikes": "skin folds on bedside films, large air blisters (bullae) or the edge of the shoulder blade",
    },
    "Atelectasis": {
        "what": "partial collapse of lung tissue, so part of the lung holds less air",
        "looks_like": "a streak or band of whiter lung, sometimes with signs of volume loss",
        "lookalikes": "scarring, early pneumonia or shallow breathing",
    },
}

OUT_OF_SCOPE: Sequence[Tuple[str, str]] = (
    (r"\b(?:lung\s+)?cancer\b|\btumou?rs?\b|\bmalignan\w*|\bmass(?:es)?\b|\bnodules?\b|\blesions?\b",
     "lung cancer, masses or nodules"),
    (r"\btuberculosis\b|\btb\b", "tuberculosis"),
    (r"\bcovid\w*|\bcoronavirus\b|\bsars\b", "COVID-19"),
    (r"\bfractur\w*|\bbroken\s+(?:ribs?|bones?)\b", "fractures"),
    (r"\bo?edema\b", "pulmonary edema"),
    (r"\bemphysema\b|\bcopd\b", "emphysema or COPD"),
    (r"\bfibrosis\b", "fibrosis"),
    (r"\bhernias?\b", "hernias"),
    (r"\basthma\b", "asthma"),
    (r"\b(?:pacemakers?|catheters?|lines?\s+and\s+tubes?|chest\s+tubes?|devices?)\b", "lines, tubes or devices"),
)

IDENTITY = re.compile(
    r"\b(?:name|date\s+of\s+birth|dob|birth\s*date|born|mrn|medical\s+record|record\s+number|address|"
    r"phone|how\s+old|age|gender|sex|identity|who\s+is\s+(?:the|this)\s+patient|hospital|institution|"
    r"referring|doctor'?s\s+name)\b"
)
GREETING = re.compile(r"^\s*(?:hi|hello|hey|hiya|good\s+(?:morning|afternoon|evening))\b[\s!.,]*$")
THANKS = re.compile(r"^\s*(?:thanks?|thank\s+you|thx|ok(?:ay)?|cool|great|got\s+it|perfect)\b[\w\s!.,]{0,30}$")
FOLLOW_UP = re.compile(
    r"^\s*(?:why|how\s+so|tell\s+me\s+more|more|go\s+on|explain(?:\s+(?:that|more|further))?|elaborate|"
    r"what\s+does\s+that\s+mean|and|really|details?|continue|such\s+as)\b[\s?!.]*$"
)
DEFINITION = re.compile(r"\bwhat\s+(?:is|are|'s)\b|\bdefin\w*|\bmeaning\s+of\b|\bwhat\s+does\s+\w+(?:\s+\w+)?\s+mean\b")
NUMBER = re.compile(r"\b0?\.\d{1,3}\b|\b[01](?:\.\d{1,3})?\b")

TOPIC_PATTERNS: Dict[str, re.Pattern] = {
    "heatmap": re.compile(
        r"\b(?:heat\s*maps?|highlight\w*|where|zones?|regions?|areas?|spots?|grad-?cam|saliency|"
        r"locali[sz]\w*|focus\w*|look(?:ed|ing|s)?\s+at|attention)\b"
    ),
    "steps": re.compile(
        r"\b(?:next|steps?|recommend\w*|workup|actions?|ct|follow(?:-|\s)?up|management|protocols?|order\w*|"
        r"treat\w*|should\s+(?:i|we|the\s+patient|they)|what\s+(?:to|should\s+\w+)\s+do)\b"
    ),
    "reliability": re.compile(
        r"\b(?:reliab\w*|accura\w*|trust\w*|sure|certain\w*|uncertain\w*|confiden\w*|wrong|mistakes?|"
        r"false\s+(?:positive|negative)s?|errors?|epistemic|differential)\b"
    ),
    "priority": re.compile(
        r"\b(?:stat|urgent\w*|urgency|priorit\w*|serious|severe|severity|emergency|critical|triage|"
        r"dangerous|worr(?:y|ied))\b"
    ),
    "score": re.compile(
        r"\b(?:scores?|threshold|percent\w*|probabilit\w*|chances?|numbers?|mean\s+by)\b|\b0?\.\d+\b"
    ),
    "laterality": re.compile(r"\b(?:left|right|which\s+side|both\s+(?:sides|lungs))\b"),
    "plain": re.compile(r"\b(?:simple|simply|plain|layman'?s?|lay\s+terms|everyday|easy|eli5|in\s+english)\b"),
    "summary": re.compile(
        r"\b(?:normal|abnormal|summar\w*|overall|results?|findings?|shows?|found|anything|okay|ok|fine|"
        r"healthy|diagnos\w*|wrong\s+with)\b"
    ),
}

# Section headings -> topic, used to work out what a short follow-up ("why?") refers to
HEADING_TOPICS: Sequence[Tuple[str, str]] = (
    ("where the heatmap", "heatmap"),
    ("how heatmaps work", "heatmap"),
    ("more about", "definition"),
    ("suggested next steps", "steps"),
    ("how reliable", "reliability"),
    ("why this scan is", "priority"),
    ("what the scores mean", "score"),
    ("left or right", "laterality"),
    ("in plain terms", "plain"),
    ("summary of this scan", "summary"),
    ("not something this tool checks", "out_of_scope"),
    ("patient details", "identity"),
)

SECTION_ORDER = (
    "identity", "out_of_scope", "findings", "priority", "score", "heatmap", "laterality",
    "reliability", "steps", "plain", "summary",
)


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

def _score(p: Dict[str, Any]) -> float:
    return float(p.get("probability", 0.0))


def _is_borderline(score: float) -> bool:
    return BORDERLINE_LOW <= score < BORDERLINE_HIGH


def verdict(p: Dict[str, Any]) -> str:
    s = _score(p)
    word = "positive" if s >= THRESHOLD else "negative"
    return f"borderline {word}" if _is_borderline(s) else word


def plain_score(p: Dict[str, Any]) -> str:
    return f"{verdict(p)}, score {_score(p):.2f}"


def overall_priority(predictions: List[Dict[str, Any]]) -> str:
    urgencies = {p.get("triage_urgency", "ROUTINE") for p in predictions}
    if "STAT_CRITICAL" in urgencies:
        return "STAT"
    if "ELEVATED" in urgencies:
        return "elevated"
    return "routine"


def _join(items: List[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _normalize_predictions(predictions: Any) -> List[Dict[str, Any]]:
    if isinstance(predictions, dict) and "predictions" in predictions:
        predictions = predictions["predictions"]
    return list(predictions) if isinstance(predictions, list) else []


def is_heatmap_question(message: str) -> bool:
    """True when answering the question benefits from a Grad-CAM heatmap (location questions)."""
    q = message.lower()
    return bool(TOPIC_PATTERNS["heatmap"].search(q) or TOPIC_PATTERNS["laterality"].search(q))


def topics_in_answer(text: str) -> List[str]:
    """Topic keys covered by an answer, read from its section headings (e.g. "priority", "definition:Pneumonia")."""
    covered: List[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not (line.startswith("**") and line.endswith("**")):
            continue
        heading = line.strip("* ").lower()
        finding = re.match(r"(?:more about\s+)?([a-z ]+?)(?::\s*(?:borderline\s+)?(?:positive|negative))?$", heading)
        name = finding.group(1).strip().title() if finding else ""
        if heading.startswith("more about") and name in FINDINGS:
            covered += [f"definition:{name}", f"finding:{name}"]
            continue
        if name in FINDINGS and ":" in heading:
            covered.append(f"finding:{name}")
            continue
        for prefix, topic in HEADING_TOPICS:
            if heading.startswith(prefix):
                covered.append(topic)
                break
    # Inline definitions, e.g. the plain-language answer's "(pneumonia is an infection ...)"
    for match in re.finditer(r"\(([a-z ]+?) is (?:an?|the|partial|fluid|air)\b", text or ""):
        name = match.group(1).strip().title()
        if name in FINDINGS:
            covered.append(f"definition:{name}")
    return covered


def _previous_topic(history: Optional[List[Dict[str, str]]]) -> Optional[str]:
    for turn in reversed(history or []):
        if turn.get("role") != "assistant":
            continue
        first_line = (turn.get("content") or "").strip().splitlines()[0:1]
        heading = first_line[0].strip("* ").lower() if first_line else ""
        for prefix, topic in HEADING_TOPICS:
            if heading.startswith(prefix):
                return topic
        match = re.match(r"([a-z ]+):\s*(?:borderline\s+)?(?:positive|negative)", heading)
        if match and match.group(1).strip().title() in FINDINGS:
            return "finding:" + match.group(1).strip().title()
        return "summary"
    return None


# ---------------------------------------------------------------------------------------------
# Topic detection
# ---------------------------------------------------------------------------------------------

def detect_topics(message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Splits a question into topics. Returns {"topics": [...], "findings": [...], "out_of_scope": [...],
    "definition": bool, "follow_up_of": Optional[str], "small_talk": Optional[str]}."""
    q = message.lower().strip()
    result: Dict[str, Any] = {
        "topics": [], "findings": [], "out_of_scope": [], "definition": False,
        "follow_up_of": None, "small_talk": None,
    }

    if GREETING.match(q):
        result["small_talk"] = "greeting"
        return result
    if THANKS.match(q):
        result["small_talk"] = "thanks"
        return result

    if FOLLOW_UP.match(q):
        result["follow_up_of"] = _previous_topic(history) or "summary"
        return result

    topics: List[str] = []
    if IDENTITY.search(q):
        topics.append("identity")

    out_of_scope = [label for pattern, label in OUT_OF_SCOPE if re.search(pattern, q)]
    if out_of_scope:
        topics.append("out_of_scope")
        result["out_of_scope"] = out_of_scope

    mentioned = sorted(
        ((m.start(), name) for name, pattern in FINDING_PATTERNS.items() for m in [re.search(pattern, q)] if m),
        key=lambda item: item[0],
    )
    result["findings"] = [name for _, name in mentioned]
    if result["findings"]:
        topics.append("findings")
        result["definition"] = bool(DEFINITION.search(q))

    for topic in ("priority", "score", "heatmap", "laterality", "reliability", "steps", "plain"):
        if TOPIC_PATTERNS[topic].search(q):
            topics.append(topic)
    # A definition question about a finding ("what does pneumonia mean") is not a score question
    if result["definition"] and "score" in topics and not NUMBER.search(q):
        topics.remove("score")

    if not topics or (TOPIC_PATTERNS["summary"].search(q) and "findings" not in topics):
        topics.append("summary")

    result["topics"] = [t for t in SECTION_ORDER if t in topics]
    return result


# ---------------------------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------------------------

class _Context:
    def __init__(self, predictions: List[Dict[str, Any]], target_pathology: str,
                 heatmap_analysis: Optional[Dict[str, Any]], heatmap_zone_summary: Optional[str]):
        self.preds = predictions
        self.by_name = {p.get("pathology", ""): p for p in predictions}
        self.ranked = sorted(predictions, key=_score, reverse=True)
        self.positives = [p for p in self.ranked if _score(p) >= THRESHOLD]
        self.borderline = [p for p in self.ranked if _is_borderline(_score(p))]
        self.priority = overall_priority(predictions)
        self.target = self.by_name.get(target_pathology) or (self.ranked[0] if self.ranked else
                                                             {"pathology": target_pathology, "probability": 0.0})
        self.heatmap_pathology = target_pathology
        if heatmap_analysis and heatmap_analysis.get("has_heatmap"):
            # Zone names are inserted mid-sentence ("strongest in the mid zone ...")
            self.peak_zone = _lower_first(heatmap_analysis.get("peak_zone", ""))
            self.secondary_zone = _lower_first(heatmap_analysis.get("secondary_zone", ""))
            self.focus_pct = heatmap_analysis.get("focus_percentage", 0.0)
        else:
            self.peak_zone, self.secondary_zone, self.focus_pct = (heatmap_zone_summary or ""), "", 0.0

    def finding(self, name: str) -> Dict[str, Any]:
        return self.by_name.get(name, {"pathology": name, "probability": 0.0, "triage_urgency": "ROUTINE"})

    def findings_list(self) -> str:
        return "\n".join(f"- {p.get('pathology')}: {plain_score(p)}" for p in self.ranked) or "- No findings available."


def _section_identity(ctx: _Context, info: Dict[str, Any]) -> str:
    return (
        "**Patient details aren't available**\n\n"
        "This study was de-identified before analysis. Names, dates of birth, record numbers and other "
        "identifiers were removed, and I only see the anonymized image and the model's scores, so I can't "
        "tell you who the patient is or give personal details."
    )


def _section_out_of_scope(ctx: _Context, info: Dict[str, Any]) -> str:
    conditions = _join(info["out_of_scope"])
    flagged = (
        f"Of the five findings it does check, it flagged {_join([p['pathology'].lower() for p in ctx.positives])}."
        if ctx.positives else
        "None of the five findings it does check was above the threshold, but that says nothing about "
        f"{conditions}."
    )
    return (
        "**Not something this tool checks**\n\n"
        "This tool only reports five findings: pneumonia, cardiomegaly, pleural effusion, pneumothorax and "
        f"atelectasis. It does not assess {conditions}, so I can't tell you anything about that from this "
        f"scan. {flagged} A radiologist's read is needed for anything else."
    )


def _section_finding(ctx: _Context, name: str, definition: bool) -> str:
    p = ctx.finding(name)
    s = _score(p)
    d = DEFINITIONS.get(name, {})
    lines = [f"**{name}: {verdict(p)}**", ""]
    if definition and d:
        lines.append(f"{name} is {d['what']}. On an X-ray it typically shows as {d['looks_like']}.")
        lines.append("")
    if s >= BORDERLINE_HIGH:
        meaning = f"The model found image features it associates with {name.lower()}."
    elif _is_borderline(s):
        meaning = ("This is close to the threshold, so treat it as uncertain: small changes to the image, such "
                   "as cropping or compression, can flip a result like this.")
    else:
        meaning = f"The model did not find the features it associates with {name.lower()}."
    lines.append(f"The model's result for {name.lower()} is {plain_score(p)}. {meaning}")
    return "\n".join(lines)


def _section_priority(ctx: _Context, info: Dict[str, Any]) -> str:
    if ctx.priority == "STAT":
        drivers = [p for p in ctx.ranked if p.get("triage_urgency") == "STAT_CRITICAL"]
        scored = _join(["%s at %.2f" % (p["pathology"].lower(), _score(p)) for p in drivers])
        reason = (
            f"It's STAT because the model scored {scored}. "
            f"Scans are marked STAT when pneumonia or pneumothorax scores {STAT_SCORE:.2f} or more, well above the "
            "0.50 threshold, so they get read first."
        )
    elif ctx.priority == "elevated":
        scored = _join(["%s (%.2f)" % (p["pathology"].lower(), _score(p)) for p in ctx.positives])
        reason = f"It's elevated because {scored} scored above the 0.50 threshold."
    else:
        reason = "It's routine because no finding scored above the 0.50 threshold."
    return (
        f"**Why this scan is {ctx.priority}**\n\n{reason}\n\n"
        "Priority only reflects the model's scores, to decide reading order. It isn't a measure of how ill the "
        "patient is; that needs clinical assessment."
    )


def _section_score(ctx: _Context, info: Dict[str, Any], message: str) -> str:
    lines = ["**What the scores mean**", ""]
    numbers = [float(n) for n in NUMBER.findall(message) if 0.0 <= float(n) <= 1.0]
    for n in numbers[:2]:
        matches = [p for p in ctx.preds if abs(_score(p) - n) < 0.006]
        if matches:
            lines.append(f"{n:.2f} is the model's score for {_join([p['pathology'] for p in matches])}.")
    lines.append(
        "Each finding gets a score from 0 to 1. The model's decision threshold is set at 0.50: at or above it the "
        "finding counts as positive, below it as negative. The score is not a percentage chance of disease; "
        "a 0.91 doesn't mean a 91% chance."
    )
    lines.append("")
    lines.append(
        "Scores further from 0.50 are more clear-cut. Between 0.40 and 0.60 a result is borderline and can flip "
        "with small changes to the image."
    )
    return "\n".join(lines)


def _section_heatmap(ctx: _Context, info: Dict[str, Any]) -> str:
    name = ctx.heatmap_pathology
    if ctx.peak_zone:
        where = f"For {name.lower()}, the heatmap is strongest in the {ctx.peak_zone}"
        where += f", with a secondary area in the {ctx.secondary_zone}" if ctx.secondary_zone else ""
        where += f". About {ctx.focus_pct}% of the image is highlighted." if ctx.focus_pct else "."
    else:
        where = f"No heatmap was available for {name.lower()} for this question."
    return (
        "**Where the heatmap is focused**\n\n"
        f"{where}\n\n"
        "A heatmap shows which regions most influenced the model's score. It doesn't outline disease, and one is "
        f"drawn even when the result is negative. Here the {name.lower()} result is {plain_score(ctx.finding(name))}."
    )


def _section_heatmap_detail(ctx: _Context) -> str:
    return (
        "**How heatmaps work**\n\n"
        "The heatmap (Grad-CAM) traces which parts of the image pushed the model's score for one finding up. "
        "Warm areas mattered most to the model; they aren't a drawn outline of disease.\n\n"
        "Keep in mind that heatmaps are coarse and can highlight things outside the lungs, such as the edges of the "
        "image, labels or devices. Use them to sanity-check what the model looked at, not to locate disease."
    )


def _section_laterality(ctx: _Context, info: Dict[str, Any]) -> str:
    lines = [
        "**Left or right**", "",
        "The model gives one score per finding for the whole image; it doesn't say which side a finding is on.",
    ]
    if ctx.peak_zone:
        lines.append(
            f"The heatmap for {ctx.heatmap_pathology.lower()} is strongest in the {ctx.peak_zone}, which hints at "
            "where the model looked, not where disease is."
        )
    lines.append("Left and right are the patient's sides: the patient's left appears on the viewer's right.")
    return "\n".join(lines)


def _section_reliability(ctx: _Context, info: Dict[str, Any]) -> str:
    if ctx.borderline:
        first = (
            f"Least reliable: {_join([p['pathology'] for p in ctx.borderline])} (scores between 0.40 and 0.60). "
            "Results this close to the threshold can change with cropping, compression or annotations on the image."
        )
    else:
        first = (
            "No finding is in the borderline band (0.40 to 0.60). Scores further from 0.50 are less likely to flip, "
            "but borders, annotations or cropping on the image can still shift them noticeably."
        )
    top = ctx.ranked[0] if ctx.ranked else None
    headline = f"The top result is {top['pathology'].lower()}: {plain_score(top)}. " if top else ""
    return (
        "**How reliable this result is**\n\n"
        f"{headline}{first}\n\n"
        "This model does not report a measured uncertainty, and its threshold was tuned to catch rare findings, so "
        "it flags some normal scans as positive. Results on photos, screenshots or annotated images are less "
        "reliable than on original DICOM files."
    )


def _section_steps(ctx: _Context, info: Dict[str, Any]) -> str:
    if ctx.priority == "STAT":
        steps = [
            "Have a radiologist review this study promptly; the model placed it in the STAT priority group.",
            "Correlate with the patient's symptoms and vital signs.",
            "If the finding is confirmed, follow your local urgent pathway; CT may help where the X-ray is unclear.",
        ]
    elif ctx.priority == "elevated":
        steps = [
            "Arrange an expedited radiologist read; the model placed it in the elevated priority group.",
            "Correlate with symptoms, examination and any prior imaging.",
            "Consider a lateral view or follow-up imaging if the finding is uncertain.",
        ]
    else:
        steps = [
            "Read this study in routine order; no finding was above the model's threshold.",
            "A negative model result does not rule out disease. Clinical concern should still guide further tests.",
        ]
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    top = ctx.ranked[0] if ctx.ranked else None
    context = f" (top result: {top['pathology'].lower()}, {plain_score(top)})" if top else ""
    return (
        "**Suggested next steps**\n\n"
        f"Priority: **{ctx.priority}**{context}.\n\n{numbered}\n\n"
        "These are general suggestions based only on the model's priority level, not on this patient's history."
    )


def _section_plain(ctx: _Context, info: Dict[str, Any]) -> str:
    focus = ctx.finding(info["findings"][0]) if info.get("findings") else ctx.target
    name, s = focus.get("pathology", ""), _score(focus)
    d = DEFINITIONS.get(name, {})
    if s >= BORDERLINE_HIGH:
        result = f"The computer model flagged signs it associates with **{name.lower()}**"
    elif _is_borderline(s):
        result = f"The computer model's result for **{name.lower()}** is borderline, so it can't call it either way"
    else:
        result = f"The computer model did not find signs of **{name.lower()}**"
    background = f" ({name.lower()} is {d['what']})" if d else ""
    closing = ("It means the image is worth a closer look by a doctor." if s >= THRESHOLD
               else "A negative result does not rule anything out.")
    return (
        "**In plain terms**\n\n"
        f"{result}{background}.\n\n"
        f"The number next to it ({s:.2f}) is not a percentage chance. The model says \"yes\" above 0.50 and "
        "\"no\" below it.\n\n"
        f"{closing} This tool helps sort scans; a doctor makes the diagnosis using the full picture, including "
        "symptoms and history."
    )


def _section_summary(ctx: _Context, info: Dict[str, Any]) -> str:
    flagged = (f"above the threshold: {_join([p['pathology'].lower() for p in ctx.positives])}."
               if ctx.positives else "no finding above the threshold.")
    return (
        "**Summary of this scan**\n\n"
        f"The model checked five findings and placed this scan in the **{ctx.priority}** priority group, with "
        f"{flagged}\n\n{ctx.findings_list()}\n\n"
        "Scores run from 0 to 1 and 0.50 is the threshold; a score is a yes/no signal, not a percentage chance."
    )


def _follow_up_sections(ctx: _Context, previous: str) -> List[str]:
    """Goes one level deeper on whatever the previous answer covered."""
    if previous.startswith("finding:"):
        name = previous.split(":", 1)[1]
        d = DEFINITIONS.get(name)
        if d:
            return [
                f"**More about {name.lower()}**\n\n"
                f"{name} is {d['what']}. On an X-ray it typically shows as {d['looks_like']}. It can be confused with "
                f"{d['lookalikes']}, which is one reason a model result needs a radiologist's read.\n\n"
                f"Here the model's result is {plain_score(ctx.finding(name))}."
            ]
    deeper = {
        "summary": lambda: [_section_priority(ctx, {}), _section_plain(ctx, {"findings": []})],
        "heatmap": lambda: [_section_heatmap_detail(ctx)],
        "laterality": lambda: [_section_heatmap_detail(ctx)],
        "priority": lambda: [_section_score(ctx, {}, "")],
        "score": lambda: [_section_reliability(ctx, {})],
        "reliability": lambda: [_section_steps(ctx, {})],
        "steps": lambda: [_section_reliability(ctx, {})],
        "plain": lambda: [_section_summary(ctx, {})],
        "out_of_scope": lambda: [_section_summary(ctx, {})],
        "identity": lambda: [_section_summary(ctx, {})],
    }
    return deeper.get(previous, deeper["summary"])()


# ---------------------------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------------------------

def answer(
    user_message: str,
    predictions: Any,
    target_pathology: str,
    heatmap_analysis: Optional[Dict[str, Any]] = None,
    heatmap_zone_summary: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Returns (markdown answer, detected topic info)."""
    preds = _normalize_predictions(predictions)
    ctx = _Context(preds, target_pathology, heatmap_analysis, heatmap_zone_summary)
    info = detect_topics(user_message, conversation_history)

    if info["small_talk"] == "greeting":
        return ("Hi. I can go through this scan's result with you: the findings, the heatmap, what the scores mean, "
                "how reliable they are, or suggested next steps.", info)
    if info["small_talk"] == "thanks":
        return "You're welcome. Ask anytime if you want to go through another part of the result.", info
    if not preds:
        return "No model results are available for this study, so there's nothing I can explain yet.", info

    if info["follow_up_of"]:
        text = "\n\n".join(_follow_up_sections(ctx, info["follow_up_of"]))
        info["rendered"] = topics_in_answer(text)
        return text, info

    builders = {
        "identity": lambda: [_section_identity(ctx, info)],
        "out_of_scope": lambda: [_section_out_of_scope(ctx, info)],
        "findings": lambda: [_section_finding(ctx, n, info["definition"]) for n in info["findings"]],
        "priority": lambda: [_section_priority(ctx, info)],
        "score": lambda: [_section_score(ctx, info, user_message.lower())],
        "heatmap": lambda: [_section_heatmap(ctx, info)],
        "laterality": lambda: [_section_laterality(ctx, info)],
        "reliability": lambda: [_section_reliability(ctx, info)],
        "steps": lambda: [_section_steps(ctx, info)],
        "plain": lambda: [_section_plain(ctx, info)],
        "summary": lambda: [_section_summary(ctx, info)],
    }
    sections: List[str] = []
    for topic in info["topics"]:
        sections.extend(builders[topic]())
    text = "\n\n".join(sections)
    rendered = topics_in_answer(text)
    if info["definition"]:
        rendered += [f"definition:{n}" for n in info["findings"]]
    if "plain" in info["topics"]:
        focus = info["findings"][0] if info["findings"] else ctx.target.get("pathology", "")
        rendered.append(f"definition:{focus}")
    info["rendered"] = rendered
    return text, info


def suggest_follow_ups(
    info: Dict[str, Any],
    predictions: Any,
    asked_before: Optional[List[str]] = None,
    limit: int = 3,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[str]:
    """Short follow-up questions about this scan that neither this answer nor earlier ones already covered."""
    preds = _normalize_predictions(predictions)
    if not preds:
        return []
    ranked = sorted(preds, key=_score, reverse=True)
    top = ranked[0].get("pathology", "")
    priority = overall_priority(preds)

    covered = set(info.get("rendered", [])) | set(info.get("topics", []))
    for turn in history or []:
        if turn.get("role") == "assistant":
            covered.update(topics_in_answer(turn.get("content", "")))
    asked = {q.strip().lower().rstrip("?") for q in (asked_before or [])}

    candidates: List[Tuple[str, str]] = []
    if top:
        candidates.append((f"definition:{top}", f"What is {top.lower()}?"))
    if priority != "routine":
        candidates.append(("priority", f"Why is it {priority}?"))
    candidates += [
        ("heatmap", "Where is the heatmap focused?"),
        ("reliability", "How reliable is this result?"),
        ("steps", "What are the next steps?"),
        ("plain", "Explain it in simple terms"),
        ("score", "What do the scores mean?"),
    ]
    out = [q for key, q in candidates if key not in covered and q.lower().rstrip("?") not in asked]
    return out[:limit]
