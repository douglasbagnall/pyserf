#!/usr/bin/python

import pyserf

TEST1 = pyserf.pathto('template.py')




def compile_test():
    ps = pyserf.py2c(TEST1)
    
    
compile_test()
