import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import sys
import os.path
import pickle
import argparse

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
		# memory access boundary
		self.dataAddrLow	= 0xffffffff
		self.dataAddrHigh	= 0x00000000
		self.stackAddrLow	= 0xffffffff
		self.stackAddrHigh	= 0x00000000
		# total instructions
		self.totalInstCnt = 0
		self.epilogue = ''

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

def initPlotFormat(ax, pltype='ldst'):
	multipleLocatorX = 500000
	multipleLocatorY = 0x200000
	if pltype != 'ldst':
		multipleLocatorX = 500000
		multipleLocatorY = 0x8000

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

## Initialize argparse ==============================================
parser = argparse.ArgumentParser()

parser.add_argument('--all', action='store_true', help='Enable all options')
parser.add_argument('--plot-ldst', action='store_true', help='Enable plotting load/store instruction traces')
parser.add_argument('--plot-arith', action='store_true', help='Enable plotting arithmetic instruction traces')
parser.add_argument('--separate', action='store_true', help='All subplots are rendered in separate windows')
parser.add_argument('--save-figure', action='store_true', help='Save figures as image files')

args = parser.parse_args()

# 아무 인자 없을 시 --plot-ldst, --plot-arith는 참으로 설정
#if len(sys.argv) < 2:
if not args.plot_ldst and not args.plot_arith:
	args.plot_ldst = True
	args.plot_arith = True

## Open the trace log or dump file ==================================
#logFileName = 'ecg_small_20240624_142406'		# stack=200K (default)
#logFileName = 'ecg_small_20240705_140632'		# stack=100K
logFileName = 'ecg_small_20240705_142117'		# stack=10M
# logFileName = 'ecg_small_20240705_143322'		# another stack=200K
#logFileName = 'mobile_net_v1_20240703_142550'
#logFileName = 'mnist_20240703_142344'

pathName = 'log/%s.txt' % logFileName
logFile = None

dumpPathName = 'dump/dump_%s.pkl' % logFileName
dumpReadMode = False
dumpFile = None

if os.path.isfile(dumpPathName):
	print('Dump file %s is detected' % dumpPathName)
	dumpFile = open(dumpPathName, 'rb')
	dumpReadMode = True

if os.path.isfile(pathName):
	logFile = open(pathName, 'r', encoding='utf-8')
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
dmemAddrBase = 0x34000000
imemAddrBase = 0x32000000
plotData = DLPlotData()
epilogue = ''

if dumpReadMode:
	plotData = pickle.load(dumpFile)
	plotData.displayBoundary()
	if plotData.totalInstCnt == 0:
		print('E: failed to load plot data')
		exit(1)
	else:
		print('Plot data is loaded from %s successfully' % dumpPathName)

else:
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
			#opc = int(matches[1], 16) # opcode
			opcCnt = int(matches[2])
			pc = int(matches[3].split(sep='=')[1].strip(), 16)
			opStr = (line.split()[1]).split(sep='(')[0]
			addr = 0

			if matchLen == 5: # load/store
				addr = int(matches[4].split(sep='=')[1].strip(), 16)
				#sys.stdout.write('\r' + '[%d] op=%s: opcode=%x, count=%d, pc=%x, addr=%x' % (instCtr, opStr, opc, opcCnt, pc, addr))
				sys.stdout.write('\r' + '[%d] op=%s: count=%d, pc=%x, addr=%x' % (instCtr, opStr, opcCnt, pc, addr))
			elif matchLen == 4: # arithmetic
				#sys.stdout.write('\r' + '[%d] op=%s: opcode=%x, count=%d, pc=%x' % (instCtr, opStr, opc, opcCnt, pc))
				sys.stdout.write('\r' + '[%d] op=%s: count=%d, pc=%x' % (instCtr, opStr, opcCnt, pc))
			
			## Update plot data
			if matchLen == 4: # arithmetic
				if 'f' in opStr: # FP arith
					plotData.fparithX.append(instCtr)
					plotData.fparithY.append(pc)
				elif 'v' in opStr: # vector arith
					plotData.varithX.append(instCtr)
					plotData.varithY.append(pc)
				else: # integer arith
					plotData.arithX.append(instCtr)
					plotData.arithY.append(pc)
				pass
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
					else: # store
						plotData.fpstoreX.append(instCtr)
						plotData.fpstoreY.append(addr)
						pass
				elif 'v' in opStr: # vector load/store
					if 'l' in opStr: # load
						plotData.vloadX.append(instCtr)
						plotData.vloadY.append(addr)
					else: # store
						plotData.vstoreX.append(instCtr)
						plotData.vstoreY.append(addr)
				else: # integer load/store
					if 'l' in opStr: # load
						plotData.loadX.append(instCtr)
						plotData.loadY.append(addr)
					elif 's' in opStr: # store
						plotData.storeX.append(instCtr)
						plotData.storeY.append(addr)
					else:
						print('%s: illegal instruction' % line)
						break

			# sys.stdout.write('\r' + '[%d] op=%s: opcode=%x, count=%d, pc=%x, addr=%x' 
			# 	% (instCtr, opStr, opc, opcCnt, pc, addr))
		else:
			print('%s: unknown instruction, matchLen=%d' % (line, matchLen))

	print('\n')
	print(epilogue, end='')
	plotData.epilogue += epilogue
	for line in logFile:
		print(line, end='')
		plotData.epilogue += line
		if "Total instructions" in line:
			plotData.totalInstCnt = int(line.split(sep=':')[1].strip())

	logFile.close()
	
if dumpReadMode:
	print()
	print(plotData.epilogue)

print()
print("## Data ##")
print("address (low) : %x" % plotData.dataAddrLow)
print("address (high): %x" % plotData.dataAddrHigh)
print("--> %d KB" % ((plotData.dataAddrHigh - plotData.dataAddrLow) / 1024))
print()
print("## Stack ##")
print("address (low) : %x" % plotData.stackAddrLow)
print("address (high): %x" % plotData.stackAddrHigh)
print("--> %d KB" % ((plotData.stackAddrHigh - plotData.stackAddrLow) / 1024))

# 덤프 파일이 존재하지 않는 경우 생성된 플롯 데이터 저장
if not dumpReadMode:
	dumpFile = open(dumpPathName, 'wb')
	plotData.saveDump(dumpFile)
	#dumpSave(dumpFile, plotData)
	#dumpFile.close()
	print('Plot data saved in %s' % dumpPathName)

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

if args.plot_ldst or args.all:
	if args.separate:
		## 4개 창 생성 및 개별 그래프 출력
		fig1, axs1 = plt.subplots(num=1)
		fig1.canvas.manager.set_window_title('Memory access trace')
		initPlotFormat(axs1)
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
		axs2.scatter(plotData.loadX, plotData.loadY, color=plotColor['load'], s=1)
		axs2.scatter(plotData.storeX, plotData.storeY, color=plotColor['store'], s=1)
		axs2.set_title('Memory access trace (integer load/store)')

		fig3, axs3 = plt.subplots(num=3)
		fig3.canvas.manager.set_window_title('Memory access trace')
		initPlotFormat(axs3)
		axs3.scatter(plotData.fploadX, plotData.fploadY, color=plotColor['fpload'], s=1)
		axs3.scatter(plotData.fpstoreX, plotData.fpstoreY, color=plotColor['fpstore'], s=1)
		axs3.set_title('Memory access trace (FP load/store)')

		fig4, axs4 = plt.subplots(num=4)
		fig4.canvas.manager.set_window_title('Memory access trace')
		initPlotFormat(axs4)
		axs4.scatter(plotData.vloadX, plotData.vloadY, color=plotColor['vload'], s=1)
		axs4.scatter(plotData.vstoreX, plotData.vstoreY, color=plotColor['vstore'], s=1)
		axs4.set_title('Memory access trace (vector load/store)')

	else:
		## 1개 창, 서브 플롯 2x2개 생성
		fig1, axs1 = plt.subplots(2, 2, num='Memory Access Trace')

		# plt.ylim(0x34000000, 0x35000000)
		# plt.ylim(0, 0x1100000)
		# plt.xlim(plotData.totalInstCnt + 1000)

		# 그래프 서식 일괄 적용
		for ax in axs1.flat:
			initPlotFormat(ax)
		
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


## 새로운 창: 산술 연산 명령어
if args.plot_arith or args.all:
	if args.separate:
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
	else:
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
