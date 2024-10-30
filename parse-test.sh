#!/bin/bash

OUTPUT_DIR=dump
#MODEL_LIST=(ecg_small)
MODEL_LIST=(fc_triple_xxl)

for mname in ${MODEL_LIST[@]}; do
    ast_name="${mname}_ast"
    fname="${OUTPUT_DIR}/${ast_name}.ast"
    echo "Model name: ${mname}, AST output path: ${fname}"
    python trace-parse.py --model-name=${mname} --enable-stat-table --ast-output=${ast_name} --disable-plot
done