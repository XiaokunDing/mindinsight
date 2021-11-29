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
from mindconverter.graph_based_converter.constant import WeightType
from mindconverter.graph_based_converter.mapper.base import AtenToMindSporeMapper


class TransposeMapper(AtenToMindSporeMapper):
    """Transpose mapper."""

    @staticmethod
    def _operation_name_in_ms(*args, **kwargs):
        return "P.Transpose"

    @staticmethod
    def _convert_trained_weights(**kwargs):
        weights = kwargs.get("weights", list())
        args_name = ["input", "dim0", "dim1"]
        args_name_list = TransposeMapper.get_args_name_list(**kwargs, args_name=args_name)
        trainable_params = dict()
        for weight in weights:
            trainable_params[args_name_list[weight.location]] = {"data": weight.value, "location": weight.location,
                                                                 "type": WeightType.PARAMETER.value,
                                                                 "onnx_name": weight.name}
        return trainable_params

    @staticmethod
    def _generate_snippet_template(**kwargs):
        template, exchange_msg, outputs_list, outputs_mappings = AtenToMindSporeMapper._generate_snippet_template(
            **kwargs)
        raw_params = kwargs.get("raw_params")
        if not raw_params:
            return template, exchange_msg, outputs_list, outputs_mappings

        op = kwargs.get("operation")
        trainable_params = kwargs.get("trainable_params", dict())
        output_shape = raw_params.get("output_shape", tuple())

        variable_slot = "var_0"
        args_name = ["input", "dim0", "dim1"]
        inputs, args, group_inputs = TransposeMapper._params_parser(raw_params=raw_params, args_name=args_name,
                                                                    trainable_params=trainable_params)
        args = TransposeMapper._get_args(args=args, output_shape=output_shape)

        init_template_list = [f"self.{{{variable_slot}}}_{arg_name} = {{{arg_name}}}" for arg_name in args]
        parameters_declared = dict()
        for name, trainable_param in trainable_params.copy().items():
            value = trainable_param["data"]
            if TransposeMapper.is_tensor(value):
                variable_slot_param_name = f"{variable_slot}/{name}"
                init_template_list.append(f"self.{{{variable_slot}}}_{name} = {{{variable_slot_param_name}}}")
                parameters_declared[name] = ""
            else:
                args[name] = value.tolist()
                init_template_list.append(f"self.{{{variable_slot}}}_{name} = {{{name}}}")
                trainable_params.pop(name)
        construct_template = f"opt_{{{variable_slot}}} = {op}()({inputs[0]}, self.{{{variable_slot}}}_input_perm)"

        template, exchange_msg = reset_template_and_exchange_msg(template, exchange_msg, variable_slot,
                                                                 init_template_list, [construct_template], args,
                                                                 trainable_params, parameters_declared, group_inputs)
        return template, exchange_msg, outputs_list, outputs_mappings

    @staticmethod
    def _get_args(**kwargs):
        """Get args from params_parser."""
        args = kwargs.get("args", dict())
        output_shape = kwargs.get("output_shape", tuple())

        if "dim0" not in args or "dim1" not in args:
            raise ValueError(
                "Dim0 or Dim1 is not constant number, which is unsupported in MindSpore operator {P.Transpose}.")

        dim0 = args.pop("dim0")
        dim1 = args.pop("dim1")
        ndim = len(output_shape)
        temp = list(range(ndim))
        temp[dim0], temp[dim1] = range(ndim)[dim1], range(ndim)[dim0]

        args["input_perm"] = tuple(temp)
        return args
