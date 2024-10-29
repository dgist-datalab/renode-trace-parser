import sys
import os.path
import pickle
import argparse
import time
import math

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
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--ast-input', action='store')
parser.add_argument('--cache-size', action='store', default='32k', help='Specify entire cache size e.g., 32k, 8M')
parser.add_argument('--cache-block-size', action='store', type=int, default=64)
parser.add_argument('--nways', action='store', type=int, default=8)
parser.add_argument('--replace-policy', '-p', action='store', default='fifo')
args = parser.parse_args()
## ==================================================================

## Process cache parameters =========================================
arg_totalSize = args.cache_size
arg_blockSize = args.cache_block_size
arg_nways = args.nways
arg_replacePolicy = args.replace_policy

if arg_totalSize.isdigit():
    arg_totalSize = int(arg_totalSize)
elif 'k' in arg_totalSize or 'K' in arg_totalSize:
    arg_totalSize = int(arg_totalSize[0:-1]) * 1024
elif 'm' in arg_totalSize or 'M' in arg_totalSize:
    arg_totalSize = int(arg_totalSize[0:-1]) * 1024 * 1024
else:
    print(f'E: {arg_totalSize} is not valid value')

print(f'total cache size: {arg_totalSize}')
print(f'cache block size: {arg_blockSize}')
print(f'number of ways: {arg_nways}')
print(f'replacement policy: {arg_replacePolicy}\n')

## ==================================================================

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
# rt.stattable.examineSectionTable(sectionTable)
# rt.stattable.examineSymbolTable(symbolTable)
# rt.stattable.examineObjectTable(objectTable)

astDumpFile = None
if os.path.isfile(astDumpFilePath):
    print(f'Open AST dump file {astDumpFilePath}...')
    astDumpFile = open(astDumpFilePath, 'rb')
else:
    print(f'E: {astDumpFilePath} does not exist')
    exit(1)
localAST = pickle.load(astDumpFile)

# cnt = 0
# for ast in localAST:
#     ast.examine()
#     cnt += 1

print(f'>> total {len(localAST)} regions')

## 캐시 설계 고려사항
# 총 캐시 크기
# 캐시 블록 크기: 기본 64바이트
# 교체 정책: FIFO, LRU, 
# read/write 정책: write-through, write-back
        
class CacheLine:
    def __init__(self):
        self.valid = False
        self.tag = 0
        self.data = 0
        self.dirty = False
        self.count = 0
        #print('CacheLine()', end=' ')

    def clear(self):
        self.valid = False
        self.tag = 0
        self.data = 0
        self.dirty = False
        self.count = 0


class CacheMem:
    def __init__(self, totalSize=32*1024, blockSize=64, nways=8, replacePolicy='fifo'):
        self.naccess = 0
        self.nhit = 0
        self.nmiss = 0
        self.nevict = 0

        self.totalSize = totalSize
        self.blockSize = blockSize
        self.nways = nways
        self.replacePolicy = replacePolicy

        self.nblocks = int(self.totalSize / self.blockSize)   # 캐시 블록 개수 계산
        self.nsets = int(self.nblocks / self.nways)           # 세트 개수 계산
        
        print(f'CacheMem: nblocks={self.nblocks}, nways={self.nways}, nsets={self.nsets}')
        self.blkBits = int(math.log(self.blockSize, 2))
        self.idxBits = int(math.log(self.nsets, 2))
        self.tagBits = 32 - self.idxBits - self.blkBits
        self.idxMask = ((1 << self.idxBits) - 1) << self.blkBits
        self.tagMask = ((1 << self.tagBits) - 1) << (self.blkBits + self.idxBits)
        print(f'Address layout: tag={self.tagBits}, index={self.idxBits} block offset={self.blkBits}')
        print(f'Tag mask: {self.tagMask:b}, Index mask: {self.idxMask:b}')

        self.mem = []
        rows = 0
        cols = 0
        for _ in range(self.nsets):
            cset = [ CacheLine() for _ in range(self.nways) ]
            self.mem.append(cset)
            cols = len(cset)
            #print()
        rows = len(self.mem)
        print(f'--> Cache memory has successfully constructed: total {rows}x{cols} cache blocks')
        
    def clear(self): # or reset, flush?
        self.naccess = 0
        self.nhit = 0
        self.nmiss = 0
        self.nevict = 0

        entryCnt = 0
        for s in self.mem: # set
            for blk in s:
                blk.clear()
                entryCnt += 1
        print(f'CacheMem.clear: total {entryCnt} cache blocks cleared')
        
    def lookup(self, addr):
        hitFlag = False
        self.naccess += 1
        idx = (addr & self.idxMask) >> self.blkBits
        tag = (addr & self.tagMask) >> (self.idxBits + self.blkBits)
        if args.verbose:
            print(f'addr={addr:8x}, tag={tag:x}, idx={idx:02x}(={idx:06b})')
        for blk in self.mem[idx]:
            if blk.valid and blk.tag == tag: # cache hit
                self.nhit += 1
                return True
        
        # cache miss
        self.nmiss += 1
        if args.verbose:
            print('>> miss', end='')
        print()
        self.fetch(idx, tag)
        return False

    # 캐시 미스 시 호출
    def fetch(self, idx, tag):
        evictFlag = True
        # 현재 인덱스의 set에 가용 캐시 블럭이 존재하는지 검사
        for blk in self.mem[idx]:
            if not blk.valid: # 가용 블럭 존재 시 insert
                self.examineSet(idx)
                blk.valid = True
                blk.tag = tag
                evictFlag = False
                print('>> ', end='')
                self.examineSet(idx)
                break
        
        # 가용 블럭 부재 시 evict 후에 insert 수행
        if evictFlag:
            self.evict(idx)
            blk = CacheLine()
            blk.valid = True
            blk.tag = tag
            if self.replacePolicy == 'fifo':
                self.mem[idx].append(blk)
                self.examineSet(idx)
            elif self.replacePolicy == 'lru':
                pass
            elif self.replacePolicy == 'random':
                pass
            else:
                print(f'E: {self.replacePolicy} is not available')

    # idx가 가리키는 set에서 replace policy에 따라 evict할 블록을 결정
    # evict된 위치의 캐시 블록을 반환한다
    def evict(self, idx):
        self.nevict += 1
        if args.verbose:
            print(f'Cache eviction occurred: idx={idx:02x}(={idx:06b})')
            self.examineSet(idx)
            print('>> ', end='')
        
        if self.replacePolicy == 'fifo':
            self.mem[idx].pop(0)
            return 0
        elif self.replacePolicy == 'lru':
            pass
        elif self.replacePolicy == 'random':
            pass
        else:
            print(f'E: {self.replacePolicy} is not available')
            exit(1)
        return

    def getHitRatio(self):
        pass

    def getMissRatio(self):
        pass

    def examineSet(self, idx):
        cset = self.mem[idx]
        cnt = 0
        print(f'set(idx={idx:02x}): ', end='')
        for i, blk in enumerate(cset):
            if not blk.valid:
                continue
            print(f'[{i}] {blk.tag:x}, ', end='')
            cnt += 1
        print(f'(total {cnt} available blocks)')
            

totalAccess = 0
totalHit = 0
totalMiss = 0
hitRatio = 0.0

# nblocks=512, nways=8, nsets=64, index bit=6 bits
# tag=20-bit
# replacePolicy="fifo", "lru", "random"
#cache1 = CacheMem(totalSize=32*1024, blockSize=64, nways=8, replacePolicy='fifo')
cache1 = CacheMem(totalSize=arg_totalSize, blockSize=arg_blockSize, nways=arg_nways, replacePolicy=arg_replacePolicy)
#cache1.clear()
#exit(0)

for ast in localAST:
    # if not 'dispatch_region' in ast.name:
    #     continue
    printSepline(label=ast.name, llen=64)
    for k, v in ast.tbl.items():
        #print(f'[{k}] {v.addr:#8x}: {v.section}')
        cache1.lookup(v.addr)
    printSepline(llen=64)
    print(f'total access: {cache1.naccess}, hit: {cache1.nhit}, miss: {cache1.nmiss}, eviction: {cache1.nevict}')
    exit(0)

print()