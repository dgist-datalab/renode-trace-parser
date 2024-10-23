DL_TRACE_SIZE_COMPACT_MEM = 13
DL_TRACE_SIZE_COMPACT_ARITH = 14

LOCAL_LOG_PATH = 'log'
GLOBAL_LOG_PATH = '/home/euntae/tmp/renode-log'
FUNC_TRACE_PATH = '/home/euntae/tmp/renode-trace/function'

# samples/{ModelName}/CMakeLists.txt 참조
# 별도의 빌드 옵션이 지정되어 있지 않으면 default
# default:
# DMem 16M, IMem 1M, Stack 10K
def getIMemLength(model_name='ecg_small'):
    if model_name == 'mobilebert':
        return 128 * 1024 * 1024 # 128M
    elif model_name == 'fc_triple_large' or model_name == 'fc_triple_xl' or model_name == 'fc_triple_xxl':
        return 128 * 1024 * 1024 # 128M
    else: # default (1M)
        return 1024 * 1024

def getDMemLength(model_name='ecg_small'):
    if model_name == 'mobilebert':
        return 256 * 1024 * 1024    # 256M
    elif model_name == 'fc_triple_large' or model_name == 'fc_triple_xl' or model_name == 'fc_triple_xxl':
        return 256 * 1024 * 1024    # 256M
    else: # default (16M)
        return 16 * 1024 * 1024     # 16M

def getStackSize(model_name='ecg_small'):
    if model_name == 'ecg_small':
        return 200 * 1024 # 200K
    elif model_name == 'mnist':
        return 100 * 1024 # 100K
    elif model_name == 'mobilenet':
        return 200 * 1024 # 200K
    elif model_name == 'mobilenet_quant':
        return 300 * 1024 # 300K
    elif model_name == 'mobilebert':
        return 32 * 1024 * 1024 # 32M
    elif model_name == 'fc_basic':
        return 200 * 1024 # 200K
    elif model_name == 'fc_triple_small' or model_name == 'fc_triple_medium':
        return 200 * 1024 # 200K
    elif model_name == 'fc_triple_large' or model_name == 'fc_triple_xl' or model_name == 'fc_triple_xxl':
        return 32 * 1024 * 1024 # 32M
    else: # default (10K)
        return 10 * 1024

def getIMemBaseAddress(model_name='ecg_small'):
    if model_name == 'mobilebert':
        return 0x32000000
    else:
        return 0x32000000

def getDMemBaseAddress(model_name='ecg_small'):
    if model_name == 'mobilebert':
        return 0x3c000000
    elif model_name == 'fc_triple_large' or model_name == 'fc_triple_xl' or model_name == 'fc_triple_xxl':
        return 0x3c000000
    else:
        return 0x34000000

# PROVIDE( _stack_ptr = ORIGIN(DTCM) + LENGTH(DTCM) - 64 );
# PROVIDE( _stack_start_sentinel = ORIGIN(DTCM) + LENGTH(DTCM) - STACK_SIZE );
# PROVIDE( _stack_end_sentinel = ORIGIN(DTCM) + LENGTH(DTCM) - 64 );
def getStackBaseAddress(model_name='ecg_small'):
    dmemBase = getDMemBaseAddress(model_name)
    dmemLength = getDMemLength(model_name)
    stackSize = getStackSize(model_name)
    return dmemBase + dmemLength - stackSize

def printSepline(label='', llen=128):
    lineLen = llen
    prefix = '## '
    suffix = ' ##'

    if label != '':
        label += ' '
    lmult = lineLen - len(label) - len(prefix) - len(suffix)
    if lmult < 1:
        lmult = 1
    print(prefix + label + ('=' * lmult) + suffix)