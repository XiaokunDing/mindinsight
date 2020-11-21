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
"""Datafile encapsulator."""

import os
import io

from PIL import Image
from PIL import UnidentifiedImageError
import numpy as np

from mindinsight.utils.exceptions import UnknownError
from mindinsight.utils.exceptions import FileSystemPermissionError
from mindinsight.datavisual.common.exceptions import ImageNotExistError
from mindinsight.explainer.encapsulator.explain_data_encap import ExplainDataEncap

# Max uint8 value. for converting RGB pixels to [0,1] intensity.
_UINT8_MAX = 255

# Color of low saliency.
_SALIENCY_CMAP_LOW = (55, 25, 86, 255)

# Color of high saliency.
_SALIENCY_CMAP_HI = (255, 255, 0, 255)

# Channel modes.
_SINGLE_CHANNEL_MODE = "L"
_RGBA_MODE = "RGBA"
_RGB_MODE = "RGB"

_PNG_FORMAT = "PNG"


def _clean_train_id_b4_join(train_id):
    """Clean train_id before joining to a path."""
    if train_id.startswith("./") or train_id.startswith(".\\"):
        return train_id[2:]
    return train_id


class DatafileEncap(ExplainDataEncap):
    """Datafile encapsulator."""

    def query_image_binary(self, train_id, image_path, image_type):
        """
        Query image binary content.

        Args:
            train_id (str): Job ID.
            image_path (str): Image path relative to explain job's summary directory.
            image_type (str): Image type, 'original' or 'overlay'.

        Returns:
            bytes, image binary.
        """

        abs_image_path = os.path.join(self.job_manager.summary_base_dir,
                                      _clean_train_id_b4_join(train_id),
                                      image_path)

        if self._is_forbidden(abs_image_path):
            raise FileSystemPermissionError("Forbidden.")

        try:

            if image_type != "overlay":
                # no need to convert
                with open(abs_image_path, "rb") as fp:
                    return fp.read()

            image = Image.open(abs_image_path)

            if image.mode == _RGBA_MODE:
                # It is RGBA already, do not convert.
                with open(abs_image_path, "rb") as fp:
                    return fp.read()

        except FileNotFoundError:
            raise ImageNotExistError(image_path)
        except PermissionError:
            raise FileSystemPermissionError(image_path)
        except UnidentifiedImageError:
            raise UnknownError(f"Invalid image file: {image_path}")

        if image.mode == _SINGLE_CHANNEL_MODE:
            saliency = np.asarray(image)/_UINT8_MAX
        elif image.mode == _RGB_MODE:
            saliency = np.asarray(image)
            saliency = saliency[:, :, 0]/_UINT8_MAX
        else:
            raise UnknownError(f"Invalid overlay image mode:{image.mode}.")

        rgba = np.empty((saliency.shape[0], saliency.shape[1], 4))
        for c in range(3):
            rgba[:, :, c] = saliency
        rgba = rgba * _SALIENCY_CMAP_HI + (1-rgba) * _SALIENCY_CMAP_LOW
        rgba[:, :, 3] = saliency * _UINT8_MAX

        overlay = Image.fromarray(np.uint8(rgba), mode=_RGBA_MODE)
        buffer = io.BytesIO()
        overlay.save(buffer, format=_PNG_FORMAT)

        return buffer.getvalue()

    def _is_forbidden(self, path):
        """Check if the path is outside summary base dir."""
        base_dir = os.path.realpath(self.job_manager.summary_base_dir)
        path = os.path.realpath(path)
        return not path.startswith(base_dir)