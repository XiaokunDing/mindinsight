# Copyright 2020 Huawei Technologies Co., Ltd
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
"""Conditionmgr restful api."""
from flask import Blueprint

from mindinsight.conf import settings
from mindinsight.backend.debugger.debugger_api import BACKEND_SERVER, _wrap_reply

BLUEPRINT = Blueprint("conditionmgr", __name__,
                      url_prefix=settings.URL_PATH_PREFIX + settings.API_PREFIX)


@BLUEPRINT.route("/conditionmgr/train-jobs/<train_id>/conditions", methods=["GET"])
def get_conditions(train_id):
    """get conditions"""
    reply = _wrap_reply(BACKEND_SERVER.get_conditions, train_id)
    return reply


@BLUEPRINT.route("/conditionmgr/train-jobs/<train_id>/condition-collections", methods=["GET"])
def get_condition_collections(train_id):
    """get condition collections"""
    reply = _wrap_reply(BACKEND_SERVER.get_condition_collections, train_id)
    return reply


def init_module(app):
    """
    Init module entry.

    Args:
        app (Flask): The application obj.
    """
    app.register_blueprint(BLUEPRINT)
