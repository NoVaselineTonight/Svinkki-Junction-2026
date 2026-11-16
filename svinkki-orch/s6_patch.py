"""agent-s6: the coach.py change for the model payload and the guardrail fixes. Applies to app/coach.py given as argv[1].
Every replacement must match exactly once."""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, ("not exactly once", old[:100])
    s = s.replace(old, new)


# 1. REFUSAL_MONEY_FI says what the app can really do (same as the English one)
rep(r'''REFUSAL_MONEY_FI = ("En voi siirtää rahaa enkä maksaa, vain katsoa tietojasi. "
                    "Haluatko nähdä, paljonko voit turvallisesti käyttää tällä viikolla?")''',
    r'''REFUSAL_MONEY_FI = ("En voi tehdä maksuja enkä siirtää rahaa pois S-mobiilista. Voin siirtää rahaa vain omalle "
                    "S-Pankin säästötilillesi tai S-Pankin rahastoon, ja vain kun hyväksyt sen.")''')

# 2. guardrail: own payments are not orders; a payment order wins over the other-people check
rep(r'''def guardrail(message):
    """Return a refusal string, or None when the message may proceed."""
    if _OTHER_RE.search(message):''',
    r'''# "did I pay", "if I pay", "should I pay off", "afford to pay": the customer talking about their own payment, not an
# order to the coach. "Can I / could I pay ..." stays an order (it asks the app to do it).
_SELF_PAY_RE = re.compile(
    r"(?<!\bcan )(?<!\bcould )(?<!\bmay )\b(?:i|we|i['’]ll|we['’]ll|afford to)\s+"
    r"(?:(?:just|already|usually|always|often|still|also|really|actually|ever|normally|even)\s+)?"
    r"(?:pay|send|transfer|move|withdraw|wire)\b", re.I)
# A message that starts as an order to the coach ("Please transfer ...", "Can you pay ..."): a long one is a payment
# order, not a document to explain.
_ORDER_START_RE = re.compile(
    r"^\s*(?:(?:please|pls|now|ok|okay|hey|hi)[,!.]?\s+)*(?:(?:can|could|would|will) you\s+(?:please\s+)?)?"
    r"(?:transfer|send|pay|wire|move|withdraw|siirrä|maksa|lähetä|nosta)\b", re.I)
_AMOUNT_RE = re.compile(r"\d|€|\beur(?:os?)?\b|\beuro\w*", re.I)


def _money_order(message):
    """True when the message asks the coach to pay or move money out of S-mobiili."""
    if bool(_INAPP_RE.search(message)) and not _EXTERNAL_RE.search(message):
        return False
    if _MOVE_RE.search(_SELF_PAY_RE.sub(" ", message)) and not _QUESTION_START.match(message):
        return True
    return bool(_MOVE_FI_RE.search(message))


def guardrail(message):
    """Return a refusal string, or None when the message may proceed."""
    if _money_order(message) and _AMOUNT_RE.search(message) and not re.search(r"cust\s*-?\s*\d", message, re.I):
        return REFUSAL_MONEY        # "send 200 euros to my friend's account": a payment, whoever it is for
    if _OTHER_RE.search(message):''')
rep(r'''    if _PROMPT_RE.search(message):
        return REFUSAL_PROMPT
    inapp = bool(_INAPP_RE.search(message)) and not _EXTERNAL_RE.search(message)
    if _MOVE_RE.search(message) and not _QUESTION_START.match(message) and not inapp:
        return REFUSAL_MONEY
    if _MOVE_FI_RE.search(message) and not inapp:
        return REFUSAL_MONEY
    return None''',
    r'''    if _PROMPT_RE.search(message):
        return REFUSAL_PROMPT
    if _money_order(message):
        return REFUSAL_MONEY
    return None''')

# 3. doc_intent: a long message that starts as a payment order is not a document
rep(r'''    if len(message) > DOC_MIN_CHARS:
        return message.strip()
    return None''',
    r'''    if len(message) > DOC_MIN_CHARS:
        if _ORDER_START_RE.match(message) and _money_order(_first_sentence(message)):
            return None         # "Please transfer 500 euros to ..." with a long reason: the guardrail answers it
        return message.strip()
    return None''')

# 4. one helper for the customer's own words
rep(r'''MODEL_RECEIPTS = 5 ''',
    r'''def anonymise_text(text):
    """The customer's own words as the model gets them: anonymise, then listed first names become [name]
    (tools.mask_names). Used for the message and the history, in both model paths."""
    return tools.mask_names(anonymise(str(text or "")))[0]


MODEL_RECEIPTS = 5 ''')

# 5. _model_view: tools.model_payload first (trimmed rows, no merchant hash), then anonymise
rep(r'''    view = {k: v for k, v in anonymise(result).items() if k not in _MODEL_DROP_KEYS}''',
    r'''    view = {k: v for k, v in anonymise(tools.model_payload(result)).items() if k not in _MODEL_DROP_KEYS}''')

# 6. history (both paths) and the Gemini message
rep(r'''        turns.append({"role": role, "parts": [{"text": anonymise(text)}]})''',
    r'''        turns.append({"role": role, "parts": [{"text": anonymise_text(text)}]})''')
rep(r'''        turns.append({"role": role, "content": anonymise(text)})''',
    r'''        turns.append({"role": role, "content": anonymise_text(text)})''')
rep(r'''    contents = _history_contents(history)
    contents.append({"role": "user", "parts": [{"text": message}]})
    sent_history = [json.loads(json.dumps(c)) for c in contents[:-1]]
    payload = {"system_prompt_summary": SYSTEM_SUMMARY, "profile": {"age_band": age_band},
               "history": sent_history, "user_message": message, "tool_results": [],''',
    r'''    contents = _history_contents(history)
    sent = anonymise_text(message)
    contents.append({"role": "user", "parts": [{"text": sent}]})
    sent_history = [json.loads(json.dumps(c)) for c in contents[:-1]]
    payload = {"system_prompt_summary": SYSTEM_SUMMARY, "profile": {"age_band": age_band},
               "history": sent_history, "user_message": sent, "tool_results": [],''')
rep(r'''    sent = anonymise(message)
    messages = _history_messages(history)''',
    r'''    sent = anonymise_text(message)
    messages = _history_messages(history)''')

# 7. the customer's own words in the customer section: notes and the goal name
rep(r'''    notes = [anonymise(" ".join(str(n).split())[:200]) for n in''',
    r'''    notes = [anonymise_text(" ".join(str(n).split())[:200]) for n in''')
rep(r'''            anonymise(g["name"]), _snap_money(g["target"]),''',
    r'''            anonymise_text(g["name"]), _snap_money(g["target"]),''')

# 8. the model is told what [name] means
rep(r'''27. The customer section is about this customer only and contains no comparison with other people; rule 11 still applies."""''',
    r'''27. The customer section is about this customer only and contains no comparison with other people; rule 11 still applies.
28. "[name]" in the customer's words is a person's first name the app removed before sending: say "they" or "that person", never "[name]"."""''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("patched", p)
