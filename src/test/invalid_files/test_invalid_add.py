from invalid_add import *

def test_invalid_add():
    """
    This test is supposed to fail. Used for testing that the CI server
    detects a failed test.
    """
    a = 1
    b = 2
    res = a + b
    assert res == invalid_add(a, b)