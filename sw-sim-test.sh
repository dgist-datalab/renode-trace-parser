#!/bin/bash

OUTPUT_DIR="sim-output-sw"

MODEL_NAME="fc_triple_medium"
CACHE_SIZE="32k"
BLOCK_SIZE=4096
NWAYS=8
POLICY="fifo"
python cache-sim.py -m ${MODEL_NAME} -a ${MODEL_NAME}_ast -s ${CACHE_SIZE} -b ${BLOCK_SIZE} -w ${NWAYS} -p ${POLICY} > ${OUTPUT_DIR}/${MODEL_NAME}_${CACHE_SIZE}_${BLOCK_SIZE}_${NWAYS}_${POLICY}.txt