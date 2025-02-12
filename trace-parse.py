import re
# import matplotlib
# import matplotlib.pyplot as plt
# import matplotlib.ticker as ticker
# import numpy as np
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
#parser.add_argument('--enable-dispatch-region-table', action='store_true')
parser.add_argument('--model-name', '-m', action='store', default=modelName, help=f'Target model name (default={modelName})')
parser.add_argument('--part', '-p', action='store', type=int, help='Number of partitioned trace (for large trace)')
parser.add_argument('--sample', '-s', action='store', type=int, help='Sampling interval')
parser.add_argument('--batch-size', action='store', type=int, default=batchSize, help=f'Specify batch size (default={batchSize})')
parser.add_argument('--verbose', '-v', action='store_true')
#parser.add_argument('--ast-output', '-a', action='store', help='Dump AccessSequenceTable (AST) to specified file')
parser.add_argument('--use-ast', action='store_true')
parser.add_argument('--env', action='store', default='desktop', help='Execution environment (default: desktop)')
parser.add_argument('--ntraces', '-t', action='store', type=int)

#parser.add_argument('--model-config', action='store', default=modelConfig, help=f'Specify FC triple model configuration: small, medium, large, xl, xxl (default={modelConfig})')
#parser.add_argument('--without-custom', action='store_true')
parser.add_argument('--all', action='store_true', help='Enable all options')
parser.add_argument('--use-dump', action='store_true', help='Read plot data from .npz dump file')
parser.add_argument('--dump-file-path', action='store', help='원하는 덤프 파일의 경로를 지정함')
#parser.add_argument('--save-figure', action='store_true', help='Save figures as image files')
args = parser.parse_args()

# 옵션을 명시하지 않을 경우 둘 다 참으로 처리 (기본값)
if (not args.plot_ldst) and (not args.plot_arith):
    args.plot_ldst = True
    args.plot_arith = True

## 파일명 불러오기
modelName = args.model_name
logFilePath, headerFilePath, readelfFilePath = getFilePath(args)
astFilePath = getASTFilePath(args)

partNum = getPartNum(args)

## Display configuration ============================================
printSepline('Configuration summary')
print(f'Model name: {modelName}')
print(f'- part (optional): {partNum}')
print(f'Environment: {args.env}')
print(f'Instruction trace file path: {logFilePath}')
print(f'Headers file path: {headerFilePath}')
print(f'ReadELF file path: {readelfFilePath}')
print(f'AST file path: {astFilePath}')
printSepline()

if args.display_config_only:
    exit(0)
## ==================================================================

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
# examineSectionTable(sectionTable)
# examineSymbolTable(symbolTable)
# examineObjectTable(objectTable)

printSepline('SymbolTable (dispatch regions only)')
examineSymbolTable(dispatchRegionTable)
printSepline()
print()

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

logFile = None
## Numpy 덤프 파일 사용 시 파싱 단계 생략 =================================
# dumpPathName = 'dump/dump_%s.pkl' % modelName
# dumpReadMode = False
# dumpFile = None
if args.use_dump: # npz 파일을 불러옴
    if args.dump_file_path is not None:
        npDumpFilePath = args.dump_file_path
    else:
        npDumpFilePath = getNumpyDumpFilePath(args)
    if os.path.isfile(npDumpFilePath):
        print(f'## Numpy dump file: read from {npDumpFilePath}...')
    else:
        print(f'E: file {npDumpFilePath} does not exist')
        exit(1)
    plotFileData = np.load(npDumpFilePath)
    print(f'--> {plotFileData.files}\n')
    # print(type(plotData))
    # print(f"plotData['loadX']:")
    # print(f" type: {type(plotData['loadX'])}, shape: {plotData['loadX'].shape}")
    #print(f"plotData['customX'](len={len(plotData['customX'])}): {plotData['customX']}")
    #print(f"plotData['customOpclass'](len={len(plotData['customOpclass'])}): {plotData['customOpclass']}")

    #sliceTable = {}
    #createSliceTable(plotData, sliceTable)
    #print(sliceTable)
    #exit(0)

else: # instruction trace 파일을 불러옴
    if os.path.isfile(logFilePath):
        if args.human_readable:
            logFile = open(logFilePath, 'r', encoding='utf-8')
        else:
            logFile = open(logFilePath, 'rb')
        print(f'File {logFilePath} is opened')
    else:
        print(f'E: file {logFilePath} does not exist')
        exit(1)

## Initialize plot data =============================================
imemAddrBase = getIMemBaseAddress(modelName)
dmemAddrBase = getDMemBaseAddress(modelName)
stackBase = getStackBaseAddress(modelName)

imemLength = getIMemLength(modelName)
dmemLength = getDMemLength(modelName)
stackSize = getStackSize(modelName)

plotData = DLPlotData()
epilogue = ''

secEntry = {}
secEntry['.text']   = getSectionTableEntry(sectionTable, '.text')
secEntry['.stack']  = getSectionTableEntry(sectionTable, '.stack')
secEntry['.rodata'] = getSectionTableEntry(sectionTable, '.rodata')
secEntry['.heap']   = getSectionTableEntry(sectionTable, '.heap')

print(f'Model name: {modelName}')
print(f'IMem base: {imemAddrBase: #08x}, size: {imemLength} --> {imemAddrBase + imemLength:#08x}')
print(f'DMem base: {dmemAddrBase: #08x}, size: {dmemLength} --> {dmemAddrBase + dmemLength:#08x}')
print(f'Stack base: {stackBase: #08x}, size: {stackSize} --> {stackBase + stackSize:#08x}')
print(f"section: .text, vma: {secEntry['.text'].vma:#08x}, size: {secEntry['.text'].size} --> {secEntry['.text'].vma + secEntry['.text'].size:#08x}")
print(f"section: .rodata, vma: {secEntry['.rodata'].vma:#08x}, size: {secEntry['.rodata'].size} --> {secEntry['.rodata'].vma + secEntry['.rodata'].size:#08x}")
print(f"section: .stack, vma: {secEntry['.stack'].vma:#08x}, size: {secEntry['.stack'].size} --> {secEntry['.stack'].vma + secEntry['.stack'].size:#08x}")
print()

# exit(0)

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

sampleInterval = -1
if args.sample is not None:
    sampleInterval = args.sample
    if sampleInterval <= 1:
        print('Warning: sampleInterval <= 1; sampling mode is disabled')
        sampleInterval = -1
sampleCnt = 0
nsamples = 0

targetNTrace = 0
if args.ntraces is not None:
    targetNTrace = args.ntraces
traceCnt = 0

plotData.pcLow  = secEntry['.text'].vma
plotData.pcHigh = secEntry['.text'].vma + secEntry['.text'].size
traceProcessTime = 0

if args.use_dump:
    if modelName == 'mobilebert':
        print(plotFileData['loadX'])
    if args.plot_ldst:
        plotData.loadX = plotFileData['loadX']
        plotData.loadY = plotFileData['loadY']
        plotData.fploadX = plotFileData['fploadX']
        plotData.fploadY = plotFileData['fploadY']
        plotData.vloadX = plotFileData['vloadX']
        plotData.vloadY = plotFileData['vloadY']

        plotData.storeX = plotFileData['storeX']
        plotData.storeY = plotFileData['storeY']
        plotData.fpstoreX = plotFileData['fpstoreX']
        plotData.fpstoreY = plotFileData['fpstoreY']
        plotData.vstoreX = plotFileData['vstoreX']
        plotData.vstoreY = plotFileData['vstoreY']
        
    if args.plot_arith:
        plotData.arithX = plotFileData['arithX']
        plotData.arithY = plotFileData['arithY']
        plotData.fparithX = plotFileData['fparithX']
        plotData.fparithY = plotFileData['fparithY']
        plotData.varithX = plotFileData['varithX']
        plotData.varithY = plotFileData['varithY']

    plotData.customX = plotFileData['customX']
    plotData.customY = plotFileData['customY']
    plotData.customOpclass = plotFileData['customOpclass']

    plotData.totalInstCnt = plotFileData['lastInstCtr'][0] + 100

    plotData.displayLength()

## Trace 파싱
if not args.use_dump:
    print(f'Analyze {logFilePath}...')
    # plotData.pcLow = getIMemBaseAddress(modelName)
    # plotData.pcHigh = getIMemBaseAddress(modelName)
    startTime = time.time()
    
    ## Human-readable format trace processing =======================
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
    if args.human_readable:
        # 패턴 매칭: 숫자 | 16진수 숫자 | pc=숫자 | addr=숫자
        pattern = re.compile(r'\b\d+\b|\b[0-9a-fA-F]+\b|\bpc=[0-9a-fA-F]+\b|\baddr=[0-9a-fA-F]+\b')

        for line in logFile:
            # 로그 파일에서 ##로 시작하는 행이 나오면 반복 종료
            epilogue = re.match(r'^##', line)
            if epilogue is not None:
                epilogue = line
                break

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
    # End of human-readable trace processing ========================

    # binary trace mode =============================================
    else:
        while True:
            if targetNTrace != 0 and traceCnt == targetNTrace:
                break
            trace = logFile.read(DL_TRACE_SIZE_COMPACT_MEM)
            if not trace:
                break
            
            ## trace로부터 데이터 추출
            # opType: load/store/arith/unknown
            # dataType: sint/uint/float/vector
            # operandSize: 8/16/32/64/128
            opType = trace[0] & 0b11
            dataType = (trace[0] >> 2) & 0b111
            operandSize = trace[0] >> 5
            instCtr = int.from_bytes(trace[1:9], byteorder='little')
            addr = int.from_bytes(trace[9:], byteorder='little')

            opclass = 0

            if args.verbose:
                #sys.stdout.write('\r' + '[%d] opType=%d dataType=%d operandSize=%d addr=%#x ' % (instCtr, opType, dataType, operandSize, addr))
                print('[%d] opType=%d dataType=%d operandSize=%d addr=%#x opclass=%d' % (instCtr, opType, dataType, operandSize, addr, opclass))
            
            # 산술 명령어 trace의 경우 14바이트 길이를 가지므로 1바이트를 추가로 읽는다
            # vector/custom instruction도 부가정보인 opclass를 포함
            if opType == 2 or dataType == 3 or opType == 3:
                opclass = (logFile.read(1))[0]
                # if args.verbose:
                #     sys.stdout.write('opclass: %#x' % opclass)

            # --disable-plot 옵션 사용 시 plotData update 비활성화
            if not args.disable_plot and ((sampleInterval < 1) or (sampleInterval > 1 and sampleCnt == 0)):
                sampleCnt = sampleInterval
                
                if opType == 0: # load
                    if args.plot_ldst:
                        nsamples += 1
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
                    if args.plot_ldst:
                        nsamples += 1
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
                    if args.plot_arith:
                        nsamples += 1
                        if dataType == 0 or dataType == 1:
                            plotData.arithX.append(instCtr)
                            plotData.arithY.append(addr)
                        elif dataType == 2: # float
                            plotData.fparithX.append(instCtr)
                            plotData.fparithY.append(addr)
                        else: # vector
                            plotData.varithX.append(instCtr)
                            plotData.varithY.append(addr)
                elif opType == 3: # custom
                    nsamples += 1
                else: # parsing error
                    print('E: unrecognized instruction:')
                    print('[%d] opType=%d dataType=%d operandSize=%d addr=%#x ' % (instCtr, opType, dataType, operandSize, addr))
                    exit(1)
            
            # if opType == 2 and plotData.pcHigh < addr:
            #     plotData.pcHigh = addr

            # --disable-plot 옵션과 무관하게 처리
            if opType == 3: # custom/unknown
                # region index나 dr.begin, dr.end 제어 정보는 여기에서 처리할 것
                # 실제 StatTable entry 삽입 등의 연산은 enable_section_stat 부분에서 처리
                # custom instruction 간의 식별은 opclass 필드 이용
                # - opclass[1:0]: identify custom-0/1/2/3
                # - opclass[4:2]: funct3
                # - opclass[7:5]: reserved; 0b111 on unknown
                # unknown은 일단 무시

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
                        print(f'Dispatch region #{curDispatchRegion} begin: instCtr={instCtr}, file pointer={logFile.tell()}, name={curDispatchRegionName} at {addr:#8x}')
                        onDispatchRegion = True

                    elif funct3 == 1: # dr.end
                        curRegion += 1
                        curHostRegion += 1
                        print(f'Dispatch region #{curDispatchRegion} end: instCtr={instCtr}, file pointer={logFile.tell()}, name={curDispatchRegionName} at {addr:#8x}')
                        onDispatchRegion = False
            
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
                    if args.use_ast:
                        localAST[curRegion].put(sectionTable, objectTable, instCtr, addr, opType, dataType, operandSize)

                ## Disable InstStatTable (IST)...
                #     if opType == 0: # load
                #         instStatTable.put(curRegion, INST_STAT_LOAD)
                #     else:
                #         instStatTable.put(curRegion, INST_STAT_STORE)

                # elif opType == 2: # arith
                #     instStatTable.put(curRegion, dataType)

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

                        # dr.begin/dr.end가 선두에 오는 경우 처리
                        if traceCnt == 0:
                            curRegion -= 1
                            localSST[curRegion].name = stName
                            localOST[curRegion].name = stName
                            if args.use_ast:
                                localAST[curRegion].name = stName
                            if sampleInterval > 1:
                                sampleCnt -= 1
                            traceCnt += 1
                            continue

                        sst = SectionStatTable(sectionTable)
                        sst.name = stName
                        localSST.append(sst)

                        ost = ObjectStatTable(objectTable)
                        ost.name = stName
                        localOST.append(ost)

                        if args.use_ast:
                            ast = AccessSequenceTable()
                            ast.name = stName
                            localAST.append(ast)

                        ## Disable IST...
                        # istEntry = InstStatTableEntry()
                        # istEntry.name = stName
                        # instStatTable.tbl.append(istEntry)


            ## Update segment boundary
            # 이미 섹션 테이블이 있는데 이 부분 필요할까? (나중에 deprecate 시킬 것)
            # if opType == 0 or opType == 1: # load/store
            #     if addr >= stackBase: # stack
            #         if plotData.stackAddrHigh < addr:
            #             plotData.stackAddrHigh = addr
            #         if plotData.stackAddrLow > addr:
            #             plotData.stackAddrLow = addr
            #     else: # data
            #         if plotData.dataAddrHigh < addr:
            #             plotData.dataAddrHigh = addr
            #         if plotData.dataAddrLow > addr:
            #             plotData.dataAddrLow = addr
            # End of while loop (in binary trace mode)

            if sampleInterval > 1:
                sampleCnt -= 1
            traceCnt += 1

        lastInstCtr = instCtr
        plotData.totalInstCnt = lastInstCtr + 100
        print(f'Last instruction counter: {lastInstCtr}')
        # End of binary trace mode
    # End of trace analysis

    endTime = time.time()
    traceProcessTime = endTime - startTime
    logFile.close()
    print('Trace analyzing has been completed')
    print(f'[Trace Analysis] elapsed time: {traceProcessTime:.5f} sec')
    plotData.displayLength()

# Deprecated
# if args.human_readable and args.use_dump:
#     print()
#     print(plotData.epilogue)

## 통계 정보 출력 및 덤프 저장 ==============================================
print()
# print('## Data ##')
# print('address (low) : %x' % plotData.dataAddrLow)
# print('address (high): %x' % plotData.dataAddrHigh)
# print('--> %d KB\n' % ((plotData.dataAddrHigh - plotData.dataAddrLow) / 1024))
# print('## Stack ##')
# print('address (low) : %x' % plotData.stackAddrLow)
# print('address (high): %x' % plotData.stackAddrHigh)
# print('--> %d KB\n' % ((plotData.stackAddrHigh - plotData.stackAddrLow) / 1024))
print('## PC    ##')
print('address (low) : %x' % plotData.pcLow)
print('address (high): %x' % plotData.pcHigh)
print('--> %d KB\n' % ((plotData.pcHigh - plotData.pcLow) / 1024))

# 캐시 시뮬레이터용: 생성된 AST를 파일로 덤프한다
if args.use_ast:
    astDumpFile = open(astFilePath, 'wb')
    pickle.dump(localAST, astDumpFile)
    print(f'ASTs are saved to {astFilePath}')
    astDumpFile.close()

# 덤프 파일이 존재하지 않는 경우 생성된 플롯 데이터 저장 (Deprecated)
# if not dumpReadMode and args.enable_dump:
#     dumpFile = open(dumpPathName, 'wb')
#     plotData.saveDump(dumpFile)
#     print('Plot data saved in %s' % dumpPathName)

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

    ## Disable IST...
    # printSepline('InstStatTable')
    # instStatTable.examine(True)
    # printSepline()
    # print()
    
    if args.verbose and args.use_ast:
        print('## AccessSequenceTables ##')
        printSepline('Local ASTs')
        for i, ast in enumerate(localAST):
            ast.examine()
            print()
        printSepline()
        print()

    # 각 localAST의 시작 명령어의 instCnt 출력
    if args.use_ast:
        print('## AccessSequenceTables (instruction counter only) ##')
        printSepline('Local ASTs')
        for i, ast in enumerate(localAST):
            print(f'{ast.name}: {ast.getFirstInstructionCounter()}')
        printSepline()
        print()

## function call trace ==============================================
# print('## FunctionStatTables ##')
# loadFunctionTrace(funcTraceFilePath)

# printSepline('Sequence of dispatch region call')
# drCnt = 0
# for drName in dispatchRegionSequence:
#     print(drName)
#     drCnt += 1
# print(f'>> Total {drCnt} dispatch regions')
# printSepline()

## 그래프 출력 ========================================================
# Initialize plot
print()

if args.disable_plot:
    print(f'[Trace Analysis] elapsed time: {traceProcessTime:.5f} sec')
    exit(0)

print('Plotting graphs...')
startTime = time.time()

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

endTime = time.time()
plotTime = endTime - startTime
print(f'Total {nsamples} samples are processed')
print(f'[Trace Analysis] elapsed time: {traceProcessTime:.5f} sec')
print(f'[Plot] elapsed time: {plotTime:.5f} sec')
plt.show()

