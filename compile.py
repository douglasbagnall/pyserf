#!/usr/bin/python

import os, sys

HERE = os.path.abspath(os.path.dirname(sys.argv[0]))
def pathto(x):
    return os.path.join(HERE, x)

NAME = 'template'
DIRECTORY = pathto('example/')
BUILD_DIR = pathto('example/build/')
EXECUTABLE = pathto('pyserf.py')


if len(sys.argv) > 1:
    NAME = sys.argv[1]

os.system("cd %s && %s %s.py -s -f && python setup.py build" %
          (DIRECTORY, EXECUTABLE, NAME))


sys.path.extend([ BUILD_DIR + x for x in os.listdir(BUILD_DIR) 
                  if x.startswith('lib') ])

print sys.path


exec("import %s as testmod" % NAME)

print "\nimported %s" % testmod
for a in dir(testmod):
    print getattr(testmod, a)
    try:
        print getattr(testmod, a)()
    except TypeError:
        pass


if hasattr(testmod, 'selftest'):
    print "found selftest, running"
    testmod.selftest()

if NAME == 'template':
    print testmod.foo
    x = testmod.bar()
    print testmod.bar.baz
    print x.baz(1)
    del x
    

