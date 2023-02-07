from add import *

def test_add():
    """
    This is a sample test to make sure that the server correctly runs 
    and detects a passing test.
    """
    a = 1
    b = 2
    res = a + b
    assert res == add(a,b)