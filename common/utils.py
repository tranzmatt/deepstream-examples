import sys
sys.path.append('/opt/nvidia/deepstream/deepstream-5.1/lib')

def long_to_int(l):
    value = ctypes.c_int(l & 0xffffffff).value
    return value
