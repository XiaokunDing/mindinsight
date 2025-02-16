# Copyright 2020-2021 Huawei Technologies Co., Ltd
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
"""Implement the debugger grpc server."""
import copy
import threading
from functools import wraps
from queue import Queue, Full, Empty

import mindinsight
from mindinsight.common.util import version_match
from mindinsight.debugger.common.log import LOGGER as log
from mindinsight.debugger.common.utils import MAX_SINGLE_TENSOR_CACHE_BYTES, get_ack_reply, ServerStatus, \
    Streams, RunLevel, load_tensor, convert_tensor_stats, \
    put_tensor_stats_in_cache, put_tensor_base_in_cache, get_tensor_value
from mindinsight.debugger.conditionmgr.condition import TargetTypeEnum, ParamNameEnum
from mindinsight.debugger.debugger_services.debugger_server_base import debugger_server_wrap
from mindinsight.debugger.proto import debug_grpc_pb2_grpc as grpc_server_base
from mindinsight.debugger.proto.debug_grpc_pb2 import ViewCMD
from mindinsight.debugger.stream_operator.watchpoint_operator import WatchpointOperator
from mindinsight.domain.graph.proto.ms_graph_pb2 import GraphProto


def debugger_wrap(func):
    """Wrapper for catch exception."""

    @wraps(func)
    def record_log(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            log.exception(err)
            raise err

    return record_log


class DebuggerGrpcServer(grpc_server_base.EventListenerServicer):
    """The grpc server used to interactive with grpc client."""

    def __init__(self, cache_store):
        """
        Initialize.

        Args:
            cache_store (DebuggerCache): Debugger cache store.
        """
        cache_store.initialize()
        self._cache_store = cache_store
        # the next position of command queue to be queried
        self._pos = None
        # the status of grpc server, the value is in ServerStatus
        self._status = None
        # the run command cache, used to deal with left continue steps or nodes
        self._old_run_cmd = None
        # the view command cache, used to update tensor history through data queue
        self._received_view_cmd = None
        # the flag of receiving watch point hit
        self._received_hit = None
        self._heartbeat = None
        self.init()

    def init(self):
        """Init debugger grpc server."""
        self._pos = '0'
        self._status = ServerStatus.PENDING
        self._old_run_cmd = {}
        self._received_view_cmd = {}
        self._received_hit = []
        if self._heartbeat is not None:
            self._heartbeat.stop()
        self._heartbeat = None
        self._cache_store.clean()

    @debugger_wrap
    def WaitCMD(self, request, context):
        """Wait for a command in DebuggerCache."""
        # check if graph have already received.
        log.info("Received WaitCMD at %s-th step.", request.cur_step)
        if self._status == ServerStatus.PENDING:
            log.warning("No graph received before WaitCMD.")
            reply = get_ack_reply(1)
            return reply

        # send graph if it has not been sent before
        self._pre_process(request)
        # deal with old command
        reply = self._deal_with_old_command()
        # wait for next command
        if reply is None:
            reply = self._wait_for_next_command()
        # check the reply
        if reply is None:
            reply = get_ack_reply(1)
            log.warning("Failed to get command event.")
        else:
            log.debug("Reply to WaitCMD: %s", reply)
        return reply

    def _pre_process(self, request):
        """Pre-process before dealing with command."""

        # check if version is mismatch, if mismatch, send mismatch info to UI
        if self._status == ServerStatus.MISMATCH:
            log.warning("Version of MindSpore and MindInsight are unmatched,"
                        "waiting for user to terminate the script.")
            metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
            # put metadata into data queue
            metadata = metadata_stream.get(['state', 'debugger_version'])
            self._cache_store.put_data(metadata)
            return

        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        is_new_step = metadata_stream.step < request.cur_step
        is_new_node = metadata_stream.full_name != request.cur_node
        # clean cache data at the beginning of new step or node has been changed.
        if is_new_step or is_new_node:
            self._cache_store.clean_data()
            self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0).clean_tensors(
                request.cur_step)
        if is_new_step:
            self._cache_store.get_stream_handler(Streams.WATCHPOINT_HIT).get_hit_handler_by_rank_id(0).clean()
        # receive graph at the beginning of the training
        if self._status == ServerStatus.RECEIVE_GRAPH:
            self._send_graph_flag(metadata_stream)
        # receive new metadata
        if is_new_step or is_new_node:
            self._update_metadata(metadata_stream, request)
        self._send_received_tensor_tag()
        self._send_watchpoint_hit_flag()

    def _send_graph_flag(self, metadata_stream):
        """
        Send graph and metadata to UI.

        Args:
            metadata_stream (MetadataHandler): Metadata handler stream.
        """
        self._cache_store.clean_command()
        # receive graph in the beginning of the training
        self._status = ServerStatus.WAITING
        metadata_stream.state = ServerStatus.WAITING.value
        metadata = metadata_stream.get()
        res = self._cache_store.get_stream_handler(Streams.GRAPH).get_graph_handler_by_rank_id(0).get()
        res.update(metadata)
        self._cache_store.put_data(res)
        log.debug("Put graph into data queue.")

    def _update_metadata(self, metadata_stream, metadata_proto):
        """
        Update metadata.

        Args:
            metadata_stream (MetadataHandler): Metadata handler stream.
            metadata_proto (MetadataProto): Metadata proto send by client.
        """
        # put new metadata into cache
        metadata_stream.put(metadata_proto)
        # update current node name and graph name
        graph_stream = self._cache_store.get_stream_handler(Streams.GRAPH).get_graph_handler_by_rank_id(0)
        full_name = metadata_proto.cur_node
        graph_name = graph_stream.get_graph_id_by_full_name(
            full_name) if full_name else metadata_stream.graph_name
        cur_node = graph_stream.get_node_name_by_full_name(full_name, graph_name)
        metadata_stream.node_name = cur_node
        metadata_stream.graph_name = graph_name
        metadata = metadata_stream.get()
        self._cache_store.put_data(metadata)
        log.debug("Put new metadata into data queue.")

    def _send_received_tensor_tag(self):
        """Send received_finish_tag."""
        node_info = self._received_view_cmd.get('node_info')
        if not node_info or self._received_view_cmd.get('wait_for_tensor'):
            return
        metadata = self._cache_store.get_stream_handler(Streams.METADATA).get(['step', 'state'])
        ret = {'receive_tensor': node_info.copy()}
        ret.update(metadata)
        self._cache_store.put_data(ret)
        self._received_view_cmd.clear()
        log.debug("Send receive tensor flag for %s", node_info)

    def _send_watchpoint_hit_flag(self):
        """Send Watchpoint hit flag."""
        watchpoint_hit_stream = self._cache_store.get_stream_handler(Streams.WATCHPOINT_HIT).get_hit_handler_by_rank_id(
            0)
        if not self._received_hit:
            return
        watchpoint_hits = self._received_hit
        self._received_hit = []
        for watchpoint_hit in watchpoint_hits:
            watchpoint_hit_stream.put(watchpoint_hit)
        watchpoint_hits_info = {'receive_watchpoint_hits': True}
        self._cache_store.put_data(watchpoint_hits_info)
        log.debug("Send the watchpoint hits to DataQueue.\nSend the reply.")

    def _deal_with_old_command(self):
        """Deal with old command."""
        event = None
        while self._cache_store.has_command(self._pos) and event is None:
            event = self._get_next_command()
            log.debug("Deal with old %s-th command:\n%s.", self._pos, event)
        # deal with continue run command
        if event is None and self._old_run_cmd:
            left_step_count = self._old_run_cmd.get('left_step_count')
            node_name = self._old_run_cmd.get('node_name')
            # node_name and left_step_count should not set at the same time
            if not (left_step_count or node_name) or (left_step_count and node_name):
                log.warning("Invalid old run command. %s", self._old_run_cmd)
                self._old_run_cmd.clear()
                return None
            if left_step_count:
                event = self._deal_with_left_continue_step(left_step_count)
            else:
                event = self._deal_with_left_continue_node(node_name)
            log.debug("Send old RunCMD.")
        return event

    def _deal_with_left_continue_step(self, left_step_count):
        """
        Construct run command with left continue step count.

        Args:
            left_step_count (int): The count of left steps to be executed.

        Returns:
            Event, the run command event.
        """
        event = get_ack_reply()
        event.run_cmd.run_steps = 1
        event.run_cmd.run_level = 'step'
        left_step_count = left_step_count - 1 if left_step_count > 0 else -1
        if not left_step_count:
            self._old_run_cmd.clear()
        else:
            self._old_run_cmd['left_step_count'] = left_step_count
        log.debug("Send old step RunCMD. Left step count: %s", left_step_count)
        return event

    def _deal_with_left_continue_node(self, node_name):
        """
        Construct run command with left continue nodes.

        Args:
            node_name (str): The target node name.

        Returns:
            Union[None, Event], the run command event.
        """
        cur_full_name = self._cache_store.get_stream_handler(Streams.METADATA).full_name
        if cur_full_name == node_name:
            log.info("Execute to target node: %s", node_name)
            self._old_run_cmd.clear()
            return None
        event = get_ack_reply()
        event.run_cmd.run_level = 'node'
        event.run_cmd.node_name = ''
        log.debug("Send old node RunCMD, cur node: %s, target node: %s", cur_full_name, node_name)
        return event

    def _wait_for_next_command(self):
        """
        Wait for next command.

        Returns:
            EventReply, the command event.
        """
        log.info("Start to wait for command.")
        if self._status != ServerStatus.MISMATCH:
            metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
            metadata_stream.state = ServerStatus.WAITING.value
            self._cache_store.put_data(metadata_stream.get())
        event = None
        while event is None and self._status not in [ServerStatus.RUNNING, ServerStatus.PENDING]:
            log.debug("Wait for %s-th command", self._pos)
            event = self._get_next_command()
        return event

    def _get_next_command(self):
        """Get next command."""
        self._pos, event = self._cache_store.get_command(self._pos)
        if event is None:
            return event
        # deal with command
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        if isinstance(event, dict):
            event = self._deal_with_view_cmd(event)
        elif event.HasField('run_cmd'):
            event = self._deal_with_run_cmd(event)
            self._cache_store.put_data(metadata_stream.get())
        elif event.HasField('exit'):
            self._cache_store.clean()
            self._cache_store.put_data(metadata_stream.get())
            log.debug("Clean cache for exit cmd.")
        else:
            event = self._deal_with_set_cmd(event)
            log.debug("get set cmd.")

        return event

    def _deal_with_view_cmd(self, event):
        """
        Deal with view cmd.

        Args:
            event (dict): View command params.

                - view_cmd (EventReply): EventReply with view command.
                - node_name (str): The center node name for view command.
                - tensor_name (str): The center tensor name for view command.
                - graph_name (str): The graph name of center node.

        Returns:
            EventReply, view command to be sent to client.
        """
        view_cmd = event.pop('view_cmd', None)
        log.debug("Receive view cmd for node: %s.", event)
        if not (view_cmd and event):
            log.debug("Invalid view command. Ignore it.")
            return None
        self._received_view_cmd['node_info'] = event
        self._received_view_cmd['wait_for_tensor'] = True
        self._received_view_cmd['view_cmd'] = view_cmd
        level_dict = {
            'stats': ViewCMD.Level.statistics,
            'base': ViewCMD.Level.base
        }
        if event.get('level'):
            view_cmd.view_cmd.level = level_dict.get(event.get('level'))
        return view_cmd

    def _deal_with_run_cmd(self, event):
        """Deal with run cmd."""
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        run_cmd = event.run_cmd
        # receive step command
        if run_cmd.run_level == RunLevel.STEP.value:
            # receive pause cmd
            if not run_cmd.run_steps:
                log.debug("Pause training and wait for next command.")
                self._old_run_cmd.clear()
                # update metadata state from sending to waiting
                metadata_stream.state = ServerStatus.WAITING.value
                return None
            # receive step cmd
            left_steps = run_cmd.run_steps - 1
            event.run_cmd.run_steps = 1
            if left_steps:
                self._old_run_cmd['left_step_count'] = left_steps if left_steps > 0 else -1
        elif run_cmd.node_name:
            self._old_run_cmd['node_name'] = run_cmd.node_name
            run_cmd.node_name = ''
        # clean watchpoint hit cache
        if run_cmd.run_level == RunLevel.RECHECK.value:
            self._cache_store.get_stream_handler(Streams.WATCHPOINT_HIT).get_hit_handler_by_rank_id(0).clean()
            log.debug("Receive RunCMD. Clean watchpoint hit cache.")
        # update metadata state from sending to running
        metadata_stream.state = ServerStatus.RUNNING.value
        return event

    def _deal_with_set_cmd(self, event):
        """
        Deal with set cmd.

        Args:
            event (EventReply): EventReply with set command.

        Returns:
            EventReply, set command to be sent to client.
        """
        set_cmd = event.set_cmd
        watchpoint_stream = self._cache_store.get_stream_handler(Streams.WATCHPOINT)
        watchpoint_stream.clean_cache_set_cmd(set_cmd)
        if set_cmd.delete:
            return event
        # add watch node and condition info into set_cmd
        multi_card_graph_stream = self._cache_store.get_stream_handler(Streams.GRAPH)
        WatchpointOperator.add_set_cmd_detail(set_cmd, watchpoint_stream, multi_card_graph_stream)
        return event

    @debugger_wrap
    def SendMetadata(self, request, context):
        """Send metadata into DebuggerCache."""
        log.info("Received Metadata.")
        if self._status != ServerStatus.PENDING:
            log.info("Re-initialize cache store when new session comes.")
            self.init()

        client_ip = context.peer().split(':', 1)[-1]
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        reply = get_ack_reply()
        if request.training_done:
            log.info("The training from %s has finished.", client_ip)
        else:
            ms_version = request.ms_version
            version_match_stat = version_match(ms_version, mindinsight.__version__)
            if version_match_stat > 1:
                log.warning("Version is mismatched, MindSpore is: %s, MindInsight is: %s",
                            ms_version, mindinsight.__version__)
                self._status = ServerStatus.MISMATCH
                reply.version_matched = False
                metadata_stream.state = ServerStatus.MISMATCH.value
            elif version_match_stat > 0:
                log.warning("Version is not completely matched, MindSpore is: %s, MindInsight is: %s",
                            ms_version, mindinsight.__version__)
                reply.version_matched = True
            else:
                log.info("version is matched.")
                reply.version_matched = True

            metadata_stream.debugger_version = {'ms': ms_version, 'mi': mindinsight.__version__}
            log.debug("Put ms_version from %s into cache.", client_ip)

            metadata_stream.put(request)
            metadata_stream.client_ip = client_ip
            log.debug("Put new metadata from %s into cache.", client_ip)
        # put metadata into data queue
        metadata = metadata_stream.get()
        self._cache_store.put_data(metadata)
        log.debug("Send the reply to %s.", client_ip)
        return reply

    @debugger_wrap
    def SendGraph(self, request_iterator, context):
        """Send graph into DebuggerCache."""
        log.info("Received graph.")
        if self._old_run_cmd:
            log.info("Clear old run command. %s", self._old_run_cmd)
            self._old_run_cmd.clear()
        reply = get_ack_reply()
        if self._status == ServerStatus.MISMATCH:
            log.info("MindSpore and MindInsight is unmatched, waiting for user to terminate the service.")
            return reply
        serial_graph = b""
        for chunk in request_iterator:
            serial_graph += chunk.buffer
        graph = GraphProto.FromString(serial_graph)
        log.debug("Deserialize the graph %s. Receive %s nodes", graph.name, len(graph.node))
        graph_dict = {graph.name: graph}
        self._cache_store.get_stream_handler(Streams.GRAPH).put({0: graph_dict})
        self._cache_store.get_stream_handler(Streams.GRAPH).parse_stack_infos()
        self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0).put_const_vals(
            graph.const_vals)
        self._cache_store.get_stream_handler(Streams.METADATA).graph_name = graph.name
        self._record_parameter_names()
        self._status = ServerStatus.RECEIVE_GRAPH
        log.debug("Send the reply for graph.")
        return reply

    @debugger_wrap
    def SendMultiGraphs(self, request_iterator, context):
        """Send graph into DebuggerCache."""
        log.info("Received multi_graphs.")
        if self._old_run_cmd:
            log.info("Clear old run command. %s", self._old_run_cmd)
            self._old_run_cmd.clear()
        reply = get_ack_reply()
        if self._status == ServerStatus.MISMATCH:
            log.info("MindSpore and MindInsight is unmatched, waiting for user to terminate the service.")
            return reply
        serial_graph = b""
        graph_dict = {}
        for chunk in request_iterator:
            serial_graph += chunk.buffer
            if chunk.finished:
                sub_graph = GraphProto.FromString(serial_graph)
                graph_dict[sub_graph.name] = sub_graph
                log.debug("Deserialize the graph %s. Receive %s nodes", sub_graph.name,
                          len(sub_graph.node))
                serial_graph = b""
                self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0).put_const_vals(
                    sub_graph.const_vals)

        self._cache_store.get_stream_handler(Streams.GRAPH).put({0: graph_dict})
        self._cache_store.get_stream_handler(Streams.GRAPH).parse_stack_infos()
        self._record_parameter_names()
        self._status = ServerStatus.RECEIVE_GRAPH
        log.debug("Send the reply for graph.")
        return reply

    def _record_parameter_names(self):
        """Record parameter full names in tensor handler."""
        parameter_nodes = self._cache_store.get_stream_handler(Streams.GRAPH).get_graph_handler_by_rank_id(0) \
            .search_in_graph(pattern={'node_category': TargetTypeEnum.PARAMETER.value})
        tensor_stream = self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0)
        for node in parameter_nodes:
            tensor_name = [node.full_name + ':0']
            tensor_stream.record_parameter_names(tensor_name)

    @debugger_wrap
    def SendTensors(self, request_iterator, context):
        """Send tensors into DebuggerCache."""
        log.info("Received tensor.")
        tensor_contents = []
        data_size = 0
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        tensor_stream = self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0)
        step = metadata_stream.step
        oversize = False
        node_info = self._received_view_cmd.get('node_info')
        if node_info and node_info.get('load'):
            load_info = node_info.get('load')
            load_info['graph_name'] = node_info.get('graph_name')
            load_info['node_name'] = node_info.get('node_name')
            # The rank_id of online debugger is 0
            load_tensor(load_info=load_info, step=step, request_iterator=request_iterator,
                        cache_store=self._cache_store, rank_id=0)
        else:
            for tensor_proto in request_iterator:
                tensor_contents.append(tensor_proto.tensor_content)
                data_size += len(tensor_proto.tensor_content)
                if data_size >= MAX_SINGLE_TENSOR_CACHE_BYTES or oversize:
                    oversize = True
                    tensor_contents = []
                if tensor_proto.finished:
                    value = get_tensor_value(tensor_proto, tensor_contents, node_info, step, oversize, data_size)
                    update_flag = tensor_stream.put(value)
                    self._update_state(update_flag)
                    tensor_contents = []
                    data_size = 0
                    oversize = False
        reply = get_ack_reply()
        return reply

    @debugger_wrap
    def SendTensorBase(self, request_iterator, context):
        """Send tensor base into DebuggerCache."""
        log.info("Received tensor base.")
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        cur_step = metadata_stream.step
        tensor_stream = self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0)
        tensor_protos = self._received_view_cmd.get('view_cmd').view_cmd.tensors
        tensor_stats_list = []
        for tensor_base in request_iterator:
            tensor_stats_list.append(_convert_tensor_base(tensor_base))
        update_data_flag = put_tensor_base_in_cache(tensor_stats_list, tensor_protos, cur_step, tensor_stream)
        self._update_state(update_data_flag)
        reply = get_ack_reply()
        return reply

    @debugger_wrap
    def SendTensorStats(self, request_iterator, context):
        """Send tensor stats into DebuggerCache."""
        log.info("Received tensor statistic.")
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        cur_step = metadata_stream.step
        tensor_stream = self._cache_store.get_stream_handler(Streams.TENSOR).get_tensor_handler_by_rank_id(0)
        tensor_protos = self._received_view_cmd.get('view_cmd').view_cmd.tensors
        tensor_stats_list = []
        for tensor_summary in request_iterator:
            tensor_stats_list.append({
                'tensor_base': _convert_tensor_base(tensor_summary.tensor_base),
                'tensor_stats': convert_tensor_stats(tensor_summary.statistics)
            })
        update_data_flag = put_tensor_stats_in_cache(tensor_stats_list, tensor_protos, cur_step, tensor_stream)
        self._update_state(update_data_flag)
        reply = get_ack_reply()
        return reply

    def _update_state(self, update_flag):
        """Update wait_for_tensor state."""
        if self._received_view_cmd.get('wait_for_tensor') and update_flag:
            # update_flag is used to avoid querying empty tensors again
            self._received_view_cmd['wait_for_tensor'] = False
            log.debug("Set wait for tensor flag to False.")

    @debugger_wrap
    def SendWatchpointHits(self, request_iterator, context):
        """Send watchpoint hits info DebuggerCache."""
        log.info("Received WatchpointHits. Left run cmd %s change to empty.", self._old_run_cmd)
        self._old_run_cmd.clear()
        if self._cache_store.get_stream_handler(Streams.METADATA).state == ServerStatus.RUNNING.value:
            # if the client session is running a script, all the cached command should be cleared
            # when received watchpoint_hits.
            self._cache_store.clean_command()

        # save the watchpoint_hits data
        watchpoint_hits = []
        watchpoint_stream = self._cache_store.get_stream_handler(Streams.WATCHPOINT)
        graph_stream = self._cache_store.get_stream_handler(Streams.GRAPH).get_graph_handler_by_rank_id(0)
        for watchpoint_hit_proto in request_iterator:
            node_full_name = watchpoint_hit_proto.tensor.node_name
            graph_name = graph_stream.get_graph_id_by_full_name(node_full_name)
            if not graph_name:
                log.warning("Cannot find node %s in graph. Skip it.", node_full_name)
                continue
            ui_node_name = graph_stream.get_node_name_by_full_name(node_full_name, graph_name)
            log.debug("Receive watch point hit: %s", watchpoint_hit_proto)
            if not ui_node_name:
                log.info("Not support to show %s on graph.", node_full_name)
                continue
            watchpoint_hit = {
                'tensor_proto': watchpoint_hit_proto.tensor,
                'watchpoint': copy.deepcopy(watchpoint_stream.get_watchpoint_by_id(watchpoint_hit_proto.id)),
                'node_name': ui_node_name,
                'graph_name': graph_name
            }
            hit_params = {}
            for param in watchpoint_hit_proto.watch_condition.params:
                if param.name not in (ParamNameEnum.RTOL.value, ParamNameEnum.RANGE_START_INCLUSIVE.value,
                                      ParamNameEnum.RANGE_END_INCLUSIVE.value) \
                        and watchpoint_hit_proto.error_code == 0:
                    hit_params[param.name] = param.actual_value
            watchpoint = watchpoint_hit.get('watchpoint', None)
            if not watchpoint:
                return get_ack_reply()
            params = watchpoint.condition.get('params', [])
            for i, param in enumerate(params):
                name = param['name']
                if name in hit_params.keys():
                    watchpoint_hit['watchpoint'].condition['params'][i]['actual_value'] = hit_params[name]
                else:
                    watchpoint_hit['watchpoint'].condition['params'][i]['actual_value'] = None
            watchpoint_hit['error_code'] = watchpoint_hit_proto.error_code
            watchpoint_hits.append(watchpoint_hit)
        self._received_hit = watchpoint_hits
        reply = get_ack_reply()
        return reply

    def SendHeartbeat(self, request, context):
        """Deal with heartbeat sent from training client."""
        # only support single card training now
        if self._heartbeat is None or not self._heartbeat.is_alive():
            period = request.period
            min_period_seconds = 5
            max_period_seconds = 3600
            if not min_period_seconds <= period <= max_period_seconds:
                log.error("Invalid period time which should be in [5, 3600].")
                return get_ack_reply(-1)
            self._heartbeat = HeartbeatListener(self._cache_store, request.period)
            self._heartbeat.start()
        self._heartbeat.send()
        return get_ack_reply()


class HeartbeatListener(threading.Thread):
    """Heartbeat listener."""
    _MAX_TRY_EXCEPT_COUNT = 3

    def __init__(self, cache_store, period=None):
        """
        Initialize Heartbeat listener object.

        Args:
            cache_store (DebuggerCacheStore): Cache store for debugger server.
            period (int): The max waiting seconds for each period.
        """
        super(HeartbeatListener, self).__init__()
        self._heartbeat_queue = Queue(maxsize=1)
        self._cache_store = cache_store
        # the waiting period time for next heartbeat, default waiting for 15 seconds
        time_delay = 0.5
        self._period = period + time_delay if period else 15
        self._running = threading.Event()
        self._running.clear()

    @debugger_server_wrap
    def run(self):
        """Function that should be called when thread started."""
        self._running.set()
        log.info("Start listening for heartbeat.")
        try_count = 0
        while self._running.is_set():
            try:
                self._heartbeat_queue.get(timeout=self._period)
                # reset try count if received heartbeat
                try_count = 0
            except Empty:
                try_count += 1
                if try_count >= self._MAX_TRY_EXCEPT_COUNT:
                    break
                log.info("Missing heartbeat. Try again.")

        log.warning("Missing heartbeat. Reset online session.")
        self._cache_store.clean()
        metadata_stream = self._cache_store.get_stream_handler(Streams.METADATA)
        # put metadata into data queue
        metadata = metadata_stream.get()
        self._cache_store.put_data(metadata)

    def send(self):
        """Send heartbeat signal."""
        try:
            self._heartbeat_queue.put(True, block=False)
        except Full:
            log.debug("Too many heartbeat received.")

    @debugger_server_wrap
    def stop(self):
        """Stop debugger server."""
        self._running.wait()
        log.info("Start to stop offline debugger server.")
        self._running.clear()
        self.send()
        self.join()


def _convert_tensor_base(tensor_data):
    """Convert tensor object to dict."""
    tensor_data_dict = {
        'dtype': tensor_data.data_type,
        'shape': tensor_data.shape,
        'data_size': tensor_data.data_size
    }
    return tensor_data_dict
