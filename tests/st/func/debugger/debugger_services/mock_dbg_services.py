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
# ============================================================================
"""
The module DbgServices provides offline debugger APIs.
"""
from unittest.mock import MagicMock

import numpy as np

import mindinsight
from mindinsight.debugger.common.log import LOGGER as log


def get_version():
    """Get version."""
    return mindinsight.__version__


class DbgServices:
    """
    DbgServices.

    Args:
        dump_file_path (str): dir where the dump files are saved.
    """
    def __init__(self, dump_file_path, verbose=True):
        self._verbose = verbose
        self.dump_file_path = dump_file_path
        self.dbg_instance = MagicMock()
        self._watchpoints = {}
        self.print_mes("in Python __init__, file path is {}".format(dump_file_path))
        self.version = get_version()
        self.initialized = False
        self.is_sync = True
        self.max_mem_usage = None

    def print_mes(self, mes):
        """Print message."""
        if self._verbose:
            log.info(mes)

    def initialize(self, net_name, is_sync_mode, max_mem_usage):
        """Initialize."""
        self.print_mes(" Python Initialize dump_file_path: {}, is_sync: {}".format(net_name, is_sync_mode))
        self.initialized = True
        self.max_mem_usage = max_mem_usage

    def add_watchpoint(self, watchpoint_id, watch_condition, check_node_list, parameter_list):
        """Add watchpoint."""
        self.print_mes("Add watchpoint with watchpoint id: {}".format(watchpoint_id))
        self._watchpoints[watchpoint_id] = {'watch_condition': watch_condition,
                                            'check_nodes': check_node_list,
                                            'parameter_list': parameter_list}
        return 0

    def remove_watchpoint(self, watchpoint_id):
        """Remove watchpoints."""
        self.print_mes("Remove watchpoint with watchpoint id: {}".format(watchpoint_id))
        return self._watchpoints.pop(watchpoint_id)

    def check_watchpoints(self, iteration, error_on_no_value=False):
        """Check watchpoints."""
        self.print_mes("Check watchpoint at iteration: {}".format(iteration))
        watch_hits = []
        if error_on_no_value:
            return []
        for watchpoint_id, watchpoint in self._watchpoints.items():
            # add param hit info
            real_param_list = []
            for param in watchpoint.get('parameter_list'):
                mock_param = MagicMock(
                    actual_value=param.actual_value,
                    disabled=param.disabled,
                    hit=True,
                    name=param.name,
                    value=0.0
                )
                real_param_list.append(mock_param)
            watchpoint['parameter_list'] = real_param_list
            for watch_node_name, node_info in watchpoint.get('check_nodes').items():
                for rank_id in node_info.get('rank_id'):
                    hit = WatchpointHit(watch_node_name,
                                        0,
                                        watchpoint.get('watch_condition'),
                                        watchpoint_id,
                                        watchpoint.get('parameter_list'),
                                        0,
                                        rank_id,
                                        watchpoint.get('root_graph_id'))
                    watch_hits.append(hit)

        return watch_hits

    def read_tensor_base(self, info):
        """Read tensor base info."""
        info_list_inst = []
        for _ in info:
            tensor_data = TensorBaseData(4, [2, 2, 3], 48)
            info_list_inst.append(tensor_data)
        return info_list_inst

    def read_tensor_stats(self, info):
        """Read tensor stats info."""
        info_list_inst = []
        for _ in info:
            tensor_data = TensorStatsData(4, [2, 2, 3], 48)
            info_list_inst.append(tensor_data)
        return info_list_inst

    def read_tensors(self, info):
        """Read tensor values."""
        value = np.asarray(list(range(12)), dtype=np.int32).tobytes()
        info_list_inst = []
        for _ in info:
            tensor_data = TensorData(value, len(value), 4, [2, 2, 3])
            info_list_inst.append(tensor_data)
        return info_list_inst


class TensorInfo:
    """Tensor Information."""
    def __init__(self, node_name, slot, iteration, rank_id, is_output, root_graph_id):
        self.node_name = node_name
        self.slot = slot
        self.iteration = iteration
        self.rank_id = rank_id
        self.is_output = is_output
        self.root_graph_id = root_graph_id


class TensorData:
    """Tensor data structure."""
    def __init__(self, data_ptr, data_size, dtype, shape):
        self.data_ptr = data_ptr
        self.data_size = data_size
        self.dtype = dtype
        self.shape = shape


class TensorStatsData:
    """Tensor data structure."""
    def __init__(self, dtype, shape, data_size):
        self.dtype = dtype
        self.shape = shape
        self.data_size = data_size
        self.is_bool = False
        self.max_value = 11.0
        self.min_value = 0.0
        self.avg_value = 5.5
        self.count = 12
        self.neg_zero_count = 0.0
        self.pos_zero_count = 11.0
        self.zero_count = 1.0
        self.nan_count = 0
        self.neg_inf_count = 0
        self.pos_inf_count = 0


class TensorBaseData:
    """Tensor data structure."""
    def __init__(self, dtype, shape, data_size):
        self.dtype = dtype
        self.shape = shape
        self.data_size = data_size


class Parameter:
    """Parameter structure."""
    def __init__(self, name, disabled, value, hit=False, actual_value=0.0):
        self.name = name
        self.disabled = disabled
        self.value = value
        self.hit = hit
        self.actual_value = actual_value


class WatchpointHit:
    """Watchpoint hit structure."""
    def __init__(self, name, slot, condition, watchpoint_id, parameters, error_code, rank_id, root_graph_id):
        self.name = name
        self.slot = slot
        self.condition = condition
        self.watchpoint_id = watchpoint_id
        self.root_graph_id = root_graph_id
        self.parameters = parameters
        self.error_code = error_code
        self.rank_id = rank_id
