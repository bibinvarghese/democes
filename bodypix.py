# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import svgwrite
import re
import PIL
import argparse
from functools import partial
from collections import deque

import numpy as np
import scipy.ndimage
import scipy.misc
from PIL import Image

import gstreamer
from pose_engine import PoseEngine, EDGES

def shadow_text(dwg, x, y, text, font_size=16):
    dwg.add(dwg.text(text, insert=(x + 1, y + 1), fill='black',
                     font_size=font_size, style='font-family:sans-serif'))
    dwg.add(dwg.text(text, insert=(x, y), fill='white',
                     font_size=font_size, style='font-family:sans-serif'))


def draw_pose(dwg, pose, color='blue', threshold=0.2):
    xys = {}
    for label, keypoint in pose.keypoints.items():
        if keypoint.score < threshold: continue
        xys[label] = (int(keypoint.yx[1]), int(keypoint.yx[0]))
        dwg.add(dwg.circle(center=(int(keypoint.yx[1]), int(keypoint.yx[0])), r=5,
                           fill='cyan', stroke=color))

    for a, b in EDGES:
        if a not in xys or b not in xys: continue
        ax, ay = xys[a]
        bx, by = xys[b]
        dwg.add(dwg.line(start=(ax, ay), end=(bx, by), stroke=color, stroke_width=2))

class Callback:
  def __init__(self, engine, anonymize=False):
    self.engine = engine
    self.anonymize = anonymize
    self.order = 1 if anonymize else 0
    self.timing = {
        "last_time" : time.monotonic(),
        "n" : 0,
        "sum_fps" : 0,
        "sum_process_time" : 0,
        "sum_inference_time" : 0
    }
    self.background_image = None

  def __call__(self, image, svg_canvas):
    start_time = time.monotonic()
    results = self.engine.DetectPosesInImage(image)
    poses = results[1]
    inference_time = results[0]
    heatmap, (width, height) = results[2], self.engine.heatmap_size
    heatmap = heatmap.reshape(height, width)
    rescale_factor = np.array(image.shape[0:2])/np.array(heatmap.shape[0:2])
    heatmap = scipy.ndimage.zoom(heatmap, rescale_factor, order=self.order)[:,:,np.newaxis]

    # Rescale heatmap logits and threshold (basically like a relu6)
    heatmap = np.clip(50/254.0 + 100/254.0*heatmap, 0, 1.0)

    if self.anonymize:
      if self.background_image is None:
        self.background_image = np.float32(np.zeros_like(image))
      # Estimate instantaneous background
      background_estimate = (self.background_image*heatmap + image*(1.0-heatmap))

      # Mix into continuous estimate with decay
      ratio = 1/max(1,self.timing["n"]/2.0)
      self.background_image = self.background_image*(1.0-ratio) + ratio*background_estimate
    else:
      self.background_image = image

    body_outlines = 250*np.concatenate([heatmap, heatmap*-0.2, heatmap*-0.2], axis=2)
    output_image = self.background_image+ heatmap*body_outlines
    int_img = np.uint8(np.clip(output_image,0,255))

    end_time = time.monotonic()

    self.timing["n"] += 1
    self.timing["sum_fps"] += 1.0 / (end_time - self.timing["last_time"])
    self.timing["sum_process_time"] += 1000 * (end_time - start_time) - inference_time
    self.timing["sum_inference_time"] += inference_time
    self.timing["last_time"] = end_time
    text_line = 'PoseNet: %.1fms Frame IO: %.2fms TrueFPS: %.2f Nposes %d' % (
        self.timing["sum_inference_time"] / self.timing["n"],
        self.timing["sum_process_time"] / self.timing["n"],
        self.timing["sum_fps"] / self.timing["n"],
        len(poses)
    )

    shadow_text(svg_canvas, 10, 20, text_line)
    for pose in poses:
        draw_pose(svg_canvas, pose)
    print(text_line)
    return int_img

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mirror', help='flip video horizontally', action='store_true')
    parser.add_argument('--model', help='.tflite model path.', required=False)
    parser.add_argument('--res', help='Resolution', default='640x480',
                        choices=['480x360', '640x480', '1280x720'])
    parser.add_argument('--videosrc', help='Which video source to use', default='/dev/video0')
    parser.add_argument('--videotgt', help='Where to write the video to', default='autovideosink')
    parser.add_argument('--anonymize', help='Use anonymizer mode', action='store_true')
    parser.add_argument('--jpg', help='Use image/jpeg input', action='store_true')
    args = parser.parse_args()

    default_model = 'models/posenet_mobilenet_v1_075_%d_%d_quant_decoder_edgetpu.tflite'
    if args.res == '480x360':
        src_size = (640, 480)
        appsink_size = (480, 360)
        model = args.model or default_model % (353, 481)
    elif args.res == '640x480':
        src_size = (640, 480)
        appsink_size = (640, 480)
        model = args.model or default_model % (481, 641)
    elif args.res == '1280x720':
        src_size = (1280, 720)
        appsink_size = (1280, 720)
        model = args.model or default_model % (721, 1281)


    print('Loading model: ', model)
    engine = PoseEngine(model, mirror=args.mirror)
    gstreamer.run_pipeline(Callback(engine, anonymize=args.anonymize),
                           src_size, appsink_size,
                           use_appsrc=True, mirror=args.mirror,
                           videosrc=args.videosrc, jpginput=args.jpg,
                           videotgt=args.videotgt)


if __name__ == '__main__':
    main()
