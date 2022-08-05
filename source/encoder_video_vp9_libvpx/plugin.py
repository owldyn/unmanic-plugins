#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     11 Aug 2021, (7:09 AM)

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

from encoder_video_vp9_libvpx.lib.ffmpeg import StreamMapper, Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.encoder_video_vp9_libvpx")


class Settings(PluginSettings):
    settings = {
        "advanced":              False,
        "crf":                   23,
        "deadline":              "good",
        "main_options":          "",
        "advanced_options":      "",
        "custom_options":        "",
        "keep_container":        True,
        "dest_container":        "mkv",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "advanced":              {
                "label": "Write your own FFmpeg params",
            },
            "crf":                   self.__set_crf_form_settings(),
            "deadline":              self.__set_deadline_form_settings(),
            "main_options":          self.__set_main_options_form_settings(),
            "advanced_options":      self.__set_advanced_options_form_settings(),
            "custom_options":        self.__set_custom_options_form_settings(),
            "keep_container":        {
                "label": "Keep the same container",
            },
            "dest_container":        self.__set_destination_container(),
        }

    def __set_crf_form_settings(self):
        values = {
            "label":          "Constant Rate Factor (CRF)",
            "input_type":     "slider",
            "slider_options": {
                "min": 0,
                "max": 51,
            },
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_deadline_form_settings(self):
        values = {
            "label":          "Quality deadline",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "best",
                    'label': "Best",
                },
                {
                    'value': "good",
                    'label': "Good",
                },
                {
                    'value': "realtime",
                    'label': "Realtime",
                },
            ],
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_main_options_form_settings(self):
        values = {
            "label":      "Write your own custom main options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_advanced_options_form_settings(self):
        values = {
            "label":      "Write your own custom advanced options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_custom_options_form_settings(self):
        values = {
            "label":      "Write your own custom video options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_destination_container(self):
        values = {
            "label":          "Set the output container",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "mkv",
                    'label': ".mkv - Matroska",
                },
            ],
        }
        if self.get_setting('keep_container'):
            values["display"] = 'hidden'
        return values


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
        elif stream_info.get('codec_name').lower() in ['vp9', 'vp9 (Profile 2)', 'yuv420p10le(tv, bt709, progressive)', 'vp9 (Profile 2), yuv420p10le(tv, bt709, progressive)']:
            return False
        return True

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        if self.settings.get_setting('advanced'):
            stream_encoding = ['-c:v:{}'.format(stream_id), 'libvpx-vp9']
            stream_encoding += self.settings.get_setting('custom_options').split()
        else:
            stream_encoding = [
                '-c:v:{}'.format(stream_id), 'libvpx-vp9',
                '-deadline', str(self.settings.get_setting('deadline')),
                '-crf', str(self.settings.get_setting('crf')),
            ]
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
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

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
        exec_command            - A command that Unmanic should execute. Can be empty.
        command_progress_parser - A function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - The source file to be processed by the command.
        file_out                - The destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - The absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

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

        # Set the output file
        if settings.get_setting('keep_container'):
            # Do not remux the file. Keep the file out in the same container
            mapper.set_output_file(data.get('file_out'))
        else:
            # Force the remux to the configured container
            container_extension = settings.get_setting('dest_container')
            split_file_out = os.path.splitext(data.get('file_out'))
            new_file_out = "{}.{}".format(split_file_out[0], container_extension.lstrip('.'))
            mapper.set_output_file(new_file_out)
            data['file_out'] = new_file_out

        # Setup the advanced settings (this will overwrite a lot of other settings)
        if settings.get_setting('advanced'):

            # If any main options are provided, overwrite them
            main_options = settings.get_setting('main_options').split()
            if main_options:
                # Overwrite all main options
                mapper.main_options = main_options

            advanced_options = settings.get_setting('advanced_options').split()
            if advanced_options:
                # Overwrite all main options
                mapper.advanced_options = advanced_options

        else:
            advanced_kwargs = {'-pix_fmt': 'yuv420p10le',
                               '-speed': '0',
                               '-threads': '4'
                            }
            mapper.set_ffmpeg_advanced_options(**advanced_kwargs)

        # Get generated ffmpeg args
        ffmpeg_args = mapper.get_ffmpeg_args()

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data
