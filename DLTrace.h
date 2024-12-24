#ifndef __DL_TRACE_H__
#define __DL_TRACE_H__
#include <stdint.h>

/* traceV1 */
// typedef struct DLTraceLow {
// 	uint8_t opType: 1;			// mem/arith
// 	uint8_t dataType: 3;		// int/float/vector/uint
// 	uint8_t operandSize: 4;		// 8/16/32/64/128
// } DLTraceLow;

/* traceV2 */
typedef struct DLTraceLow {
	uint8_t opType: 2;			// load/store/arith/custom (or unknown)
	uint8_t dataType: 3;		// sint/uint/float/vector
	uint8_t operandSize: 3;		// 8/16/32/64/128
} DLTraceLow;

typedef struct DLTraceCompactMem {
	DLTraceLow lower;
	uint64_t instCtr;			// instruction counter
	uint32_t addr;				// target address (mem) / PC (arith)
} DLTraceCompactMem;

typedef struct DLTraceCompactArith {
    DLTraceLow lower;
    uint64_t instCtr;
    uint32_t addr;
    uint8_t opclass;            // 명령어 세부 분류
} DLTraceCompactArith;

#define DL_TRACE_SIZE_COMPACT_MEM	sizeof(struct DLTraceLow) + 12
#define DL_TRACE_SIZE_COMPACT_ARITH	sizeof(struct DLTraceLow) + 13

struct SizeTest {
	uint8_t bytes[17];
};

enum DLInstClass {
    DL_RISC_ARITH_IMM = 0x00, 
    DL_RISC_ARITH, 
    DL_RISC_FMADD = 0x10,   // FP Multiply-Add; MAC 연산과 기능적으로 동일
    DL_RISC_FMSUB,          // FP Multiply-Subtract
    DL_RISC_FNMADD,         // FP Negative Multiply-Add; MAC의 결과에 부호 반전
    DL_RISC_FNMSUB,         // FP Negative Multiply-Subtract
    DL_RISC_FP_ARITH,       //
    // 벡터 산술연산: 피연산자별 분류{vv, vi, vx}
    DL_RISC_V_IVV = 0x20,
    DL_RISC_V_IVX,
    DL_RISC_V_IVI,
    DL_RISC_V_MVV,
    DL_RISC_V_MVX,
    DL_RISC_V_FVV,
    DL_RISC_V_FVF,
    DL_RISC_MEM = 0x30,     // int/FP load/store
    DL_RISC_VL_US = 0x31,   // unit-stride (vle)
    DL_RISC_VL_VS = 0x32,   // vector-strided (vlse)
    DL_RISC_VL_UVI = 0x33,  // unordered vector-indexed (vlxei)
    DL_RISC_VL_OVI = 0x33,  // ordered vector-indexed (vlxei)
    DL_RISC_VS_US = 0x34,   // unit-stride (vse)
    DL_RISC_VS_VS = 0x35,   // vector-strided (vsse)
    DL_RISC_VS_UVI = 0x36,  // unordered vector-indexed (vsxei)
    DL_RISC_VS_OVI = 0x36,  // ordered vector-indexed (vsxei)
    DL_RISC_UNKNOWN = 0xff,
    DL_RISC_CUSTOM0 = 0xf0,
    DL_RISC_CUSTOM1 = 0xf1,
    DL_RISC_CUSTOM2 = 0xf2,
    DL_RISC_CUSTOM3 = 0xf3,
    DL_RISC_CUSTOM4 = 0xf4
};

#endif