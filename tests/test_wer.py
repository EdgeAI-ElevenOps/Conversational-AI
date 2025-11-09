import math

from wer import wer


def test_perfect_match():
    ref = "hello world"
    hyp = "hello world"
    assert wer(ref, hyp) == 0.0


def test_substitution():
    ref = "hello world"
    hyp = "hello there"
    # one substitution -> 1/2
    assert math.isclose(wer(ref, hyp), 0.5)


def test_insertion():
    ref = "hello world"
    hyp = "hello beautiful world"
    # one insertion -> 1/2
    assert math.isclose(wer(ref, hyp), 0.5)


def test_deletion():
    ref = "hello wonderful world"
    hyp = "hello world"
    # one deletion -> 1/3
    assert math.isclose(wer(ref, hyp), 1.0 / 3.0)


def test_empty_reference_and_hypothesis():
    assert wer("", "") == 0.0


def test_empty_reference_nonempty_hypothesis():
    val = wer("", "hello")
    assert val == float('inf')
