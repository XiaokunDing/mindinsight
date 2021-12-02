# Copyright 2021 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Watchpoints."""
from abc import ABC
from enum import Enum

from mindinsight.debugger.api.debugger_tensor import DebuggerTensor
from mindinsight.debugger.common.utils import validate_type
from mindinsight.debugger.common.exceptions.exceptions import DebuggerParamValueError


class ConditionBase(ABC):
    """
    Base class for conditions.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Note:
        - If multiple checking parameters is specified for one condition instance,
          a WatchpointHit happens for the parameters that the tensor triggered for the watchpoint.

    Examples:
            >>> from mindinsight.debugger import DumpAnalyzer
            >>> from mindinsight.debugger import (TensorTooLargeCondition,
            ...                                   Watchpoint)
            >>> my_run = DumpAnalyzer(dump_dir="/path/to/your/dump_dir_with_dump_data")
            >>> tensors = my_run.select_tensors(query_string="Conv2D-op156")
            >>> watchpoint = Watchpoint(tensors=tensors,
            ...                         condition=TensorTooLargeCondition(abs_mean_gt=0.0, max_gt=0.0)
            >>> hit = list(my_run.check_watchpoints(watchpoints=[watchpoint]))[0]
            >>> print(hit.get_hit_detail())
            The setting for watchpoint is abs_mean_gt = 0.0, max_gt = 0.0.
            The actual value of the tensor is abs_mean_gt = 0.0665460056158321, max_gt = 0.48099958896636963.
            >>> watchpoint = Watchpoint(tensors=tensors,
            ...                         condition=TensorTooLargeCondition(abs_mean_gt=0.0, max_gt=1.0)
            >>> hit = list(my_run.check_watchpoints(watchpoints=[watchpoint]))[0]
            >>> print(hit.get_hit_detail())
            The setting for watchpoint is abs_mean_gt = 0.0.
            The actual value of the tensor is abs_mean_gt = 0.0665460056158321.
    """

    @property
    def name(self):
        """Get the name for the condition."""
        raise NotImplementedError

    @property
    def condition_id(self):
        """Get the name for the condition Id."""
        raise NotImplementedError

    @property
    def param_dict(self):
        """Get the parameters list."""
        return {}


class WatchpointHit(ABC):
    """
    Watchpoint hit.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Note:
        - This class is not meant to be instantiated by user.
        - The instances of this class is immutable.

    Examples:
        >>> from mindinsight.debugger import DumpAnalyzer
        >>> from mindinsight.debugger import TensorTooLargeCondition, Watchpoint
        >>> my_run = DumpAnalyzer(dump_dir="/path/to/your/dump_dir_with_dump_data")
        >>> tensor_list = my_run.select_tensors(
        ...                                     query_string="Conv",
        ...                                     use_regex=True,
        ...                                     iterations=[0],
        ...                                     ranks=[0],
        ...                                     slots=[0]
        ...                                     )
        >>> watchpoint = Watchpoint(tensors=tensor_list,
        ...                         condition=TensorTooLargeCondition(abs_mean_gt=0.0))
        >>> hits = my_run.check_watchpoints(watchpoints=[watchpoint])
        >>> hit = list(hits)[0]
        >>> print(str(hit))
        Watchpoint TensorTooLarge triggered on slot 0 of node Default/network-WithLossCell/
        _backbone-AlexNet/conv2-Conv2d/Conv2D-op156.
        The setting for watchpoint is abs_mean_gt = 0.0.
        The actual value of the tensor is abs_mean_gt = 0.0665460056158321.
        >>> print(hit.error_code)
        0
        >>> print(hit.tensor)
        rank: 0
        graph_name: kernel_graph_0
        node_name: Default/network-WithLossCell/_backbone-AlexNet/conv2-Conv2d/Conv2D-op156
        slot: 0
        iteration: 0
        >>> print(hit.get_hit_detail())
        The setting for watchpoint is abs_mean_gt = 0.0.
        The actual value of the tensor is abs_mean_gt = 0.0665460056158321.
    """

    @property
    def error_code(self):
        """
        Get the error code when checking the watchpoint if there is error.

        Returns:
            int, the error number.
        """
        raise NotImplementedError

    @property
    def error_msg(self):
        """
        Get the error msg when checking the watchpoint if there is error.

        Returns:
            list[str], the error message list.
        """
        raise NotImplementedError

    @property
    def tensor(self) -> DebuggerTensor:
        """Get the tensor for this watchpoint hit."""
        raise NotImplementedError

    def get_threshold(self):
        """
        Get the condition set by user.

        Returns:
            ConditionBase, the condition with user threshold, see info with str(ConditionBase).
        """
        raise NotImplementedError

    def get_hit_detail(self):
        """
        Get the actual values for the thresholds in the watchpoint.
        If error_code is not zero or None, None will be returned.

        Returns:
            ConditionBase, the condition with hit detail, see info with str(ConditionBase).
        """
        raise NotImplementedError


class WatchpointHitImpl(WatchpointHit):
    """
    Watchpoint hit.

    Args:
        tensor (DebuggerTensor): The tensor which hits the watchpoint.
        condition (ConditionBase): The ConditionBase object initialized with
            user setting value.
        hit_detail (ConditionBase): The ConditionBase object
            initialized with actual value of the Tensor.
        error_code (str): The code describing error.
    """

    def __init__(self,
                 tensor: DebuggerTensor,
                 condition: ConditionBase,
                 hit_detail: ConditionBase,
                 error_code):
        self._tensor = tensor
        self._condition = condition
        self._error_code = error_code
        self._hit_detail = hit_detail

    @property
    def error_code(self):
        """
        Get the error code when checking the watchpoint if there is error.

        Returns:
            int, the error number.
        """
        return self._error_code

    @property
    def error_msg(self):
        """
        Get the error msg when checking the watchpoint if there is error.

        Returns:
            list[str], the error message list.
        """
        error_code = self._error_code
        all_error_list = [
            "Tensor contains NaN.",
            "A tensor contains +/-INF.",
            "The previous step value cannot be found.",
            "The tensor size exceeds the memory limit.",
            "Graph history file is not available.",
            "Tensor has no value."
        ]
        error_list = []
        for i, error_str in enumerate(all_error_list):
            error = (error_code >> i) & 1
            if error == 1:
                error_list.append(error_str)

        return error_list

    @property
    def tensor(self) -> DebuggerTensor:
        """Get the tensor for this watchpoint hit."""
        return self._tensor

    def get_threshold(self):
        """Get the threshold set by user."""
        return self._condition

    def get_hit_detail(self):
        """
        Get the actual values for the thresholds in the watchpoint.
        If error_code is not zero or None, None will be returned.
        """
        if self._error_code:
            return None
        return self._hit_detail

    def __str__(self):
        if self._error_code:
            msg = f"Watchpoint {self._condition.name} check failed on tensor:\n" \
                  f"{str(self.tensor)}" \
                  f"Error detail: {self.error_msg}"
            return msg
        msg = f"Watchpoint {self._condition.name} triggered on tensor:\n" \
              f"{str(self.tensor)}" \
              f"Hit detail: {str(self._hit_detail)}"
        return msg


class HitDetail(ConditionBase):
    """Hit Detail."""

    def __init__(self, param_list, condition):
        self._param_list = param_list
        self._condition = condition

    @property
    def name(self):
        """Get the name for the condition."""
        return self._condition.name

    @property
    def condition_id(self):
        """Get the name for the condition Id."""
        return self._condition.condition_id

    @property
    def param_dict(self):
        """Get the parameters list."""
        return self._param_list

    def __str__(self):
        setting_detail = "The setting for watchpoint is "
        value_detail = " The actual value of the tensor is "
        show_set_value = True
        show_actual_value = True
        show_all_settings = False
        if self._condition.condition_id == WatchpointConditionId.TENSOR_OVERFLOW.value:
            show_set_value = False
        if self._condition.condition_id == WatchpointConditionId.UNCHANGED_TENSOR.value:
            show_all_settings = True
        if self._condition.condition_id in [WatchpointConditionId.UNCHANGED_TENSOR.value,
                                            WatchpointConditionId.TENSOR_OVERFLOW.value]:
            show_actual_value = False
        # list of the parameters with disabled = False and hit = 1
        hit_param_list = []
        for param in self._param_list:
            if not param.disabled and (param.hit or show_all_settings):
                hit_param_list.append(param)

        param_size = len(hit_param_list)
        if show_set_value:
            for idx, param in enumerate(hit_param_list):
                setting_detail += f"{param.name} = {param.value}"
                if idx == param_size - 1:
                    setting_detail += "."
                else:
                    setting_detail += ", "

        if show_actual_value:
            for idx, param in enumerate(hit_param_list):
                value_detail += f"{param.name} = {param.actual_value}"
                if idx == param_size - 1:
                    value_detail += "."
                else:
                    value_detail += ", "

        result = ""
        if show_set_value:
            result += setting_detail
        if show_actual_value:
            result += value_detail

        return result


class TensorTooLargeCondition(ConditionBase):
    """
    Tensor too large watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        abs_mean_gt (float, optional): The threshold for mean of the absolute
            value of the tensor. When the actual value was greater than this
            threshold, this checking condition would be satisfied.
        max_gt (float, optional): The threshold for maximum of the tensor. When
            the actual value was greater than this threshold, this checking
            condition would be satisfied.
        min_gt (float, optional): The threshold for minimum of the tensor. When
            the actual value was greater than this threshold, this checking
            condition would be satisfied.
        mean_gt (float, optional): The threshold for mean of the tensor. When
            the actual value was greater than this threshold, this checking
            condition would be satisfied.

    Examples:
        >>> from mindinsight.debugger import TensorTooLargeCondition
        >>> my_condition = TensorTooLargeCondition(abs_mean_gt=0.0)
        >>> print(my_condition.name)
        TensorTooLarge
    """


    def __init__(self,
                 abs_mean_gt=None, max_gt=None, min_gt=None, mean_gt=None):
        self._abs_mean_gt = abs_mean_gt
        self._max_gt = max_gt
        self._min_gt = min_gt
        self._mean_gt = mean_gt
        self.param_validate()

    @property
    def name(self):
        return "TensorTooLarge"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_TOO_LARGE.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._abs_mean_gt is not None:
            param_dict["abs_mean_gt"] = float(self._abs_mean_gt)
        if self._max_gt is not None:
            param_dict["max_gt"] = float(self._max_gt)
        if self._min_gt is not None:
            param_dict["min_gt"] = float(self._min_gt)
        if self._mean_gt is not None:
            param_dict["mean_gt"] = float(self._mean_gt)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify at least one of the parameters for TensorTooLargeCondition."
            raise DebuggerParamValueError(msg)


class TensorTooSmallCondition(ConditionBase):
    """
    Tensor too small watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        abs_mean_lt (float, optional): The threshold for mean of the absolute
            value of the tensor. When the actual value was less than this
            threshold, this checking condition would be satisfied.
        max_lt (float, optional): The threshold for maximum of the tensor. When
            the actual value was less than this threshold, this checking
            condition would be satisfied.
        min_lt (float, optional): The threshold for minimum of the tensor. When
            the actual value was less than this threshold, this checking
            condition would be satisfied.
        mean_lt (float, optional): The threshold for mean of the tensor. When
            the actual value was less than this threshold, this checking
            condition would be satisfied.

    Examples:
        >>> from mindinsight.debugger import TensorTooSmallCondition
        >>> my_condition = TensorTooSmallCondition(abs_mean_lt=0.2)
        >>> print(my_condition.name)
        TensorTooSmall
    """

    def __init__(self,
                 abs_mean_lt=None, max_lt=None, min_lt=None, mean_lt=None):
        self._abs_mean_lt = abs_mean_lt
        self._max_lt = max_lt
        self._min_lt = min_lt
        self._mean_lt = mean_lt
        self.param_validate()

    @property
    def name(self):
        return "TensorTooSmall"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_TOO_SMALL.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._abs_mean_lt is not None:
            param_dict["abs_mean_lt"] = float(self._abs_mean_lt)
        if self._max_lt is not None:
            param_dict["max_lt"] = float(self._max_lt)
        if self._min_lt is not None:
            param_dict["min_lt"] = float(self._min_lt)
        if self._mean_lt is not None:
            param_dict["mean_lt"] = float(self._mean_lt)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify at least one of the parameters for TensorTooSmallCondition."
            raise DebuggerParamValueError(msg)


class TensorRangeCondition(ConditionBase):
    """
    Tensor range watchpoint.

    Set a threshold to check the tensor value range. There are four options:
    range_percentage_lt, range_percentage_gt,  max_min_lt and max_min_gt.
    If the threshold is set to one of the first two options,
    then both range_start_inclusive and range_end_inclusive must be set.
    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        range_percentage_lt (float, optional): The threshold for the
            percentage of the tensor in the range. The checking condition will be satisfied
            when the percentage of the tensor in the specified range is less than this value.

        range_percentage_gt (float, optional): The threshold for the
            percentage of the tensor in the range. The checking condition will be satisfied
            when the percentage of the tensor in the specified range is greater than this value.

        max_min_lt (float, optional): Threshold for the difference of
            max and min of a tensor less than this value.

        max_min_gt (float, optional): Threshold for the difference of
            max and min of a tensor greater than this value.

        range_start_inclusive (float, required): The start of the range.

        range_end_inclusive (float, required): The end of the range.

    Examples:
        >>> from mindinsight.debugger import TensorRangeCondition
        >>> my_condition = TensorRangeCondition(max_min_gt=0.05)
        >>> print(my_condition.name)
        TensorRange
    """

    def __init__(self,
                 range_start_inclusive=None, range_end_inclusive=None, range_percentage_lt=None,
                 range_percentage_gt=None, max_min_lt=None, max_min_gt=None):
        self._range_start_inclusive = range_start_inclusive
        self._range_end_inclusive = range_end_inclusive
        self._range_percentage_lt = range_percentage_lt
        self._range_percentage_gt = range_percentage_gt
        self._max_min_lt = max_min_lt
        self._max_min_gt = max_min_gt
        self.param_validate()

    @property
    def name(self):
        return "TensorRange"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_RANGE.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._range_start_inclusive is not None:
            param_dict["range_start_inclusive"] = float(self._range_start_inclusive)
        if self._range_end_inclusive is not None:
            param_dict["range_end_inclusive"] = float(self._range_end_inclusive)
        if self._range_percentage_lt is not None:
            param_dict["range_percentage_lt"] = float(self._range_percentage_lt)
        if self._range_percentage_gt is not None:
            param_dict["range_percentage_gt"] = float(self._range_percentage_gt)
        if self._max_min_lt is not None:
            param_dict["max_min_lt"] = float(self._max_min_lt)
        if self._max_min_gt is not None:
            param_dict["max_min_gt"] = float(self._max_min_gt)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify at least one of the parameters for TensorRangeCondition."
            raise DebuggerParamValueError(msg)
        if ("range_percentage_lt" in self.param_dict.keys() or
                "range_percentage_gt" in self.param_dict.keys()):
            if ("range_start_inclusive" not in self.param_dict.keys() or
                    "range_end_inclusive" not in self.param_dict.keys()):
                msg = ("Please specify both range_start_inclusive and "
                       "range_end_inclusive parameters for TensorRangeCondition.")
                raise DebuggerParamValueError(msg)
        if ("range_start_inclusive" in self.param_dict.keys() or
                "range_end_inclusive" in self.param_dict.keys()):
            if ("range_percentage_lt" not in self.param_dict.keys() and
                    "range_percentage_gt" not in self.param_dict.keys()):
                msg = ("Please specify range_percentage_lt and/or "
                       "range_percentage_gt parameters for TensorRangeCondition.")
                raise DebuggerParamValueError(msg)


class TensorOverflowCondition(ConditionBase):
    """
    Tensor overflow watchpoint.

    Tensor overflow whatchpoint checks for inf and nan tensors.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Examples:
        >>> from mindinsight.debugger import TensorOverflowCondition
        >>> my_condition = TensorOverflowCondition()
        >>> print(my_condition.name)
        TensorOverflow
    """

    def __init__(self):
        pass

    @property
    def name(self):
        return "TensorOverflow"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_OVERFLOW.value


class OperatorOverflowCondition(ConditionBase):
    """
    Operator overflow watchpoint.

    Operator overflow whatchpoint checks whether overflow occurs during operator computation.
    Only Ascend AI processor is supported.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Examples:
        >>> from mindinsight.debugger import OperatorOverflowCondition
        >>> my_condition = OperatorOverflowCondition()
        >>> print(my_condition.name)
        OperatorOverflow
    """

    def __init__(self):
        pass

    @property
    def name(self):
        return "OperatorOverflow"

    @property
    def condition_id(self):
        return WatchpointConditionId.OPERATOR_OVERFLOW.value


class TensorAllZeroCondition(ConditionBase):
    """
    Tensor all zero watchpoint

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        zero_percentage_ge (float, required): The threshold to check if the percentage of
            zero tensor values are greater than this value.

    Examples:
        >>> from mindinsight.debugger import TensorAllZeroCondition
        >>> my_condition = TensorAllZeroCondition(zero_percentage_ge=0.0)
        >>> print(my_condition.name)
        TensorAllZero
    """

    def __init__(self, zero_percentage_ge=None):
        self._zero_percentage_ge = zero_percentage_ge
        self.param_validate()

    @property
    def name(self):
        return "TensorAllZero"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_ALL_ZERO.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._zero_percentage_ge is not None:
            param_dict["zero_percentage_ge"] = float(self._zero_percentage_ge)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify zero_percentage_ge parameter for TensorAllZeroCondition."
            raise DebuggerParamValueError(msg)


class TensorUnchangedCondition(ConditionBase):
    """
    Tensor unchanged condition watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.
    Checks allclose function on previous and current tensor.
    (abs_mean(current_tensor - previous_tensor) <= (atol + rtol * abs_mean(previous_tensor)))

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        rtol (float, required): The relative tolerance parameter.
        atol (float, required): The absolute tolerance parameter.

    Examples:
        >>> from mindinsight.debugger import TensorUnchangedCondition
        >>> my_condition = TensorUnchangedCondition(rtol=1000.0)
        >>> print(my_condition.name)
        TensorUnchanged
    """

    def __init__(self, rtol=None, atol=None):
        self._rtol = rtol
        self._atol = atol
        self.param_validate()

    @property
    def name(self):
        return "TensorUnchanged"

    @property
    def condition_id(self):
        return WatchpointConditionId.UNCHANGED_TENSOR.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._rtol is not None:
            param_dict["rtol"] = float(self._rtol)
        if self._atol is not None:
            param_dict["atol"] = float(self._atol)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify rtol or atol parameter for TensorUnchangedCondition."
            raise DebuggerParamValueError(msg)


class TensorInitializationCondition(ConditionBase):
    """
    Tensor initialization watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        zero_percentage_ge (float, optional): The threshold to check if the percentage of
            zero values for initial tensor is greater than or equal to this value.
        max_gt (float, optional): The threshold to check if the max value of
            the initial tensor is greater than this value.
        min_lt (float, optional): The threshold to check if the min value of
            the initial tensor is less than this value.

    Examples:
        >>> from mindinsight.debugger import TensorInitializationCondition
        >>> my_condition = TensorInitializationCondition(max_gt=0.0)
        >>> print(my_condition.name)
        TensorInitialization
    """

    def __init__(self, zero_percentage_ge=None, max_gt=None, min_lt=None):
        self._zero_percentage_ge = zero_percentage_ge
        self._max_gt = max_gt
        self._min_lt = min_lt
        self.param_validate()

    @property
    def name(self):
        return "TensorInitialization"

    @property
    def condition_id(self):
        return WatchpointConditionId.INITIAL_WEIGHT.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._zero_percentage_ge is not None:
            param_dict["zero_percentage_ge"] = float(self._zero_percentage_ge)
        if self._max_gt is not None:
            param_dict["max_gt"] = float(self._max_gt)
        if self._min_lt is not None:
            param_dict["min_lt"] = float(self._min_lt)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if not self.param_dict:
            msg = "Please specify at least one of the parameters for TensorInitializationCondition."
            raise DebuggerParamValueError(msg)


class TensorChangeBelowThresholdCondition(ConditionBase):
    """
    Tensor change below threshold watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.
    (abs_mean(current_tensor - previous_tensor) < epsilon + mean_update_ratio_lt * abs_mean(previous_tensor))

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        mean_update_ratio_lt (float, optional): The threshold value for mean update ration,
            if the mean update ratio is less that this value the watchpoint will be triggered.
        epsilon (float, optional): epsilon value.

    Examples:
        >>> from mindinsight.debugger import TensorChangeBelowThresholdCondition
        >>> my_condition = TensorChangeBelowThresholdCondition(abs_mean_update_ratio_lt=2.0)
        >>> print(my_condition.name)
        TensorChangeBelowThreshold
    """

    def __init__(self, abs_mean_update_ratio_lt=None, epsilon=None):
        self._abs_mean_update_ratio_lt = abs_mean_update_ratio_lt
        self._epsilon = epsilon
        self.param_validate()

    @property
    def name(self):
        return "TensorChangeBelowThreshold"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_CHANGE_TOO_SMALL.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._abs_mean_update_ratio_lt is not None:
            param_dict["abs_mean_update_ratio_lt"] = float(self._abs_mean_update_ratio_lt)
        if self._epsilon is not None:
            param_dict["epsilon"] = float(self._epsilon)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if "abs_mean_update_ratio_lt" not in self.param_dict.keys():
            msg = "Please specify abs_mean_update_ratio_lt parameter for TensorChangeBelowThresholdCondition."
            raise DebuggerParamValueError(msg)


class TensorChangeAboveThresholdCondition(ConditionBase):
    """
    Tensor change above threshold watchpoint.

    When all specified checking conditions were satisfied, this watchpoint would
    be hit after a check.
    (abs_mean(current_tensor - previous_tensor) > epsilon + mean_update_ratio_gt * abs_mean(previous_tensor))

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or deletion.

    Args:
        mean_update_ratio_gt (float, optional): The threshold value for mean update ration,
            if the mean update ratio is greater than this value the watchpoint will be triggered.
        epsilon (float, optional): epsilon value.

    Examples:
        >>> from mindinsight.debugger import TensorChangeAboveThresholdCondition
        >>> my_condition = TensorChangeAboveThresholdCondition(abs_mean_update_ratio_gt=0.0)
        >>> print(my_condition.name)
        TensorChangeAboveThreshold
    """

    def __init__(self, abs_mean_update_ratio_gt=None, epsilon=None):
        self._abs_mean_update_ratio_gt = abs_mean_update_ratio_gt
        self._epsilon = epsilon
        self.param_validate()

    @property
    def name(self):
        return "TensorChangeAboveThreshold"

    @property
    def condition_id(self):
        return WatchpointConditionId.TENSOR_CHANGE_TOO_LARGE.value

    @property
    def param_dict(self):
        param_dict = {}
        if self._abs_mean_update_ratio_gt is not None:
            param_dict["abs_mean_update_ratio_gt"] = float(self._abs_mean_update_ratio_gt)
        if self._epsilon is not None:
            param_dict["epsilon"] = float(self._epsilon)
        return param_dict

    def param_validate(self):
        """
        Checks if the parameters of the condition are valid.
        Raises exception for invalid.
        """
        if "abs_mean_update_ratio_gt" not in self.param_dict.keys():
            msg = "Please specify abs_mean_update_ratio_gt parameter for TensorChangeAboveThresholdCondition."
            raise DebuggerParamValueError(msg)


class Watchpoint:
    """
    Watchpoint applies condition to specified tensors.

    .. warning::
        All APIs in this class are experimental prototypes that are subject to
        change and/or delete.

    Args:
        tensors (Iterable[DebuggerTensor]): The tensors to check.
        condition (ConditionBase): The condition to apply to tensors.

    Examples:
        >>> from mindinsight.debugger import DumpAnalyzer
        >>> from mindinsight.debugger import TensorTooLargeCondition, Watchpoint
        >>> my_run = DumpAnalyzer(dump_dir="/path/to/your/dump_dir_with_dump_data")
        >>> tensor_list = my_run.select_tensors(
        ...                                     query_string="Conv",
        ...                                     use_regex=True,
        ...                                     iterations=[0],
        ...                                     ranks=[0],
        ...                                     slots=[0]
        ...                                     )
        >>> watchpoint = Watchpoint(tensors=tensor_list,
        ...                         condition=TensorTooLargeCondition(abs_mean_gt=0.0))
        >>> tensor = list(watchpoint.tensors)[0]
        >>> print(tensor.node.name)
        Default/network-WithLossCell/_backbone-AlexNet/conv2-Conv2d/Conv2D-op156
        >>> print(watchpoint.condition.name)
        TensorTooLarge
    """

    def __init__(self, tensors, condition):
        self._tensors = tensors
        self._condition = condition

    @property
    def tensors(self):
        """
        Get tensors to check.

        Returns:
            Iterable[DebuggerTensor]), the tensors to check.
        """
        return self._tensors

    @property
    def condition(self):
        """
        Get the condition to apply to tensors.

        Returns:
            ConditionBase, the condition to apply to tensors.
        """
        return self._condition


class WatchpointHandle:
    """Watchpoint handle."""

    def __init__(self, watchpoint_id, watchpoint):
        validate_type(watchpoint, 'watchpoint', Watchpoint, 'Watchpoint')
        self.watchpoint_id = watchpoint_id
        self.condition = watchpoint.condition
        self.sorted_tensors = self._organize_tensor(watchpoint.tensors)
        self.tensors = watchpoint.tensors

    @staticmethod
    def _get_value(default_map, key, default_value):
        """Get key in default map."""
        value = default_map.get(key)
        if value is None:
            value = default_value
            default_map[key] = value
        return value

    def _organize_tensor(self, tensors):
        """Sort out the tensor and remove the duplication."""
        sorted_tensor = {}
        for tensor in tensors:
            validate_type(tensor, 'tensors', DebuggerTensor, 'List[DebuggerTensor]')
            node_map = self._get_value(sorted_tensor, tensor.iteration, {})
            slot_map = self._get_value(node_map, tensor.node.unique_id, {
                'node': tensor.node,
                'slot_map': {}
            }).get('slot_map')
            slot_map[tensor.slot] = tensor
        return sorted_tensor

    def get_iterations(self):
        """Get iterations to be check in this watchpoint."""
        return list(self.sorted_tensors.keys())

    def need_check(self, tensor):
        """Check if the tensor need to be checked."""
        slot_map = self.sorted_tensors.get(tensor.iteration,
                                           {}).get(tensor.node.unique_id, {}).get('slot_map')
        if slot_map.get(tensor.slot) is not None:
            return True
        return False

    def get_check_nodes(self, iteration):
        """Get check nodes."""
        if iteration is None:
            return {}
        check_nodes = {}
        for node_info in self.sorted_tensors.get(iteration, {}).values():
            node = node_info.get('node')
            node_name = node.full_name_with_graph
            check_node = self._get_value(check_nodes, node_name, {
                "rank_id": [node.rank],
                "is_output": True,
                "root_graph_id": [node.root_graph_id]
            })
            if node.rank not in check_node.get('rank_id'):
                check_node["rank_id"].append(node.rank)
        return check_nodes

    def add_watchpoint(self, iteration, debugger_engine):
        """
        Add watchpoint for the selected iteration.
        """
        check_nodes = self.get_check_nodes(iteration)
        # check if watchpoint must be added for the current iteration
        if check_nodes:
            params = []
            for key, value in self.condition.param_dict.items():
                param = debugger_engine.dbg_services_module.Parameter(name=key,
                                                                      disabled=False, value=value)
                params.append(param)
            debugger_engine.dbg_service.add_watchpoint(
                watchpoint_id=self.watchpoint_id,
                watch_condition=self.condition.condition_id,
                check_node_list=check_nodes,
                parameter_list=params
            )

    def watchpoint_hit_on_no_value(self, iteration):
        """
        Returns list of WatchpointHit if tensors' npy files are missing,
        when error_on_no_value =True
        """
        no_value_hit_list = []
        node_map = self.sorted_tensors.get(iteration)
        if not node_map:
            return no_value_hit_list
        for node_info in node_map.values():
            for tensor in node_info.get('slot_map', {}).values():
                if tensor.has_value() is False:
                    hit_params = []
                    hit_detail = HitDetail(hit_params, self.condition)
                    # 32 means there is no value found
                    error_no_value_code = 32
                    no_value_hit = WatchpointHitImpl(tensor=tensor,
                                                     condition=self.condition,
                                                     hit_detail=hit_detail,
                                                     error_code=error_no_value_code)
                    no_value_hit_list.append(no_value_hit)
        return no_value_hit_list


class WatchpointConditionId(Enum):
    """Watchpoint condition ID."""
    OPERATOR_OVERFLOW = 2
    TENSOR_OVERFLOW = 13
    INITIAL_WEIGHT = 14
    TENSOR_TOO_LARGE = 15
    TENSOR_TOO_SMALL = 16
    TENSOR_ALL_ZERO = 17
    TENSOR_CHANGE_TOO_LARGE = 18
    TENSOR_CHANGE_TOO_SMALL = 19
    UNCHANGED_TENSOR = 20
    TENSOR_RANGE = 21
