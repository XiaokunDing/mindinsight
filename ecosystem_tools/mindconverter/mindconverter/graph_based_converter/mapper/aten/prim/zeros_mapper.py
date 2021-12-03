# Copyright 2021 Huawei Technologies Co., Ltd.All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Mapper module."""
from mindconverter.graph_based_converter.common.utils import reset_template_and_exchange_msg
from mindconverter.graph_based_converter.constant import WeightType, PYTORCH_MS_MAP
from mindconverter.graph_based_converter.mapper.base import AtenToMindSporeMapper


class ZerosMapper(AtenToMindSporeMapper):
    """Zeros mapper."""

    @staticmethod
    def _operation_name_in_ms(*args, **kwargs):
        return "zeros"

    @staticmethod
    def _convert_params(**kwargs):
        return dict()

    @staticmethod
    def _convert_trained_weights(**kwargs):
        weights = kwargs.get("weights", list())
        args_name_list_mapper = {
            2: ["shape", "unused"],
            3: ["shape", "unused", "unused"],
            5: ["shape", "dtype", "unused", "unused", "unused"],
            6: ["shape", "unused", "dtype", "unused", "unused", "unused"]
        }
        args_name_list = ZerosMapper.get_args_name_list(**kwargs, args_name=args_name_list_mapper)
        trainable_params = dict()
        for weight in weights:
            trainable_params[args_name_list[weight.location]] = {"data": weight.value, "location": weight.location,
                                                                 "type": WeightType.PARAMETER.value,
                                                                 "onnx_name": weight.name}
        return trainable_params

    @staticmethod
    def _generate_snippet_template(**kwargs):
        template, exchange_msg, outputs_list, outputs_mapping = AtenToMindSporeMapper._generate_snippet_template(
            **kwargs)
        raw_params = kwargs.get("raw_params")
        if not raw_params:
            return template, exchange_msg, outputs_list, outputs_mapping

        op = kwargs.get("operation")

        variable_slot = "var_0"
        trainable_params = kwargs.get("trainable_params", dict())
        args_name_list_mapper = {
            2: ["shape", "unused"],
            3: ["shape", "unused", "unused"],
            5: ["shape", "dtype", "unused", "unused", "unused"],
            6: ["shape", "unused", "dtype", "unused", "unused", "unused"]
        }
        raw_arg_name_list = ZerosMapper.get_args_name_list(raw_params=raw_params.copy(),
                                                           args_name=args_name_list_mapper,
                                                           return_raw=True)
        inputs, args, group_inputs = ZerosMapper._params_parser(raw_params, args_name_list_mapper, trainable_params)

        init_template_list = [f"self.{{{variable_slot}}}_{arg_name} = {{{arg_name}}}" for arg_name in args
                              if arg_name != "unused"]
        dtype = args.get("dtype")
        args["dtype"] = PYTORCH_MS_MAP["default"] if dtype is None else PYTORCH_MS_MAP[dtype]
        parameters_declared = dict()
        for name, trainable_param in trainable_params.copy().items():
            value = trainable_param["data"]
            if ZerosMapper.is_tensor(value):
                variable_slot_param_name = f"{variable_slot}/{name}"
                init_template_list.append(f"self.{{{variable_slot}}}_{name} = {{{variable_slot_param_name}")
                parameters_declared[name] = ""
            else:
                args[name] = value.tolist()
                init_template_list.append(f"self.{{{variable_slot}}}_{name} = {{{name}}}")
                trainable_params.pop(name)

        diff = len(inputs) - len(raw_arg_name_list)
        if diff > 0:
            construct_template = f"opt_{{{variable_slot}}} = ms_np.{op}" \
                                 f"(({' ,'.join(inputs[:diff + 1])}), " \
                                 f"self.{{{variable_slot}}}_dtype)"
        else:
            construct_template = f"opt_{{{variable_slot}}} = ms_np.{op}" \
                                 f"({inputs[0]}, " \
                                 f"self.{{{variable_slot}}}_dtype)"

        template, exchange_msg = reset_template_and_exchange_msg(template, exchange_msg, variable_slot,
                                                                 init_template_list, [construct_template], args,
                                                                 trainable_params, parameters_declared, group_inputs)
        return template, exchange_msg, outputs_list, outputs_mapping
    