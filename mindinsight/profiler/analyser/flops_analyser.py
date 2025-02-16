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
"""The Flops Analyser."""
import json
import os
import pandas as pd

from mindinsight.profiler.analyser.base_analyser import BaseAnalyser
from mindinsight.profiler.common.exceptions.exceptions import ProfilerIOException
from mindinsight.profiler.common.log import logger
from mindinsight.profiler.common.validator.validate_path import validate_and_normalize_path
from mindinsight.profiler.common.util import analyse_device_list_from_profiler_dir


class FlopsAnalyser(BaseAnalyser):
    """
    Analyse flops data from file.
    """
    _flops_summary_filename = 'flops_summary_{}.json'
    _flops_scope_filename = 'flops_scope_{}.json'
    _flops_operator_filename = 'flops_{}.txt'

    def _load(self):
        """Load data according to the parsed profiling files."""

    def _filter(self, filter_condition):
        """
        Filter the profiling data according to the filter condition.

        Args:
            filter_condition (dict): The filter condition.
        """

    def get_flops_summary(self):
        """
        Get flops summary information for UI display.

        Returns:
            json, the content of flops summary information.
        """
        summary_filename = self._flops_summary_filename.format(self._device_id)

        file_path = os.path.join(self._profiling_dir, summary_filename)
        file_path = validate_and_normalize_path(
            file_path, raise_key='Invalid flops summary path.'
        )

        flops_summary = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f_obj:
                    flops_summary = json.load(f_obj)
            except (IOError, OSError, json.JSONDecodeError) as err:
                logger.error('Error occurred when read flops summary file: %s', err)
                raise ProfilerIOException()
        else:
            logger.warning('No flops summary file. Please check the output path.')

        return flops_summary

    def get_flops_scope(self):
        """
        Get flops information of each scope for UI display.

        Returns:
            json, the content of flops summary information.
        """
        flops_scope_filename = self._flops_scope_filename.format(self._device_id)

        file_path = os.path.join(self._profiling_dir, flops_scope_filename)
        file_path = validate_and_normalize_path(
            file_path, raise_key='Invalid flops scope path.'
        )

        flops_scope = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f_obj:
                    flops_scope = json.load(f_obj)
            except (IOError, OSError, json.JSONDecodeError) as err:
                logger.error('Error occurred when read flops scope file: %s', err)
                raise ProfilerIOException()
        else:
            logger.warning('No flops scope file. Please check the output path.')

        return flops_scope

    def get_flops_data_for_marey(self):
        """
        Get flops information for marey's graph.

        Returns:
            json, the content of flops information for marey's graph.
        """
        device_list, _, _ = analyse_device_list_from_profiler_dir(self._profiling_dir)
        data = {}
        for device in device_list:
            flops_summary_filename = self._flops_summary_filename.format(device)
            flops_operator_filename = self._flops_operator_filename.format(device)
            device_entry = "device" + device
            data[device_entry] = {}
            file_path = os.path.join(self._profiling_dir, flops_summary_filename)
            file_path = validate_and_normalize_path(
                file_path, raise_key='Invalid flops scope path.'
            )
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f_obj:
                        data.get(device_entry)['summary'] = json.load(f_obj)
                except (IOError, OSError, json.JSONDecodeError) as err:
                    logger.error('Error occurred when read flops scope file: %s', err)
                    raise ProfilerIOException()
            else:
                logger.warning('No flops scope file. Please check the output path.')

            file_path = os.path.join(self._profiling_dir, flops_operator_filename)
            file_path = validate_and_normalize_path(
                file_path, raise_key='Invalid flops scope path.'
            )

            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    data.get(device_entry)['details'] = list(json.loads(df.to_json(orient="index")).values())
                except (IOError, OSError, json.JSONDecodeError) as err:
                    logger.error('Error occurred when read flops scope file: %s', err)
                    raise ProfilerIOException()
            else:
                logger.warning('No flops scope file. Please check the output path.')
        return data
