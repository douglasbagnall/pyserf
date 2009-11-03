"Module documentation"

def foo(int_a, int_b):
    "function documentation"
    return(int_c, int_b)

class bar:
    "class documentation"
    def baz(self, int_c):
        "method documentation"
        print "line 1 to skip"
        print "line 2 to skip"
        return int_c

    def foo(self):
        """this method should not clash with the function"""

    def hi(a):
        "should raise a warning"'about first argument not being \\\"self\\\"'

    def __init__(self):
        print "hello"

    def quux(self):
        return None

def self_test():
    return int_a
