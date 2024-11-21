import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pickle

from renodetrace import *

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

def to_hex(data, pos):
    return f'0x{int(data):X}'

def to_sampled(data, pos):
    return f'{int(data) * sampleInterval}'

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

def initPlotFormat(ax, plotData, pltype='ldst', model_name='ecg_small'):
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
    # if args.verbose:
    #     print(f'multipleLocator: {multipleLocatorX}, {multipleLocatorY: #x}')
    print(f'multipleLocator: X={multipleLocatorX}, Y={multipleLocatorY: #x}')
    print(f'DMEM length ({model_name}): {getDMemLength(model_name)}')

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

def plotSectionBoundary(modelName, secTbl, ax):
    # if args.disable_plot_section_boundary:
    #     return
    for s in secTbl:
        if s.vma < getDMemBaseAddress(modelName):
            continue
        # if args.verbose:
        #     print('%-30s VMA=%08x, Size=%08x' % (s.name, s.vma, s.size))
        ax.axhline(y=s.vma, color='#aaaaaa', linestyle='--', linewidth=1, alpha=0.7, label=s.name)
    # if args.verbose:
    #     print()

def plotLdstSep(modelName, secTbl, plotData, typeWise=False):
    ## 4개 창 생성 및 개별 그래프 출력
    fig1, axs1 = plt.subplots(num=1)
    # fig1.canvas.manager.set_window_title('Memory access trace')
    fig1.canvas.manager.set_window_title(f'{modelName}: memory access trace')
    initPlotFormat(axs1, plotData, model_name=modelName)
    plotSectionBoundary(modelName, secTbl, axs1)
    axs1.scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs1.scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs1.scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs1.scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs1.scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs1.scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs1.set_title('Memory access trace (all)')

    if not typeWise:
        return

    fig2, axs2 = plt.subplots(num=2)
    fig2.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs2, plotData, model_name=modelName)
    plotSectionBoundary(modelName, secTbl, axs2)
    axs2.scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
    axs2.scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
    axs2.set_title('Memory access trace (integer load/store)')

    fig3, axs3 = plt.subplots(num=3)
    fig3.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs3, plotData, model_name=modelName)
    plotSectionBoundary(modelName, secTbl, axs3)
    axs3.scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
    axs3.scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
    axs3.set_title('Memory access trace (FP load/store)')

    fig4, axs4 = plt.subplots(num=4)
    fig4.canvas.manager.set_window_title('Memory access trace')
    initPlotFormat(axs4, plotData, model_name=modelName)
    plotSectionBoundary(modelName, secTbl, axs4)
    axs4.scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
    axs4.scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
    axs4.set_title('Memory access trace (vector load/store)')

def plotLdst(modelName, secTbl, plotData):
    ## 1개 창, 서브 플롯 2x2개 생성
    fig1, axs1 = plt.subplots(2, 2, num='Memory Access Trace')

    # plt.ylim(0x34000000, 0x35000000)
    # plt.ylim(0, 0x1100000)
    # plt.xlim(plotData.totalInstCnt + 1000)

    # 그래프 서식 일괄 적용
    for ax in axs1.flat:
        initPlotFormat(ax, plotData, model_name=modelName)
        plotSectionBoundary(modelName, secTbl, ax)
    
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

def plotArith(modelName, plotData):
    # 서브 플롯 2x2개 생성
    fig2, axs2 = plt.subplots(2, 2, num='Arithmetic Operations')
    # 그래프 서식 일괄 적용
    for ax in axs2.flat:
        initPlotFormat(ax, plotData, pltype='arith', model_name=modelName)

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

def plotArithSep(modelName, plotData, typeWise=False):
    fig1, axs1 = plt.subplots(num=5)
    initPlotFormat(axs1, plotData, pltype='arith', model_name=modelName)
    #fig1.canvas.manager.set_window_title('Arithmetic operations trace')
    fig1.canvas.manager.set_window_title(f'{modelName}: arithmetic operations trace')
    axs1.scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs1.scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs1.scatter(plotData.varithX, plotData.varithY, color=plotColor['varith'], s=1)
    axs1.set_title('Arithmetic operations trace (all)')

    if not typeWise:
        return

    fig2, axs2 = plt.subplots(num=6)
    initPlotFormat(axs2, plotData, pltype='arith', model_name=modelName)
    fig2.canvas.manager.set_window_title('Arithmetic operations trace')
    axs2.scatter(plotData.arithX, plotData.arithY, color=plotColor['arith'], s=1)
    axs2.set_title('Integer arithmetic only')

    fig3, axs3 = plt.subplots(num=7)
    initPlotFormat(axs3, plotData, pltype='arith', model_name=modelName)
    fig3.canvas.manager.set_window_title('Arithmetic operations trace')
    axs3.scatter(plotData.fparithX, plotData.fparithY, color=plotColor['fparith'], s=1)
    axs3.set_title('FP arithmetic only')

    fig4, axs4 = plt.subplots(num=8)
    initPlotFormat(axs4, plotData, pltype='arith', model_name=modelName)
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
