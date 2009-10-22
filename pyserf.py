#!/usr/bin/python

import compiler
from warnings import warn

import sys, os
import textwrap
import linecache

DEBUG = 0
COMMENTS = 2 # 1 -> few, 3 -> many
CONCAT_DECLS = 0

def log(*args):
    for x in args:
        print >> sys.stdout, x

def perhaps(write, string, level=2):
    if level <= COMMENTS:
        write(string)

def docformat(doc, mode='typestruct'):
    d = doc.split('\n')
    d2 = []
    for line in d:
        if len(line) > 70:
            d2.extend(textwrap.wrap(line, 70))
        else:
            d2.append(line)
    if mode != 'comment':
        return '"%s"' %('"\\\n    "'.join(d2))
    return ''.join([ '/* %-70s */\n' for x in d2 ])


class Class:
    type_struct_elements = (
        #(type,  name,  default)
        # some don't have types, because it looks naff eg: (char *)"string"
        ('int', 'ob_size', 0),
        ('', 'tp_name', '"%(py_fullname)s"'),
        ('', 'tp_basicsize', 'sizeof(%(obj)s)'),
        ('int', 'tp_itemsize', 0),
        ('destructor', 'tp_dealloc', '%(__del__)s'),
        ('printfunc', 'tp_print', 0),
        ('getattrfunc', 'tp_getattr', 0),
        ('setattrfunc', 'tp_setattr', 0),
        ('cmpfunc', 'tp_compare', '%(__cmp__)s'),
        ('reprfunc', 'tp_repr', '%(__repr__)s'),
        ('PyNumberMethods *', 'tp_as_number', 0),
        ('PySequenceMethods *', 'tp_as_sequence', 0),
        ('PyMappingMethods *', 'tp_as_mapping', 0),
        ('hashfunc', 'tp_hash', '%(__hash__)s'),
        ('ternaryfunc', 'tp_call', '%(__call__)s'),
        ('reprfunc', 'tp_str', '%(__str__)s'),
        ('getattrofunc', 'tp_getattro', '%(__getattr__)s'),
        ('setattrofunc', 'tp_setattro', '%(__setattr__)s'),
        ('PyBufferProcs *', 'tp_as_buffer', 0),
        ('long', 'tp_flags', 'Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE'),
        ('', 'tp_doc', '%(doc)s'),
        ('traverseproc', 'tp_traverse', 0),
        ('inquiry', 'tp_clear', 0),
        ('richcmpfunc', 'tp_richcompare', 0),
        ('long', 'tp_weaklistoffset', 0),
        ('getiterfunc', 'tp_iter', '%(__iter__)s'),
        ('iternextfunc', 'tp_iternext', 0),
        ('struct PyMethodDef *', 'tp_methods', '%(bindings_name)s'),
        ('struct PyMemberDef *', 'tp_members', 0),
        ('struct PyGetSetDef *', 'tp_getset', 0),
        ('struct _typeobject *', 'tp_base', 0),
        ('PyObject *', 'tp_dict', 0),
        ('descrgetfunc', 'tp_descr_get', 0),
        ('descrsetfunc', 'tp_descr_set', 0),
        ('long', 'tp_dictoffset', 0),
        ('initproc', 'tp_init', '%(__init__)s'),
        ('allocfunc', 'tp_alloc', 0),
        ('newfunc', 'tp_new', '%(__new__)s'),
        ('freefunc', 'tp_free', 0),
        )


    def __init__(self, node, module):
        self.node = node
        self.name = node.name
        self.module = module
        self.doc = docformat(node.doc)
        self.type = "%s_%s_type" % (module, self.name)
        self.obj = "%s_%s_object" % (module, self.name)
        self.methods = []
        self.magic_methods = {'__new__': 0,
                              '__del__': 0,
                              '__init__': 0,
                              '__cmp__': 0,
                              '__repr__': 0,
                              '__str__': 0,
                              '__getattr__': 0,
                              '__setattr__': 0,
                              '__iter__': 0,
                              '__hash__': 0,
                              '__call__': 0,
                              '__dealloc__': 0,
                              }
        self.bindings_name = '%s_methods' % self.name

    def addMethod(self, f):
        self.methods.append(f)
        if f.name in self.magic_methods.keys():
            self.magic_methods[f.name] = f.cname


    def write_meth_bindings(self, fh):
        write = fh.write
        perhaps(write, "/* bindings for %s */\n" % self.name)
        write("static PyMethodDef %s[] = {\n" % self.bindings_name)
        for meth in self.methods:
            if meth.name not in self.magic_methods:
                write('    {"%s", (PyCFunction)%s, %s,\n    "%s"},\n' % meth.bindinfo)

        write("    {NULL}\n};\n\n")

    def write_init_1(self, fh):
        write = fh.write
        if not self.magic_methods['__new__']:
            write("    %(type)s.tp_new = PyType_GenericNew;\n" % self.__dict__)
        s = "    if (PyType_Ready(&%(type)s) < 0)\n        return;\n\n"
        write(s % self.__dict__)

    def write_init_2(self, fh):
        write = fh.write
        s = ('    Py_INCREF(&%(type)s);\n    PyModule_AddObject(m, "%(name)s",'
             ' (PyObject *)&%(type)s);\n\n'
             )
        write(s % self.__dict__)

    def write_object_struct(self, fh):
        fh.write("typedef struct {\n    PyObject_HEAD\n")
        perhaps(fh.write, "    /* XXX define %s.%s objects here. */\n" %(self.module, self.name), 1)
        fh.write("\n} %s;\n\n" % self.obj)

    def write_type_struct(self, fh):
        write = fh.write
        write("static PyTypeObject %s = {\n    PyObject_HEAD_INIT(NULL)\n" % self.type)
        d = self.__dict__.copy()
        d['py_fullname'] = '%s.%s' % (self.module, self.name)
        d.update(self.magic_methods)
        for t, slot, default in self.type_struct_elements:
            if isinstance(default, str):
                val = default % d
                if val != '0' and t:
                    f1 = '    (%s)%s,' % (t, (default % d))
                else:
                    f1 = '    %s,' % val
            else:
                f1 = '    %s,' % default
            if len(f1) <= 50:
                write("%-50s /*%17s */\n" % (f1, slot))
            else:
                write("%s /*%17s */\n" % (f1, slot))

        write('};\n')


class TopLevel(Class):
    def __init__(self, ast, module):
        self.node = ast.node
        self.name = 'top_level'
        self.module = module
        self.doc = ast.doc
        self.type = None
        self.obj = None
        self.methods = []
        self.magic_methods = {}
        self.bindings_name = '%s_functions' % self.name


    def write_init(self, fh):
        warn("TopLevel.write_init: go away!")
    def write_object_struct(self, fh):
        warn("TopLevel.write_init: go away!")
    def write_type_struct(self, fh):
        warn("TopLevel.type_struct: go away!")



class Method:
    def __init__(self, node, module, classname):
        self.node = node
        self.name = node.name
        self.module = module
        self.classname = classname
        self.skippedlines = []
        self.cname = "%s_py_%s_%s" % (module, classname, self.name)

    def parseNode(self):
        n = self.node
        argtypes = []
        if self.classname != 'Function':
            if n.argnames.pop(0) != 'self':
                warn("popped argument 0, but it wasn't 'self', line %s" % n.lineno)

        self.ftypes, self.args, self.cvars, self.returns = [], [], [], []

        #find method type -- if 1 object arg, use METH_O
        for a in n.argnames:
            argtypes.append(self.find_c_type(a))
        for v, tf, t in argtypes:
            self.args.append(v)
            self.ftypes.append(tf)
            self.cvars.append((t, v))

        arity = len(n.argnames)
        print arity
        if arity == 0:
            self.methtype = 'METH_NOARGS'
        elif arity == 1 and self.ftypes == ['O']:
            self.methtype = 'METH_O'
            self.cvars = []    #don't redeclare object
        else:
            self.methtype = 'METH_VARARGS'

        for fnode in n.code.nodes:
            if repr(fnode).startswith('Return'):
                values = []
                formats = []
                retlist = fnode.value.asList()
                if retlist == ('None',):
                    self.returns = [([], [])]
                    continue
                for retval in retlist:
                    if type(retval) is tuple:
                        retval = retval[0]
                    v, tf, t = self.find_c_type(retval)
                    if (t, v) not in self.cvars:
                        self.cvars.append((t, v))
                    values.append(v)
                    formats.append(tf)
                self.returns.append((formats, values))
            else:
                print fnode, fnode.lineno
                self.skippedlines.append(
                    linecache.getline("%s.py" % self.module, fnode.lineno))

        if not self.returns:
            self.returns = [([], [])]


        if n.doc:
            self.doc = [ x.strip() + ' ' for x in n.doc.split('\n') ]
        else:
            self.doc = []

        self.bindinfo = (self.name, self.cname, self.methtype, '"\\\n    "'.join(self.doc))
        self.cvars.sort()

    def write_decl(self, fh):
        # does this ever vary?
        fh.write('static PyObject *%s (PyObject*, PyObject*);\n' %(self.cname))

    def write(self, fh):
        write = fh.write
        perhaps(write, "/* %s (binds to %s.%s) */\n" %(self.cname,
                                                       self.classname or '<module %s>' % self.module,
                                                       self.name), 2)

        for line in self.doc:
            perhaps(write, '/* %s  */\n' % line, 1)

        if self.methtype == 'METH_O':
            write('\nstatic PyObject *\n%s (PyObject *self, PyObject *%s)\n{\n' %(self.cname, self.args[0]))
        else:
            write('\nstatic PyObject *\n%s (PyObject *self, PyObject *args)\n{\n' %(self.cname))
        prev = None
        for t, v in self.cvars:
            if not CONCAT_DECLS:
                write("    %s%s;\n" % (t, v))
            elif t == prev:
                write(", %s" % v)
            elif prev is not None:
                write(";\n    %s%s" % (t, v))
            else:
                write("    %s%s" % (t, v))
            prev = t
        if self.cvars and CONCAT_DECLS:
            write(";\n\n")
        if self.methtype == 'METH_VARARGS':
            write('    if (!PyArg_ParseTuple(args, "%s", &%s))\n' %(''.join(self.ftypes),
                                                          ', &'.join(self.args)))
            write('        return NULL;\n')
        elif self.methtype == 'METH_O':
            perhaps(write, '    /*no arguments to parse (using METH_O) */')
        else:
            perhaps(write, '    /*no arguments to parse (using METH_NOARGS) */')

        if self.skippedlines:
            perhaps(write, '\n    /*********** ignoring these lines of python ***********/\n')
            for line in self.skippedlines:
                write('    /* %s */\n' % line.rstrip())
            perhaps(write, '    /******************************************************/\n')
        perhaps(write, '\n    /* XXX your code here */\n\n', 1)
        if DEBUG:
            write('    /*debug*/\n    printf("in %s\\n\\n");\n' % self.cname)

        if self.returns == [([], [])]:
            write('    return Py_BuildValue("");\n')
        else:
            log(self.returns)
            for tf, v in self.returns:
                log(*((str(x), dir(x)) for x in v))
                log(*(getattr(x, 'name', '') for x in v))
                write('    return Py_BuildValue("%s", %s);\n' % (''.join(tf),
                                                                 ', '.join(str(x) for x in v)))
        write('}\n\n')



    def find_c_type(self, pyarg):
        if '_' not in pyarg: #assume object
            return (pyarg,) + self.type_info['object']
        for splitter in ('____', '___', '__', '_'):
            if splitter in pyarg:
                t, arg = pyarg.split(splitter, 1)
                if t in self.type_info:
                    return (arg,) + self.type_info[t]
                else:#assume object
                    return (pyarg,) + self.type_info['object']

        raise ValueError("can't parse the argument '%s'" % pyarg)

    type_info = {
        'int'  : ('i', 'int '),
        'str'  : ('s', 'char *'),
        'float32': ('f', 'float '),
        'float': ('d', 'double '),
        'double': ('d', 'double '),
        'list': ('O', 'PyObject *'),
        'tuple': ('O', 'PyObject *'),
        'dict': ('O', 'PyObject *'),
        'object': ('O', 'PyObject *'),
        'obj': ('O', 'PyObject *'),
        'PyObject': ('O', 'PyObject *'),
        'floatSeq': ('O', 'PyObject *'),
        'intSeq': ('O', 'PyObject *'),
        }


class BlankMethod:
    """same interface as Method, but not interpreted from a node."""
    def __init__(self, name, module, classname):
        self.name = name
        self.module = module
        self.classname = classname
        self.skippedlines = []
        self.cname = "%s_py_%s_%s" % (module, classname, self.name)
        self.code = ''
        self.type = 'static PyObject *'

    def parseNode(self):
        pass

    def write_decl(self, fh):
        fh.write('%s %s (PyObject*, PyObject*);\n' %(self.type, self.cname))

    def write(self, fh):
        fh.write('\n%s %s (PyObject *self, PyObject *args)\n{\n    ' %(self.type, self.cname))
        fh.write('\n    '.join(self.code))
        fh.write('\n}\n\n')



class py2c:
    def __init__(self, f, output=sys.stdout,
                 comments=None, setup_py=False, force_overwrite=False):
        self.ast = compiler.parseFile(f)
        self.mod = f.replace('.py', '')
        self.toplevel = TopLevel(self.ast, self.mod)
        self.classes = []
        if hasattr(output, 'write'):
            self.fh = output
            self.outfilename = None
        else: #default to using python name with s/py/c/
            if not output:
                output = self.mod + '.c'
            if (os.path.exists(output) and not force_overwrite and
                raw_input("%s exists, overwrite? [y/N]" % output).lower() != 'y'):
                raise IOError("won't overwrite %s, stopping" % output)
            self.outfilename = output
            self.fh = open(output, 'w')

        self.setup_py = setup_py
        self.force_overwrite = force_overwrite
        if comments is not None:
            global COMMENTS
            COMMENTS = comments

    def go(self):
        nodes = self.ast.node.nodes
        for n in nodes:
            if repr(n).startswith('Function'):
                f = Method(n, self.mod, 'Function')
                self.toplevel.addMethod(f)
                f.parseNode()

            elif repr(n).startswith('Class'):
                self.doClass(n)

            else:
                warn("ignoring %s" % n)

        # parsed, now print
        all = [self.toplevel] + self.classes # putting functions at the top.
        self.doHeader()
        self.title('headers.')

        for c in self.classes:
            c.write_object_struct(self.fh)

        for c in all:
            for m in c.methods:
                m.write_decl(self.fh)

        self.title('functions and methods')
        for c in all:
            for m in c.methods:
                m.write(self.fh)
        self.title('method binding structs')
        for c in all:
            c.write_meth_bindings(self.fh)
        self.title('type definition structs')
        for c in self.classes:
            c.write_type_struct(self.fh)
        self.title('initialisation.')
        self.doInit()
        if self.setup_py:
            self.write_setup_py()

    def doClass(self, n):
        c = Class(n, self.mod)
        self.classes.append(c)
        for n in n.code.getChildNodes():
            if repr(n).startswith('Function'):
                f = Method(n, self.mod, c.name)
                c.addMethod(f)
                f.parseNode()
        if not c.magic_methods['__dealloc__']:
            f = BlankMethod('__dealloc__', self.mod, c.name)
            f.type = 'static void'
            f.code = ['self->ob_type->tp_free((PyObject*)self);']
            c.addMethod(f)

    def doHeader(self):
        self.fh.write('#include <Python.h>\n#include "structmember.h"\n\n')

    def doInit(self):
        write = self.fh.write
        write("#ifndef PyMODINIT_FUNC\n#define PyMODINIT_FUNC void\n#endif\n")
        write("PyMODINIT_FUNC\ninit%s(void)\n{\n    PyObject* m;\n" % self.mod)
        for c in self.classes:
            c.write_init_1(self.fh)
        write('    m = Py_InitModule3("%s", %s,\n'
              '        "%s");\n\n' % (self.mod,
                                      self.toplevel.bindings_name,
                                      self.ast.doc))
        write('    if (m == NULL)\n        return;\n\n')

        for c in self.classes:
            c.write_init_2(self.fh)

        write('\n}\n\n')


    def comment(self, s):
        perhaps(self.fh.write, '/* %s */\n' % s, 1)

    def title(self, s):
        perhaps(self.fh.write, '\n', 1)
        hr = '/%s/\n' % ('*' * 70)
        perhaps(self.fh.write, hr, 2)
        perhaps(self.fh.write, '/* %-66s */\n' % s, 1)
        perhaps(self.fh.write, hr, 2)


    def write_setup_py(self):
        """Writes a distutils setup script for comilation"""
        if (os.path.exists("setup.py") and not self.force_overwrite and
            raw_input("setup.py exists, overwrite? [y/N]").lower() != 'y'):
            return
        f = open("setup.py", "w")
        f.write("from distutils.core import setup, Extension\n")
        f.write('setup(name="%s",\n'
                '      version="1.0",\n'
                '      ext_modules=[Extension("%s", ["%s"])])\n'
                % (self.mod, self.mod, self.outfilename)
                )
        f.close()



if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-i", "--input", dest="filename",
                      help="read python from FILE", metavar="FILE")

    parser.add_option("-o", "--output", dest="output",
                      help="write C code to FILE", metavar="FILE")

    parser.add_option("-c", "--comments", dest="comments", default=2, type="int",
                      help="comment verbosity (0-3)", metavar="LEVEL")

    parser.add_option("-v", "--verbose", dest="verbose", default=False,
                      help="verbose debugging", action="store_true")

    parser.add_option("--concat-declarations", dest="concat", default=False,
                      help="declare similar vars on one line", action="store_true")

    parser.add_option("-s", "--setup-py", dest="setup_py", default=False,
                      help="generate setup.py stub", action="store_true")

    parser.add_option("-f", "--force", dest="force", default=False,
                      help="force overwriting of files", action="store_true")


    (options, args) = parser.parse_args()
    fn = options.filename or args[0]
    output = options.output or None
    if output == '-':
        output = sys.stdout

    #next two are global vars!
    DEBUG = options.verbose
    CONCAT_DECLS = options.concat
    x = py2c(fn, output, options.comments, options.setup_py, options.force)
    x.go()
