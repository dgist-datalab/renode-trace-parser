#!/bin/bash

OUTPUT_DIR=sim-output
MODEL_LIST=(ecg_small fc_triple_small fc_triple_medium) # +fc_triple_large fc_triple_xl fc_triple_xxl
CACHE_SIZE_LIST=(16k 32k 48k 64k 128k 256k 512k 1m)
N_WAYS_LIST=(1 2 4 8 16)
POLICY_LIST=(fifo) # + lru random

for mname in ${MODEL_LIST[@]}; do
    for policy in ${POLICY_LIST[@]}; do
        for csize in ${CACHE_SIZE_LIST[@]}; do
            for nways in ${N_WAYS_LIST[@]}; do
                    fname=${OUTPUT_DIR}/cache-${mname}_${csize}_64B_${nways}ways_${policy}.txt
                    python cache-sim.py --model-name=${mname} --ast-input=${mname}_ast --cache-size=${csize} --cache-block-size=64 --nways=${nways} --replace-policy=${policy} > ${fname}
                    echo ${fname}:
                    tail -n 1 ${fname}
            done
        done
    done
done
