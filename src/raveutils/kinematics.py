#!/usr/bin/env python
import numpy as np
import openravepy as orpy
from . import conversions
from . import transforms as tr


def compute_jacobian(robot, link_name=None, translation_only=False):
  """
  Compute the Jacobian matrix

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot
  link_name: str, optional
    The name of link. If it's `None`, the last link of the kinematic chain is
    used
  translation_only: bool, optional
    If set, only the translation Jacobian is computed

  Returns
  -------
  J: array_like
    The computed Jacobian matrix
  """
  if link_name is None:
    link_name = robot.GetLinks()[-1].GetName()
  names = [l.GetName() for l in robot.GetLinks()]
  if link_name not in names:
    raise KeyError('Invalid link name: {0}'.format(link_name))
  idx = names.index(link_name)
  origin = robot.GetLink(link_name).GetTransform()[:3,3]
  manip = robot.GetActiveManipulator()
  indices = manip.GetArmIndices()
  Jtrans = robot.ComputeJacobianTranslation(idx, origin)[:,indices]
  if translation_only:
    J = Jtrans
  else:
    J = np.zeros((6, Jtrans.shape[1]))
    J[:3,:] = Jtrans
    J[3:,:] = robot.ComputeJacobianAxisAngle(idx)[:,indices]
  return J

def compute_yoshikawa_index(robot, link_name=None, translation_only=False,
                                                      penalize_jnt_limits=True):
  """
  Compute the Yoshikawa index (manipulability index)

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot
  link_name: str, optional
    The name of link. If it's `None`, the last link of the kinematic chain is
    used.
  translation_only: bool, optional
    If `True` use only the translation part of the Jacobian matrix to
    compute the index. If `False` use the translation and rotation.
  penalize_jnt_limits: bool, optional
    If True penalize/attenuate the manipulability proportionally
    to the *distance* to the joint limits of the robot

  Returns
  -------
  index: float
    The Yoshikawa manipulability index
  """
  weight = 1.0
  if penalize_jnt_limits:
    with robot.GetEnv():
      q = robot.GetActiveDOFValues()
    if translation_only:
      indices = np.arange(3)
    else:
      indices = np.arange(robot.GetActiveDOF())
    q = q[indices]
    lm = robot.GetActiveDOFLimits()[0][indices]
    lp = robot.GetActiveDOFLimits()[1][indices]
    qbest = (lp + lm) / 2.
    max_dist = np.linalg.norm(lp-qbest)
    weight = 1. - np.exp(np.linalg.norm(qbest - q) - max_dist)
  J = compute_jacobian(robot, link_name=link_name,
                                            translation_only=translation_only)
  if translation_only:
    scale = 10.
  else:
    scale = 20.
  index = np.sqrt( max(np.linalg.det(np.dot(J, J.T)), 0) )*weight*scale
  return index

def find_ik_solutions(robot, target, iktype, collision_free=True, freeinc=0.1):
  """
  Find all the possible IK solutions

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot
  target: array_like or orpy.Ray
    The target in the task space (Cartesian). A target can be defined as a Ray
    (position and direction) which is 5D or as an homogeneous transformation
    which is 6D.
  iktype: orpy.IkParameterizationType
    Inverse kinematics type to use. Supported values:
    `orpy.IkParameterizationType.Transform6D` and
    `orpy.IkParameterizationType.TranslationDirection5D`
  collision_free: bool, optional
    If true, find only collision-free solutions
  freeinc: float, optional
    The free increment (discretization) to be used for the free DOF when the
    target is 5D.

  Returns
  -------
  solutions: list
    The list of IK solutions found
  """
  # Populate the target list
  target_list = []
  if iktype == orpy.IkParameterizationType.TranslationDirection5D:
    if type(target) is not orpy.Ray:
      ray = conversions.to_ray(goal)
      target_list.append(ray)
    else:
      target_list.append(target)
  elif iktype == orpy.IkParameterizationType.Transform6D:
    if type(target) is orpy.Ray:
      Tray = conversions.from_ray(target)
      for angle in np.arange(0, 2*np.pi, freeinc):
        Toffset = orpy.matrixFromAxisAngle(angle*tr.Z_AXIS)
        target_list.append(np.dot(Tray, Toffset))
    else:
      target_list.append(target)
  # Concatenate all the solutions
  solutions = []
  for goal in target_list:
    ikparam = orpy.IkParameterization(goal, iktype)
    manipulator = robot.GetActiveManipulator()
    opt = 0
    if collision_free:
      opt = orpy.IkFilterOptions.CheckEnvCollisions
    solutions += list(manipulator.FindIKSolutions(ikparam, opt))
  return solutions

def load_ikfast(robot, iktype, freejoints=['J6'], freeinc=[0.01],
                                                            autogenerate=True):
  """
  Load the IKFast solver

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot
  iktype: orpy.IkParameterizationType
    Inverse kinematics type to be used
  freeinc: list
    The free increment (discretization) to be used for the free DOF when the
    target is the `iktype` is `TranslationDirection5D`
  autogenerate: bool, optional
    If true, auto-generate the IKFast solver

  Returns
  -------
  success: bool
    `True` if succeeded, `False` otherwise
  """
  # Improve code readability
  from openravepy.databases.inversekinematics import InverseKinematicsModel
  # Initialize the ikmodel
  if iktype == orpy.IkParameterizationType.TranslationDirection5D:
    ikmodel = InverseKinematicsModel(robot, iktype=iktype,
                                                        freejoints=freejoints)
  else:
    ikmodel = InverseKinematicsModel(robot, iktype=iktype)
  # Load or generate
  if not ikmodel.load() and autogenerate:
    print 'Generating IKFast {0}. Will take few minutes...'.format(iktype.name)
    if iktype == orpy.IkParameterizationType.Transform6D:
      ikmodel.autogenerate()
    elif iktype == orpy.IkParameterizationType.TranslationDirection5D:
      ikmodel.generate(iktype=iktype, freejoints=freejoints)
      ikmodel.save()
    else:
      ikmodel.autogenerate()
    print 'IKFast {0} has been successfully generated'.format(iktype.name)
  if iktype == orpy.IkParameterizationType.TranslationDirection5D:
    success = ikmodel.load(freeinc=freeinc)
  elif iktype == orpy.IkParameterizationType.Transform6D:
    success = ikmodel.load()
  else:
    success = ikmodel.load()
  return success

def load_link_stats(robot, xyzdelta=0.01, autogenerate=True):
  """
  Load/generate the `Link Statistics` database which contains statistics on body
  links like swept volumes.

  When using link statics, it is possible to set the joints weights and
  resolutions so that planning is fastest. The `xyzdelta` parameter specifies
  the smallest object that can be found in the environment, this becomes the new
  discretization factor when checking collision. Higher values mean faster
  planning.

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot
  xyzdelta: float
    Smallest object that can be found in the environment (meters)
  autogenerate: bool, optional
    If true, auto-generate the `Link Statistics` database

  Returns
  -------
  success: bool
    `True` if succeeded, `False` otherwise
  """
  success = False
  statsmodel = orpy.databases.linkstatistics.LinkStatisticsModel(robot)
  if not statsmodel.load() and autogenerate:
    print 'Generating LinkStatistics database. Will take ~1 minute...'
    statsmodel.autogenerate()
  if statsmodel.load():
    statsmodel.setRobotWeights()
    statsmodel.setRobotResolutions(xyzdelta=xyzdelta)
    success = True
  else:
    manip = robot.GetActiveManipulator()
    indices = manip.GetArmIndices()
    if robot.GetActiveDOF() == 6:
      origins = [l.GetTransform()[:3,3] for l in robot.GetLinks()]
      jweights = [np.linalg.norm(origins[1] - origins[2]),
                  np.linalg.norm(origins[2] - origins[3]),
                  np.linalg.norm(origins[3] - origins[4]),
                  np.linalg.norm(origins[4] - origins[5]),
                  np.linalg.norm(origins[5] - origins[6]),
                  np.linalg.norm(origins[6] - origins[-1])]
      for i in range(robot.GetActiveDOF()):
        jweights[i] = np.sum(jweights[i:])
      robot_weights = np.ones(robot.GetDOF())
      robot_weights[indices] = np.array(jweights) / np.max(jweights)
      robot.SetDOFWeights(robot_weights)
    else:
      robot.SetDOFWeights([1]*robot.GetDOF())
  return success

def random_joint_values(robot):
  """
  Generate random joint values within the joint limits of the robot.

  Parameters
  ----------
  robot: orpy.Robot
    The OpenRAVE robot

  Returns
  -------
  values: array_like
    The random joint values
  """
  # Get the limits of the active DOFs
  lower, upper = robot.GetActiveDOFLimits()
  values = lower + np.random.rand(len(lower))*(upper-lower)
  return values
