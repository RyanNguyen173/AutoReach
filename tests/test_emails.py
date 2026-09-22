from autoreach.emails import clean, decode_cfemail, deobfuscate, find_emails


def test_deobfuscate_bracket_styles():
    assert deobfuscate("kharjo [at] example [dot] org") == "kharjo@example.org"
    assert deobfuscate("sramirez(at)example(dot)org") == "sramirez@example.org"
    assert deobfuscate("a {AT} b {DOT} com") == "a@b.com"


def test_plain_word_at_is_left_alone():
    assert find_emails("We meet at school at noon.") == []


def test_decode_cfemail():
    assert decode_cfemail("422f252330212b2302273a232f322e276c2d3025") == "mgarcia@example.org"


def test_clean():
    assert clean("mailto:JDoe@Example.org?subject=Hi") == "jdoe@example.org"
    assert clean("jdoe@example.org.") == "jdoe@example.org"
    assert clean("logo@2x.png") is None
    assert clean("not-an-email") is None


def test_find_emails_dedupes_in_order():
    text = "b@example.org, A@example.org and b@example.org again"
    assert find_emails(text) == ["b@example.org", "a@example.org"]
