import os.path
import argparse

srcDir  = '/home/euntae/tmp/compiled-tflite-models'
destDir = '/home/euntae/tmp/compiled-tflite-models/patched'

parser = argparse.ArgumentParser()
parser.add_argument('--model-name', '-m', default='', action='store')
parser.add_argument('--output', '-o', action='store')
args = parser.parse_args()

srcName = ''
if args.model_name == 'fc_triple_small':
    srcName = 'fc_triple_small_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'fc_triple_medium':
    srcName = 'fc_triple_medium_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'fc_triple_large':
    srcName = 'fc_triple_large_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'fc_triple_xl':
    srcName = 'fc_triple_xl_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'fc_triple_xxl':
    srcName = 'fc_triple_xxl_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'ecg_small':
    srcName = 'ecg_small_fp32_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'mobilenet' or args.model_name == 'mobilenet_v1':
    args.model_name = 'mobilenet_v1'
    srcName = 'mobilenet_v1_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'mobilenet_v2':
    srcName = 'mobilenetv2_iree-dist-20230218.434_llvm-cpu_flow'
elif args.model_name == 'mobilebert':
    srcName = 'mobilebert_iree-dist-20230218.434_llvm-cpu_flow'
else:
    print(f'E: The model "{args.model_name}" is not available')
    exit(1)

srcPath = f'{srcDir}/{srcName}.mlir'
destPath = f'{destDir}/{args.model_name}_flow.mlir'

print(f'srcPath : {srcPath}')
print(f'destPath: {destPath}\n')


instDRbegin = 'llvm.inline_asm ".word 0x0000000b", "" : () -> () // dr.begin'
instDRend   = 'llvm.inline_asm ".word 0x0000100b", "" : () -> () // dr.end'
intent = '        '

if os.path.isfile(srcPath):
    mlirFile = open(srcPath, 'r')
    mlirLines = mlirFile.readlines()
    mlirFile.close()
else:
    print(f'E: failed to open the file "{srcPath}"')
    exit(1)

lineCtr = 0
drCnt = 0
onDR = False
newLines = []

for lineCtr in range(len(mlirLines)):
    line = mlirLines[lineCtr]

    newLines.append(line)

    if onDR:
        if 'return' in mlirLines[lineCtr+1]:
            onDR = False
            print(f'{lineCtr+1:05}: {mlirLines[lineCtr+1]}', end='')
            newLines.append(f'{intent}{instDRend}\n')
        else:
            continue

    if 'func.func @main_dispatch_' in line:
        onDR = True
        drCnt += 1
        print(f'{lineCtr+1:05}: {line}', end='')
        newLines.append(f'{intent}{instDRbegin}\n')

print(f'--> total {drCnt} dispatch regions')
print()
with open(destPath, 'w') as file:
    file.writelines(newLines)
    print(f'{destPath} is successfully generated')