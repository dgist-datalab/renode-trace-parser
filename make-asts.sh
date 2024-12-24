#!/bin/bash

AST_PATH="dump"
STAT_TABLE_LOG_PATH="stat-table-log"
MODEL_LIST=( "fc_triple_small" "fc_triple_medium" "fc_triple_large" "fc_triple_xl" "fc_triple_xxl" "ecg_small" "mobilenet_v1" )

options="--enable-stat-table --disable-plot"

for model_name in ${MODEL_LIST[@]}; do
    ast_name="${model_name}_ast"
    echo "Model name: ${model_name}"
    python trace-parse.py --model-name=${model_name} --ast-output=${ast_name} ${options} > ${STAT_TABLE_LOG_PATH}/${model_name}.txt
done
