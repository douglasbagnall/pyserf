#!/usr/bin/python

import pyserf

TEST1 = pyserf.pathto('template.py')




def compile_test():
    f = open('template.c', 'w')
    pyserf.write = f.write
    ps = pyserf.py2c(TEST1)
    pyserf.write_makefile('template', 'template.c')
    
compile_test()
