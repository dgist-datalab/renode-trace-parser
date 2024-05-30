import re
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import sys
import os.path
import pickle

def to_hex(data, pos):
	return f'0x{int(data):X}'

pathName = 'log/ecg_small_20240524_160327.txt'
logFile = None

dumpPathName = 'dump/dump0.pkl'
dumpReadMode = False
dumpFile = None

if os.path.isfile(dumpPathName):
	print('Dump file %s is detected' % dumpPathName)
	dumpFile = open(dumpPathName, 'rb')
	dumpReadMode = True

if len(sys.argv) == 2:
	pathName = sys.argv[1]

if os.path.isfile(pathName):
	logFile = open(pathName, 'r', encoding='utf-8')
	print('File %s is opened' % pathName)
else:
	print('E: file %s does not exist' % pathName)
	exit(1)

fig, ax = plt.subplots()

addrBase = 0x34000000
# plt.ylim(0x34000000, 0x35000000)
# plt.ylim(0, 0x1100000)

plt.grid(False)
ax.set_title('Memory access trace in ECG model')
ax.set_xlabel('time')
ax.set_ylabel('address')
# 눈금 간격 설정
ax.xaxis.set_major_locator(ticker.MultipleLocator(500000))
ax.yaxis.set_major_locator(ticker.MultipleLocator(0x200000))
# 눈금 형식 설정
ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))
ax.yaxis.set_major_formatter(ticker.FuncFormatter(to_hex))
# x축 눈금 라벨을 세로로 회전
plt.xticks(rotation=90)

# sb(=0023)/319929: pc=3203298a, addr=3406b292
ctr = 0
loadX  = []
loadY  = []
storeX = []
storeY = []
fploadX  = []
fploadY  = []
fpstoreX = []
fpstoreY = []

addrDataLow  = 0xffffffff
addrDataHigh = 0
addrStackLow = 0xffffffff
addrStackHigh = 0

epilogue = ''

if dumpReadMode:
	loadedData = pickle.load(dumpFile)
	dumpFile.close()
	loadX = loadedData['loadX']
	loadY = loadedData['loadY']
	storeX = loadedData['storeX']
	storeY = loadedData['storeY']
	fploadX = loadedData['fploadX']
	fploadY = loadedData['fploadY']
	fpstoreX = loadedData['fpstoreX']
	fpstoreY = loadedData['fpstoreY']
	addrDataLow = loadedData['addrDataLow']
	addrDataHigh = loadedData['addrDataHigh']
	addrStackLow = loadedData['addrStackLow']
	addrStackHigh = loadedData['addrStackHigh']
	totalInstrCount = loadedData['totalInstrCount']
	print('Dumped data is fully loaded!')

else:
	for line in logFile:
		#if ctr > 100:
		#	break

		epilogue = re.match(r'^##', line)
		if epilogue is not None:
			epilogue = line
			break
		instCtr = re.search(r'^\[[0-9]+\]', line)
		opc = re.search(r'[a-z]{2,}', line)
		numbers = re.findall(r'([=/][0-9a-f]+)', line)
		#print(line, end='')
		#print('op=%s' % opc.group())
		#print('opcode=%s, count=%s, addr=%s' % (numbers[0][1:], numbers[1][1:], numbers[3][1:]))
		ctrStr    = instCtr.group()
		opStr     = opc.group()
		opcodeStr = numbers[0][1:]
		countStr  = numbers[1][1:]
		addrStr   = numbers[3][1:]

		instCtrInt = int(ctrStr[1:-1])

		if opStr != 'unknown':
			#print('[%d] op=%s: opcode=%s, count=%s, addr=%s' % (ctr, opc.group(), opcodeStr, countStr, addrStr))
			#print('[%d] op=%s: opcode=%s, count=%s, addr=%x' % (ctr, opc.group(), opcodeStr, countStr, int(addrStr, 16) - 0x34000000))
			addrInt = int(addrStr, 16)
			# addrPlot = int(addrStr, 16) - addrBase
			addrPlot = int(addrStr, 16)
			if addrInt >= 0x34f00000: # stack
				if addrStackHigh < addrInt:
					addrStackHigh = addrInt
				if addrStackLow > addrInt:
					addrStackLow = addrInt
			else: # data
				if addrDataHigh < addrInt:
					addrDataHigh = addrInt
				if addrDataLow > addrInt:
					addrDataLow = addrInt
			sys.stdout.write('\r' + '[%d] op=%s: opcode=%s, count=%s, addr=%x' % (instCtrInt, opc.group(), opcodeStr, countStr, addrInt))
			#print('[%d] op=%s: opcode=%s, count=%s, addr=%x' % (instCtrInt, opc.group(), opcodeStr, countStr, addrInt))

			if 'f' in opStr: # FP load/store
				if 'l' in opStr: # load
					fploadX.append(instCtrInt)
					fploadY.append(addrPlot)
				elif 's' in opStr: #store
					fpstoreX.append(instCtrInt)
					fpstoreY.append(addrPlot)
				else:
					print("E: Illegal instruction")
					break
			else:
				if 'l' in opStr: # load
					loadX.append(instCtrInt)
					loadY.append(addrPlot)
				elif 's' in opStr: # store
					storeX.append(instCtrInt)
					storeY.append(addrPlot)
				else:
					print("E: Illegal instruction")
					break
			#ctr += 1

	totalInstrCountStr = ''
	totalInstrCount = 0
	print('\n')
	print(epilogue, end='')
	for line in logFile:
		print(line, end='')
		if "Total instructions" in line:
			totalInstrCountStr = line.split(sep=':')[1].strip()
			totalInstrCount = int(totalInstrCountStr)

	logFile.close()
	
print()
print("## Data ##")
print("address (low) : %x" % addrDataLow)
print("address (high): %x" % addrDataHigh)
print("--> %d KB" % ((addrDataHigh - addrDataLow) / 1024))
print()
print("## Stack ##")
print("address (low) : %x" % addrStackLow)
print("address (high): %x" % addrStackHigh)
print("--> %d KB" % ((addrStackHigh - addrStackLow) / 1024))

# 덤프 파일 저장
if not dumpReadMode:
	dumpFile = open(dumpPathName, 'wb')
	dumpData = { 'loadX': loadX, 'loadY': loadY, 'storeX': storeX, 'storeY': storeY, 
		'fploadX': fploadX, 'fploadY': fploadY, 'fpstoreX': fpstoreX, 'fpstoreY': fpstoreY,
		'addrDataLow': addrDataLow, 'addrDataHigh': addrDataHigh, 
		'addrStackHigh': addrStackHigh, 'addrStackLow': addrStackLow, 
		'totalInstrCount': totalInstrCount
	}
	pickle.dump(dumpData, dumpFile)
	dumpFile.close()
	print('%s is created' % dumpPathName)

# plt.xlim(totalInstrCount + 1000)
plt.scatter(loadX, loadY, color='blue', s=1)# , label='load')
plt.scatter(storeX, storeY, color='red', s=1)#, label='store')
plt.scatter(fploadX, fploadY, color='green', s=1)#, label='FP load')
plt.scatter(fpstoreX, fpstoreY, color='yellow', s=1)#, label='FP store')

# 프로그램 시작과 끝 지점에 세로선 출력
plt.axvline(x=0, color='#aaaaaa', linestyle='--', linewidth=1)
plt.axvline(x=totalInstrCount, color='#aaaaaa', linestyle='--', linewidth=1)
#plt.legend()

plt.show()