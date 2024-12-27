import time
import argparse

from renodetrace import *
from renodetrace.stattable import *
from renodetrace.plotdata import *

modelName = 'mobilenet_v1'
partNum = -1
logFileName = ''

parser = argparse.ArgumentParser()
parser.add_argument('--model-name', '-m', action='store', default=modelName)
parser.add_argument('--part', '-p', action='store')
args = parser.parse_args()

if args.part is not None:
    partNum = int(args.part)

if modelName == 'ecg_small':
    logFileName = 'ecg_small_20241208_203107'
elif modelName == 'fc_triple_small':
    logFileName = 'fc_triple_small_20241208_220506'
elif modelName == 'fc_triple_medium':
    logFileName = 'fc_triple_medium_20241208_220321'
elif modelName == 'fc_triple_large':
    logFileName = 'fc_triple_large_20241208_223442'
elif modelName == 'fc_triple_xl':
    logFileName = 'fc_triple_xl_20241218_155509'
elif modelName == 'fc_triple_xxl':
    logFileName = 'fc_triple_xxl_20241218_155656'
elif modelName == 'mobilenet_v1':
    logFileName = 'mobilenet_v1_20241208_220017'
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
    print(f'E: model {modelName} is not available')
    exit(1)

logFilePath = f'/home/euntae/renode-trace/instruction/{logFileName}.bin'
print(f'Open {logFilePath}...')

startTime = time.time()

logFile = open(logFilePath, 'rb')
trace = logFile.read(DL_TRACE_SIZE_COMPACT_MEM)

opType = trace[0] & 0b11
dataType = (trace[0] >> 2) & 0b111
operandSize = trace[0] >> 5
instCtr = int.from_bytes(trace[1:9], byteorder='little')
addr = int.from_bytes(trace[9:], byteorder='little')

opclass = -1
if opType == 2 or dataType == 3 or opType == 3:
    opclass = (logFile.read(1))[0]

print('[%d] opType=%d dataType=%d operandSize=%d addr=%#x opclass=%d' % (instCtr, opType, dataType, operandSize, addr, opclass))

logFile.close()
endTime = time.time()

print(f'Elapsed time: {endTime - startTime}')