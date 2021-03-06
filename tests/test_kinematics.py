#! /usr/bin/env python
import unittest
import numpy as np
import openravepy as orpy
# Tested package
import raveutils as ru


class Test_kinematics(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    np.set_printoptions(precision=6, suppress=True)
    cls.env = orpy.Environment()
    if not cls.env.Load('data/lab1.env.xml'):
      raise Exception('Could not load scene: data/lab1.env.xml')
    cls.robot = cls.env.GetRobot('BarrettWAM')
    np.random.seed(123)
    q = ru.kinematics.random_joint_values(cls.robot)
    cls.robot.SetActiveDOFValues(q)
    print('') # dummy line

  @classmethod
  def tearDownClass(cls):
    cls.env.Reset()
    cls.env.Destroy()

  def test_compute_jacobian(self):
    robot = self.robot
    # Try the function with its variants
    Jtrans = ru.kinematics.compute_jacobian(robot, translation_only=True)
    J = ru.kinematics.compute_jacobian(robot, translation_only=False)
    link_name = robot.GetLinks()[-1].GetName()
    J = ru.kinematics.compute_jacobian(robot, link_name=link_name)
    # Raise KeyError invalid link name
    try:
      J = ru.kinematics.compute_jacobian(robot, link_name='invalid_name')
      raised_error = False
    except KeyError:
      raised_error = True
    self.assertTrue(raised_error)
    # Raise IndexError invalid link index
    num_links = len(robot.GetLinks())
    try:
      J = ru.kinematics.compute_jacobian(robot, link_idx=num_links)
      raised_error = False
    except IndexError:
      raised_error = True
    self.assertTrue(raised_error)

  def test_compute_yoshikawa_index(self):
    robot = self.robot
    # Try all the variants
    idx = ru.kinematics.compute_yoshikawa_index(robot, penalize_jnt_limits=True)
    idx = ru.kinematics.compute_yoshikawa_index(robot, penalize_jnt_limits=False)
    idx = ru.kinematics.compute_yoshikawa_index(robot, translation_only=True)
    idx = ru.kinematics.compute_yoshikawa_index(robot, translation_only=False)

  def test_load_ikfast_and_find_ik_solutions(self):
    robot = self.robot
    # Test loading IKFast: Transform6D
    iktype = orpy.IkParameterizationType.Transform6D
    success = ru.kinematics.load_ikfast(robot, iktype, autogenerate=False)
    self.assertTrue(success)
    # Test find IK solutions: Transform6D
    iktype = orpy.IkParameterizationType.Transform6D
    manip = robot.GetActiveManipulator()
    T = manip.GetEndEffectorTransform()
    solutions = ru.kinematics.find_ik_solutions(robot, T, iktype,
                                                          collision_free=False)
    self.assertTrue(len(solutions) > 0)
    ray = ru.conversions.to_ray(T)
    solutions = ru.kinematics.find_ik_solutions(robot, ray, iktype,
                                                          collision_free=False)
    self.assertTrue(len(solutions) > 0)
    return
    # TODO: Speed-up this test
    # Test loading IKFast: TranslationDirection5D
    iktype = orpy.IkParameterizationType.TranslationDirection5D
    success = ru.kinematics.load_ikfast(robot, iktype, autogenerate=True,
                                    freejoints=['Shoulder_Roll', 'Wrist_Roll'])
    self.assertTrue(success)
    # Test find IK solutions: TranslationDirection5D
    iktype = orpy.IkParameterizationType.TranslationDirection5D
    solutions = ru.kinematics.find_ik_solutions(robot, T, iktype,
                                                          collision_free=False)
    self.assertTrue(len(solutions) > 0)
    ray = ru.conversions.to_ray(T)
    solutions = ru.kinematics.find_ik_solutions(robot, ray, iktype,
                                                          collision_free=False)
    self.assertTrue(len(solutions) > 0)

  def test_load_link_stats(self):
    # Autogenerate: False
    success = ru.kinematics.load_link_stats(self.robot, autogenerate=False)
    self.assertTrue(success)
    # Autogenerate: True
    success = ru.kinematics.load_link_stats(self.robot, autogenerate=True)
    self.assertTrue(success)
