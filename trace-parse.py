import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import sys
import os.path
import pickle
import argparse
import time

from renodetrace import *
from renodetrace.stattable import *
from renodetrace.plotdata import *

modelName = 'fc_triple_medium'
batchSize = 1
modelConfig = ''

## Initialize argparse ==============================================
parser = argparse.ArgumentParser()

parser.add_argument('--display-config-only', action='store_true')
parser.add_argument('--plot-type-wise', action='store_true')
parser.add_argument('--plot-ldst', action='store_true', help='Plot load/store instructions')
parser.add_argument('--plot-arith', action='store_true', help='Plot arithmetic instructions')
parser.add_argument('--separate', action='store_true', help='All subplots are rendered in separate windows')
parser.add_argument('--disable-plot', action='store_true')
parser.add_argument('--disable-plot-section-boundary', action='store_true')
parser.add_argument('--human-readable', action='store_true', help='Read from human-readable trace')
parser.add_argument('--enable-stat-table', action='store_true', default=False, help='Enable construct StatTables (default=False)')
parser.add_argument('--model-name', '-m', action='store', default=modelName, help=f'Specify target model name (default={modelName})')
parser.add_argument('--batch-size', action='store', type=int, default=batchSize, help=f'Specify batch size (default={batchSize})')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--ast-output', '-a', action='store', help='Dump AccessSequenceTable (AST) to specified file')

#parser.add_argument('--model-config', action='store', default=modelConfig, help=f'Specify FC triple model configuration: small, medium, large, xl, xxl (default={modelConfig})')
#parser.add_argument('--without-custom', action='store_true')
parser.add_argument('--all', action='store_true', help='Enable all options')
parser.add_argument('--enable-dump', action='store_true', help='Enable dump save/load')
parser.add_argument('--cumulative', action='store_true', help='CDF mode')
#parser.add_argument('--save-figure', action='store_true', help='Save figures as image files')
args = parser.parse_args()

## 로그 파일명 설정
LOCAL_LOG_PATH  = 'log'
GLOBAL_LOG_PATH = '/home/euntae/tmp/renode-log'
FUNC_TRACE_PATH = '/home/euntae/tmp/renode-trace/function'

# logFilePath = LOCAL_LOG_PATH
logFilePath = GLOBAL_LOG_PATH
memConfig = 'default'
#memConfigSuffix = '_default' # default='default'
logFileName = ''
headerFileName = ''
readelfFileName = ''
funcTraceFileName = ''

modelName = args.model_name
batchSize = args.batch_size

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

## FC triple
# FC triple small, medium은 default, config1에서 실행한 결과를 동시에 가지고 있지만, 
# 분석의 편의상 default만을 사용한다
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

    #print(f'memConfig: {memConfig}')
    # if memConfig != '': # 빈 문자열인 경우 기본값인 _default
    #     memConfigSuffix = '_' + memConfig

    headerFileName = f'fc_triple_{modelConfig}_emitc_static_headers'
    readelfFileName = f'fc_triple_{modelConfig}_emitc_static_readelf'
    funcTraceFileName = f'{modelName}_{memConfig}'

elif modelName == 'ecg_small':
    # if args.without_custom:
    #     logFileName = 'ecg_small_20240911_162931' # binary, with arithmetic, no custom instructions
    #     headerFileName = 'ecg_small_fp32_emitc_static_no_custom_headers'
    #     readelfFileName = ''
    #     funcTraceFileName = ''
    #     print('E: ECG small without custom instruction is not supported yet:(')
    #     exit(1)
    # else:
    logFileName = 'ecg_small_20240906_165242' # binary, with arithmetic, with custom instructions
    headerFileName = 'ecg_small_fp32_emitc_static_headers'
    readelfFileName = 'ecg_small_fp32_emitc_static_readelf'
    funcTraceFileName = 'ecg_small'

# w/o custom instruction
# elif modelName == 'mobilenet_v1':
#     logFileName = 'mobilenet_v1_20241113_203002'
#     headerFileName = 'mobilenet_v1_emitc_static_headers'
#     readelfFileName = 'mobilenet_v1_emitc_static_readelf'
#     funcTraceFileName = ''

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

# trace log 파일 경로 결정
if 'ecg_small' in modelName:
    logFilePath = LOCAL_LOG_PATH

logFileExt = '.bin'
if args.human_readable:
    logFileExt = '.txt'

pathName = logFilePath + '/' + logFileName + logFileExt

# ELF header 및 symbol table 파일의 실제 경로 결정
ELF_DUMP_BASE = f'/home/euntae/tmp/springbok-samples-elfs-dump_{memConfig}'
HEADER_PATH   = f'{ELF_DUMP_BASE}/headers'
READELF_PATH  = f'{ELF_DUMP_BASE}/home/euntae/tmp/springbok-samples-elfs-dump_{memConfig}/readelf-sym'

headerFilePath = f'{HEADER_PATH}/{headerFileName}.dump'
readelfFilePath = f'{READELF_PATH}/{readelfFileName}.dump'
funcTraceFilePath = f'{FUNC_TRACE_PATH}/{funcTraceFileName}.log'

## Test =============================================================
printSepline('File information summary')
print(f'model name: {modelName}')
print(f'model config: {modelConfig}')
print(f'memConfig: "{memConfig}"')
print(f'trace log file path: {pathName}')
print(f'headers file path: {headerFilePath}')
print(f'readelf file path: {readelfFilePath}')
print(f'function call trace file path: {funcTraceFilePath}')
printSepline()

if args.display_config_only:
    exit(0)
## ==================================================================


# TODO:
# Add Human-readable MNIST and MobileNet traces
# Add --file-name or -f option to specify input file name
# Add --disable-dump-read option
# Add sampling
# Add elapsed time for graph plotting
# Add --model-name option to configure specific ML model
# Add 'Section Table'
# Section Table도 dump file로 save/load 가능하도록
# Add --enable-section-stat option


## Load tables  =====================================================
sectionTable = []
symbolTable = []
objectTable = []

dispatchRegionTable = []    # part of SymbolTable
dispatchRegionSequence = [] # list of string

loadSectionTable(headerFilePath, sectionTable)
loadSymbolTable(readelfFilePath, symbolTable)
createDispatchRegionTable(symbolTable, dispatchRegionTable) # 심볼 테이블로부터 dispatch region에 해당하는 엔트리만 추출하여 새로운 테이블 'dispatchRegionTable'을 생성한다
loadObjectTable(sectionTable, symbolTable, objectTable)
examineSectionTable(sectionTable)
examineSymbolTable(symbolTable)
examineObjectTable(objectTable)

printSepline('SymbolTable (dispatch regions only)')
examineSymbolTable(dispatchRegionTable)
printSepline()

DR_STAT_TABLE_NAME = 'dispatch_region'
NON_DR_STAT_TABLE_NAME = 'host'

# SectionStatTables (SSTs)
globalSST = SectionStatTable(sectionTable)
globalSST.name = 'global'
localSST = []
initSST = SectionStatTable(sectionTable)
initSST.name = NON_DR_STAT_TABLE_NAME + '#0'
localSST.append(initSST)

# ObjectStatTables (OSTs)
globalOST = ObjectStatTable(objectTable)
globalOST.name = 'global'
localOST = []
initOST = ObjectStatTable(objectTable)
initOST.name = NON_DR_STAT_TABLE_NAME + '#0'
localOST.append(initOST)

# AccessSequenceTables (ASTs)
localAST = []
initAST = AccessSequenceTable()
initAST.name = NON_DR_STAT_TABLE_NAME + '#0'
localAST.append(initAST)

# InstStatTable
instStatTable = InstStatTable()

# Custom instruction data
curRegion = 0               # dispatch region을 포함, 현재 영역의 인덱스; 처음엔 0번으로 시작한다
curHostRegion = 0           # dispatch region 바깥 영역의 인덱스; 프로그램 흐름상 0번으로 시작한다
curDispatchRegion = -1      # 현재 dispatch region의 인덱스; 첫 DR 진입 시 0번으로 시작한다
onDispatchRegion = False

print()

## Open the trace log or dump file ==================================
#logFileName = 'ecg_small_20240624_142406'		# stack=200K (default)
#logFileName = 'ecg_small_20240705_140632'		# stack=100K
#logFileName = 'ecg_small_20240705_142117'		# stack=10M
# logFileName = 'ecg_small_20240705_143322'		# another stack=200K
#logFileName = 'mobile_net_v1_20240703_142550'
#logFileName = 'mnist_20240703_142344'

logFile = None

dumpPathName = 'dump/dump_%s.pkl' % logFileName
dumpReadMode = False
dumpFile = None

if os.path.isfile(dumpPathName) and args.enable_dump:
    print('Dump file %s is detected' % dumpPathName)
    dumpFile = open(dumpPathName, 'rb')
    dumpReadMode = True

if not dumpReadMode:
    if os.path.isfile(pathName):
        if args.human_readable:
            logFile = open(pathName, 'r', encoding='utf-8')
        else:
            logFile = open(pathName, 'rb')
        print('File %s is opened' % pathName)
    else:
        print('E: file %s does not exist' % pathName)
        exit(1)

# class:
# (1) load/store
# [11581] lw(=2003)/742: pc=3201ae48, addr=340327f4
# [11589] sw(=2023)/805: pc=3201ae84, addr=34fffbd0

# (2) FP load/store
# [2992325] flw(=2007)/1: pc=32009404, addr=34031f70
# [2992358] fsw(=2027)/1: pc=32009438, addr=34064dc0

# (3) vector load/store
# [3122315] vle32(=0007)/147: pc=32020c44, addr=34ffc900
# [3122318] vse32(=0027)/160: pc=32020c50, addr=34ffc8f0

# (4) arith
# [103] arith(=0033)/3: pc=320329f8

# (5) arith imm
# [93] arithimm(=0013)/37: pc=320000cc

# (6) FP arith
# [2992339] fparith(=20000053)/3: pc=32009460

# (7) fm{add, sub}, fnm{add, sub}
# [3433716] fmadd.s(=0043)/3: pc=3200990c

# (8) varithi{vv, vx, vi}, varithm{vv, vx}, varith{vv, vf}
# [4931914] varithi.vi(=3057)/43: pc=32021510

## Initialize plot data =============================================
imemAddrBase = getIMemBaseAddress(modelName)
dmemAddrBase = getDMemBaseAddress(modelName)
stackBase = getStackBaseAddress(modelName)
plotData = DLPlotData()
epilogue = ''

print(f'Model name: {modelName}')
print(f'IMem base: {imemAddrBase: #08x}')
print(f'DMem base: {dmemAddrBase: #08x}')
print(f'Stack base: {stackBase: #08x}')
print()

loadCnt = 0
storeCnt = 0
arithCnt = 0

fploadCnt = 0
fpstoreCnt = 0
fparithCnt = 0

vloadCnt = 0
vstoreCnt = 0
varithCnt = 0

loadCntTotal = 0
storeCntTotal = 0
arithCntTotal = 0

lastInstCtr = 0

if dumpReadMode:
    plotData = pickle.load(dumpFile)
    plotData.displayBoundary()
    if plotData.totalInstCnt == 0:
        print('E: failed to load plot data')
        exit(1)
    else:
        print('Plot data is loaded from %s successfully' % dumpPathName)

else: # 덤프 파일이 감지되지 않는 경우 trace 파일을 분석함
    print(f'Analyze {pathName}...')
    plotData.pcLow = getIMemBaseAddress(modelName)
    plotData.pcHigh = getIMemBaseAddress(modelName)
    startTime = time.time()
    if args.human_readable:
        # 패턴 매칭: 숫자 | 16진수 숫자 | pc=숫자 | addr=숫자
        pattern = re.compile(r'\b\d+\b|\b[0-9a-fA-F]+\b|\bpc=[0-9a-fA-F]+\b|\baddr=[0-9a-fA-F]+\b')

        for line in logFile:
            # 로그 파일에서 ##로 시작하는 행이 나오면 반복 종료
            epilogue = re.match(r'^##', line)
            if epilogue is not None:
                epilogue = line
                break
            
            ## Update cumulative graph ======================================================
            # loadCntTotal = loadCnt + fploadCnt + vloadCnt
            # storeCntTotal = storeCnt + fpstoreCnt + vstoreCnt
            # memCntTotal = loadCntTotal + storeCntTotal
            # arithCntTotal = arithCnt + fparithCnt + varithCnt
            # plotData.loadCDF.append(loadCntTotal)
            # plotData.storeCDF.append(storeCntTotal)
            # plotData.arithCDF.append(arithCntTotal)
            #================================================================================

            matches = pattern.findall(line)
            matchLen = len(matches)
            if (matchLen == 4 or matchLen == 5): # arithmetic(=4) or load/store(=5)
                ## Tokenize
                instCtr = int(matches[0])
                plotData.instCtr.append(instCtr)
                #opc = int(matches[1], 16) # opcode
                opcCnt = int(matches[2])
                pc = int(matches[3].split(sep='=')[1].strip(), 16)
                opStr = (line.split()[1]).split(sep='(')[0]
                addr = 0

                if matchLen == 5: # load/store
                    addr = int(matches[4].split(sep='=')[1].strip(), 16)
                    if args.verbose:
                        sys.stdout.write('\r' + '[%d] op=%s: count=%d, pc=%x, addr=%x' % (instCtr, opStr, opcCnt, pc, addr))
                elif matchLen == 4: # arithmetic
                    if args.verbose:
                        sys.stdout.write('\r' + '[%d] op=%s: count=%d, pc=%x' % (instCtr, opStr, opcCnt, pc))
                    if plotData.pcHigh < pc:
                        plotData.pcHigh = pc
                
                ## Update plot data
                if matchLen == 4: # arithmetic
                    if 'f' in opStr: # FP arith
                        plotData.fparithX.append(instCtr)
                        plotData.fparithY.append(pc)
                        fparithCnt += 1
                    elif 'v' in opStr: # vector arith
                        plotData.varithX.append(instCtr)
                        plotData.varithY.append(pc)
                        varithCnt += 1
                    else: # integer arith
                        plotData.arithX.append(instCtr)
                        plotData.arithY.append(pc)
                        arithCnt += 1
                else: # load/store
                    ## Update segment boundary
                    if addr > (dmemAddrBase | 0x00f00000): # stack
                        if plotData.stackAddrHigh < addr:
                            plotData.stackAddrHigh = addr
                        if plotData.stackAddrLow > addr:
                            plotData.stackAddrLow = addr
                    else: # data
                        if plotData.dataAddrHigh < addr:
                            plotData.dataAddrHigh = addr
                        if plotData.dataAddrLow > addr:
                            plotData.dataAddrLow = addr
                    
                    ## Append graph points
                    if 'f' in opStr: # FP load/store
                        if 'l' in opStr: # load
                            plotData.fploadX.append(instCtr)
                            plotData.fploadY.append(addr)
                            fploadCnt += 1
                        else: # store
                            plotData.fpstoreX.append(instCtr)
                            plotData.fpstoreY.append(addr)
                            fpstoreCnt += 1
                    elif 'v' in opStr: # vector load/store
                        if 'l' in opStr: # load
                            plotData.vloadX.append(instCtr)
                            plotData.vloadY.append(addr)
                            vloadCnt += 1
                        else: # store
                            plotData.vstoreX.append(instCtr)
                            plotData.vstoreY.append(addr)
                            vstoreCnt += 1
                    else: # integer load/store
                        if 'l' in opStr: # load
                            plotData.loadX.append(instCtr)
                            plotData.loadY.append(addr)
                            loadCnt += 1
                        elif 's' in opStr: # store
                            plotData.storeX.append(instCtr)
                            plotData.storeY.append(addr)
                            storeCnt += 1
                        else:
                            print('%s: illegal instruction' % line)
                            break

                # sys.stdout.write('\r' + '[%d] op=%s: opcode=%x, count=%d, pc=%x, addr=%x' 
                # 	% (instCtr, opStr, opc, opcCnt, pc, addr))
            else:
                print('%s: unknown instruction, matchLen=%d' % (line, matchLen))

        print('\n')
        if epilogue is not None:
            print(epilogue, end='')
            plotData.epilogue += epilogue
            for line in logFile:
                print(line, end='')
                plotData.epilogue += line
                if "Total instructions" in line:
                    plotData.totalInstCnt = int(line.split(sep=':')[1].strip())
    else: # binary trace mode
        while True:
            trace = logFile.read(DL_TRACE_SIZE_COMPACT_MEM)
            if not trace:
                break
            ## traceV2: lower부만 변경 있음
            opType = trace[0] & 0b11
            dataType = (trace[0] >> 2) & 0b111
            operandSize = trace[0] >> 5
            instCtr = int.from_bytes(trace[1:9], byteorder='little')
            addr = int.from_bytes(trace[9:], byteorder='little')

            opclass = 0

            if args.verbose:
                sys.stdout.write('\r' + '[%d] opType=%d dataType=%d operandSize=%d addr=%#x ' % (instCtr, opType, dataType, operandSize, addr))
            if opType == 2 or dataType == 3 or opType == 3: # custom instruction도 opclass를 읽어야 한다
                opclass = (logFile.read(1))[0]
                if args.verbose:
                    sys.stdout.write('opclass: %#x' % opclass)
            
            # opType: load/store/arith/unknown
            # dataType: sint/uint/float/vector
            # operandSize: 8/16/32/64/128
            if opType == 0: # load
                if dataType == 0 or dataType == 1: # int
                    plotData.loadX.append(instCtr)
                    plotData.loadY.append(addr)
                elif dataType == 2: # float
                    plotData.fploadX.append(instCtr)
                    plotData.fploadY.append(addr)
                else: # vector
                    plotData.vloadX.append(instCtr)
                    plotData.vloadY.append(addr)
            elif opType == 1: # store
                if dataType == 0 or dataType == 1: # int
                    plotData.storeX.append(instCtr)
                    plotData.storeY.append(addr)
                elif dataType == 2: # float
                    plotData.fpstoreX.append(instCtr)
                    plotData.fpstoreY.append(addr)
                else: # vector
                    plotData.vstoreX.append(instCtr)
                    plotData.vstoreY.append(addr)
            elif opType == 2: # arith
                if dataType == 0 or dataType == 1:
                    plotData.arithX.append(instCtr)
                    plotData.arithY.append(addr)
                elif dataType == 2: # float
                    plotData.fparithX.append(instCtr)
                    plotData.fparithY.append(addr)
                else: # vector
                    plotData.varithX.append(instCtr)
                    plotData.varithY.append(addr)
                if plotData.pcHigh < addr:
                    plotData.pcHigh = addr
            elif opType == 3: # custom/unknown
                # region index나 dr.begin, dr.end 제어 정보는 여기에서 처리할 것
                # 실제 StatTable entry 삽입 등의 연산은 enable_section_stat 부분에서 처리
                # TODO: custom instruction의 경우 opclass에 따라 세분화할 것
                # unknown은 무시할 수 있다
                # if opclass & 0b11100000:
                plotData.customX.append(instCtr)
                plotData.customY.append(addr)
                plotData.customOpclass.append(opclass)
                opc = opclass & 0b11
                funct3 = (opclass >> 2) & 0b111
                #print('[%d] custom-%d opclass=%02x funct3=%x pc=%#x ' % (instCtr, opc, opclass, funct3, addr))
                if opc == 0:
                    if funct3 == 0: # dr.begin
                        curRegion += 1
                        curDispatchRegion += 1
                        curDispatchRegionName = getDispatchRegionName(dispatchRegionTable, addr)
                        dispatchRegionSequence.append(curDispatchRegionName)
                        print(f'Dispatch region #{curDispatchRegion} begin: instCtr={instCtr}, addr={addr:#8x}, name={curDispatchRegionName}')
                        onDispatchRegion = True

                    elif funct3 == 1: #dr.end
                        curRegion += 1
                        curHostRegion += 1
                        print(f'Dispatch region #{curDispatchRegion} end: instCtr={instCtr}, addr={addr:#8x}')
                        onDispatchRegion = False
            else: # parsing error
                print('E: unrecognized instruction:')
                print('[%d] opType=%d dataType=%d operandSize=%d addr=%#x ' % (instCtr, opType, dataType, operandSize, addr))
                exit(1)
            
            ## StatTable류 생성 허용
            # curDispatchRegion: 현재 dispatch region 인덱스
            # curHostRegion: 현재 host region 인덱스
            # curRegion: 현재 region 인덱스
            if args.enable_stat_table:
                if opType == 0 or opType == 1: # load/store
                    globalSST.put(sectionTable, opType, dataType, addr)
                    globalOST.put(objectTable, opType, dataType, addr)
                    # if onDispatchRegion:
                    #     localSST[curDispatchRegion].put(sectionTable, opType, dataType, addr)
                    #     localOST[curDispatchRegion].put(objectTable, opType, dataType, addr)
                    localSST[curRegion].put(sectionTable, opType, dataType, addr)
                    localOST[curRegion].put(objectTable, opType, dataType, addr)
                    localAST[curRegion].put(sectionTable, objectTable, instCtr, addr, opType, dataType, operandSize)

                    if opType == 0: # load
                        instStatTable.put(curRegion, INST_STAT_LOAD)
                    else:
                        instStatTable.put(curRegion, INST_STAT_STORE)

                elif opType == 2: # arith
                    instStatTable.put(curRegion, dataType)

                elif opType == 3: # custom
                    #globalSectionAccessTable
                    if opc == 0 and (funct3 == 0 or funct3 == 1): # dr.begin or dr.end
                        stName = ''
                        if onDispatchRegion:
                            #stName = DR_STAT_TABLE_NAME + ('#%d' % curRegion)
                            stName = DR_STAT_TABLE_NAME + ('#%d' % curDispatchRegion)
                        else:
                            #stName = NON_DR_STAT_TABLE_NAME + ('#%d' % curRegion)
                            stName = NON_DR_STAT_TABLE_NAME + ('#%d' % curHostRegion)
                        sst = SectionStatTable(sectionTable)
                        sst.name = stName
                        localSST.append(sst)

                        ost = ObjectStatTable(objectTable)
                        ost.name = stName
                        localOST.append(ost)

                        ast = AccessSequenceTable()
                        ast.name = stName
                        localAST.append(ast)

                        istEntry = InstStatTableEntry()
                        istEntry.name = stName
                        instStatTable.tbl.append(istEntry)


            ## Update segment boundary
            # 이미 섹션 테이블이 있는데 이 부분 필요할까? (나중에 deprecate 시킬 것)
            if opType == 0 or opType == 1: # load/store
                if addr >= stackBase: # stack
                    if plotData.stackAddrHigh < addr:
                        plotData.stackAddrHigh = addr
                    if plotData.stackAddrLow > addr:
                        plotData.stackAddrLow = addr
                else: # data
                    if plotData.dataAddrHigh < addr:
                        plotData.dataAddrHigh = addr
                    if plotData.dataAddrLow > addr:
                        plotData.dataAddrLow = addr
            # End of while loop (in binary trace mode)

        lastInstCtr = instCtr
        plotData.totalInstCnt = lastInstCtr + 100
        print(f'Last instruction counter: {lastInstCtr}')
        # End of binary trace mode
    # End of trace analysis

    endTime = time.time()
    logFile.close()
    print('Trace analyzing has been completed')
    print(f'Elapsed time: {endTime - startTime:.5f} sec')
    
if args.human_readable and dumpReadMode:
    print()
    print(plotData.epilogue)

## 통계 정보 출력 및 덤프 저장 ==============================================
print()
print('## Data ##')
print('address (low) : %x' % plotData.dataAddrLow)
print('address (high): %x' % plotData.dataAddrHigh)
print('--> %d KB\n' % ((plotData.dataAddrHigh - plotData.dataAddrLow) / 1024))
print('## Stack ##')
print('address (low) : %x' % plotData.stackAddrLow)
print('address (high): %x' % plotData.stackAddrHigh)
print('--> %d KB\n' % ((plotData.stackAddrHigh - plotData.stackAddrLow) / 1024))
print('## PC    ##')
print('address (low) : %x' % plotData.pcLow)
print('address (high): %x' % plotData.pcHigh)
print('--> %d KB\n' % ((plotData.pcHigh - plotData.pcLow) / 1024))

# 캐시 시뮬레이터용: 생성된 AST를 파일로 덤프한다
if args.ast_output is not None:
    astDumpFileName = 'dump/' + args.ast_output + '.ast'
    astDumpFile = open(astDumpFileName, 'wb')
    pickle.dump(localAST, astDumpFile)
    print(f'ASTs are saved to {astDumpFileName}')
    astDumpFile.close()

# 덤프 파일이 존재하지 않는 경우 생성된 플롯 데이터 저장
if not dumpReadMode and args.enable_dump:
    dumpFile = open(dumpPathName, 'wb')
    plotData.saveDump(dumpFile)
    print('Plot data saved in %s' % dumpPathName)

if args.cumulative:
    print()
    print("## Cumulative mode statistics ##")
    print('loadCntTotal: %d' % loadCntTotal)
    print('storeCntTotal: %d' % storeCntTotal)
    print('arithCntTotal: %d' % arithCntTotal)
    print('len(loadCDF): %d' % len(plotData.loadCDF))
    print('len(fploadCDF): %d' % len(plotData.fploadCDF))
    print('len(vloadCDF): %d' % len(plotData.vloadCDF))
    print('len(storeCDF): %d' % len(plotData.storeCDF))
    print('len(arithCDF): %d' % len(plotData.storeCDF))
    print('len(plotData.instCtr): %d' % len(plotData.instCtr))

## enable-section-stat 옵션이 활성화되어 있는 경우 관련 통계 데이터 출력 =====
if args.enable_stat_table:
    print('## SectionStatTables ##')
    printSepline('Global SST')
    globalSST.examine()
    printSepline()
    print()
    printSepline('Local SST')
    for i, sst in enumerate(localSST):
        #print(f'Dispatch region #{i}' + ('=' * 80))
        sst.examine(True)
        print()
    printSepline()
    print()
    
    print('## ObjectStatTables ##')
    printSepline('Global OST')
    globalOST.examine()
    printSepline()
    print()
    printSepline('Local OST')
    for i, ost in enumerate(localOST):
        ost.examine(True)
        print()
    printSepline()
    print()

    printSepline('InstStatTable')
    instStatTable.examine(True)
    printSepline()
    print()
    
    if args.verbose:
        print('## AccessSequenceTables ##')
        printSepline('Local ASTs')
        for i, ast in enumerate(localAST):
            ast.examine()
            print()
        printSepline()
        print()

    # 각 localAST의 시작 명령어의 instCnt 출력
    print('## AccessSequenceTables (instruction counter only) ##')
    printSepline('Local ASTs')
    for i, ast in enumerate(localAST):
        print(f'{ast.name}: {ast.getFirstInstructionCounter()}')
    printSepline()
    print()

## function call trace ==============================================
# print('## FunctionStatTables ##')
# loadFunctionTrace(funcTraceFilePath)

printSepline('Sequence of dispatch region call')
for drName in dispatchRegionSequence:
    print(drName)
printSepline()

## 그래프 출력 ========================================================
# Initialize plot
print()

if args.disable_plot:
    exit(0)

print('Plotting graphs...')

# 옵션을 명시하지 않을 경우 둘 다 출력
if (not args.plot_ldst) and (not args.plot_arith):
    args.plot_ldst = True
    args.plot_arith = True

if args.cumulative:
    plotCumul()
else:
    ## load/store 명령어
    if args.plot_ldst:
        if args.separate:
            plotLdstSep(modelName, sectionTable, plotData, args.plot_type_wise)

        else:
            plotLdst(modelName, sectionTable, plotData)
            

    ## 새로운 창: 산술 연산 명령어
    if args.plot_arith:
        if args.separate:
            plotArithSep(modelName, plotData, args.plot_type_wise)
        else:
            plotArith(modelName, plotData)

# 전체 레이아웃 조정
#fig1.tight_layout()
#fig2.tight_layout()

# 서브 플롯들을 파일로 저장 ====================================================
# if args.save_figure or args.all:
# 	figFilePrefix = 'figure/'
# 	figFileSuffix = '.png'
# 	for i, ax in enumerate(axs1.flat):
# 		figFileName = figFilePrefix + logFileName + '_ldst_' + str(i) + figFileSuffix
# 		extent = ax.get_window_extent().transformed(fig1.dpi_scale_trans.inverted())
# 		fig1.savefig(figFileName, bbox_inches=extent, dpi=100)

# 	for i, ax in enumerate(axs2.flat):
# 		figFileName = figFilePrefix + logFileName + '_arith_' + str(i) + figFileSuffix
# 		extent = ax.get_window_extent().transformed(fig2.dpi_scale_trans.inverted())
# 		fig2.savefig(figFileName, bbox_inches=extent, dpi=100)

#plt.tight_layout()
plt.show()
