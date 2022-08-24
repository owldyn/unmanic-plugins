#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     30 Jul 2021, (9:34 AM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging
import os

from unmanic.libs.unplugins.settings import PluginSettings

from encoder_video_libvpx_vp9.lib.ffmpeg.parser import Parser
from encoder_video_libvpx_vp9.lib.ffmpeg.probe import Probe
from encoder_video_libvpx_vp9.lib.ffmpeg.stream_mapper import StreamMapper


# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.encoder_video_libvpx_vp9")


class Settings(PluginSettings):
    settings = {
        "mode":     "constrained_quality",
        "crf":      "30",
        "bitrate":  "2M",
        "deadline": "good",
        "cpu-used": "0",
        "row-mt": False,
        "threads": "4",
        "10-bit": False,
        "2-pass": True,
    }
    form_settings = {
        "mode":     {
            "label":          "Encoding Mode",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "average_bitrate",
                    'label': "Variable Bitrate (VBR)",
                },
                {
                    'value': "constant_quality",
                    'label': "Constant Quantizer (Q)",
                },
                {
                    'value': "constrained_quality",
                    'label': "Constrained Quality (CQ)",
                },
                {
                    'value': "constant_bitrate",
                    'label': "Constant Bitrate (CBR)",
                },
                {
                    'value': "lossless",
                    'label': "Lossless VP9",
                },
            ],
        },
        "crf":      {
            "label":         "Constant Rate Factor (CRF)",
            "input_type":    "range",
            "range_options": {
                "min": 0,
                "max": 63,
            },
        },
        "bitrate":  {
            "label": "Bitrate",
        },
        "deadline": {
            "label":          "Deadline / Quality",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "good",
                    'label': "good",
                },
                {
                    'value': "best",
                    'label': "best",
                },
                {
                    'value': "realtime",
                    'label': "realtime",
                },
            ],
        },
        "cpu-used": {
            "label":         "CPU Utilization / Speed",
            "input_type":    "range",
            "range_options": {
                "min": 0,
                "max": 5,
            },
        },
        "row-mt": {
            "label":         "Row Multi-threading",
            "input_type":    "checkbox",
        },
        "threads": {
            "label":         "How Many Threads",
            "input_type":    "range",
            "range_options": {
                "min": 0,
                "max": 8,
            },
        },
        "10-bit": {
            "label":         "10 bit encoding (requires support in ffmpeg)",
            "input_type":    "checkbox",
        },
        "2-pass": {
            "label":         "2-pass encoding",
            "input_type":    "checkbox",
        },
    }


class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, ['video'])
        self.settings = None
        self.image_video_codecs = [
            'alias_pix',
            'apng',
            'brender_pix',
            'dds',
            'dpx',
            'exr',
            'fits',
            'gif',
            'mjpeg',
            'mjpegb',
            'pam',
            'pbm',
            'pcx',
            'pfm',
            'pgm',
            'pgmyuv',
            'pgx',
            'photocd',
            'pictor',
            'pixlet',
            'png',
            'ppm',
            'ptx',
            'sgi',
            'sunrast',
            'tiff',
            'vc1image',
            'wmv3image',
            'xbm',
            'xface',
            'xpm',
            'xwd',
        ]

    def set_settings(self, settings):
        self.settings = settings

    def test_stream_needs_processing(self, stream_info: dict):
        if stream_info.get('codec_name').lower() in self.image_video_codecs:
            return False
        if stream_info.get('codec_name').lower() in ['vp9']:
            return False
        return True

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        # Default settings for 'Average Bitrate' encoder mode
        # stream_encoding = ['-c:v:{}'.format(stream_id), 'libvpx-vp9', '-b:v', '2M']

        # Set stream encoder bitrate
        encoder_mode = self.settings.get_setting('mode')
        # All encoders share these settings.
        stream_encoding = [
                '-c:v:{}'.format(stream_id), 'libvpx-vp9',
                '-threads', self.settings.get_setting('threads'),
                '-row-mt', '1' if self.settings.get_setting('row-mt') else '0',
                '-deadline', self.settings.get_setting('deadline'),
                '-cpu-used', self.settings.get_setting('cpu-used')
        ]

        if encoder_mode == 'average_bitrate':
            stream_encoding.extend([
                '-b:v:{}'.format(stream_id), self.settings.get_setting('bitrate'),
            ])
        elif encoder_mode == 'constant_quality':
            stream_encoding.extend([
                '-crf', self.settings.get_setting('crf'),
                '-b:v:{}'.format(stream_id), '0',
            ])
        elif encoder_mode == 'constrained_quality':
            stream_encoding.extend([
                '-crf', self.settings.get_setting('crf'),
                '-b:v:{}'.format(stream_id), self.settings.get_setting('bitrate'),
            ])
        elif encoder_mode == 'constant_bitrate':
            stream_encoding.extend([
                '-minrate', self.settings.get_setting('bitrate'),
                '-maxrate', self.settings.get_setting('bitrate'),
                '-b:v:{}'.format(stream_id), self.settings.get_setting('bitrate'),
            ])
        elif encoder_mode == 'lossless':
            stream_encoding.extend([
                '-lossless', '1',
            ])

        if self.settings.get_setting("10-bit"):
            stream_encoding.extend(
                ['-pix_fmt', 'yuv420p10le']
            )
        return {
            'stream_mapping':  ['-map', '0:v:{}'.format(stream_id)],
            'stream_encoding': stream_encoding,
        }


def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    probe.file(abspath)

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_settings(settings)
    mapper.set_probe(probe)

    if mapper.streams_need_processing():
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
    else:
        logger.debug("File '{}' does not contain streams require processing.".format(abspath))

    return data


def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        exec_ffmpeg             - Boolean, should Unmanic run FFMPEG with the data returned from this plugin.
        file_probe              - A dictionary object containing the current file probe state.
        ffmpeg_args             - A list of Unmanic's default FFMPEG args.
        file_in                 - The source file to be processed by the FFMPEG command.
        file_out                - The destination that the FFMPEG command will output.
        original_file_path      - The absolute path to the original library file.

    :param data:
    :return:
    
    """
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    # DEPRECIATED: 'exec_ffmpeg' kept for legacy Unmanic versions
    data['exec_ffmpeg'] = False

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    probe.file(abspath)

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_settings(settings)
    mapper.set_probe(probe)

    if mapper.streams_need_processing():
        # Set the input file
        mapper.set_input_file(abspath)
        two_pass_subfix = "-0.log" # TODO check all numbers not just 0, just in case.

        # Set the output file
        # Do not remux the file. Keep the file out in the same container
        split_file_in = os.path.splitext(abspath)
        split_file_out = os.path.splitext(data.get('file_out'))

        output_file_path = f'{split_file_out[0]}{split_file_in[1]}'

        if settings.settings.get('2-pass'):
            two_pass_folder_split = os.path.split(data.get('file_out'))
            two_pass_file_split = os.path.split(abspath)
            two_pass_log_file_path = f'{two_pass_folder_split[0]}/{two_pass_file_split[1]}'
            data['repeat'] = True

            if os.path.exists(f'{two_pass_log_file_path}{two_pass_subfix}'):
                mapper.set_output_file(output_file_path)
                two_pass_args = ['-pass', '2', '-passlogfile', f'{two_pass_log_file_path}']
                data['repeat'] = False
            else:
                mapper.set_output_null()
                two_pass_args = ['-pass', '1', '-passlogfile', f'{two_pass_log_file_path}', '-an']
            mapper.stream_encoding.extend(two_pass_args)
        else:
            data['repeat'] = False
            mapper.set_output_file(output_file_path)

        # Get generated ffmpeg args
        ffmpeg_args = mapper.get_ffmpeg_args()
        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args
        # DEPRECIATED: 'ffmpeg_args' kept for legacy Unmanic versions
        data['ffmpeg_args'] = ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data
