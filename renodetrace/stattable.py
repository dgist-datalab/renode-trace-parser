import os.path

DR_STAT_TABLE_NAME = 'dispatch_region'
NON_DR_STAT_TABLE_NAME = 'host'

OP_TYPE_STR = ( 'load', 'store', 'arith', 'custom' )
DATA_TYPE_STR = ( 'sint', 'uint', 'float', 'vector' )
OPERAND_SIZE = ( 8, 16, 32, 64, 128 )

# 딕셔너리로 접근할지 아님 idx를 배열 인덱스로 접근할지? -> 그냥 인덱스 번호로 인덱싱을 하기로 함 (하지만 별도로 다시 저장)
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
        #print(f'idx: {self.idx}, {self.name}, size: {self.size:08x}, vma: {self.vma:08x}, lma: {self.lma:08x}, fileOff: {self.fileOff:08x}, align: {self.align}')
        print(f'{self.idx:3d} {self.name:28s}  {self.size:08x}  {self.vma:08x}  {self.lma:08x}  {self.fileOff:08x}  {self.align}')

def loadSectionTable(filepath, secTbl):
    #fpath = HEADER_PATH + '/' + filename + '.dump'
    fpath = filepath
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
        secTbl.append(entry)
    headerFile.close()
    # if args.verbose:
    #     examineSectionTable(secTbl)
    print(f'Section Table has successfully constructed: total {len(secTbl)} items')

def examineSectionTable(secTbl):
    print('Sections:')
    print('Idx Name                           Size      VMA       LMA       File off  Algn')
    for entry in secTbl:
        entry.examine()

def getSectionName(secTbl, addr):
    for s in secTbl:
        if addr >= s.vma and addr < s.vma + s.size:
            return s.name
    return None

# SectionStatTableEntry -> StatTableEntry
class StatTableEntry:
    def __init__(self):
        #self.secName = ''
        self.loadInt = 0
        self.loadUint = 0
        self.loadFP = 0
        self.loadVec = 0
        self.storeInt = 0
        self.storeUint = 0
        self.storeFP = 0
        self.storeVec = 0

    def examine(self):
        #print(f'{self.secName:-30s}',end=' ')
        print(f'{self.loadInt:6d} {self.loadUint:6d} {self.loadFP:6d} {self.loadVec:6d}', end=' | ')
        print(f'{self.storeInt:6d} {self.storeUint:6d} {self.storeFP:6d} {self.storeVec:6d}')

    def isNonZero(self):
        if self.loadInt != 0 or self.loadUint != 0 or self.loadFP != 0 or self.loadVec != 0 or self.storeInt != 0 or self.storeUint != 0 or self.storeFP != 0 or self.storeVec != 0:
            return True
        return False

    def getTotalLoads(self):
        return self.loadInt + self.loadUint + self.loadFP + self.loadVec
    
    def getTotalStores(self):
        return self.storeInt + self.storeUint + self.storeFP + self.storeVec

class SectionStatTable:
    def __init__(self, secTbl):
        self.tbl = {}
        self.name = ''
        for s in secTbl:
            if s.vma == 0:
                continue
            self.tbl[s.name] = StatTableEntry()
            #self.tbl[s.name].secName = s.name

    # optype: load/store/arith/custom
    # dtype: sint/uint/float/vector
    def putWithSectionName(self, secName, optype, dtype, addr):
        name = secName
        if name is None:
            print('SectionStatTable.put: illegal address %08x' % addr)
            return
        #print('%08x: %s' % (addr, name))
        if optype == 0: # load
            if dtype == 0: # sint
                self.tbl[name].loadInt += 1
            elif dtype == 1: # uint
                self.tbl[name].loadUint += 1
            elif dtype == 2: # float
                self.tbl[name].loadFP += 1
            elif dtype == 3: # vector
                self.tbl[name].loadVec += 1
            else:
                print('SectionStatTable.put: %d is illegal data type' % dtype)
        elif optype == 1: # store
            if dtype == 0: # sint
                self.tbl[name].storeInt += 1
            elif dtype == 1: # uint
                self.tbl[name].storeUint += 1
            elif dtype == 2: # float
                self.tbl[name].storeFP += 1
            elif dtype == 3: # vector
                self.tbl[name].storeVec += 1
            else:
                print('SectionStatTable.put: %d is illegal data type' % dtype)
        else:
            print('SectionStatTable.put: %d is illegal operation type' % optype)
            return

    def put(self, secTbl, optype, dtype, addr):
        name = getSectionName(secTbl, addr)
        self.putWithSectionName(name, optype, dtype, addr)

    def examine(self, nonZero=False):
        print(f'{self.name}:')
        print('%-30s %-27s | %-27s' % (' ', 'load', 'store'))
        print('%-30s %-6s %-6s %-6s %-6s | %-6s %-6s %-6s %-6s' % ('section', 'int', 'uint', 'float', 'vector', 'int', 'uint', 'float', 'vector'))
        for k, v in self.tbl.items():
            if not nonZero or (nonZero and v.isNonZero()):
                print('%-30s' % k, end=' ')
                v.examine()

    def getTotalLoads(self):
        nloads = 0
        # tbl은 섹션마다 엔트리 존재
        for sec, entry in self.tbl.items():
            nloads += entry.getTotalLoads()
        return nloads

    def getTotalStores(self):
        nstores = 0
        for sec, entry in self.tbl.items():
            nstores += entry.getTotalStores()
        return nstores

# def initSectionStat(accTbl):
#     for s in sectionTable:
#         if s.vma == 0x00000000:
#             continue
#         accTbl[s.name] = 0

# def putSectionStat(accTbl, addr):
#     name = getSectionName(addr)
#     if name is None:
#         print('[putSectionStat] E: illegal address %08x' % addr)
#         return
#     #print('%08x: %s' % (addr, name))
#     accTbl[name] += 1

# def displaySectionStat(accTbl):
#     for k, v in accTbl.items():
#         print('%-30s %d' % (k, v))

class SymbolTableEntry:
    def __init__(self):
        self.num = 0
        self.value = 0
        self.size = 0
        self.type = ''
        self.bind = ''
        self.vis = ''
        self.ndx = ''
        self.name = ''
    
    def examine(self, abb=False, endl='\n'):
        if abb:
            print(f'{self.num:4d} {self.value:08x}  {self.size:5d}  {self.type:6}  {self.name:64}', end=endl)
        else:
            print(f'{self.num:4d} {self.value:08x}  {self.size:5d}  {self.type:6}  {self.bind:6}  {self.vis:7}  {self.ndx:3}  {self.name:64}', end=endl)

def loadSymbolTable(filepath, symTbl):
    #fpath = READELF_PATH + '/' + filename + '.dump'
    fpath = filepath
    print(f'Load from {fpath}...')
    if os.path.isfile(fpath):
        readelfFile = open(fpath, 'r', encoding='utf-8')
    else:
        print(f'E: file {fpath} does not exist')
        exit(1)

    # 데이터 이전의 행들은 읽어서 무시
    for line in readelfFile:
        if 'Num:' in line:
            break
    
    for line in readelfFile:
        tokens = line.split()
        entry = SymbolTableEntry()
        if not tokens[0][:-1].isnumeric():
            print('Warning: %s is not numeric' % tokens[0][:-1])
            continue
        entry.num = int(tokens[0][:-1])
        entry.value = int(tokens[1], 16)
        if '0x' in tokens[2]:
            entry.size = int(tokens[2], 16)
        else:
            entry.size = int(tokens[2])
        entry.type = tokens[3]
        entry.bind = tokens[4]
        entry.vis = tokens[5]
        entry.ndx = tokens[6]
        if len(tokens) < 8:
            entry.name = ''
        else:
            entry.name = tokens[7]
        symTbl.append(entry)

        # if entry.type == 'OBJECT':
        #     entry.examine()

    readelfFile.close()
    print(f'Symbol Table has successfully constructed: total {len(symTbl)} items')
        
# filter example: 'FUNC', 'OBJECT', 'FILE', 'NOTYPE', 'SECTION'
#    Num:    Value  Size Type    Bind   Vis      Ndx Name

def displaySymbolTableColumns(abb=False, endl='\n'):
    if abb:
        print('Num: Value     Size  Type    Name', end=endl)
        # print(f'{self.num:4d} {self.value:08x}  {self.size:4d}  {self.type:6}  {self.name:64}', end=endl)
    else:
        print('Num: Value     Size  Type    Bind    Vis      Ndx  Name', end=endl)
        #print(f'{self.num:4d} {self.value:08x}  {self.size:4d}  {self.type:6}  {self.bind:6}  {self.vis:7}  {self.ndx:3}  {self.name:64}', end=endl)

def examineSymbolTable(symTbl, filter=None):
    entryCnt = 0
    displaySymbolTableColumns()
    for e in symTbl:
        if filter is not None:
            if e.type == filter:
                e.examine()
                entryCnt += 1
        else:
            e.examine()
            entryCnt += 1
    print(f'>> Total {entryCnt} items\n')

class ObjectTableEntry:
    def __init__(self):
        self.num = 0
        self.value = 0
        self.size = 0
        self.name = ''
        self.section = ''

    def examine(self, endl='\n'):
        print(f'{self.num:4d} {self.value:08x}  {self.size:5d}  {self.name:64}  {self.section}', end=endl)

def loadObjectTable(secTbl, symTbl, objTbl):
    #entryCnt = 0
    for e in symTbl:
        if e.type == 'OBJECT':
            entry = ObjectTableEntry()
            entry.num = e.num
            entry.value = e.value
            entry.size = e.size
            entry.name = e.name
            entry.section = getSectionName(secTbl, e.value)
            if entry.section is None:
                print(f'E: symbol {entry.name} does not have a section name')
            objTbl.append(entry)
            #entry.examine()
            #entryCnt += 1
    print(f'ObjectTable has successfully constructed: total {len(objTbl)} items')

def examineObjectTable(objTbl):
    print('Num: Value      Size  Name' + (' ' * 62) + 'Section')
    for e in objTbl:
        e.examine()
    
def getObjectName(objTbl, addr):
    for e in objTbl:
        if addr >= e.value and addr < e.value + e.size:
            return e.name # 섹션 이름이랑 튜플로 묶어서 반환하는 방법도 있을 듯
    return None

def getObjectAndSectionName(objTbl, addr):
    for e in objTbl:
        if addr >= e.value and addr < e.value + e.size:
            return ( e.name, e.section )
    return None

class ObjectStatTable:
    def __init__(self, objTbl):
        self.tbl = {}
        self.name = ''
        for e in objTbl:
            self.tbl[e.name] = StatTableEntry()

    def put(self, objTbl, optype, dtype, addr):
        name = getObjectName(objTbl, addr)
        if name is None:
            # if args.verbose:
            #     print('ObjectStatTable.put: %08x not found in ObjectTable (section: %s)' % (addr, getSectionName(sectionTable, addr)))
            return
        if optype == 0: # load
            if dtype == 0: # int
                self.tbl[name].loadInt += 1
            elif dtype == 1: # uint
                self.tbl[name].loadUint += 1
            elif dtype == 2: # float
                self.tbl[name].loadFP += 1
            elif dtype == 3: # vector
                self.tbl[name].loadVec += 1
            else:
                print('ObjectStatTable.put: %d is illegal data type' % dtype)
        elif optype == 1: # store
            if dtype == 0: # int
                self.tbl[name].storeInt += 1
            elif dtype == 1: # uint
                self.tbl[name].storeUint += 1
            elif dtype == 2: # float
                self.tbl[name].storeFP += 1
            elif dtype == 3: # vector
                self.tbl[name].storeVec += 1
            else:
                print('ObjectStatTable.put: %d is illegal data type' % dtype)
        else:
            print('ObjectStatTable.put: %d is illegal operation type' % optype)
            return

    def examine(self, nonZero=False):
        print(f'{self.name}:')
        print('%-58s %-27s | %-27s' % (' ', 'load', 'store'))
        print('%-58s %-6s %-6s %-6s %-6s | %-6s %-6s %-6s %-6s' % ('object', 'int', 'uint', 'float', 'vector', 'int', 'uint', 'float', 'vector'))
        for k, v in self.tbl.items():
            if not nonZero or (nonZero and v.isNonZero()): # non-zero인 원소만 출력한다
                print('%-58s' % k, end=' ')
                v.examine()

class FunctionStatTableEntry:
    def __init__(self):
        #self.name = ''
        self.addr = 0
        self.count = 0
    
class FunctionStatTable:
    def __init__(self):
        self.tbl = {}
        self.name = ''
        self.seq = []

    def examine(self):
        print(f'{self.name}:')
        for k, v in self.tbl.items():
            print(f'{k}: {v.count}')
        print()

    def examineSequence(self, filter=None):
        print(f'{self.name}:')
        for fn in self.seq:
            if filter is None:
                print(fn)
            elif filter in fn:
                print(fn)
        print(f'--> Total {len(self.seq)} functions are called')

def loadFunctionTrace(filepath):
    #fpath = FUNC_TRACE_PATH + '/' + filename + '.log'
    fpath = filepath
    print(f'Load from {fpath}...')
    if os.path.isfile(fpath):
        funcTraceFile = open(fpath, 'r', encoding='utf-8')
    else:
        print(f'E: file {fpath} does not exist')
        exit(1)

    curRegion = 0
    curHostRegion = 0
    curDispatchRegion = -1
    onDispatchRegion = False
    stName = ''

    globalFST = FunctionStatTable() # global FunctionStatTable
    globalFST.name = 'global'
    localFST = []  # local FunctionStatTable
    localFST.append(FunctionStatTable())
    localFST[0].name = NON_DR_STAT_TABLE_NAME + '#0'

    scnt = 0 # short
    lcnt = 0 # long
    ecnt = 0 # entry

    for line in funcTraceFile:
        if 'function' in line:
            tokens = line.split()
            if len(tokens) > 8:
                #print(tokens)
                if 'entry' in tokens[6]: # 함수의 entry인 경우에만 필터링
                    name = tokens[5]
                    addr = tokens[8]

                    globalFST.seq.append(name)
                    localFST[curRegion].seq.append(name)

                    if name in globalFST.tbl:
                        globalFST.tbl[name].count += 1
                    else:
                        globalFST.tbl[name] = FunctionStatTableEntry()
                        globalFST.tbl[name].addr = addr
                        globalFST.tbl[name].count = 1

                    if name in localFST[curRegion].tbl:
                        localFST[curRegion].tbl[name].count += 1
                    else: # 현재 region에 대한 StatTable은 형성되어 있지만, 테이블에 해당 함수명이 없는 경우
                        localFST[curRegion].tbl[name] = FunctionStatTableEntry()
                        localFST[curRegion].tbl[name].addr = addr
                        localFST[curRegion].tbl[name].count = 1

                    # if args.verbose:
                    #     print(f'{name} at {addr} {tokens[6]}')
                    ecnt += 1
                lcnt += 1
            else: # 함수 내부에서의 분기문 포함
                #print(tokens)
                # print(f'> {tokens[5]} at {tokens[7]}')
                scnt += 1
        if 'dr.begin' in line:
            #curRegion += 1
            curDispatchRegion += 1
            onDispatchRegion = True
            stName = DR_STAT_TABLE_NAME + ('#%d' % curDispatchRegion)
        if 'dr.end' in line:
            #curRegion += 1
            curHostRegion += 1
            onDispatchRegion = False
            stName = NON_DR_STAT_TABLE_NAME + ('#%d' % curHostRegion)
        if ('dr.begin' in line) or ('dr.end' in line):
            curRegion += 1
            stEntry = FunctionStatTable()
            stEntry.name = stName
            # stEntry.tbl[name] = FunctionStatTableEntry()
            # stEntry.tbl[name].addr = addr
            # stEntry.tbl[name].count = 1
            localFST.append(stEntry)
            print(f'>> {stName} begin (curRegion={curRegion})')
    print(f'scnt: {scnt}, lcnt: {lcnt}, total: {scnt + lcnt}')
    print(f'entry: {ecnt}')
    funcTraceFile.close()
    
    print('[Global FunctionStatTable]')
    globalFST.examine()
    print()
    print('[Local FunctionStatTable]')
    for fst in localFST:
        fst.examine()
    print()
    print('[Global function call sequence] (filtered by main_dispatch_)')
    globalFST.examineSequence('main_dispatch_')
    print()
    print('[Local function call sequence] (filtered by main_dispatch_)')
    for fst in localFST:
        fst.examineSequence('main_dispatch_')
    print()
    print()
    print('[Global function call sequence]')
    globalFST.examineSequence()
    print()
    print('[Local function call sequence]')
    for fst in localFST:
        fst.examineSequence()

class AccessSequenceTableEntry:
    def __init__(self):
        #self.instCtr = 0 # 이걸 인덱스로 쓰는건 어떨까?
        self.addr = 0
        self.opType = 0
        self.dataType = 0
        self.operandSize = 0
        self.section = ''
        self.object = ''
    def examine(self):
        #print(f'{self.instCtr:8} {self.addr:8x} {OP_TYPE_STR[self.opType]} {DATA_TYPE_STR[self.dataType]} {OPERAND_SIZE[self.operandSize]} {self.section} {self.object}')
        if self.object is None:
            self.object = ''
        print(f'{self.addr:8x} {OP_TYPE_STR[self.opType]:6} {DATA_TYPE_STR[self.dataType]:6} {OPERAND_SIZE[self.operandSize]:2} {self.section:6}  {self.object}')

class AccessSequenceTable:
    def __init__(self):
        self.tbl = {}
        self.name = ''

    def put(self, secTbl, objTbl, instCtr, addr, opType, dataType, operandSize):
        entry = AccessSequenceTableEntry()
        entry.addr = addr
        entry.opType = opType
        entry.dataType = dataType
        entry.operandSize = operandSize
        entry.object = getObjectName(objTbl, addr)
        entry.section = getSectionName(secTbl, addr)
        self.tbl[instCtr] = entry

    def examine(self):
        print(f'{self.name} (total {len(self.tbl)} accesses):')
        for k, v in self.tbl.items():
            print(f'{k:8}', end=' ')
            v.examine()

