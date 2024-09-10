import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import sys
import os.path
import pickle
import argparse
import time

DL_TRACE_SIZE_COMPACT_MEM = 13
DL_TRACE_SIZE_COMPACT_ARITH = 14

## 로그 파일명 설정
# 구버전
# logFileName = 'ecg_small_20240624_142406' # human-readable, with arithmetic

# 신버전
#logFileName = 'ecg_small_20240807_013502' # human-readable, with arithmetic
#logFileName = 'ecg_small_20240812_163305' # binary, with arithmetic

#logFileName = 'mnist_20240813_200917' # binary, with arithmetic
#logFileName = 'mobilenet_20240813_201434' # binary, with arithmetic

#logFileName = 'ecg_small_20240906_165242' # binary, with arithmetic, with custom instructions
#modelName = 'ecg_small'
#modelName = 'mobilenet'

# logFileName = 'fc_basic_20240909_171650_batch1'
# logFileName = 'fc_basic_20240909_171747_batch4'
# logFileName = 'fc_basic_20240909_172026_batch8'
# logFileName = 'fc_basic_20240909_172133_batch16'
# logFileName = 'fc_basic_20240909_172400_batch32'
logFileName = 'fc_basic_20240909_172615_batch128'
modelName = 'fc_basic'

headerFileName = 'fc_basic_emitc_static_batch128_headers'

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

# 딕셔너리로 접근할지 아님 idx를 배열 인덱스로 접근할지?
class SectionTableEntry:
    def __init__(self):
        self.idx = 0
        self.name = ''
        self.size = 0
        self.vma = 0
        self.lma = 0
        self.fileOff = 0
        self.aligh = 0
    
    def examine(self):
        print(f'idx: {self.idx}, {self.name}, size: {self.size:08x}, vma: {self.vma:08x}, lma: {self.lma:08x}, fileOff: {self.fileOff:08x}, align: {self.align}')
    
def loadSectionTable(filename):
    fpath = 'header/' + filename + '.dump'
    print(f'Load from {fpath}...')
    if os.path.isfile(fpath):
        headerFile = open(fpath, 'r', encoding='utf-8')
    else:
        print('E: file %s does not exist' % fpath)
        exit(1)

    # 데이터 이전의 행들은 읽어서 무시
    for line in headerFile:
        if 'Idx' in line:
            break

    for line in headerFile:
        tokens = line.split()
        if not tokens[0].isnumeric():
            continue
        entry = SectionTableEntry()
        entry.idx = int(tokens[0])
        entry.name = tokens[1]
        entry.size = int(tokens[2], 16)
        entry.vma = int(tokens[3], 16)
        entry.lma = int(tokens[4], 16)
        entry.fileOff = int(tokens[5], 16)
        entry.align = tokens[6]
        entry.examine()
        sectionTable.append(entry)
    headerFile.close()
    print('Section Table has successfully constructed')

class DLPlotData:
    def __init__(self):
        # load/store
        self.loadX = []
        self.loadY = []
        self.storeX = []
        self.storeY = []
        # FP load/store
        self.fploadX = []
        self.fploadY = []
        self.fpstoreX = []
        self.fpstoreY = []
        # vector load/store
        self.vloadX = []
        self.vloadY = []
        self.vstoreX = []
        self.vstoreY = []
        # arithmetic
        self.arithX = []
        self.arithY = []
        # FP arithmetic
        self.fparithX = []
        self.fparithY = []
        # vector arithmetic
        self.varithX = []
        self.varithY = []
        # unknown and custom
        # TODO: custom instruction의 경우 opclass에 따라 세분화할 것
        self.customX = [] # instCtr
        self.customY = [] # PC
        self.customOpclass = [] # funct3 and opcode

        # memory access boundary
        self.dataAddrLow	= 0xffffffff
        self.dataAddrHigh	= 0x00000000
        self.stackAddrLow	= 0xffffffff
        self.stackAddrHigh	= 0x00000000
        # PC boundary
        self.pcLow          = 0x00000000
        self.pcHigh         = 0xffffffff
        # total instructions
        self.totalInstCnt = 0
        self.epilogue = ''

        # cumulative data
        self.memCDF = []
        self.loadCDF = []
        self.storeCDF = []
        self.arithCDF = []

        self.fploadCDF = []
        self.fpstoreCDF = []
        self.fparithCDF = []

        self.vloadCDF = []
        self.vstoreCDF = []
        self.varithCDF = []

        self.instCtr = []

    def displayBoundary(self):
        print("Data (low):   0x%x" % self.dataAddrLow)
        print("Data (high):  0x%x" % self.dataAddrHigh)
        print("Stack (low):  0x%x" % self.stackAddrLow)
        print("Stack (high): 0x%x" % self.stackAddrHigh)
    
    # def loadDump(self, dfile):
    # 	if dfile is None:
    # 		print('E: file %s is not opened' % dumpPathName)
    # 		return False
    # 	self = pickle.load(dfile)
    # 	dfile.close()

    def saveDump(self, dfile):
        pickle.dump(self, dfile)
        dfile.close()

def to_hex(data, pos):
    return f'0x{int(data):X}'

def to_sampled(data, pos):
    return f'{int(data) * sampleInterval}'

# samples/{ModelName}/CMakeLists.txt 참조
# 별도의 빌드 옵션이 지정되어 있지 않으면 default
# default:
# DMem 16M, IMem 1M, Stack 10K
def getIMemLength(model_name='ecg_small'):
    if model_name == 'mobilebert':
        return 128 * 1024 * 1024 # 128M
    else: # default (1M)
        return 1024 * 1024

def getDMemLength(model_name='ecg_small'):
    if model_name == 'mobilebert':
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

def getIntegerRound(num, mode='dec'):
    base = 10       # 진수
    shiftamt = 0    # 얼마나 나눴는지
    if mode == 'hex':
        base = 0x10
    # 최상위 n자리 추출
    nUpperDigits = 2
    upperDigits = num
    while upperDigits > base ** nUpperDigits:
        upperDigits /= base
        shiftamt += 1
    upperDigits = int(upperDigits)
    msd = int(upperDigits / (base ** (nUpperDigits-1)))         # 최상위 숫자
    subUpperDigits = upperDigits % (base ** (nUpperDigits-1))   # 최상위 숫자를 제외한 나머지 부분
    # print(f'msd: {msd}')
    # print(f'subUpperDigits: {subUpperDigits}')

    if subUpperDigits >= (base ** (nUpperDigits-1)) / 2: # 반올림
        msd += 1
    msd *= base ** (shiftamt + nUpperDigits - 1)
    # print(f'result: {msd}')
    return msd

def initPlotFormat(ax, pltype='ldst', model_name='ecg_small'):
    '''
    multipleLocatorX = 500000
    multipleLocatorY = 0x200000

    if model_name == 'ecg_small':
        if pltype == 'ldst':
            multipleLocatorX = 500000
            multipleLocatorY = 0x200000
        else: # 산술연산; IMem 접근
            multipleLocatorX = 500000
            multipleLocatorY = 0x8000
    elif model_name == 'mnist':
        if pltype == 'ldst':
            pass
        else:
            pass
    elif model_name == 'mobilenet':
        if pltype == 'ldst':
            pass
        else:
            pass
    elif model_name == 'mobilebert':
        if pltype == 'ldst':
            pass
        else:
            pass
    '''
    xtickNum = 25 # x축 눈금의 개수를 25개로 제한
    multipleLocatorX = int(plotData.totalInstCnt / xtickNum)

    ytickNum = 10 # y축 눈금의 개수를 10개로 제한
    if pltype == 'ldst':
        multipleLocatorY = int(getDMemLength(model_name) / ytickNum)
    else:
        #multipleLocatorY = int(getIMemLength(model_name) / ytickNum)
        # IMem 전체 영역을 기준으로 하는 것보다 실제 실행된 명령어의 PC 범위를 사용하는 것이 더욱 정확함
        multipleLocatorY = int((plotData.pcHigh - plotData.pcLow) / ytickNum)
    
    #print(f'multipleLocator: {multipleLocatorX}, {multipleLocatorY: #x}')
    #print(f'total instruction count: {plotData.totalInstCnt}')
    multipleLocatorX = getIntegerRound(multipleLocatorX, 'dec')
    multipleLocatorY = getIntegerRound(multipleLocatorY, 'hex')
    print(f'multipleLocator: {multipleLocatorX}, {multipleLocatorY: #x}')

    ax.grid(False)
    ax.set_xlabel('# instruction')
    ax.set_ylabel('address')
    # 눈금 간격 설정
    ax.xaxis.set_major_locator(ticker.MultipleLocator(multipleLocatorX))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(multipleLocatorY))
    # 눈금 형식 설정
    ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(to_hex))
    # x축 눈금 라벨을 세로로 회전
    ax.tick_params(axis='x', rotation=90)
    # 프로그램 시작과 끝 지점에 세로선 출력
    ax.axvline(x=0, color='#aaaaaa', linestyle='--', linewidth=1)
    ax.axvline(x=plotData.totalInstCnt, color='#aaaaaa', linestyle='--', linewidth=1)
    # 커스텀 명령어 실행 지점 출력
    for i, cx in enumerate(plotData.customX):
        opclass = plotData.customOpclass[i]
        opcode = opclass & 0b11
        funct3 = (opclass >> 2) & 0b111
        lcolor = '#aaaaaa'
        if opcode == 0b00: # custom-0
            if funct3 == 0: # dr.bedin
                lcolor = '#c8fe2e'
            elif funct3 == 1: # dr.end
                lcolor = '#facc2e'
            ax.axvline(x=cx, color=lcolor, linestyle='--', linewidth=1)

def plotSectionBoundary(ax):
    for s in sectionTable:
        if s.vma < getDMemBaseAddress(modelName):
            continue
        print('%-30s VMA=%08x, Size=%08x' % (s.name, s.vma, s.size))
        ax.axhline(y=s.vma, color='#aaaaaa', linestyle='--', linewidth=1, alpha=0.7, label=s.name)
    print()

def plotLdstSep():
    ## 4개 창 생성 및 개별 그래프 출력
    fig1, axs1 = plt.subplots(num=1)
    fig1.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs1)
    plotSectionBoundary(axs1)
    axs1.scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs1.scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs1.scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs1.scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs1.scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs1.scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs1.set_title('Memory access trace (all)')

    fig2, axs2 = plt.subplots(num=2)
    fig2.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs2)
    plotSectionBoundary(axs2)
    axs2.scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs2.scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs2.set_title('Memory access trace (integer load/store)')

    fig3, axs3 = plt.subplots(num=3)
    fig3.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs3)
    plotSectionBoundary(axs3)
    axs3.scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs3.scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs3.set_title('Memory access trace (FP load/store)')

    fig4, axs4 = plt.subplots(num=4)
    fig4.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs4)
    plotSectionBoundary(axs4)
    axs4.scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs4.scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs4.set_title('Memory access trace (vector load/store)')

def plotLdst():
    ## 1개 창, 서브 플롯 2x2개 생성
    fig1, axs1 = plt.subplots(2, 2, num='Memory Access Trace')

    # plt.ylim(0x34000000, 0x35000000)
    # plt.ylim(0, 0x1100000)
    # plt.xlim(plotData.totalInstCnt + 1000)

    # 그래프 서식 일괄 적용
    for ax in axs1.flat:
        initPlotFormat(ax)
        plotSectionBoundary(ax)
    
    # 개별 그래프 출력
    axs1[0, 0].scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs1[0, 0].scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs1[0, 0].scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs1[0, 0].scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs1[0, 0].scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs1[0, 0].scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs1[0, 0].set_title('Memory access trace (all)')

    axs1[0, 1].scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs1[0, 1].scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs1[0, 1].set_title('Integer load/store only')

    axs1[1, 0].scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs1[1, 0].scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs1[1, 0].set_title('FP load/store only')

    axs1[1, 1].scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs1[1, 1].scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs1[1, 1].set_title('Vector load/store only')

def plotArith():
    # 서브 플롯 2x2개 생성
    fig2, axs2 = plt.subplots(2, 2, num='Arithmetic Operations')
    # 그래프 서식 일괄 적용
    for ax in axs2.flat:
        initPlotFormat(ax, pltype='arith')

    # 개별 그래프 출력
    axs2[0, 0].scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs2[0, 0].scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs2[0, 0].scatter(plotData.varithX, plotData.varithY, color=plotColor['varith'], s=1)
    axs2[0, 0].set_title('Arithmetic operations trace (all)')

    axs2[0, 1].scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs2[0, 1].set_title('Integer arithmetic only')

    axs2[1, 0].scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs2[1, 0].set_title('FP arithmetic only')

    axs2[1, 1].scatter(plotData.varithX, plotData.varithY, color=plotColor['varith'], s=1)
    axs2[1, 1].set_title('Vector arithmetic only')

def plotArithSep():
    fig1, axs1 = plt.subplots(num=5)
    initPlotFormat(axs1, pltype='arith')
    fig1.canvas.manager.set_window_title('Arithmetic operations trace')
    axs1.scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs1.scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs1.scatter(plotData.varithX, plotData.varithY, color=plotColor['varith'], s=1)
    axs1.set_title('Arithmetic operations trace (all)')

    fig2, axs2 = plt.subplots(num=6)
    initPlotFormat(axs2, pltype='arith')
    fig2.canvas.manager.set_window_title('Arithmetic operations trace')
    axs2.scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs2.set_title('Integer arithmetic only')

    fig3, axs3 = plt.subplots(num=7)
    initPlotFormat(axs3, pltype='arith')
    fig3.canvas.manager.set_window_title('Arithmetic operations trace')
    axs3.scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs3.set_title('FP arithmetic only')

    fig4, axs4 = plt.subplots(num=8)
    initPlotFormat(axs4, pltype='arith')
    fig4.canvas.manager.set_window_title('Arithmetic operations trace')
    axs4.scatter(plotData.varithX, plotData.varithY, color=plotColor['varith'], s=1)
    axs4.set_title('Vector arithmetic only')

sampleInterval = 1000
def plotCumul():
    fig1, axs1 = plt.subplots(num=1)
    x = np.arange(len(plotData.loadCDF[::sampleInterval]))

    sampledLoadCDF = plotData.loadCDF[::sampleInterval]
    sampledStoreCDF = plotData.storeCDF[::sampleInterval]
    sampledArithCDF = plotData.arithCDF[::sampleInterval]

    '''
    loadCDF  = axs1.bar(x, plotData.loadCDF, color=plotColor['load'])
    storeCDF = axs1.bar(x, plotData.storeCDF, bottom=plotData.loadCDF, color=plotColor['store'])
    arithCDF = axs1.bar(x, plotData.arithCDF, bottom=np.array(plotData.loadCDF) + np.array(plotData.storeCDF), color=plotColor['varith'])
    '''
    
    loadCDF  = axs1.bar(x, sampledLoadCDF, color=plotColor['load'])
    storeCDF = axs1.bar(x, sampledStoreCDF, bottom=sampledLoadCDF, color=plotColor['store'])
    arithCDF = axs1.bar(x, sampledArithCDF, bottom=np.array(sampledLoadCDF) + np.array(sampledStoreCDF), color=plotColor['varith'])

    #xticks = x * sampleInterval
    #axs1.set_xticks(x)
    #axs1.set_xticklabels(xticks)
    #axs1.tick_params(axis='x', rotation=90)

    # axs1.xaxis.set_major_locator(ticker.MultipleLocator(10000))
    axs1.xaxis.set_major_formatter(ticker.FuncFormatter(to_sampled))
    axs1.tick_params(axis='x', rotation=90)

    axs1.yaxis.set_major_locator(ticker.MultipleLocator(1000000))
    axs1.yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))


## Initialize argparse ==============================================
parser = argparse.ArgumentParser()

parser.add_argument('--all', action='store_true', help='Enable all options')
parser.add_argument('--plot-ldst', action='store_true', help='Enable plotting load/store instruction traces')
parser.add_argument('--plot-arith', action='store_true', help='Enable plotting arithmetic instruction traces')
parser.add_argument('--separate', action='store_true', help='All subplots are rendered in separate windows')
parser.add_argument('--save-figure', action='store_true', help='Save figures as image files')
parser.add_argument('--cumulative', action='store_true', help='CDF mode')
parser.add_argument('--human-readable', action='store_true', help='Read from human-readable trace')
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--disable-dump', action='store_true', help='Disable plot dump save/load')

args = parser.parse_args()

## Load Section Table from file =====================================
sectionTable = []
loadSectionTable(headerFileName)


# 아무 인자 없을 시 --plot-ldst, --plot-arith는 참으로 설정
#if len(sys.argv) < 2:
if not args.plot_ldst and not args.plot_arith:
    args.plot_ldst = True
    args.plot_arith = True

## Open the trace log or dump file ==================================
#logFileName = 'ecg_small_20240624_142406'		# stack=200K (default)
#logFileName = 'ecg_small_20240705_140632'		# stack=100K
#logFileName = 'ecg_small_20240705_142117'		# stack=10M
# logFileName = 'ecg_small_20240705_143322'		# another stack=200K
#logFileName = 'mobile_net_v1_20240703_142550'
#logFileName = 'mnist_20240703_142344'

if args.human_readable:
    pathName = 'log/%s.txt' % logFileName
else:
    pathName = 'log/%s.bin' % logFileName
logFile = None

dumpPathName = 'dump/dump_%s.pkl' % logFileName
dumpReadMode = False
dumpFile = None

if os.path.isfile(dumpPathName) and (not args.disable_dump):
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
                # TODO: custom instruction의 경우 opclass에 따라 세분화할 것
                # unknown은 무시할 수 있다
                # if opclass & 0b11100000:
                plotData.customX.append(instCtr)
                plotData.customY.append(addr)
                plotData.customOpclass.append(opclass)
                opc = opclass & 0b11
                funct3 = (opclass >> 2) & 0b111
                print('[%d] custom-%d opclass=%02x funct3=%x pc=%#x ' % (instCtr, opc, opclass, funct3, addr))
            else: # parsing error
                print('E: unrecognized instruction:')
                print('[%d] opType=%d dataType=%d operandSize=%d addr=%#x ' % (instCtr, opType, dataType, operandSize, addr))
                exit(1)
            ## Update segment boundary
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
            
            lastInstCtr = instCtr
        # End of while loop
        plotData.totalInstCnt = lastInstCtr + 100
        print(f'Last instruction counter: {lastInstCtr}')
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

# 덤프 파일이 존재하지 않는 경우 생성된 플롯 데이터 저장
if not dumpReadMode and (not args.disable_dump):
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

## 그래프 출력 ========================================================
# Initialize plot
plotColor = {
    'load': '#1772c4',		# 파란색
    'store': '#cd3939',		# 빨간색
    'fpload': '#d0eb06',	# 연두색
    'fpstore': '#ffbd2e',	# 주황색
    'vload': '#009aa6',		# 청록색
    'vstore': '#ff97cf',	# 분홍색

    'arith': '#1772c4',		# 파란색
    'fparith': '#cd3939',	# 빨간색
    'varith': '#d0eb06'		# 연두색
}

print()
print('Plotting graphs...')

if args.cumulative:
    plotCumul()
else:
    ## load/store 명령어
    if args.plot_ldst or args.all:
        if args.separate:
            plotLdstSep()

        else:
            plotLdst()
            

    ## 새로운 창: 산술 연산 명령어
    if args.plot_arith or args.all:
        if args.separate:
            plotArithSep()
        else:
            plotArith()

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
