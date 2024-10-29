#!/bin/bash

OUTPUT_DIR=dump
MODEL_LIST=(ecg_small)

for mname in ${MODEL_LIST[@]}; do
    ast_name="${mname}_ast"
    fname="${OUTPUT_DIR}/${ast_name}.ast"
    python trace-parse.py --model-name=${mname} --enable-stat-table --ast-output=${ast_name} --disable-plot > ${fname}
done