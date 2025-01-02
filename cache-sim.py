import sys
import os.path
import pickle
import argparse
import time
import math
import random

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

parser.add_argument('--env', action='store', default='desktop', help='Execution environment (default: desktop)')
parser.add_argument('--display-config-only', action='store_true')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--use-ast', action='store_true')
parser.add_argument('--human-readable', action='store_true', help='Read from human-readable trace')

parser.add_argument('--model-name', '-m', action='store', default=modelName, help=f'Specify the target model name (default={modelName})')
parser.add_argument('--batch-size', action='store', type=int, default=batchSize, help=f'Specify the batch size (default={batchSize})')
parser.add_argument('--part', action='store', type=int, help='Number of partitioned trace (for large trace)')

parser.add_argument('--cache-size', '-s', action='store', default='32k', help='Specify the entire cache size e.g., 32k, 8M (default=32k)')
parser.add_argument('--cache-block-size', '-b', action='store', type=int, default=64, help='Specify the byte size of a cache block (default=64)')
parser.add_argument('--nways', '-w', action='store', type=int, default=8, help='Specify the number of ways (default=8)')
parser.add_argument('--replace-policy', '-p', action='store', default='fifo', help='Specify the cache replacement policy (available options: fifo, lru, random; default=fifo)')
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

# trace log 파일 경로 결정
logFilePath, headerFilePath, readelfFilePath = rt.getFilePath(args)
astFilePath = rt.getASTFilePath(args)

## Display configuration ============================================
printSepline('Configuration summary')
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

rt.stattable.loadSectionTable(headerFilePath, sectionTable)
rt.stattable.loadSymbolTable(readelfFilePath, symbolTable)
rt.stattable.loadObjectTable(sectionTable, symbolTable, objectTable)
# rt.stattable.examineSectionTable(sectionTable)
# rt.stattable.examineSymbolTable(symbolTable)
# rt.stattable.examineObjectTable(objectTable)

astDumpFile = None
logFile = None

if args.ast_input is not None: # AST mode
    if os.path.isfile(astDumpFilePath):
        print(f'Open AST dump file {astDumpFilePath}...')
        astDumpFile = open(astDumpFilePath, 'rb')
    else:
        print(f'E: {astDumpFilePath} does not exist')
        exit(1)
    localAST = pickle.load(astDumpFile)
    print(f'>> total {len(localAST)} regions')
    print(f'>> file {astDumpFilePath} is closed')
    astDumpFile.close()

else: # instruction trace file mode
    if os.path.isfile(logFilePath):
        print(f'Open instruction trace file {logFilePath}...')
        logFile = open(logFilePath, 'rb')

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
    def __init__(self, totalSize=32*1024, blockSize=64, nways=8, replacePolicy='fifo', targetSection=None):      
        self.naccess = 0
        self.nhit = 0
        self.nmiss = 0
        self.nevict = 0

        self.localSST = []

        self.totalSize = totalSize
        self.blockSize = blockSize
        self.nways = nways
        self.replacePolicy = replacePolicy

        self.nblocks = int(self.totalSize / self.blockSize)   # 캐시 블록 개수 계산
        self.nsets = int(self.nblocks / self.nways)           # 세트 개수 계산
        
        self.blkBits = int(math.log(self.blockSize, 2))
        self.idxBits = int(math.log(self.nsets, 2))
        self.tagBits = 32 - self.idxBits - self.blkBits
        self.idxMask = ((1 << self.idxBits) - 1) << self.blkBits
        self.tagMask = ((1 << self.tagBits) - 1) << (self.blkBits + self.idxBits)
        if args.verbose:
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
        if args.verbose:
            print(f'--> Cache memory has successfully constructed: total {rows}x{cols} cache blocks')
    
    def resetAccessStat(self):
        self.naccess = 0
        self.nhit = 0
        self.nmiss = 0
        self.nevict = 0

    def reset(self): # or reset, flush?
        self.resetAccessStat()
        entryCnt = 0
        for s in self.mem: # set
            for blk in s:
                blk.clear()
                entryCnt += 1
        if args.verbose:
            print(f'CacheMem.clear: total {entryCnt} cache blocks cleared')

    def refCountup(self, idx, tag):
        # idx에 대응되는 현재 set의 캐시 블록들 탐색
        for blk in self.mem[idx]:
            if blk.valid:
                if blk.tag == tag: # 참조된 블록은 카운터를 0으로 리셋
                    blk.count = 0
                else: # 그외 valid한 블록은 카운터를 1씩 증가
                    blk.count += 1

        
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
                if self.replacePolicy == 'lru':
                    self.refCountup(idx, tag)
                return True
        
        # cache miss
        self.nmiss += 1
        if args.verbose:
            print(f'>> miss', end='')
            print()
        self.fetch(idx, tag)

        if self.replacePolicy == 'lru':
            self.refCountup(idx, tag) # 참조된 블록은 0으로 리셋, 나머지 valid 블록들은 +1
        return False

    # 캐시 미스 시 호출
    def fetch(self, idx, tag):
        evictFlag = True
        # 현재 인덱스의 set에 가용 캐시 블럭이 존재하는지 검사
        for blk in self.mem[idx]:
            if not blk.valid: # 가용 블럭 존재 시 insert
                if args.verbose:
                    self.examineSet(idx)
                blk.valid = True
                blk.tag = tag
                evictFlag = False
                if args.verbose:
                    print('>> ', end='')
                    self.examineSet(idx)
                break
        
        # 가용 블럭 부재 시 evict 후에 insert 수행
        if evictFlag:
            replaceIdx = self.evict(idx) # 교체할 블록의 인덱스 결정
            # if args.verbose:
            #     print(f'replaceIdx: {replaceIdx}')

            if self.replacePolicy == 'fifo':
                blk = CacheLine()
                blk.valid = True
                blk.tag = tag
                self.mem[idx].append(blk)    
            elif self.replacePolicy == 'lru':
                (self.mem[idx])[replaceIdx].tag = tag
            elif self.replacePolicy == 'random':
                #print(f'type of self.mem[idx]: {type(self.mem[idx])}')
                (self.mem[idx])[replaceIdx].tag = tag
            else:
                print(f'E: {self.replacePolicy} is not available')
                exit(1)
            
            if args.verbose:
                self.examineSet(idx)

    # idx가 가리키는 set에서 replace policy에 따라 evict할 블록을 결정
    # evict된 위치의 캐시 블록을 반환한다
    def evict(self, idx):
        self.nevict += 1
        if args.verbose:
            print(f'Cache eviction occurred: idx={idx:02x}(={idx:06b})')
            self.examineSet(idx)
            if args.verbose:
                print('>> ', end='')
        
        if self.replacePolicy == 'fifo':
            self.mem[idx].pop(0)
            return self.nways - 1
            #return 0
        elif self.replacePolicy == 'lru':
            lruIdx = 0
            maxCount = (self.mem[idx])[0].count
            # sprint('counts: ', end='')
            for i, blk in enumerate(self.mem[idx]):
                # 모든 블록이 valid인 상태이므로 valid bit를 검사할 필요는 없다
                # print(f'{blk.count} ', end='')
                if maxCount < blk.count:
                    lruIdx = i
                    maxCount = blk.count
            # print()
            return lruIdx
        elif self.replacePolicy == 'random':
            return random.randint(0, self.nways - 1)
        else:
            print(f'E: {self.replacePolicy} is not available')
            exit(1)
        return

    def examineSet(self, idx):
        cset = self.mem[idx]
        cnt = 0
        if args.verbose:
            print(f'set(idx={idx:02x}): ', end='')
        for i, blk in enumerate(cset):
            if not blk.valid:
                continue
            if args.verbose:
                print(f'[{i}] {blk.tag:x}, ', end='')
            cnt += 1
        if args.verbose:
            print(f'(total {cnt} available blocks)')

    def examineCacheInfo(self):
        print(f'Cache configuration: total size={self.totalSize} bytes, block size={self.blockSize} bytes, #blocks={self.nblocks}, #ways={self.nways}, #sets={self.nsets}, replace policy={self.replacePolicy}')
    
    def examineAccessInfo(self):
        print(f'total access: {self.naccess}, hit: {self.nhit}, miss: {self.nmiss}, eviction: {self.nevict} --> hit ratio: {(self.nhit / self.naccess):.4f}, miss ratio: {(self.nmiss / self.naccess):.4f}')

    def getTotalLoads(self):
        nloads = 0
        for sst in self.localSST:
            nloads += sst.getTotalLoads()
        return nloads

    def getTotalStores(self):
        nstores = 0
        for sst in self.localSST:
            nstores += sst.getTotalStores()
        return nstores
            
def examineCachesAccessInfo(**caches):
    naccess = 0
    nhit = 0
    nmiss = 0
    nevict = 0
    for name, cache in caches.items():
        naccess += cache.naccess
        nhit += cache.nhit
        nmiss += cache.nmiss
        nevict += cache.nevict
        hitratio = 0
        missratio = 0
        if cache.naccess != 0:
            hitratio = cache.nhit / cache.naccess
            missratio = cache.nmiss / cache.naccess
        print(f'[{name}] total access: {cache.naccess}, hit: {cache.nhit}, miss: {cache.nmiss}, eviction: {cache.nevict} --> hit ratio: {hitratio:.4f}, miss ratio: {missratio:.4f})')
        
        nloads = cache.getTotalLoads()
        nstores = cache.getTotalStores()
        print(f'    >> loads: {nloads}, stores: {nstores}, total: {nloads + nstores}')
    
    hitratio = 0
    missratio = 0
    if naccess != 0:
        hitratio = nhit / naccess
        missratio = nmiss / naccess
    print(f'--> total access: {naccess}, hit: {nhit}, miss: {nmiss}, eviction: {nevict} --> hit ratio: {(nhit / naccess):.4f}, miss ratio: {(nmiss / naccess):.4f}')

def singleCacheTest(localAST, total_size, block_size, n_ways, replace_policy):
    cache = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    cache.examineCacheInfo()
    for ast in localAST:
        # if not 'dispatch_region' in ast.name:
        #     continue
        if args.verbose:
            printSepline(label=ast.name)
        for k, v in ast.tbl.items():
            cache.lookup(v.addr)
        if args.verbose:
            cache.examineAccessInfo()
    cache.examineAccessInfo()

def perSectionCacheTest(localAST, total_size, block_size, n_ways, replace_policy):
    heapCache  = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    stackCache = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    #dataCache  = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    #dataCache  = CacheMem(totalSize=256 * 1024, blockSize=4096, nways=64, replacePolicy=replace_policy)
    
    dTotalSize = 128 * 1024
    dBlockSize = block_size
    dNways     = int(dTotalSize / dBlockSize)
    dataCache  = CacheMem(totalSize=dTotalSize, blockSize=dBlockSize, nways=dNways, replacePolicy=replace_policy)

    heapLowerAddress = 0
    heapUpperAddress = 0
    stackLowerAddress = 0
    stackUpperAddress = 0

    lowerAddress = { '.data': 0, '.rodata': 0, '.sdata': 0, '.bss': 0, '.stack': 0, '.heap': 0 }
    upperAddress = { '.data': 0, '.rodata': 0, '.sdata': 0, '.bss': 0, '.stack': 0, '.heap': 0 }
    
    print('[heap]', end=' ')
    heapCache.examineCacheInfo()
    print('[stack]', end=' ')
    stackCache.examineCacheInfo()
    print('[data]', end=' ')
    dataCache.examineCacheInfo()

    for ast in localAST:
        if args.verbose:
            printSepline(label=ast.name)

        hSST = rt.stattable.SectionStatTable(sectionTable)
        hSST.name = ast.name
        sSST = rt.stattable.SectionStatTable(sectionTable)
        sSST.name = ast.name
        dSST = rt.stattable.SectionStatTable(sectionTable)
        dSST.name = ast.name

        for k, v in ast.tbl.items():
            for sec, addr in lowerAddress.items():
                # print(f'v.section: {v.section}, sec: {sec}, addr: {addr:8x}, v.addr: {v.addr:8x}')
                if v.section == sec:
                    #print(f'v.section: {v.section}, sec: {sec}, addr: {addr:8x}, v.addr: {v.addr:8x}')
                    if addr == 0 or addr > v.addr:
                        lowerAddress[sec] = v.addr
            for sec, addr in upperAddress.items():
                if v.section == sec:
                    if addr < v.addr:
                        upperAddress[sec] = v.addr

            if v.section == '.heap':
                hSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                heapCache.lookup(v.addr)
            elif v.section == '.stack':
                sSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                stackCache.lookup(v.addr)
            else:
                dSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                onHit = dataCache.lookup(v.addr)
                if v.section == '.rodata' and not onHit:
                    print(f'instCtr={k}, addr={v.addr:#8x}({v.object})')
                    
        heapCache.localSST.append(hSST)
        stackCache.localSST.append(sSST)
        dataCache.localSST.append(dSST)

        # if args.verbose:
        print(f'## {ast.name} ##')
        examineCachesAccessInfo(heap=heapCache, stack=stackCache, data=dataCache)
        for sec, addr in lowerAddress.items():
            lower = lowerAddress[sec]
            upper = upperAddress[sec]
            byteDiff = upper - lower
            # 접근되지 않은 섹션은 출력 생략
            if byteDiff == 0 and (lower == 0 or upper == 0):
                continue
            print(f'{sec:6}: {lower:#08x}-{upper:#08x} ({byteDiff + 1} bytes = {(byteDiff + 1) / 1024} KB)')

        for sec, addr in lowerAddress.items():
            lowerAddress[sec] = 0
            upperAddress[sec] = 0
    examineCachesAccessInfo(heap=heapCache, stack=stackCache, data=dataCache)

def perSectionCacheTestWithFile(logFile, total_size, block_size, n_ways, replace_policy):
    heapCache  = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    stackCache = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    #dataCache  = CacheMem(totalSize=total_size, blockSize=block_size, nways=n_ways, replacePolicy=replace_policy)
    #dataCache  = CacheMem(totalSize=256 * 1024, blockSize=4096, nways=64, replacePolicy=replace_policy)
    
    dTotalSize = 128 * 1024
    dBlockSize = block_size
    dNways     = int(dTotalSize / dBlockSize)
    dataCache  = CacheMem(totalSize=dTotalSize, blockSize=dBlockSize, nways=dNways, replacePolicy=replace_policy)

    heapLowerAddress = 0
    heapUpperAddress = 0
    stackLowerAddress = 0
    stackUpperAddress = 0

    lowerAddress = { '.data': 0, '.rodata': 0, '.sdata': 0, '.bss': 0, '.stack': 0, '.heap': 0 }
    upperAddress = { '.data': 0, '.rodata': 0, '.sdata': 0, '.bss': 0, '.stack': 0, '.heap': 0 }
    
    print('[heap]', end=' ')
    heapCache.examineCacheInfo()
    print('[stack]', end=' ')
    stackCache.examineCacheInfo()
    print('[data]', end=' ')
    dataCache.examineCacheInfo()

    for ast in localAST:
        if args.verbose:
            printSepline(label=ast.name)

        hSST = rt.stattable.SectionStatTable(sectionTable)
        hSST.name = ast.name
        sSST = rt.stattable.SectionStatTable(sectionTable)
        sSST.name = ast.name
        dSST = rt.stattable.SectionStatTable(sectionTable)
        dSST.name = ast.name

        for k, v in ast.tbl.items():
            for sec, addr in lowerAddress.items():
                # print(f'v.section: {v.section}, sec: {sec}, addr: {addr:8x}, v.addr: {v.addr:8x}')
                if v.section == sec:
                    #print(f'v.section: {v.section}, sec: {sec}, addr: {addr:8x}, v.addr: {v.addr:8x}')
                    if addr == 0 or addr > v.addr:
                        lowerAddress[sec] = v.addr
            for sec, addr in upperAddress.items():
                if v.section == sec:
                    if addr < v.addr:
                        upperAddress[sec] = v.addr

            if v.section == '.heap':
                hSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                heapCache.lookup(v.addr)
            elif v.section == '.stack':
                sSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                stackCache.lookup(v.addr)
            else:
                dSST.putWithSectionName(v.section, v.opType, v.dataType, v.addr)
                onHit = dataCache.lookup(v.addr)
                if v.section == '.rodata' and not onHit:
                    print(f'instCtr={k}, addr={v.addr:#8x}({v.object})')
                    
        heapCache.localSST.append(hSST)
        stackCache.localSST.append(sSST)
        dataCache.localSST.append(dSST)

        # if args.verbose:
        print(f'## {ast.name} ##')
        examineCachesAccessInfo(heap=heapCache, stack=stackCache, data=dataCache)
        for sec, addr in lowerAddress.items():
            lower = lowerAddress[sec]
            upper = upperAddress[sec]
            byteDiff = upper - lower
            # 접근되지 않은 섹션은 출력 생략
            if byteDiff == 0 and (lower == 0 or upper == 0):
                continue
            print(f'{sec:6}: {lower:#08x}-{upper:#08x} ({byteDiff + 1} bytes = {(byteDiff + 1) / 1024} KB)')

        for sec, addr in lowerAddress.items():
            lowerAddress[sec] = 0
            upperAddress[sec] = 0
    examineCachesAccessInfo(heap=heapCache, stack=stackCache, data=dataCache)


## Cache simulation =================================================
# cacheTest = CacheMem(totalSize=arg_totalSize, blockSize=arg_blockSize, nways=arg_nways, replacePolicy=arg_replacePolicy)
# printSepline(label='Functional test')
# for ast in localAST:
#     printSepline(label=ast.name)
#     lookupCnt = 0
#     for k, v in ast.tbl.items():
#         cacheTest.lookup(v.addr)
#         lookupCnt += 1
#         if lookupCnt > 30:
#             break
#     cacheTest.examineAccessInfo()
#     printSepline()
# exit(0)

#cache1 = CacheMem(totalSize=arg_totalSize, blockSize=arg_blockSize, nways=arg_nways, replacePolicy=arg_replacePolicy)
# printSepline(label='Single cache, per region test')
# for ast in localAST:
#     printSepline(label=ast.name)
#     cache1.reset()
#     #cache1.resetAccessStat()
#     for k, v in ast.tbl.items():
#         #print(f'[{k}] {v.addr:#8x}: {v.section}')
#         cache1.lookup(v.addr)
#     cache1.examineAccessInfo()
#     #printSepline()
# printSepline()
# print()

# 512B-2MB
totalSizeSet = ( 512, 1024, 2 * 1024, 4 * 1024, 8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024, 128 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024, 2 * 1024 * 1024 )
nwaysSet     = ( 1, 2, 4, 8, 16, 32, 64, 128, 256 )
policySet    = ( 'fifo', 'lru', 'random' )
blockSize = arg_blockSize

printSepline(label='Per-section cache, entire region test (single test)')
perSectionCacheTest(localAST, arg_totalSize, blockSize, arg_nways, arg_replacePolicy)
exit(0)

printSepline(label='Single cache, entire region test (extremely small case)')
for policy in policySet:
    singleCacheTest(localAST, 64,  blockSize, 1, policy)
    singleCacheTest(localAST, 128, blockSize, 1, policy)
    singleCacheTest(localAST, 128, blockSize, 2, policy)
    singleCacheTest(localAST, 256, blockSize, 1, policy)
    singleCacheTest(localAST, 256, blockSize, 2, policy)
    singleCacheTest(localAST, 256, blockSize, 4, policy)
printSepline()
print()

printSepline(label='Per-section cache, entire region test (extremely small case)')
for policy in policySet:
    perSectionCacheTest(localAST, 64,  blockSize, 1, policy)
    perSectionCacheTest(localAST, 128, blockSize, 1, policy)
    perSectionCacheTest(localAST, 128, blockSize, 2, policy)
    perSectionCacheTest(localAST, 256, blockSize, 1, policy)
    perSectionCacheTest(localAST, 256, blockSize, 2, policy)
    perSectionCacheTest(localAST, 256, blockSize, 4, policy)
printSepline()
print()

exit(0)

printSepline(label='Single cache, entire region test')
for policy in policySet:
    for nways in nwaysSet:
        for totalSize in totalSizeSet:
            nblocks = int(totalSize / blockSize)
            nsets = int(nblocks / nways)
            if nsets < 1: # 불가능한 조합은 건너뛴다 (예: 128bytes, 8-way)
                continue
            singleCacheTest(localAST, totalSize, blockSize, nways, policy)
printSepline()
print()

printSepline(label='Per section cache, entire region test')
for policy in policySet:
    for nways in nwaysSet:
        for totalSize in totalSizeSet:
            nblocks = int(totalSize / blockSize)
            nsets = int(nblocks / nways)
            if nsets < 1:
                continue
            perSectionCacheTest(localAST, totalSize, blockSize, nways, policy)
printSepline()

# printSepline(label='Per section cache, per region test')
# for ast in localAST:
#     printSepline(label=ast.name)
#     heapCache.reset()
#     stackCache.reset()
#     dataCache.reset()
#     for k, v in ast.tbl.items():
#         if v.section == '.heap':
#             heapCache.lookup(v.addr)
#         elif v.section == '.stack':
#             stackCache.lookup(v.addr)
#         else:
#             dataCache.lookup(v.addr)
#     examineCachesAccessInfo(heap=heapCache, stack=stackCache, data=dataCache)
# printSepline()
# print()

# heapCache.reset()   # cache for .heap
# stackCache.reset()  # cache for .stack
# dataCache.reset()   # cache for .rodata, .sdata, .data, ...