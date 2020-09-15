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
"""Command module."""
import os
import sys
import argparse

import mindinsight
from mindinsight.mindconverter.converter import main
from mindinsight.mindconverter.graph_based_converter.framework import main_graph_base_converter

from mindinsight.mindconverter.common.log import logger as log


class FileDirAction(argparse.Action):
    """File directory action class definition."""

    @staticmethod
    def check_path(parser_in, values, option_string=None):
        """
        Check argument for file path.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile = values
        if outfile.startswith('~'):
            outfile = os.path.realpath(os.path.expanduser(outfile))

        if not outfile.startswith('/'):
            outfile = os.path.realpath(os.path.join(os.getcwd(), outfile))

        if os.path.exists(outfile) and not os.access(outfile, os.R_OK):
            parser_in.error(f'{option_string} {outfile} not accessible')
        return outfile

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from argparse.Action.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile_dir = self.check_path(parser_in, values, option_string)
        if os.path.isfile(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} is a file')

        setattr(namespace, self.dest, outfile_dir)


class OutputDirAction(argparse.Action):
    """File directory action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from argparse.Action.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        output = values
        if output.startswith('~'):
            output = os.path.realpath(os.path.expanduser(output))

        if not output.startswith('/'):
            output = os.path.realpath(os.path.join(os.getcwd(), output))

        if os.path.exists(output):
            if not os.access(output, os.R_OK):
                parser_in.error(f'{option_string} {output} not accessible')

            if os.path.isfile(output):
                parser_in.error(f'{option_string} {output} is a file')

        setattr(namespace, self.dest, output)


class ProjectPathAction(argparse.Action):
    """Project directory action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from argparse.Action.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile_dir = FileDirAction.check_path(parser_in, values, option_string)
        if not os.path.exists(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} not exists')
        if not os.path.isdir(outfile_dir):
            parser_in.error(f'{option_string} [{outfile_dir}] should be a directory.')

        setattr(namespace, self.dest, outfile_dir)


class InFileAction(argparse.Action):
    """Input File action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from argparse.Action.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile_dir = FileDirAction.check_path(parser_in, values, option_string)
        if not os.path.exists(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} not exists')

        if not os.path.isfile(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} is not a file')

        setattr(namespace, self.dest, outfile_dir)


class ModelFileAction(argparse.Action):
    """Model File action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from argparse.Action.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile_dir = FileDirAction.check_path(parser_in, values, option_string)
        if not os.path.exists(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} not exists')

        if not os.path.isfile(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} is not a file')

        if not outfile_dir.endswith('.pth'):
            parser_in.error(f"{option_string} {outfile_dir} should be a Pytorch model, ending with '.pth'.")

        setattr(namespace, self.dest, outfile_dir)


class LogFileAction(argparse.Action):
    """Log file action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from FileDirAction.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        outfile_dir = FileDirAction.check_path(parser_in, values, option_string)
        if os.path.exists(outfile_dir) and not os.path.isdir(outfile_dir):
            parser_in.error(f'{option_string} {outfile_dir} is not a directory')
        setattr(namespace, self.dest, outfile_dir)


class ShapeAction(argparse.Action):
    """Shape action class definition."""

    def __call__(self, parser_in, namespace, values, option_string=None):
        """
        Inherited __call__ method from FileDirAction.

        Args:
            parser_in (ArgumentParser): Passed-in argument parser.
            namespace (Namespace): Namespace object to hold arguments.
            values (object): Argument values with type depending on argument definition.
            option_string (str): Optional string for specific argument name. Default: None.
        """
        in_shape = None
        shape_str = values
        try:
            in_shape = [int(num_shape) for num_shape in shape_str.split(',')]
        except ValueError:
            parser_in.error(
                f"{option_string} {shape_str} should be a list of integer split by ',', check it please.")
        setattr(namespace, self.dest, in_shape)


parser = argparse.ArgumentParser(
        prog='mindconverter',
        description='MindConverter CLI entry point (version: {})'.format(mindinsight.__version__))

parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s ({})'.format(mindinsight.__version__))

parser.add_argument(
        '--in_file',
        type=str,
        action=InFileAction,
        required=False,
        default=None,
        help="""
            Specify path for script file to use AST schema to 
            do script conversation.
        """)

parser.add_argument(
        '--model_file',
        type=str,
        action=ModelFileAction,
        required=False,
        help="""
            PyTorch .pth model file path to use graph 
            based schema to do script generation. When 
            `--in_file` and `--model_file` are both provided,
            use AST schema as default.
        """)

parser.add_argument(
        '--shape',
        type=str,
        action=ShapeAction,
        default=None,
        required=False,
        help="""
            Optional, excepted input tensor shape of
            `--model_file`. It's required when use graph based
            schema. 
            Usage: --shape 3,244,244
        """)

parser.add_argument(
        '--output',
        type=str,
        action=OutputDirAction,
        default=os.path.join(os.getcwd(), 'output'),
        help="""
            Optional, specify path for converted script file 
            directory. Default output directory is `output` folder 
            in the current working directory.
        """)

parser.add_argument(
        '--report',
        type=str,
        action=LogFileAction,
        default=None,
        help="""
            Optional, specify report directory. Default is 
            converted script directory.
        """)

parser.add_argument(
        '--project_path',
        type=str,
        action=ProjectPathAction,
        required=False,
        default=None,
        help="""
            Optional, PyTorch scripts project path. If PyTorch
            project is not in PYTHONPATH, please assign
            `--project_path` when use graph based schema. 
            Usage: --project_path ~/script_file/
        """)


def cli_entry():
    """Entry point for mindconverter CLI."""

    permissions = os.R_OK | os.W_OK | os.X_OK
    os.umask(permissions << 3 | permissions)

    argv = sys.argv[1:]
    if not argv:
        argv = ['-h']
        args = parser.parse_args(argv)
    else:
        args = parser.parse_args()
    mode = permissions << 6
    os.makedirs(args.output, mode=mode, exist_ok=True)
    if args.report is None:
        args.report = args.output
    os.makedirs(args.report, mode=mode, exist_ok=True)
    _run(args.in_file, args.model_file, args.shape, args.output, args.report, args.project_path)


def _run(in_files, model_file, shape, out_dir, report, project_path):
    """
    Run converter command.

    Args:
        in_files (str): The file path or directory to convert.
        model_file(str): The pytorch .pth to convert on graph based schema.
        shape(list): The input tensor shape of module_file.
        out_dir (str): The output directory to save converted file.
        report (str): The report file path.
        project_path(str): Pytorch scripts project path.
    """
    if in_files:
        files_config = {
            'root_path': in_files,
            'in_files': [],
            'outfile_dir': out_dir,
            'report_dir': report if report else out_dir
        }

        if os.path.isfile(in_files):
            files_config['root_path'] = os.path.dirname(in_files)
            files_config['in_files'] = [in_files]
        else:
            for root_dir, _, files in os.walk(in_files):
                for file in files:
                    files_config['in_files'].append(os.path.join(root_dir, file))
        main(files_config)

    elif model_file:
        file_config = {
            'model_file': model_file,
            'shape': shape if shape else [],
            'outfile_dir': out_dir,
            'report_dir': report if report else out_dir
        }
        if project_path:
            paths = sys.path
            if project_path not in paths:
                sys.path.append(project_path)

        main_graph_base_converter(file_config)

    else:
        error_msg = "`--in_file` and `--model_file` should be set at least one."
        error = FileNotFoundError(error_msg)
        log.error(str(error))
        log.exception(error)
        raise error
