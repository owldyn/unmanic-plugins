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
import re
import subprocess

from unmanic.libs.unplugins.settings import PluginSettings

from encoder_video_av1.lib.ffmpeg.parser import Parser
from encoder_video_av1.lib.ffmpeg.probe import Probe
from encoder_video_av1.lib.ffmpeg.stream_mapper import StreamMapper

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.encoder_video_libvpx_vp9")


class Settings(PluginSettings):
    settings = {
        "crf":      "30",
        "preset": "6",
        "auto-crop": False,
        "10-bit": True,
    }
    form_settings = {
        "crf":      {
            "label":         "Constant Rate Factor (CRF)",
            "input_type":    "range",
            "range_options": {
                "min": 0,
                "max": 63,
            },
        },
        "preset": {
            "label":         "preset",
            "input_type":    "range",
            "range_options": {
                "min": 0,
                "max": 8,
            },
        },
        "auto-crop": {
            "label":         "Auto Crop Black Bars",
            "input_type":    "checkbox",
        },
        "10-bit": {
            "label":         "10 bit encoding",
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
        if stream_info.get('codec_name').lower() in ['vp9', 'av1']:
            return False
        return True

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        # Default settings for 'Average Bitrate' encoder mode
        # stream_encoding = ['-c:v:{}'.format(stream_id), 'libvpx-vp9', '-b:v', '2M']

        # Set stream encoder bitrate
        encoder_mode = self.settings.get_setting('mode')
        # All encoders share these settings.
        stream_encoding = [
                '-c:v:{}'.format(stream_id), 'libsvtav1',
                '-preset', self.settings.get_setting('preset'),
                '-qp', self.settings.get_setting('crf'),
        ]
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

def conv_duration(duration):
    duration_list = duration.split(':')
    duration = 0
    duration += float(duration_list[0]) * 60 * 60
    duration += float(duration_list[1]) * 60
    duration += float(duration_list[2])
    return duration

def get_video_stream_data(streams, format):
    width = 0
    height = 0
    video_stream_index = 0
    for stream in streams:
        if stream.get('codec_type') == 'video':
            width = stream.get('width', stream.get('coded_width', 0))
            height = stream.get('height', stream.get('coded_height', 0))
            # Multiple places duration could be, apparently?
            duration = format.get('duration')
            if duration:
                duration = float(duration)
            else:
                duration = stream.get('tags', {}).get('DURATION')
                duration = conv_duration(duration)
            break

    return duration, width, height

def detect_black_bars(abspath, probe):
    """
    Detect if black bars exist

    Fetch the current video width/height from the file probe


    :param abspath:
    :param probe_data:
    :return:
    """
    logger = logging.getLogger("Unmanic.Plugin.video_transcoder")
    probe_data = probe.get_probe()

    # TODO: Detect video duration. Base the ss param off the duration of the video in the probe data
    duration, v_width, v_height = get_video_stream_data(probe_data.get('streams'), probe_data.get('format'))
    timestamps = [duration/i for i in range(2,6)]
    crop_values = []
    for timestamp in timestamps:
        # Run a ffmpeg command to cropdetect
        mapper = StreamMapper(logger, ['video', 'audio', 'subtitle', 'data', 'attachment'])
        mapper.set_input_file(abspath)
        mapper.set_ffmpeg_generic_options(**{"-ss": str(timestamp)})
        mapper.set_ffmpeg_advanced_options(**{"-vframes": '100', '-vf': 'cropdetect=round=2'})
        mapper.set_output_null()

        # Build ffmpeg command for detecting black bars
        # TODO: See if we can support hardware decoding here
        ffmpeg_args = mapper.get_ffmpeg_args()
        ffmpeg_command = ['ffmpeg'] + ffmpeg_args
        # Execute ffmpeg
        pipe = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = pipe.communicate()
        raw_results = out.decode("utf-8")

        # Parse the output of the ffmpeg command -read the crop value, crop width and crop height into variables
        crop_value = None
        regex = re.compile(r'\[Parsed_cropdetect.*\].*crop=(\d+:\d+:\d+:\d+)')
        findall = re.findall(regex, raw_results)
        if findall:
            crop_values.append(findall[-1])
        else:
            logger.error("Unable to parse cropdetect from FFmpeg on file %s.", abspath)
    final_crop_value = None
    for value in crop_values:
        crop_split = value.split(':')
        crop_width = int(crop_split[0])
        crop_height = int(crop_split[1])
        crop_x = int(crop_split[2])
        crop_y = int(crop_split[3])

        if crop_width < 0 or crop_height < 0:
            continue
        if not final_crop_value:
            final_crop_value = value
        else:
            final_crop_split = final_crop_value.split(':')
            final_crop_width = int(final_crop_split[0])
            final_crop_height = int(final_crop_split[1])
            # We want the crop that takes the most away, but in a sane way.
            # Since the vast majority of black bars will be on the top and bottom
            # We'll assume widest and shortest is correct, as long as it is more than 50% the original height.
            if crop_height > (v_height/2):
                if final_crop_width <= crop_width:
                    final_crop_value = value
                elif final_crop_height > crop_height:
                    if (final_crop_width*0.95) <= crop_width:
                        final_crop_value = value


    if final_crop_value:
        crop_split = final_crop_value.split(':')
        crop_width = int(crop_split[0])
        crop_height = int(crop_split[1])
        crop_x = int(crop_split[2])
        crop_y = int(crop_split[3])

        # If the crop starting positions (x, y) are 0, return None.
        # This may cause issues if the video is for some reason just on the top left? but I'm fine with that.
        if crop_x == 0 and crop_y == 0:
            # Video is already cropped to the correct resolution
            logger.debug("File '%s' is already cropped to the resolution %sx%s.", abspath, crop_width, crop_height)
            return None

    return final_crop_value

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

        # Set the output file
        # Do not remux the file. Keep the file out in the same container
        split_file_in = os.path.splitext(abspath)
        split_file_out = os.path.splitext(data.get('file_out'))

        output_file_path = f'{split_file_out[0]}{split_file_in[1]}'
        if settings.get_setting('auto-crop'):
            crop_value = detect_black_bars(abspath, probe)
            if crop_value:
                mapper.stream_encoding.extend(['-vf', f'crop={crop_value}'])

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
