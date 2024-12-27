#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>

#include "DLTrace.h"

#define BUF_SIZE 256
#define STR_SIZE 256
// https://mousepotato.tistory.com/61

void printTrace(uint64_t instCtr, int opType, int dataType, int operandSize, uint32_t addr, int opclass) {
    if (opclass == -1) {
        printf("[%lu] opType=%d dataType=%d operandSize=%d addr=%#x\n",
            instCtr, opType, dataType, operandSize, addr);
    } else {
        if (opType == 3) { // custom
            uint8_t opc = opclass & 0b11;
            uint8_t funct3 = (opclass >> 2) & 0b111;
            printf("[%lu] opType=%d dataType=%d operandSize=%d addr=%#x opc=%d funct3=%d\n",
                instCtr, opType, dataType, operandSize, addr, opc, funct3);
        } else {
            printf("[%lu] opType=%d dataType=%d operandSize=%d addr=%#x opclass=%02x\n",
                instCtr, opType, dataType, operandSize, addr, opclass);
        }
    }
}

int main(int argc, char **argv) {
    int optChr;
    extern char *optarg;
    extern int optind;

    bool verbose = false;
	int part = -1;
    uint64_t ntraces = 0;
    long skipBytes = 0;

    const char *ELF_DUMP_BASE = "/home/euntae/renode/springbok-elfs/dumps";
    const char *GLOBAL_LOG_PATH = "/home/euntae/renode-trace/instruction";

    char modelName[STR_SIZE];

    char *logFileName = NULL;
    char *memConfig = "default";

    char logFilePath[STR_SIZE];
    char headerFilePath[STR_SIZE];
    char readelfFilePath[STR_SIZE];
    char astFileName[STR_SIZE];

    FILE *logFile     = NULL;
    FILE *headerFile  = NULL;
    FILE *readelfFile = NULL;

    clock_t startTime, endTime;

    if (argc < 2) {
        // m: model name
        // v: verbose
        // n: #of traces to process
        // s: skip bytes (start file pointer)
		// p: part of trace (start from 0)
        //printf("Usage: %s -m <model_name> [-a <ast-output>] [-v] [-s <skip-bytes>]\n", argv[0]);
        printf("Usage: %s -m <model_name> [-v] [-n] [-s <skip-bytes>] [-p <part_number>]\n", argv[0]);
        return 0;
    }

    while ((optChr = getopt(argc, argv, "m:a:n:s:p:v")) != -1) {
        switch (optChr) {
        case 'm':
            //printf("-m %s\n", optarg);
            strcpy(modelName, optarg);
            break;
        case 'a':
            //printf("-a %s\n", optarg);
            strcpy(astFileName, optarg);
            break;
        case 'n':
            ntraces = atol(optarg);
            break;
        case 's':
            skipBytes = atol(optarg);
            break;
		case 'p':
			part = atoi(optarg);
			break;
        case 'v':
            verbose = true;
            break;
        }
    }

    if (strcmp(modelName, "fc_triple_small") == 0) {
        logFileName = "fc_triple_small_20241208_220506";
    }
    else if (strcmp(modelName, "fc_triple_medium") == 0) {
        logFileName = "fc_triple_medium_20241208_220321";
    }
    else if (strcmp(modelName, "fc_triple_large") == 0) {
        logFileName = "fc_triple_large_20241208_223442";
        memConfig = "config1";
    }
    else if (strcmp(modelName, "fc_triple_xl") == 0) {
        logFileName = "fc_triple_xl_20241218_155509";
        memConfig = "config1";
    }
    else if (strcmp(modelName, "fc_triple_xxl") == 0) {
        logFileName = "fc_triple_xxl_20241218_155656";
        memConfig = "config1";
    }
    else if (strcmp(modelName, "ecg_small") == 0) {
        logFileName = "ecg_small_20241208_203107";
    }
    else if (strcmp(modelName, "mobilenet_v1") == 0) {
        logFileName = "mobilenet_v1_20241208_220017";
    }
    else if (strcmp(modelName, "mobilebert") == 0) {
		if (part != -1) {
			switch (part) {
			case 0: // DR#0-653
				logFileName = "mobilebert_0_653";
				break;
			case 1: // DR#654-1211
				logFileName = "mobilebert_654_1211";
				break;
			case 2: // DR#1212-1769
				logFileName = "mobilebert_1212_1769";
				break;
            case 3: // DR#1770-2327
                logFileName = "mobilebert_1770_2327";
                break;
            case 100: // DR#12372-12929
                logFileName = "mobilebert_12372_12929";
                break;
            case 101: // DR#12930-13491
                logFileName = "mobilebert_12930_13491";
                break;
			default:
				fprintf(stderr, "E: part#%d is not available\n", part);
				return -1;
			}
		}
		else {
	        logFileName = "mobilebert_20241118_160735";
		}
        memConfig = "config1";
    }
    else {
        fprintf(stderr, "%s is not available\n", modelName);
        return -1;
    }

    sprintf(logFilePath, "%s/%s.bin", GLOBAL_LOG_PATH, logFileName);
    sprintf(headerFilePath, "%s_%s/headers/%s_emitc_static_headers.dump", ELF_DUMP_BASE, memConfig, modelName);
    sprintf(readelfFilePath, "%s_%s/readelf-sym/%s_emitc_static_readelf.dump", ELF_DUMP_BASE, memConfig, modelName);

    printf("modelName: %s\n", modelName);
    printf("logFilePath: %s\n", logFilePath);
    printf("headerFilePath: %s\n", headerFilePath);
    printf("readelfFilePath: %s\n", readelfFilePath);
    if (ntraces != 0)
        printf("ntraces: %lu\n", ntraces);
    if (skipBytes > 0)
        printf("skipBytes: %lu\n", skipBytes);

    logFile = fopen(logFilePath, "rb");
    if (!logFile) {
        fprintf(stderr, "E: failed to open %s\n", logFilePath);
        return -1;
    }
    if (skipBytes > 0) {
        fseek(logFile, skipBytes, SEEK_SET); // 시작 지점 기준에서 skipBytes만큼 포인터 이동
    }

    // printf("Trace test...\n");
    // printf("DL_TRACE_SIZE_COMPACT_MEM: %d\n", DL_TRACE_SIZE_COMPACT_MEM);
    // printf("DL_TRACE_SIZE_COMPACT_ARITH: %d\n", DL_TRACE_SIZE_COMPACT_ARITH);
    // printf("sizeof(DLTraceCompactMem): %d\n", sizeof(DLTraceCompactMem));
    // printf("sizeof(DLTraceCompactArith): %d\n", sizeof(DLTraceCompactArith));

    uint8_t traceBuf[32];
    size_t byteReads = 0;

    uint8_t opType = 0;
    uint8_t dataType = 0;
    uint8_t operandSize = 0;
    uint64_t instCtr = 0;
    uint32_t addr = 0;
    uint8_t opclass = 0;

    int curRegion = 0;
    int curDispatchRegion = -1;
    int curHostRegion = 0;
    uint64_t icnt = 0;

    // size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream);
    // opType: load/store/arith/custom
    // dataType: sint/uint/float/vector
    // operandSize: 8/16/32/64/128

    startTime = clock();
    while (!feof(logFile)) {
        if (ntraces != 0 && ntraces == icnt)
            break;

        byteReads = fread(traceBuf, 1, DL_TRACE_SIZE_COMPACT_MEM, logFile);
        opType = traceBuf[0] & 0b11;
        dataType = (traceBuf[0] >> 2) & 0b111;
        operandSize = traceBuf[0] >> 5;
        instCtr = *((uint64_t*)&traceBuf[1]);
        addr = *((uint32_t*)&traceBuf[9]);

        // MEM 타입 명령어 외에는 opclass를 위해 1바이트를 추가적으로 읽는다.
        if (opType == 2 || opType == 3 || dataType == 3) {
            byteReads = fread(traceBuf, 1, 1, logFile);
            // if (byteReads < 1) {
            //     fprintf(stderr, "E: file read error\n");
            //     return -1;
            // }
            opclass = traceBuf[0];
            if (verbose)
                printTrace(instCtr, opType, dataType, operandSize, addr, opclass);
        }
        else {
            if (verbose)
                printTrace(instCtr, opType, dataType, operandSize, addr, -1);
        }

        // trace 처리
        if (opType == 0) { // load
        }
        else if (opType == 1) { // store
        }
        else if (opType == 2) { // arith
        }
        else if (opType == 3) { // custom or unknown
            uint8_t opc = opclass & 0b11;
            uint8_t funct3 = (opclass >> 2) & 0b111;
            if (opc == 0) {
                if (funct3 == 0) { // dr.begin
                    curRegion++;
                    curDispatchRegion++;
                    printf("[%lu] dispatch_region#%d begin: addr=%#x, filepointer=%ld\n",
                        instCtr, curDispatchRegion, addr, ftell(logFile));
                }
                else if (funct3 == 1) { // dr.end
                    curRegion++;
                    curHostRegion++;
                    printf("[%lu] dispatch_region#%d end: addr=%#x, filepointer=%ld\n",
                        instCtr, curDispatchRegion, addr, ftell(logFile));
                }
            }
        }
        else { // parsing error
            fprintf(stderr, "E: unrecognized instruction: [%lu] opType=%d dataType=%d operandSize=%d addr=%#x\n", instCtr, opType, dataType, operandSize, addr);
            fclose(logFile);
            return -1;
        }
        icnt++;
    }
    
    endTime = clock();
    double cpuTimeUsed = ((double)(endTime - startTime)) / CLOCKS_PER_SEC;

    printf("total %lu traces\n", icnt);
    printf("Elapsed time: %lf\n", cpuTimeUsed);

    fclose(logFile);
    return 0;
}
