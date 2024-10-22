import re
#import matplotlib.pyplot as plt
#import matplotlib.ticker as ticker
#import numpy as np
import sys
import os.path
import pickle
import argparse
import time

import renodetrace as rt
from renodetrace import printSepline
from renodetrace.stattable import OP_TYPE_STR
from renodetrace.stattable import DATA_TYPE_STR
from renodetrace.stattable import OPERAND_SIZE

modelName = 'fc_triple_medium'
batchSize = 1
modelConfig = ''


## Initialize argparse ==============================================
parser = argparse.ArgumentParser()

#parser.add_argument('--separate', action='store_true', help='All subplots are rendered in separate windows')
parser.add_argument('--model-name', action='store', default=modelName, help=f'Specify target model name (default={modelName})')
parser.add_argument('--batch-size', action='store', type=int, default=batchSize, help=f'Specify batch size (default={batchSize})')
#parser.add_argument('--model-config', action='store', default=modelConfig, help=f'Specify FC triple model configuration: small, medium, large, xl, xxl (default={modelConfig})')
#parser.add_argument('--disable-plot-section-boundary', action='store_true')
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--ast-input', action='store')
parser.add_argument('--cache-size', action='store', default=100)
args = parser.parse_args()

logFilePath = rt.LOCAL_LOG_PATH
memConfig = 'default'
logFileName = ''
headerFileName = ''
readelfFileName = ''
funcTraceFileName = ''

modelName = args.model_name
batchSize = args.batch_size

#print(f'Model name: {modelName}')

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
    if args.without_custom:
        logFileName = 'ecg_small_20240911_162931' # binary, with arithmetic, no custom instructions
        headerFileName = 'ecg_small_fp32_emitc_static_no_custom_headers'
        readelfFileName = ''
        funcTraceFileName = ''
        print('E: ECG small without custom instruction is not supported yet:(')
        exit(1)
    else:
        logFileName = 'ecg_small_20240906_165242' # binary, with arithmetic, with custom instructions
        headerFileName = 'ecg_small_fp32_emitc_static_headers'
        readelfFileName = 'ecg_small_fp32_emitc_static_readelf'
        funcTraceFileName = 'ecg_small'

astDumpFileName = ''
if args.ast_input is not None:
    astDumpFileName = args.ast_input

astDumpFilePath = f'dump/{astDumpFileName}.ast'

# trace log 파일 경로 결정
if 'fc_triple' in modelName:
    logFilePath = rt.GLOBAL_LOG_PATH

logFileExt = '.bin'
pathName = logFilePath + '/' + logFileName + logFileExt

# ELF header 및 symbol table 파일의 실제 경로 결정
HEADER_PATH = f'/home/euntae/tmp/springbok-samples-elfs-dump_{memConfig}/headers'
READELF_PATH = f'/home/euntae/tmp/springbok-samples-elfs-dump_{memConfig}/readelf-sym'

headerFilePath = f'{HEADER_PATH}/{headerFileName}.dump'
readelfFilePath = f'{READELF_PATH}/{readelfFileName}.dump'
funcTraceFilePath = f'{rt.FUNC_TRACE_PATH}/{funcTraceFileName}.log'

## Test =============================================================
printSepline('File information summary')
print(f'model name: {modelName}')
print(f'model config: {modelConfig}')
print(f'memConfig: "{memConfig}"')
print(f'trace log file path: {pathName}')
print(f'headers file path: {headerFilePath}')
print(f'readelf file path: {readelfFilePath}')
print(f'function call trace file path: {funcTraceFilePath}')
print(f'AccessSequenceTable dump file path: {astDumpFilePath}')
printSepline()
## ==================================================================

## Load tables  =====================================================
sectionTable = []
symbolTable = []
objectTable = []

rt.stattable.loadSectionTable(headerFilePath, sectionTable)
rt.stattable.loadSymbolTable(readelfFilePath, symbolTable)
rt.stattable.loadObjectTable(sectionTable, symbolTable, objectTable)
rt.stattable.examineSectionTable(sectionTable)
rt.stattable.examineSymbolTable(symbolTable)
rt.stattable.examineObjectTable(objectTable)

if os.path.isfile(astDumpFilePath):
    print(f'Open AST dump file {astDumpFilePath}...')
    astDumpFile = open(astDumpFilePath, 'rb')
else:
    print(f'E: {astDumpFilePath} does not exist')
    exit(1)
localAST = pickle.load(astDumpFile)

localAST[0].examine()