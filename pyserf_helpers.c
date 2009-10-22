/************** turning python lists into C arrays and vice versa  ****************/

//#include "Python.h"
#include <stddef.h>

#define INDEX_ERROR(format, ...) PyErr_Format(PyExc_IndexError, (format), ## __VA_ARGS__);


static inline int * 
int_vector_from_list(int *vector, PyObject *list, int len){
    unsigned int i;    
    PyObject *item;
    if (PySequence_Size(list) != len){
	INDEX_ERROR("vector wrong size %d != %d\n", PySequence_Size(list), len);
	return NULL;
    }
    for (i = 0; i < len; i++){	    
	if (! (item = PySequence_GetItem(list, i))){
	    INDEX_ERROR("could not find %dth item!? ( of %d)\n", i, len);
	    return NULL;
	}
	vector[i] = (int)PyInt_AsLong(item);
	Py_DECREF(item);	
    }
    return vector;
}

static inline double * 
double_vector_from_list(double *vector, PyObject *list, int len){
    unsigned int i;    
    PyObject *item;
    if (PySequence_Size(list) != len){
	INDEX_ERROR("vector wrong size %d != %d\n", PySequence_Size(list), len);
	return NULL;
    }
    for (i = 0; i < len; i++){	    
	if (! (item = PySequence_GetItem(list, i))){
	    INDEX_ERROR("could not find %dth item!? ( of %d)\n", i, len);
	    return NULL;
	}
	vector[i] = (double)PyFloat_AsDouble(item);
	Py_DECREF(item);	
    }
    return vector;
}

static inline float *
float32_vector_from_list(float *vector, PyObject *list, int len){
    unsigned int i;    
    PyObject *item;
    if (PySequence_Size(list) != len){
	INDEX_ERROR("vector wrong size %d != %d\n", PySequence_Size(list), len);
	return NULL;
    }
    for (i = 0; i < len; i++){	    
	if (! (item = PySequence_GetItem(list, i))){
	    INDEX_ERROR("could not find %dth item!? ( of %d)\n", i, len);
	    return NULL;
	}
	vector[i] = (float)PyFloat_AsDouble(item);
	Py_DECREF(item);	
    }
    return vector;
}



static inline PyObject * 
new_list_from_int_vector(int *a, int len){
    PyObject * list = PyList_New(len);
    int i;
    for (i = 0; i < len; i++){
	PyList_SetItem(list, i, PyInt_FromLong(a[i]));
    }
    return list;
}

static inline PyObject * 
new_list_from_uint8_vector(uint8_t *a, int len){
    PyObject * list = PyList_New(len);
    int i;
    for (i = 0; i < len; i++){
	PyList_SetItem(list, i, PyInt_FromLong((long)a[i]));
    }
    return list;
}

static inline PyObject * 
new_list_from_double_vector(double *a, int len){
    PyObject *list = PyList_New(len);
    int i;
    for (i = 0; i < len; i++){
	PyList_SetItem(list, i, PyFloat_FromDouble(a[i]));
    }
    return list;
}

static inline PyObject * 
new_list_from_float32_vector(float *a, int len){
    PyObject *list = PyList_New(len);
    int i;
    for (i = 0; i < len; i++){
	PyList_SetItem(list, i, PyFloat_FromDouble((double)a[i]));
    }
    return list;
}

