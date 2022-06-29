#!/usr/bin/env python3

import sys
sys.path.append('../')
import gi
import configparser
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from gi.repository import GLib
from ctypes import *
import time
import math
import cv2
import numpy as np
import platform
from common.bus_call import bus_call
from common.create_element_or_error import create_element_or_error
import pyds

def main(args):

    # Standard GStreamer initialization
    cameras_list = [
        { "source": 0, "name": "camera1" },
        { "source": 1, "name": "camera2" },
    ]
    
    GObject.threads_init()
    Gst.init(None)

    pipeline = Gst.Pipeline()

    # Muxer
    muxer = create_element_or_error("nvstreammux", "muxer")
    muxer.set_property('live-source', True)
    muxer.set_property('sync-inputs', True)
    muxer.set_property('width', 720)
    muxer.set_property('height', 480)
    muxer.set_property('batch-size', 3)
    muxer.set_property('batched-push-timeout', 4000000)
    pipeline.add(muxer)

    # Primart Inferance
    pgie = create_element_or_error("nvinfer", "primary-inference")
    pgie.set_property('config-file-path', "/opt/nvidia/deepstream/deepstream-5.1/samples/configs/deepstream-app/config_infer_primary.txt")
    pipeline.add(pgie)
    muxer.link(pgie)

    #Tracker
    tracker = create_element_or_error("nvtracker", "tracker")
    tracker.set_property('ll-lib-file', '/opt/nvidia/deepstream/deepstream-5.1/lib/libnvds_mot_klt.so')
    tracker.set_property('gpu-id', 0)
    tracker.set_property('enable-past-frame', 1)
    tracker.set_property('enable-batch-process', 1)
    pipeline.add(tracker)
    pgie.link(tracker)

    #Analitics
    analytics = create_element_or_error("nvdsanalytics", "analytics")
    analytics.set_property("config-file", "./../Analitycs/analitycs.txt")
    pipeline.add(analytics)
    tracker.link(analytics)

    # Converter
    converterOsd = create_element_or_error("nvvideoconvert", "to-osd-convertor")
    pipeline.add(converterOsd)
    analytics.link(converterOsd)

    # Demuxer
    demux = create_element_or_error("nvstreamdemux", "demuxer")
    pipeline.add(demux)
    converterOsd.link(demux)

    # Sources
    for camera in cameras_list:
        source = create_element_or_error("nvarguscamerasrc", "source-" + camera['name'])
        source.set_property('sensor-id', camera['source'])

        caps = create_element_or_error("capsfilter", "source-caps-" + camera['name'])
        caps.set_property("caps", Gst.Caps.from_string("video/x-raw(memory:NVMM), width=(int)1920, height=(int)1080, framerate=(fraction)30/1, format=(string)NV12"))

        source.set_property('do-timestamp', True)
        source.set_property('bufapi-version', True)
        source.set_property('tnr-mode', 2)
        source.set_property('ee-mode', 2)
        source.set_property('aeantibanding', 0)

        pipeline.add(source)
        pipeline.add(caps)

        source.link(caps)
        
        srcpad = caps.get_static_pad("src")
        sinkpad = muxer.get_request_pad('sink_' + str(camera['source']))

        if not sinkpad:
            print("Unable to create source sink pad")
            exit(0)
        if not srcpad:
            print("Unable to create source src pad")
            exit(0)
        srcpad.link(sinkpad)
    

    # Outputs
    for camera in cameras_list:

        queue = create_element_or_error("queue", "queue-" + camera['name'])
        pipeline.add(queue)

        _srcpad = demux.get_request_pad("src_" + str(camera['source']))
        if not _srcpad:
            print("Unable to create output src pad")
            exit(0)

        _sinkpad = queue.get_static_pad('sink')
        if not _sinkpad:
            print("Unable to create output sink pad")
            exit(0)

        _srcpad.link(_sinkpad)

        # Converter
        converter = create_element_or_error("nvvideoconvert", "converter-" + camera['name'])
        pipeline.add(converter)
        queue.link(converter)

        # Nvosd
        nvosd = create_element_or_error("nvdsosd", "on-screen-display" + camera['name'])
        pipeline.add(nvosd)
        converter.link(nvosd)

        # Transform
        transform = create_element_or_error("nvegltransform", "nvegl-transform-" + camera['name'])
        pipeline.add(transform)
        nvosd.link(transform)

        # Sink
        sink = create_element_or_error("nveglglessink", "sink-" + camera['name'])
        sink.set_property('sync', False)
        pipeline.add(sink)
        transform.link(sink)

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    # List the sources
    print("Starting pipeline")
    pipeline.set_state(Gst.State.PLAYING)

    try:
        loop.run()
    except:
        pass
        
    # cleanup
    pipeline.set_state(Gst.State.NULL)

    print("Exiting app")
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))