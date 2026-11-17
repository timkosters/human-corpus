from evals.heuristics import expected_tags, flags, has_tag, near_dup_rate


def test_flags():
    assert flags("Thank you for all your kindness.") == []
    assert "quote_debris" in flags('And I will miss you every day."')
    assert "quoted" in flags('"I hope you forgive me."')
    assert "dialogue_tag" in flags('"Forgive me," he said.')
    assert "dangling_ref" in flags("He has taught me to say thank you.")
    assert "proper_name" in flags("You know that Brooke has always been a good friend to me.")
    assert "proper_name" not in flags("There's less dusk and dark, and much more sunlight.")
    assert "archaic" in flags("Thou quiet soul, sleep thou a quiet sleep!")
    assert flags("Thou quiet soul.", allow_archaic=True) == []


def test_tags():
    r = {"register": "personal+emotive", "styles": ["grateful"]}
    assert has_tag(r, "intimate") and has_tag(r, "grateful") and has_tag(r, "personal")
    assert not has_tag({"register": "narrative"}, "intimate")
    assert expected_tags({"register": "intimate", "style": "grateful, casual"}) == ["intimate", "grateful", "casual"]


def test_dups():
    assert near_dup_rate(["I am so sorry.", "I am so sorry!", "The river rose."]) == 1 / 3
