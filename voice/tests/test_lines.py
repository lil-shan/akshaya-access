import lines

PAIRS = {name: value for name, value in vars(lines).items()
         if isinstance(value, tuple) and len(value) == 2 and all(isinstance(part, str) for part in value)}
PAIRS |= {f"HANDOFF_WHY[{key}]": value for key, value in lines.HANDOFF_WHY.items()}
PAIRS |= {f"HEARD[{key}]": value for key, value in lines.HEARD.items()}


def test_every_line_has_malayalam_and_english():
    assert len(PAIRS) > 20
    assert all(ml.strip() and en.strip() for ml, en in PAIRS.values())


def test_whatever_is_labelled_simulated_in_english_is_labelled_in_malayalam_too():  # review round 1, finding 17
    unlabelled = [name for name, (ml, en) in PAIRS.items() if "SIMULATED" in en and "സിമുലേറ്റഡ്" not in ml and "ഡെമോ" not in ml]
    assert unlabelled == []


def test_no_line_promises_a_call_back_a_later_lookup_or_a_live_transfer():  # review round 1, finding 9
    for name, (ml, en) in PAIRS.items():
        for promise in ["call you back", "call back", "passing this call", "talk to a person"]:
            assert promise not in en, name
        for promise in ["തിരിച്ചു വിളിക്കും", "കൈമാറുന്നു", "സ്ഥിതി അന്വേഷിക്കാം"]:
            assert promise not in ml, name
