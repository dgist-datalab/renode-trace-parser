list1 = [ i for i in range(101) ]
sampledList1 = []

sampleInterval = 2
sampleCnt = 0
for i in list1:
    if sampleCnt == 0:
        sampledList1.append(i)
        sampleCnt = sampleInterval
    
    if sampleInterval > 1: # args.sample is not None
        sampleCnt -= 1
    
print(sampledList1)