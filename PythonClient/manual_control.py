#!/usr/bin/env python3

# Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB), and the INTEL Visual Computing Lab.
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

# Keyboard controlling for carla. Please refer to client_example for a simpler
# and more documented example.

"""
Welcome to CARLA manual control.

Use ARROWS or WASD keys for control.

    W            : throttle
    S            : brake
    AD           : steer
    Q            : toggle reverse
    Space        : hand-brake

    R            : restart level

STARTING in a moment...
"""

from __future__ import print_function

import argparse
import logging
import random
import sys
import time

try:
    import pygame
    from pygame.locals import *
except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')

try:
    import numpy as np
except ImportError:
    raise RuntimeError('cannot import numpy, make sure numpy package is installed')

from carla import image_converter
from carla import sensor
from carla.client import make_carla_client, VehicleControl
from carla.planner.map import CarlaMap
from carla.settings import CarlaSettings
from carla.tcp import TCPConnectionError
from carla.util import print_over_same_line


WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
MINI_WINDOW_WIDTH = 320
MINI_WINDOW_HEIGHT = 180


def make_carla_settings():
    """Make a CarlaSettings object with the settings we need."""
    settings = CarlaSettings()
    settings.set(
        SynchronousMode=False,
        SendNonPlayerAgentsInfo=True,
        NumberOfVehicles=15,
        NumberOfPedestrians=30,
        WeatherId=random.choice([1, 3, 7, 8, 14]))
    settings.randomize_seeds()
    camera0 = sensor.Camera('CameraRGB')
    camera0.set_image_size(WINDOW_WIDTH, WINDOW_HEIGHT)
    camera0.set_position(200, 0, 140)
    camera0.set_rotation(0.0, 0.0, 0.0)
    settings.add_sensor(camera0)
    camera1 = sensor.Camera('CameraDepth', PostProcessing='Depth')
    camera1.set_image_size(MINI_WINDOW_WIDTH, MINI_WINDOW_HEIGHT)
    camera1.set_position(200, 0, 140)
    camera1.set_rotation(0.0, 0.0, 0.0)
    settings.add_sensor(camera1)
    camera2 = sensor.Camera('CameraSemSeg', PostProcessing='SemanticSegmentation')
    camera2.set_image_size(MINI_WINDOW_WIDTH, MINI_WINDOW_HEIGHT)
    camera2.set_position(200, 0, 140)
    camera2.set_rotation(0.0, 0.0, 0.0)
    settings.add_sensor(camera2)
    lidar0 = sensor.Lidar('Lidar32')
    lidar0.set_position(0, 0, 250)
    lidar0.set_rotation(0, 0, 0)
    lidar0.set(
        Channels = 32,
        Range = 5000,
        PointsPerSecond = 100000,
        RotationFrequency = 10,
        UpperFovLimit = 10,
        LowerFovLimit = -30,
        ShowDebugPoints = False)
    settings.add_sensor(lidar0)

    return settings


class Timer(object):
    def __init__(self):
        self.step = 0
        self._lap_step = 0
        self._lap_time = time.time()

    def tick(self):
        self.step += 1

    def lap(self):
        self._lap_step = self.step
        self._lap_time = time.time()

    def ticks_per_second(self):
        return float(self.step - self._lap_step) / self.elapsed_seconds_since_lap()

    def elapsed_seconds_since_lap(self):
        return time.time() - self._lap_time


class CarlaGame(object):
    def __init__(self, carla_client, city_name=None, save_images_to_disk=False):
        self.client = carla_client
        self._timer = None
        self._display = None
        self._main_image = None
        self._mini_view_image1 = None
        self._mini_view_image2 = None
        self._map_view = None
        self._is_on_reverse = False
        self._city_name = city_name
        self._map = CarlaMap(city_name) if city_name is not None else None
        self._map_shape = self._map.map_image.shape if city_name is not None else None
        self._map_view = self._map.get_map(WINDOW_HEIGHT) if city_name is not None else None
        self._save_images_to_disk = save_images_to_disk
        self._image_filename_format='_images/episode_{:0>3d}/{:s}/image_{:0>5d}.png'
        self._lidar_filename_format='_lidars/episode_{:0>3d}/{:s}/lidar_{:0>5d}.json'
        self._episode = 0
        self._frame = 0

    def execute(self):
        """Launch the PyGame."""
        pygame.init()
        self._initialize_game()
        try:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                self._on_loop()
                self._on_render()
        finally:
            pygame.quit()

    def _initialize_game(self):
        if self._city_name is not None:
            self._display = pygame.display.set_mode(
                (WINDOW_WIDTH + int((WINDOW_HEIGHT/float(self._map.map_image.shape[0]))*self._map.map_image.shape[1]), WINDOW_HEIGHT),
                pygame.HWSURFACE | pygame.DOUBLEBUF)
        else:
            self._display = pygame.display.set_mode(
                (WINDOW_WIDTH, WINDOW_HEIGHT),
                pygame.HWSURFACE | pygame.DOUBLEBUF)

        logging.debug('pygame started')
        self._on_new_episode()

    def _on_new_episode(self):
        scene = self.client.load_settings(make_carla_settings())
        number_of_player_starts = len(scene.player_start_spots)
        player_start = np.random.randint(number_of_player_starts)
        print('Starting new episode...')
        self.client.start_episode(player_start)
        self._timer = Timer()
        self._is_on_reverse = False
        self._episode += 1
        self._frame = 0

    def _on_loop(self):
        self._timer.tick()

        measurements, sensor_data = self.client.read_data()

        self._main_image = sensor_data['CameraRGB'] if 'CameraRGB' in sensor_data else None
        self._mini_view_image1 = sensor_data['CameraDepth'] if 'CameraDepth' in sensor_data else None
        self._mini_view_image2 = sensor_data['CameraSemSeg'] if 'CameraSemSeg' in sensor_data else None
        self._lidar_measurement = sensor_data['Lidar32'] if 'Lidar32' in sensor_data else None

        # Print measurements every second.
        if self._timer.elapsed_seconds_since_lap() > 1.0:
            if self._city_name is not None:
                # Function to get car position on map.
                map_position = self._map.get_position_on_map([
                    measurements.player_measurements.transform.location.x,
                    measurements.player_measurements.transform.location.y,
                    measurements.player_measurements.transform.location.z])
                # Function to get orientation of the road car is in.
                lane_orientation = self._map.get_lane_orientation([
                    measurements.player_measurements.transform.location.x,
                    measurements.player_measurements.transform.location.y,
                    measurements.player_measurements.transform.location.z])

                self._print_player_measurements_map(
                    measurements.player_measurements,
                    map_position,
                    lane_orientation)
            else:
                self._print_player_measurements(measurements.player_measurements)

            # Plot position on the map as well.

            self._timer.lap()

        control = self._get_keyboard_control(pygame.key.get_pressed())
        # Set the player position
        if self._city_name is not None:
            self._position = self._map.get_position_on_map([
                        measurements.player_measurements.transform.location.x,
                        measurements.player_measurements.transform.location.y,
                        measurements.player_measurements.transform.location.z])
            self._agent_positions = measurements.non_player_agents

        if control is None:
            self._on_new_episode()
        else:
            self.client.send_control(control)

        # Save the images to disk if requested.
        if self._save_images_to_disk:
            for name, measurement in sensor_data.items():
                if isinstance(measurement, sensor.LidarMeasurement):
                    measurement.data
                    measurement.save_to_disk(self._lidar_filename_format.format(self._episode, name, self._frame))
                else:
                    measurement.save_to_disk(self._image_filename_format.format(self._episode, name, self._frame))

        self._frame += 1

    def _get_keyboard_control(self, keys):
        """
        Return a VehicleControl message based on the pressed keys. Return None
        if a new episode was requested.
        """
        if keys[K_r]:
            return None
        control = VehicleControl()
        if keys[K_LEFT] or keys[K_a]:
            control.steer = -1.0
        if keys[K_RIGHT] or keys[K_d]:
            control.steer = 1.0
        if keys[K_UP] or keys[K_w]:
            control.throttle = 1.0
        if keys[K_DOWN] or keys[K_s]:
            control.brake = 1.0
        if keys[K_SPACE]:
            control.hand_brake = True
        if keys[K_q]:
            self._is_on_reverse = not self._is_on_reverse
        control.reverse = self._is_on_reverse
        return control

    def _print_player_measurements_map(
            self,
            player_measurements,
            map_position,
            lane_orientation):
        message = 'Step {step} ({fps:.1f} FPS): '
        message += 'Map Position ({map_x:.1f},{map_y:.1f}) Lane Orientation ({ori_x:.1f},{ori_y:.1f})  '
        message += '{speed:.2f} km/h, '
        message += '{other_lane:.0f}% other lane, {offroad:.0f}% off-road'
        message = message.format(
            map_x=map_position[0],
            map_y=map_position[1],
            ori_x=lane_orientation[0],
            ori_y=lane_orientation[1],
            step=self._timer.step,
            fps=self._timer.ticks_per_second(),
            speed=player_measurements.forward_speed,
            other_lane=100 * player_measurements.intersection_otherlane,
            offroad=100 * player_measurements.intersection_offroad)
        print_over_same_line(message)

    def _print_player_measurements(self, player_measurements):
        message = 'Step {step} ({fps:.1f} FPS): '
        message += '{speed:.2f} km/h, '
        message += '{other_lane:.0f}% other lane, {offroad:.0f}% off-road'
        message = message.format(
            step=self._timer.step,
            fps=self._timer.ticks_per_second(),
            speed=player_measurements.forward_speed,
            other_lane=100 * player_measurements.intersection_otherlane,
            offroad=100 * player_measurements.intersection_offroad)
        print_over_same_line(message)

    def _on_render(self):
        gap_x = (WINDOW_WIDTH - 2 * MINI_WINDOW_WIDTH) / 3
        mini_image_y = WINDOW_HEIGHT - MINI_WINDOW_HEIGHT - gap_x

        if self._main_image is not None:
            array = image_converter.to_rgb_array(self._main_image)
            surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
            self._display.blit(surface, (0, 0))

        if self._mini_view_image1 is not None:
            array = image_converter.depth_to_logarithmic_grayscale(self._mini_view_image1)
            surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))
            self._display.blit(surface, (gap_x, mini_image_y))

        if self._mini_view_image2 is not None:
            array = image_converter.labels_to_cityscapes_palette(
                self._mini_view_image2)
            surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))

            self._display.blit(
                surface, (2 * gap_x + MINI_WINDOW_WIDTH, mini_image_y))

        if self._lidar_measurement is not None:

            lidar_points = np.array(self._lidar_measurement.data['points'][:, :, :2])
            lidar_points /= 50.0
            lidar_points += 100.0
            lidar_points = np.fabs(lidar_points)
            lidar_points = lidar_points.astype(np.int32)
            lidar_points = np.reshape(lidar_points, (-1, 2))

            lidar_points_labels = self._lidar_measurement.data['labels']
            lidar_points_labels = np.reshape(lidar_points_labels, (-1))

            #draw lidar
            lidar_img_size = (200, 200, 3)
            lidar_img = np.zeros(lidar_img_size)

            for class_id, color in image_converter.semantic_segmentation_classes_to_colors.items():
                lidar_img[tuple(lidar_points[lidar_points_labels == class_id].T)] = color

            surface = pygame.surfarray.make_surface(
                lidar_img
            )
            self._display.blit(surface, (10, 10))

        if self._map_view is not None:
            array = self._map_view
            array = array[:, :, :3]
            new_window_width =(float(WINDOW_HEIGHT)/float(self._map_shape[0]))*float(self._map_shape[1])
            surface = pygame.surfarray.make_surface(array.swapaxes(0, 1))

            w_pos = int(self._position[0]*(float(WINDOW_HEIGHT)/float(self._map_shape[0])))
            h_pos =int(self._position[1] *(new_window_width/float(self._map_shape[1])))

            pygame.draw.circle(surface, [255, 0, 0, 255], (w_pos,h_pos), 6, 0)
            for agent in self._agent_positions:
                if agent.HasField('vehicle'):
                    agent_position = self._map.get_position_on_map([
                        agent.vehicle.transform.location.x,
                        agent.vehicle.transform.location.y,
                        agent.vehicle.transform.location.z])
                    w_pos = int(agent_position[0]*(float(WINDOW_HEIGHT)/float(self._map_shape[0])))
                    h_pos =int(agent_position[1] *(new_window_width/float(self._map_shape[1])))
                    pygame.draw.circle(surface, [255, 0, 255, 255], (w_pos,h_pos), 4, 0)

            self._display.blit(surface, (WINDOW_WIDTH, 0))

        pygame.display.flip()


def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='localhost',
        help='IP of the host server (default: localhost)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-m', '--map-name',
        metavar='M',
        default=None,
        help='plot the map of the current city (needs to match active map in server, options: Town01 or Town02)')
    argparser.add_argument(
        '-i', '--images-to-disk',
        action='store_true',
        help='save images to disk')
    args = argparser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    print(__doc__)

    while True:
        try:

            with make_carla_client(args.host, args.port) as client:
                game = CarlaGame(client, args.map_name, save_images_to_disk=args.images_to_disk)
                game.execute()
                break

        except TCPConnectionError as error:
            logging.error(error)
            time.sleep(1)
        except Exception as exception:
            logging.exception(exception)
            sys.exit(1)


if __name__ == '__main__':

    try:
        main()
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')
