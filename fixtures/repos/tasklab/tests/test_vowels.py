from tasklab.vowels import count_vowels


def test_vowels_basic() -> None:
    assert count_vowels("hello") == 2
    assert count_vowels("Rhythm") == 0
    assert count_vowels("AEIOU") == 5
