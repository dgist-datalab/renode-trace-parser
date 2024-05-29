import re
import matplotlib.pyplot as plt
import sys
import os.path

pathName = 'log/ecg_small_20240524_160327.txt'

if len(sys.argv) == 2:
	pathName = sys.argv[1]

if os.path.isfile(pathName):
	logFile = open(pathName, 'r', encoding='utf-8')
	print('File %s is opened' % pathName)
else:
	print('E: file %s does not exist' % pathName)
	exit(1)

addrBase = 0x34000000
#plt.ylim(0x34000000, 0x35000000)
plt.ylim(0, 0x1100000)
plt.xlabel('time')
plt.ylabel('address')
plt.grid(True)

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
		addrPlot = int(addrStr, 16) - addrBase
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

print('\n')
print(epilogue, end='')
for line in logFile:
	print(line, end='')

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

plt.scatter(loadX, loadY, color='blue', s=1)# , label='load')
plt.scatter(storeX, storeY, color='red', s=1)#, label='store')
plt.scatter(fploadX, fploadY, color='green', s=1)#, label='FP load')
plt.scatter(fpstoreX, fpstoreY, color='yellow', s=1)#, label='FP store')

#plt.legend()

plt.show()