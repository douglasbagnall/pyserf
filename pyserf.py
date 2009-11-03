#!/usr/bin/python

import ast
import _ast

from warnings import warn

import sys, os
import textwrap
import linecache
from pprint import pprint, pformat

HERE = os.path.dirname(sys.argv[0])
#print HERE
MAKEFILE_TEMPLATE = os.path.join(HERE, 'makefile-template')

DEBUG = 0
COMMENTS = 2 # 1 -> few, 3 -> many
CONCAT_DECLS = 0
OVERWRITE = False
write = sys.stdout.write

HERE = os.path.abspath(os.path.dirname(sys.argv[0]))
def pathto(x):
    return os.path.join(HERE, x)

def log(*args):
    for x in args:
        print >> sys.stderr, x

def dump_node(node, recurse=False):
    log(ast.dump(node, annotate_fields=True, include_attributes=True))

def perhaps_write(string, level=2):
    if level <= COMMENTS:
        write(string)

def title(s):
    perhaps_write('\n', 1)
    hr = '/%s/\n' % ('*' * 70)
    perhaps_write(hr, 2)
    perhaps_write('/* %-66s */\n' % s, 1)
    perhaps_write(hr, 2)


def get_doc(node):
    try:
        #node->first_expr->str_obj->string_value
        raw_doc = node.body[0].value.s
    except (LookupError, AttributeError), e:
        return []
    lines = [x.strip() for x in raw_doc.split('\n')]
    reformatted = []
    for line in lines:
        if len(line) > 70:
            reformatted.extend(textwrap.wrap(line, 70))
        elif line:
            reformatted.append(line)
    #delete the doc node, so it doesn't show in ignored function body.
    del node.body[0]
    return reformatted


def pydoc_format(doc):
    return '\\\n    '.join('"%s"' % x for x in doc)

def cdoc_format(doc):
    return ''.join('/* %-70s */\n' % x for x in doc)


class MethodContext(object):
    def write_meth_bindings(self):
        perhaps_write("/* bindings for %s */\n" % self.name)
        write("static PyMethodDef %s[] = {\n" % self.bindings_name)
        for meth in self.methods:
            if meth.name not in self.magic_methods:
                write('    {"%s", (PyCFunction)%s, %s,\n    "%s"},\n' % meth.bindinfo)

        write("    {NULL}\n};\n\n")


class Module(MethodContext):
    name = 'top_level'
    def __init__(self, tree, name):
        #dump_node(tree)
        self.doc = get_doc(tree)
        self.name = name
        self.type = None
        self.obj = None
        self.methods = []
        self.classes = []
        self.magic_methods = {}
        self.bindings_name = 'top_level_functions'

    def addchild(self, name, child):
        if isinstance(child, Function):
            self.methods.append(child)
        else:
            self.classes.append(child)


class Class(MethodContext):
    def __init__(self, node, context):
        self.doc = get_doc(node)
        self.name = node.name
        self.module = context.name
        self.type = "%s_%s_type" % (self.module, self.name,)
        self.obj = "%s_%s_object" % (self.module, self.name,)
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

        f = BlankMethod('__dealloc__', self.name)
        f.type = 'static void'
        f.code = ['self->ob_type->tp_free((PyObject*)self);']
        self.addchild(f.name, f)

        self.bindings_name = '%s_methods' % self.name

    def addchild(self, name, child):
        if not isinstance(child, (Function, BlankMethod)):
            raise NotImplementedError("can only add methods to classes, not %s" % child)
        self.methods.append(child)
        if child.name in self.magic_methods.keys():
            self.magic_methods[child.name] = child.cname

    def write_init_1(self):
        if not self.magic_methods['__new__']:
            write("    %(type)s.tp_new = PyType_GenericNew;\n" % self.__dict__)
        s = "    if (PyType_Ready(&%(type)s) < 0)\n        return;\n\n"
        write(s % self.__dict__)

    def write_init_2(self):
        s = ('    Py_INCREF(&%(type)s);\n    PyModule_AddObject(m, "%(name)s",'
             ' (PyObject *)&%(type)s);\n\n'
             )
        write(s % self.__dict__)

    def write_object_struct(self):
        write("typedef struct {\n    PyObject_HEAD\n")
        perhaps_write("    /* XXX define %s.%s objects here. */\n" % (self.module, self.name,), 1)
        write("\n} %s;\n\n" % self.obj)

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

    def write_type_struct(self):
        write("static PyTypeObject %s = {\n    PyObject_HEAD_INIT(NULL)\n" % self.type)
        d = self.__dict__.copy()
        d['doc'] = pydoc_format(self.doc)
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


class Argument(object):
    """Parse an _ast.Name object"""
    def __init__(self, source):
        self.pyname = source.id
        self.cname, self.ftype, self.ctype = self.find_c_type(self.pyname)

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

    def __str__(self):
        return "<Argument %s %s %s %s>" % (self.ctype, self.ftype,
                                           self.pyname, self.cname,)

    __repr__ = __str__
    def __cmp__(self, other):
        return cmp(repr(self), repr(other))


class Function(object):
    def __init__(self, node, owner):
        self.doc = get_doc(node)
        self.name = node.name
        self.owner = owner
        self.classname = self.owner.name
        self.cname = "%s_%s" % (owner.name, self.name)

        #dump_node(node)
        self.args = [Argument(x) for x in node.args.args]
        if isinstance(self.owner, Class):
            if self.args[0].pyname != 'self':
                log("First argument in method '%s.%s' isn't 'self', line %s"
                    % (self.owner.name, self.name, node.lineno))
            del self.args[0]

        self.returns = []
        cvars = dict(((x.cname, x) for x in self.args))

        #find method type -- if 1 object arg, use METH_O
        if not self.args:
            self.methtype = 'METH_NOARGS'
        elif len(self.args) == 1 and self.args[0].ftype == ['O']:
            self.methtype = 'METH_O'
        else:
            self.methtype = 'METH_VARARGS'

        unskippedlines = set()
        skippedlines = set()
        for fnode in node.body:
            if isinstance(fnode, _ast.Return):
                #log('found a Return!')
                if isinstance(fnode.value, _ast.Tuple):
                    retlist = [Argument(x) for x in fnode.value.elts]
                elif fnode.value.id != 'None':
                    retlist = [Argument(fnode.value)]
                else:
                    self.returns.append([])
                    continue
                cvars.update((x.cname, x) for x in retlist)
                self.returns.append(retlist)
                unskippedlines.add(fnode.lineno)
            else:
                skippedlines.add(fnode.lineno)

        self.skippedlines = [pylines[x - 1] for x in sorted(skippedlines - unskippedlines)]
        #log(self.skippedlines, skippedlines, unskippedlines, cvars)

        if not self.returns:
            self.returns = [[]]
        self.bindinfo = (self.name, self.cname, self.methtype, '"\\\n    "'.join(self.doc))
        self.cvars = [v for k, v in sorted(cvars.items())]

    def write_decl(self):
        # does this ever vary?
        write('static PyObject *%s (PyObject*, PyObject*);\n' %(self.cname))

    def write(self):
        perhaps_write("/* %s (binds to %s.%s) */\n" %(self.cname,
                                                      self.classname or '<module %s>' % self.module,
                                                      self.name), 2)

        perhaps_write(cdoc_format(self.doc), 1)

        if self.methtype == 'METH_O':
            write('\nstatic PyObject *\n%s (PyObject *self, PyObject *%s)\n{\n' %(self.cname, self.args[0]))
        else:
            write('\nstatic PyObject *\n%s (PyObject *self, PyObject *args)\n{\n' %(self.cname))
        prev = None
        for x in self.cvars:
            if not CONCAT_DECLS:
                write("    %s%s;\n" % (x.ctype, x.cname))
            elif x.ctype == prev:
                write(", %s" % (x.cname,))
            elif prev is not None:
                write(";\n    %s%s" % (x.ctype, x.cname))
            else:
                write("    %s%s" % (x.ctype, x.cname))
            prev = x.ctype
        if self.cvars and CONCAT_DECLS:
            write(";\n\n")
        if self.methtype == 'METH_VARARGS':
            write('    if (!PyArg_ParseTuple(args, "%s", &%s))\n' %
                  (''.join(x.ftype for x in self.args),
                   ', &'.join(x.cname for x in self.args)))
            write('        return NULL;\n')
        elif self.methtype == 'METH_O':
            perhaps_write('    /*no arguments to parse (using METH_O) */')
        else:
            perhaps_write('    /*no arguments to parse (using METH_NOARGS) */')

        if self.skippedlines:
            perhaps_write('\n    /***  ignoring these lines of python  ***/\n')
            for line in self.skippedlines:
                write('    /* %s */\n' % line.rstrip())
            perhaps_write('    /***  finished ignoring  ***/\n')
        perhaps_write('\n    /* XXX your code here */\n\n', 1)
        if DEBUG:
            write('    /*debug*/\n    printf("in %s\\n\\n");\n' % self.cname)

        if self.returns == [[]]:
            write('    return Py_BuildValue("");\n')
        else:
            for rset in self.returns:
                write('    return Py_BuildValue("%s", %s);\n' %
                      (''.join(x.ftype for x in rset), ', '.join(x.cname for x in rset)))
        write('}\n\n')




class BlankMethod:
    """same interface as Method, but not interpreted from a node."""
    def __init__(self, name, classname):
        self.name = name
        self.classname = classname
        self.skippedlines = []
        self.cname = "%s_%s" % (classname, self.name)
        self.code = ''
        self.type = 'static PyObject *'

    def write_decl(self):
        write('%s %s (PyObject*, PyObject*);\n' %(self.type, self.cname))

    def write(self):
        write('\n%s %s (PyObject *self, PyObject *args)\n{\n    ' %(self.type, self.cname))
        write('\n    '.join(self.code))
        write('\n}\n\n')


def compile2ast(filepath):
    f = open(filepath)
    s = f.read()
    f.close()
    return s, compile(s, os.path.basename(filepath), 'exec', ast.PyCF_ONLY_AST)

def climb(tree, parent=None, context=None):
    if isinstance(tree, _ast.ClassDef):
        klass = Class(tree, context)
        context.addchild(tree.name, klass)
        context = klass

    elif isinstance(tree, _ast.FunctionDef):
        fn = Function(tree, context)
        context.addchild(tree.name, fn)
        return context #no further descent -- ignore nested functions

    for c in ast.iter_child_nodes(tree):
        climb(c, tree, context)

    return context


def py2c(fn):
    module_string, tree = compile2ast(fn)
    module_name = os.path.basename(fn).split('.', 1)[0]
    global pylines
    pylines = [x.rstrip() for x in module_string.split('\n')]

    module = Module(tree, module_name)
    climb(tree, context=module)

    # parsed, now print
    pyversion = sys.version[:3]
    write('#include <python%s/Python.h>\n#include "python%s/structmember.h"\n\n' %
          (pyversion, pyversion))
    title('headers.')

    for c in module.classes:
        c.write_object_struct()

    function_holders = ([module] + module.classes)

    for c in function_holders:
        for m in c.methods:
            m.write_decl()

    title('functions and methods')
    for c in function_holders:
        for m in c.methods:
            m.write()
    title('method binding structs')
    for c in function_holders:
        c.write_meth_bindings()
    title('type definition structs')
    for c in module.classes:
        c.write_type_struct()
    title('initialisation.')

    # init
    write("#ifndef PyMODINIT_FUNC\n#define PyMODINIT_FUNC void\n#endif\n")
    write("PyMODINIT_FUNC\ninit%s(void)\n{\n    PyObject* m;\n" % module.name)
    for c in module.classes:
        c.write_init_1()
    write('    m = Py_InitModule3("%s", %s,\n'
          '        %s);\n\n' % (module.name,
                                  module.bindings_name,
                                  pydoc_format(module.doc)))
    write('    if (m == NULL)\n        return;\n\n')

    for c in module.classes:
        c.write_init_2()

    write('\n}\n\n')
    return module

def open_if_allowed(filename):
    if (os.path.exists(filename) and not OVERWRITE and
        raw_input("%s exists, overwrite? [y/N]" % filename).strip() not in 'Yy'):
        raise IOError("Can't overwrite %s" % filename)
    return open(filename, 'w')

def write_setup_py(modname, cfilename):
    """Writes a distutils setup script for compilation"""
    #XXX not recently  tested.
    try:
        f = open_if_allowed("setup.py")
    except IOError, e:
        print >>sys.stderr, e
        return
    f.write("from distutils.core import setup, Extension\n")
    f.write('setup(name="%s",\n'
            '      version="1.0",\n'
            '      ext_modules=[Extension("%s", ["%s"])])\n'
            % (modname, modname, cfilename)
            )
    f.close()

def write_makefile(modname, cfilename):
    """Write a Makefile for compilation"""
    try:
        f = open_if_allowed("Makefile")
    except IOError, e:
        print >>sys.stderr, e
        return
    f2 = open(MAKEFILE_TEMPLATE)
    makefile = f2.read()
    f2.close()
    f.write(makefile % {'modulename': modname,
                        'cfilename': cfilename})

    f.close()


def main():
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

    parser.add_option("-m", "--makefile", dest="makefile", default=False,
                      help="generate makefile", action="store_true")

    parser.add_option("-f", "--force", dest="force", default=False,
                      help="force overwriting of files", action="store_true")

    (options, args) = parser.parse_args()
    fn = options.filename or args[0]
    global OVERWRITE
    OVERWRITE = options.force
    global DEBUG, CONCAT_DECLS, COMMENTS
    DEBUG = options.verbose
    CONCAT_DECLS = options.concat
    COMMENTS = options.comments

    if options.output == '-':
        output = sys.stdout
    else:
        if options.output:
            ofn = options.output
        elif fn[-3:] == '.py':
            ofn = fn[:-3] + '.c'
        else:
            ofn = fn + '.c'

        try:
            output = open_if_allowed(ofn)
        except IOError, e:
            print >>sys.stderr, e
            print >>sys.stderr, "use -f to force yes to overwrite questions."
            sys.exit(1)
    global write
    write = output.write

    x = py2c(fn)

    if output is not sys.stdout:
        if options.setup_py:
            write_setup_py(x.name, ofn)
        if options.makefile:
            write_makefile(x.name, ofn)


if __name__ == '__main__':
    main()

