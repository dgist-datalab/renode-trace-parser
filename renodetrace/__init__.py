DL_TRACE_SIZE_COMPACT_MEM = 13
DL_TRACE_SIZE_COMPACT_ARITH = 14

LOCAL_LOG_PATH  = 'log'
#GLOBAL_LOG_PATH = '/home/euntae/tmp/renode-log'
GLOBAL_LOG_PATH = '/home/euntae/renode-trace/instruction'
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
    elif model_name == 'mobilenet' or model_name == 'mobilenet_v1':
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

def getFilePath(args):
    modelName = args.model_name
    batchSize = 1 if args.batch_size is not True else args.batch_size
    memConfig = 'default'
    partNum = -1 if args.part is None else args.part
    logFileExt = '.txt' if args.human_readable else '.bin'

    logFilePath = ''
    headerFilePath = ''
    readelfFilePath = ''
    funcTraceFilePath = ''

    if args.env == 'desktop':
        if modelName == 'fc_basic':
            if batchSize == 1:
                logFileName = 'fc_basic_20240909_171650_batch1'
            elif batchSize == 4:
                logFileName = 'fc_basic_20240909_171747_batch4'
            elif batchSize == 8:
                logFileName = 'fc_basic_20240909_172026_batch8'
            elif batchSize == 16:
                logFileName = 'fc_basic_20240909_172133_batch16'
            elif batchSize == 32:
                logFileName = 'fc_basic_20240909_172400_batch32'
            elif batchSize == 128:
                logFileName = 'fc_basic_20240909_172615_batch128'
            elif batchSize == 512:
                logFileName = 'fc_basic_20240911_144402_batch512'
            else:
                print('E: %s, batch=%d is not available' % (modelName, batchSize))
                exit(1)
            headerFileName = 'fc_basic_emitc_static_batch%d_headers' % batchSize
            readelfFileName = 'fc_basic_emitc_static_batch%d_readelf' % batchSize
            funcTraceFileName = 'fc_basic_%d' % batchSize

        elif 'fc_triple' in modelName:
            if modelName == 'fc_triple_small':
                logFileName = 'fc_triple_small_default_20241014_193642'
                modelConfig = 'small'
            elif modelName == 'fc_triple_medium':
                logFileName = 'fc_triple_medium_default_20241014_194008'
                modelConfig = 'medium'
            elif modelName == 'fc_triple_large':
                logFileName = 'fc_triple_large_config1_20241014_194627'
                modelConfig = 'large'
                memConfig = 'config1'
            elif modelName == 'fc_triple_xl':
                logFileName = 'fc_triple_xl_config1_20241014_165044'
                modelConfig = 'xl'
                memConfig = 'config1'
            elif modelName == 'fc_triple_xxl':
                logFileName = 'fc_triple_xxl_config1_20241014_202340'
                modelConfig = 'xxl'
                memConfig = 'config1'
            elif modelName == 'fc_triple_huge':
                logFileName = ''
                modelConfig = 'huge'
                memConfig = ''
                print('E: FC triple huge is not supported yet:(')
                exit(1)
            else:
                print(f'E: model {modelName} is not available')
                exit(1)

            headerFileName = f'fc_triple_{modelConfig}_emitc_static_headers'
            readelfFileName = f'fc_triple_{modelConfig}_emitc_static_readelf'
            funcTraceFileName = f'{modelName}_{memConfig}'

        elif modelName == 'ecg_small':
            logFileName = 'ecg_small_20240906_165242' # binary, with arithmetic, with custom instructions
            headerFileName = 'ecg_small_fp32_emitc_static_headers'
            readelfFileName = 'ecg_small_fp32_emitc_static_readelf'
            funcTraceFileName = 'ecg_small'

        elif modelName == 'mobilenet_v1':
            logFileName = 'mobilenet_v1_mlir_20241113_203119'
            headerFileName = 'mobilenet_v1_mlir_emitc_static_headers'
            readelfFileName = 'mobilenet_v1_mlir_emitc_static_readelf'
            funcTraceFileName = ''


        elif modelName == 'mobilebert':
            logFileName = 'mobilebert_20241113_203119'
            headerFileName = 'mobilebert_emitc_static_headers'
            readelfFileName = 'mobilebert_emitc_static_readelf'
            funcTraceFileName = ''

        else:
            print(f'The model {modelName} is not supported')

        logFileBase = '/home/euntae/tmp/renode-log'
        elfDumpBase = f'/home/euntae/tmp/springbok-samples-elfs-dump_{memConfig}'
        funcTraceBase = '/home/euntae/tmp/renode-trace/function'

        logFilePath = f'{logFileBase}/{logFileName}{logFileExt}'
        headerFilePath  = f'{elfDumpBase}/headers/{headerFileName}.dump'
        readelfFilePath = f'{elfDumpBase}/readelf-sym/{readelfFileName}.dump'
        funcTraceFilePath = f'{funcTraceBase}/{funcTraceFileName}.log'

    elif args.env == 'server':
        if modelName == 'fc_basic':
            if batchSize == 1:
                logFileName = 'fc_basic_20240909_171650_batch1'
            elif batchSize == 4:
                logFileName = 'fc_basic_20240909_171747_batch4'
            elif batchSize == 8:
                logFileName = 'fc_basic_20240909_172026_batch8'
            elif batchSize == 16:
                logFileName = 'fc_basic_20240909_172133_batch16'
            elif batchSize == 32:
                logFileName = 'fc_basic_20240909_172400_batch32'
            elif batchSize == 128:
                logFileName = 'fc_basic_20240909_172615_batch128'
            elif batchSize == 512:
                logFileName = 'fc_basic_20240911_144402_batch512'
            else:
                print('E: %s, batch=%d is not available' % (modelName, batchSize))
                exit(1)
            headerFileName = 'fc_basic_emitc_static_batch%d_headers' % batchSize
            readelfFileName = 'fc_basic_emitc_static_batch%d_readelf' % batchSize
            funcTraceFileName = 'fc_basic_%d' % batchSize

        elif 'fc_triple' in modelName:
            if modelName == 'fc_triple_small':
                logFileName = 'fc_triple_small_20241208_220506'
            elif modelName == 'fc_triple_medium':
                logFileName = 'fc_triple_medium_20241208_220321'
            elif modelName == 'fc_triple_large':
                logFileName = 'fc_triple_large_20241208_223442'
                memConfig = 'config1'
            elif modelName == 'fc_triple_xl':
                logFileName = 'fc_triple_xl_20241218_155509'
                memConfig = 'config1'
            elif modelName == 'fc_triple_xxl':
                logFileName = 'fc_triple_xxl_20241218_155656'
                memConfig = 'config1'
            else:
                print(f'E: model {modelName} is not available')
                exit(1)
            
            headerFileName = f'{modelName}_emitc_static_headers'
            readelfFileName = f'{modelName}_emitc_static_readelf'
            funcTraceFileName = f'{modelName}_{memConfig}'

        elif modelName == 'ecg_small':
            logFileName = 'ecg_small_20241208_203107' # binary, with arithmetic, with custom instructions
            headerFileName = 'ecg_small_fp32_emitc_static_headers'
            readelfFileName = 'ecg_small_fp32_emitc_static_readelf'
            funcTraceFileName = 'ecg_small'

        elif modelName == 'mobilenet_v1':
            logFileName = 'mobilenet_v1_20241208_220017'
            headerFileName = 'mobilenet_v1_emitc_static_headers'
            readelfFileName = 'mobilenet_v1_emitc_static_readelf'
            funcTraceFileName = ''

        elif modelName == 'mobilebert':
            if partNum == -1:
                logFileName = 'mobilebert_20241118_160735'
            elif partNum == 0:
                logFileName = 'mobilebert_0_653'
            elif partNum == 1:
                logFileName = 'mobilebert_654_1211'
            elif partNum == 2:
                logFileName = 'mobilebert_1212_1769'
            else:
                print(f'E: mobilebert part#{partNum} is not available')
                exit(-1)
                
            headerFileName = 'mobilebert_emitc_static_headers'
            readelfFileName = 'mobilebert_emitc_static_readelf'
            funcTraceFileName = ''
            memConfig = 'config1'

        else:
            print(f'The model {modelName} is not supported')
            exit(-1)

        logFileBase = '/home/euntae/renode-trace/instruction'
        elfDumpBase = f'/home/euntae/renode/springbok-elfs/dumps_{memConfig}'
        funcTraceBase = ''

        logFilePath = f'{logFileBase}/{logFileName}{logFileExt}'
        headerFilePath  = f'{elfDumpBase}/headers/{headerFileName}.dump'
        readelfFilePath = f'{elfDumpBase}/readelf-sym/{readelfFileName}.dump'
        funcTraceFilePath = f'{funcTraceBase}/{funcTraceFileName}.log'

    else:
        print(f'E: the environment {args.env} is not available')
        exit(-1)

    # 딕셔너리 형태로 반환할지 단순 튜플로 반환할지?
    return ( logFilePath, headerFilePath, readelfFilePath )

def getASTFileName(args):
    astFileName = ''
    if args.part is not None:
        if args.model_name == 'mobilebert' and args.part == 1:
            astFileName = 'mobilebert_p1_ast_0'
        else:
            astFileName = f'{args.model_name}_p{args.part}_ast'
    else:
        astFileName = f'{args.model_name}_ast'
    return astFileName

def getASTFilePath(args):
    astPathBase = 'dump'
    if not args.use_ast:
        return None
    astFileName = getASTFileName(args)
    astFilePath = f'dump/{astFileName}.ast'
    return astFilePath