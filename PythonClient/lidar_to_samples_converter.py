#!/usr/bin/env python

import os
import json
import numpy as np


dirs = [
    '_lidars_town_2'
]

lidar_name = 'Lidar32'
lidar_channels = 32
lidar_points_per_second = 640000
lidar_frequency = 10
point_in_one_channel_per_circle = lidar_points_per_second / lidar_frequency / lidar_channels
print(point_in_one_channel_per_circle)

result_dir = '_samples/'
if not os.path.isdir(result_dir):
    os.makedirs(result_dir)


def write_sample(sample, filepath):
    points = np.zeros((32, 0, 5)).astype(np.float32)

    for packet in sample:
        points_per_channel = packet['points_count_by_channel'][0]

        ring_number = []
        for i in range(lidar_channels):
            ring_number += [i] * points_per_channel
        ring_number = np.array(ring_number).astype(np.float32).reshape((-1, 1))

        # cut to circle
        new_points = np.concatenate([
            np.array(packet['points']).astype(np.float32).reshape((-1, 3)),
            np.array(packet['labels']).astype(np.float32).reshape((-1, 1)),
            ring_number
        ], axis=1).reshape((32, -1, 5))

        points = np.concatenate([
            points,
            new_points
        ], axis=1)

    print(points.shape)
    points = points[:, -point_in_one_channel_per_circle:, :]
    print(points.shape)
    points = points.reshape((-1, 5))
    print(points.shape)
    with open(filepath, 'wb') as f:
        f.write(points)


def main():

    sample = []
    captured_points = 0
    sample_i = 0

    for d in dirs:
        for episode_i in range(1, 100):
            episode_i_str = '%03d' % episode_i
            for li in range(1, 100000):
                frame_i_str = '%05d' % li
                lidar_file_path = os.path.join(d, 'episode_' + episode_i_str, lidar_name, 'lidar_' + frame_i_str) + '.json'
                if os.path.exists(lidar_file_path):
                    print(lidar_file_path)
                    with open(lidar_file_path, 'rt') as f:
                        packet = json.loads(f.read())

                    sample.append(packet)
                    point_count = packet['points_count_by_channel'][0]
                    captured_points += point_count

                    if captured_points >= point_in_one_channel_per_circle:
                        print('--- sample {}'.format(len(sample)))
                        write_sample(sample, os.path.join(result_dir, 'sample_' + str(sample_i) + '.bin'))
                        sample_i += 1
                        sample = []
                        captured_points = 0

                else:
                    break


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')
