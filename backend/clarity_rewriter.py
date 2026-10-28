"""
Guideline Clarity Rewriter & Deterministic Ambiguity Scorer (Round 3 Part B).
Extends the LoomShield Ambiguity Radar and guideline_feedback telemetry with:
- B1: Deterministic ambiguity scorer (0-100) using an editable lexicon (backend/vague_lexicon.json),
      matched character spans, per-rule reasons, and explicit formula.
- B2: Correlation with override rate from guideline_feedback above a configurable minimum audit sample
      (default 5 audits; below it reports "Not enough data"). Priority is High ONLY when vague AND
      override rate > 20% over the minimum sample; vague without usage data is labelled "Vague (no usage data)".
- B3: Candidate rewrite where quantified thresholds come ONLY from (a) numeric tokens already in the rule text
      or (b) Verified Facts retrieved via TF-IDF cosine similarity (cited by FACT id), else inserting an
      explicit placeholder "[SET THRESHOLD: unit]". Do/Don't examples cite real finding IDs or rule wording.
      Candidate is scored with the same scorer; if not strictly lower, returns "no improvement found".
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

LEXICON_PATH = Path(__file__).resolve().parent / "vague_lexicon.json"

AMBIGUITY_FORMULA = (
    "Ambiguity Score (0-100) = min(100, 20 * vague_qualifier_spans [max 60] "
    "+ 20 [if no numeric threshold] + 15 [if missing both Do & Don't examples, or +8 if missing one] "
    "+ 15 [if subjective-only wording with no measurable anchor])."
)

_NUMERIC_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_OBJECTIVE_ANCHOR_RE = re.compile(
    r"(?:#[0-9a-fA-F]{3,6}\b|\[SET THRESHOLD:[^\]]+\]|['\"][^'\"]{2,}['\"]|\b(?:WCAG|ISO|SOC|GDPR|HIPAA|PCI|AA|AAA)\b)",
    re.IGNORECASE,
)


def load_vague_lexicon(lexicon_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the editable vague qualifier lexicon from JSON."""
    path = lexicon_path or LEXICON_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        qualifiers = [str(q).strip() for q in data.get("qualifiers", []) if str(q).strip()]
        replacements = {str(k).lower(): str(v) for k, v in (data.get("replacements") or {}).items()}
        return {"qualifiers": qualifiers, "replacements": replacements}
    except Exception:
        default_quals = [
            "appropriate amount",
            "when appropriate",
            "where appropriate",
            "as appropriate",
            "appropriate",
            "where suitable",
            "suitable",
            "reasonably",
            "reasonable",
            "intuitive",
            "intuitively",
            "timely",
            "significantly",
            "significant",
            "as needed",
            "where possible",
            "generally",
            "usually",
            "sufficient",
            "adequate",
        ]
        return {"qualifiers": default_quals, "replacements": {}}


def find_vague_spans(text: str, qualifiers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Deterministically find non-overlapping vague qualifier spans sorted by start index."""
    if not text:
        return []
    if qualifiers is None:
        qualifiers = load_vague_lexicon()["qualifiers"]

    # Sort longest phrases first so "appropriate amount" matches before "appropriate"
    sorted_quals = sorted(set(qualifiers), key=lambda q: (-len(q), q.lower()))
    occupied: List[Tuple[int, int]] = []
    spans: List[Dict[str, Any]] = []

    for q in sorted_quals:
        pat = re.compile(r"(?<!\w)" + re.escape(q) + r"(?!\w)", re.IGNORECASE)
        for m in pat.finditer(text):
            s, e = m.start(), m.end()
            if any(not (e <= os_ or s >= oe_) for os_, oe_ in occupied):
                continue
            occupied.append((s, e))
            spans.append({
                "phrase": m.group(0),
                "qualifier": q.lower(),
                "start": s,
                "end": e,
            })

    spans.sort(key=lambda item: (item["start"], item["end"]))
    return spans


def score_rule_ambiguity(
    rule_text: str,
    do_example: str = "",
    dont_example: str = "",
    lexicon: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministically score a guideline rule from 0 (completely clear) to 100 (highly ambiguous)."""
    text = str(rule_text or "").strip()
    do_ex = str(do_example or "").strip()
    dont_ex = str(dont_example or "").strip()

    lex = lexicon or load_vague_lexicon()
    matched_spans = find_vague_spans(text, lex.get("qualifiers"))

    score = 0
    reasons: List[str] = []

    # 1. Vague qualifiers (+20 per span, max 60)
    if matched_spans:
        vague_pts = min(60, 20 * len(matched_spans))
        score += vague_pts
        phrases_str = ", ".join(f"'{sp['phrase']}'" for sp in matched_spans)
        reasons.append(f"Contains {len(matched_spans)} vague qualifier(s): {phrases_str} (+{vague_pts})")

    # 2. Numeric / quantified threshold check (+20 if absent)
    has_numeric = bool(_NUMERIC_TOKEN_RE.search(text))
    if not has_numeric:
        score += 20
        reasons.append("No numeric threshold or quantified limit in rule wording (+20)")

    # 3. Do / Don't examples check (+15 if both missing, +8 if one missing)
    has_do = bool(do_ex)
    has_dont = bool(dont_ex)
    if not has_do and not has_dont:
        score += 15
        reasons.append("Missing both Do and Don't concrete examples (+15)")
    elif not has_do or not has_dont:
        score += 8
        missing_which = "Do example" if not has_do else "Don't example"
        reasons.append(f"Missing concrete {missing_which} (+8)")

    # 4. Subjective-only wording check (+15 if vague qualifiers exist with no number and no objective anchor)
    has_anchor = bool(_OBJECTIVE_ANCHOR_RE.search(text))
    subjective_only = bool(len(matched_spans) > 0 and not has_numeric and not has_anchor)
    if subjective_only:
        score += 15
        reasons.append("Subjective-only wording without a measurable criterion or objective anchor (+15)")

    final_score = min(100, max(0, int(score)))
    is_vague = bool(len(matched_spans) > 0 or final_score >= 35)

    return {
        "score": final_score,
        "reasons": reasons,
        "matched_spans": matched_spans,
        "has_numeric_threshold": has_numeric,
        "has_do_example": has_do,
        "has_dont_example": has_dont,
        "subjective_only": subjective_only,
        "is_vague": is_vague,
        "formula": AMBIGUITY_FORMULA,
        "breakdown": {
            "vague_qualifiers_count": len(matched_spans),
            "has_numeric_threshold": has_numeric,
            "has_do_example": has_do,
            "has_dont_example": has_dont,
            "subjective_only": subjective_only,
        },
    }


def correlate_ambiguity_and_overrides(
    ambiguity: Optional[Dict[str, Any]] = None,
    violations_count: int = 0,
    overrides_count: int = 0,
    audits_sample_count: int = 0,
    min_sample: Optional[int] = None,
    ambiguity_score: int = 0,
    is_vague: Optional[bool] = None,
) -> Dict[str, Any]:
    """Combine deterministic ambiguity score with override telemetry respecting the minimum sample threshold."""
    if min_sample is None:
        try:
            min_sample = max(1, int(os.environ.get("LOOMSHIELD_MIN_AUDIT_SAMPLE", "5") or "5"))
        except ValueError:
            min_sample = 5

    if is_vague is None:
        if isinstance(ambiguity, dict):
            is_vague = bool(ambiguity.get("is_vague"))
        else:
            is_vague = bool(ambiguity_score >= 25)
    has_usage_events = (violations_count > 0 or overrides_count > 0)

    if audits_sample_count < min_sample:
        return {
            "min_sample_required": min_sample,
            "sample_audits_count": audits_sample_count,
            "sufficient_sample": False,
            "override_rate": None,
            "override_rate_display": "Not enough data",
            "priority": "Medium" if is_vague else "Low",
            "priority_rank": 2 if is_vague else 1,
            "classification_label": "Vague (no usage data)" if is_vague else "Not enough data",
        }

    if not has_usage_events:
        return {
            "min_sample_required": min_sample,
            "sample_audits_count": audits_sample_count,
            "sufficient_sample": True,
            "override_rate": 0.0,
            "override_rate_display": "0.0%",
            "priority": "Medium" if is_vague else "Low",
            "priority_rank": 2 if is_vague else 1,
            "classification_label": "Vague (no usage data)" if is_vague else "Consistent enforcement",
        }

    denom = max(violations_count, overrides_count, 1)
    override_rate = round((float(overrides_count) / float(denom)) * 100.0, 1)

    if is_vague and override_rate > 20.0:
        priority = "High"
        priority_rank = 3
        label = "High priority: Vague & >20% override rate"
    elif is_vague:
        priority = "Medium"
        priority_rank = 2
        label = "Vague (low override rate)"
    elif override_rate > 20.0:
        priority = "Medium"
        priority_rank = 2
        label = "Frequent overrides (clear wording)"
    else:
        priority = "Low"
        priority_rank = 1
        label = "Consistent enforcement"

    return {
        "min_sample_required": min_sample,
        "sample_audits_count": audits_sample_count,
        "sufficient_sample": True,
        "override_rate": override_rate,
        "override_rate_display": f"{override_rate}%",
        "priority": priority,
        "priority_rank": priority_rank,
        "classification_label": label,
    }


def _retrieve_relevant_verified_fact(
    query_text: str,
    verified_facts: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], float]:
    """Use the embedded Scikit-Learn TF-IDF cosine similarity engine to find a matching Verified Fact."""
    verified_only = [
        f for f in (verified_facts or [])
        if str(f.get("verification_status", "")).strip() == "Verified"
    ]
    if not verified_only or not query_text.strip():
        return None, 0.0

    corpus = [
        f"{f.get('product_context', '')} {f.get('statement', '')} {f.get('numeric_value', '')} {f.get('numeric_units', '')} {f.get('applicable_conditions', '')}"
        for f in verified_only
    ]
    try:
        vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        mat = vec.fit_transform(corpus)
        q_vec = vec.transform([query_text])
        sims = cosine_similarity(q_vec, mat)[0]
        best_idx = int(np.argmax(sims))
        best_sim = round(float(sims[best_idx]), 3)
        if best_sim >= 0.10:
            return verified_only[best_idx], best_sim
    except Exception:
        pass
    return None, 0.0


def extract_numeric_tokens(text: str) -> List[str]:
    """Extract all numeric tokens from a string."""
    if not text:
        return []
    return _NUMERIC_TOKEN_RE.findall(str(text))


def generate_candidate_rewrite(
    rule: Dict[str, Any],
    verified_facts: List[Dict[str, Any]],
    past_findings: Optional[List[Dict[str, Any]]] = None,
    lexicon: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a deterministic candidate rewrite for human sign-off without ever inventing numbers."""
    lex = lexicon or load_vague_lexicon()
    replacements = lex.get("replacements", {})

    rule_id = str(rule.get("id", "RULE-UNKNOWN"))
    title = str(rule.get("title", "")).strip()
    old_text = str(rule.get("description", "")).strip()
    orig_do = str(rule.get("do_example", "")).strip()
    orig_dont = str(rule.get("dont_example", "")).strip()

    before_eval = score_rule_ambiguity(old_text, orig_do, orig_dont, lexicon=lex)
    spans = before_eval["matched_spans"]

    # Collect numeric tokens already present in the rule text (title + description)
    rule_num_matches = list(
        re.finditer(
            r"\b(\d+(?:\.\d+)?)(?:\s*(%|percent|px|pt|ms|s|words?|characters?|chars?|lines?|hours?|days?|bps|:1|x))?\b",
            f"{title} {old_text}",
            re.IGNORECASE,
        )
    )
    rule_numbers = set(extract_numeric_tokens(f"{title} {old_text}"))

    # Attempt TF-IDF retrieval against Verified Facts
    matched_fact, fact_similarity = _retrieve_relevant_verified_fact(
        f"{title} {old_text}",
        verified_facts,
    )
    fact_numbers: set = set()
    if matched_fact and str(matched_fact.get("numeric_value", "")).strip():
        fact_blob = " ".join(
            str(matched_fact.get(k, ""))
            for k in ("id", "statement", "numeric_value", "numeric_units", "applicable_conditions")
        )
        fact_numbers = set(extract_numeric_tokens(fact_blob))

    # 1. Replace vague qualifier spans in old_text
    if spans:
        parts: List[str] = []
        cursor = 0
        for sp in spans:
            s, e = int(sp["start"]), int(sp["end"])
            if s < cursor:
                continue
            parts.append(old_text[cursor:s])
            qual_key = str(sp["qualifier"]).lower()
            rep = replacements.get(qual_key, "explicitly defined")
            # Preserve leading capitalization if at start of sentence
            orig_phrase = sp["phrase"]
            if orig_phrase and orig_phrase[0].isupper() and rep:
                rep = rep[0].upper() + rep[1:]
            parts.append(rep)
            cursor = e
        parts.append(old_text[cursor:])
        rewritten = "".join(parts).strip()
    else:
        rewritten = old_text

    # 2. Ensure quantified threshold from (a) rule numbers, (b) Verified Fact, or (c) explicit placeholder
    threshold_source = "none"
    cited_fact_id: Optional[str] = None
    has_num_in_rewritten = bool(_NUMERIC_TOKEN_RE.search(rewritten))

    if has_num_in_rewritten:
        threshold_source = "rule_text"
        allowed_numbers = set(rule_numbers)
    elif rule_num_matches:
        m0 = rule_num_matches[0]
        num_val = m0.group(1)
        unit_val = (m0.group(2) or "").strip()
        num_phrase = f"{num_val} {unit_val}".strip()
        suffix = "" if rewritten.endswith(".") else "."
        rewritten = f"{rewritten}{suffix} Enforce the configured threshold of {num_phrase}."
        threshold_source = "rule_text"
        allowed_numbers = set(rule_numbers)
    elif matched_fact and str(matched_fact.get("numeric_value", "")).strip():
        cited_fact_id = str(matched_fact["id"])
        f_val = str(matched_fact.get("numeric_value", "")).strip()
        f_unit = str(matched_fact.get("numeric_units", "")).strip()
        f_cond = str(matched_fact.get("applicable_conditions", "")).strip()
        val_with_unit = f"{f_val}{f_unit}" if f_unit.startswith("%") else f"{f_val} {f_unit}".strip()
        cond_clause = f" ({f_cond})" if f_cond else ""
        suffix = "" if rewritten.endswith(".") else "."
        rewritten = (
            f"{rewritten}{suffix} Enforce the verified benchmark of {val_with_unit}{cond_clause} "
            f"[cited: {cited_fact_id}]."
        )
        threshold_source = "verified_fact"
        allowed_numbers = rule_numbers | fact_numbers
    else:
        # Insert explicit placeholder without any invented numbers
        if "[SET THRESHOLD:" not in rewritten:
            suffix = "" if rewritten.endswith(".") else "."
            rewritten = f"{rewritten}{suffix} Enforce an explicit measurable limit of [SET THRESHOLD: unit]."
        threshold_source = "placeholder"
        allowed_numbers = set(rule_numbers)

    # Guardrail: strip any accidental number not in allowed_numbers
    def _guard_number(match: re.Match) -> str:
        tok = match.group(0)
        if tok in allowed_numbers:
            return tok
        return "[SET THRESHOLD: unit]"

    rewritten = _NUMERIC_TOKEN_RE.sub(_guard_number, rewritten)

    # 3. Build Do and Don't examples with explicit provenance
    findings_list = list(past_findings or [])
    do_examples: List[Dict[str, Any]] = []
    dont_examples: List[Dict[str, Any]] = []

    for f in findings_list:
        fid = str(f.get("id") or "").strip()
        flagged = str(f.get("flagged_text") or "").strip()
        sugg = str(f.get("suggested_correction") or "").strip()
        dec_note = str(f.get("decision_note") or "").strip()
        r_state = str(f.get("review_state") or "")

        if fid and flagged and len(dont_examples) < 2:
            if not any(d["text"] == flagged for d in dont_examples):
                dont_examples.append({
                    "text": flagged,
                    "provenance": f"finding:{fid}",
                    "finding_id": fid,
                    "audit_id": f.get("audit_id"),
                    "source_type": "finding",
                })

        good_candidate = sugg or (dec_note if r_state in ("accepted", "modified") else "")
        if fid and good_candidate and len(do_examples) < 2:
            if not any(d["text"] == good_candidate for d in do_examples):
                do_examples.append({
                    "text": good_candidate,
                    "provenance": f"finding:{fid}",
                    "finding_id": fid,
                    "audit_id": f.get("audit_id"),
                    "source_type": "finding",
                })

    if not do_examples:
        if orig_do:
            do_examples.append({
                "text": orig_do,
                "provenance": f"rule:{rule_id}:do_example",
                "finding_id": None,
                "audit_id": None,
                "source_type": "rule_wording",
            })
        else:
            do_examples.append({
                "text": f"Comply with {title}: {rewritten}",
                "provenance": f"rule:{rule_id}:description",
                "finding_id": None,
                "audit_id": None,
                "source_type": "rule_wording",
            })

    if not dont_examples:
        if orig_dont:
            dont_examples.append({
                "text": orig_dont,
                "provenance": f"rule:{rule_id}:dont_example",
                "finding_id": None,
                "audit_id": None,
                "source_type": "rule_wording",
            })
        else:
            dont_examples.append({
                "text": f"Publish copy that omits the required criterion in {title} ({old_text})",
                "provenance": f"rule:{rule_id}:description",
                "finding_id": None,
                "audit_id": None,
                "source_type": "rule_wording",
            })

    primary_do_str = do_examples[0]["text"] if do_examples else ""
    primary_dont_str = dont_examples[0]["text"] if dont_examples else ""

    after_eval = score_rule_ambiguity(rewritten, primary_do_str, primary_dont_str, lexicon=lex)

    if after_eval["score"] >= before_eval["score"]:
        return {
            "status": "no improvement found",
            "improved": False,
            "message": "no improvement found",
            "rule_id": rule_id,
            "old_text": old_text,
            "new_text": old_text,
            "do_examples": do_examples,
            "dont_examples": dont_examples,
            "ambiguity_before": before_eval["score"],
            "ambiguity_after": before_eval["score"],
            "before_detail": before_eval,
            "after_detail": before_eval,
            "threshold_source": threshold_source,
            "cited_fact_id": cited_fact_id,
            "fact_similarity": fact_similarity if cited_fact_id else None,
            "human_signoff_note": "Suggestion for human sign-off. Nothing is applied automatically.",
        }

    return {
        "status": "candidate_ready",
        "improved": True,
        "message": "Suggestion for human sign-off generated.",
        "rule_id": rule_id,
        "old_text": old_text,
        "new_text": rewritten,
        "do_examples": do_examples,
        "dont_examples": dont_examples,
        "ambiguity_before": before_eval["score"],
        "ambiguity_after": after_eval["score"],
        "before_detail": before_eval,
        "after_detail": after_eval,
        "threshold_source": threshold_source,
        "cited_fact_id": cited_fact_id,
        "fact_similarity": fact_similarity if cited_fact_id else None,
        "human_signoff_note": "Suggestion for human sign-off. Nothing is applied automatically.",
    }
