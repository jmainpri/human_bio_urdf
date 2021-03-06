#!/usr/bin/python

import rospy
import xml.dom.minidom
import subprocess
from sensor_msgs.msg import *
from math import pi


class JointStatePublisher:
    def __init__(self, description_file):
        robot = (
            xml.dom.minidom.parseString(description_file).getElementsByTagName(
                'robot')[0])
        self.free_joints = {}
        self.warnings = {}
        self.latest_state = None
        self.last_time = rospy.get_time()

        # Create all the joints based off of the URDF and
        # assign them joint limits based on their properties
        for child in robot.childNodes:
            if child.nodeType is child.TEXT_NODE:
                continue
            if child.localName == 'joint':
                jtype = child.getAttribute('type')
                if jtype == 'fixed':
                    continue
                name = child.getAttribute('name')
                if jtype == 'continuous':
                    minval = -pi
                    maxval = pi
                else:
                    limit = child.getElementsByTagName('limit')[0]
                    minval = float(limit.getAttribute('lower'))
                    maxval = float(limit.getAttribute('upper'))

                if minval > 0 or maxval < 0:
                    zeroval = (maxval + minval) / 2
                else:
                    zeroval = 0

                joint = {'min': minval, 'max': maxval, 'zero': zeroval,
                         'value': zeroval}
                self.free_joints[name] = joint

        # Setup the joint state publisher
        self.human_pub = rospy.Publisher(rospy.get_namespace() + "joint_states",
                                         JointState)

    def human_cb(self, msg):
        new_state = {}
        try:
            assert (len(msg.name) == len(msg.position))
            for index in range(len(msg.name)):
                new_state[msg.name[index]] = msg.position[index]
            self.latest_state = new_state
        except:
            rospy.logerr("*** Malformed HumanState! ***")
        self.last_time = rospy.get_time()

    def loop(self, hz=10.0):
        r = rospy.Rate(hz)

        # Publish Joint States
        while not rospy.is_shutdown():
            # Check to warn if the data is too old
            time_difference = rospy.get_time() - self.last_time
            threshold = 0.05
            if time_difference > threshold:
                rospy.logdebug("Human messages are old")
            # Convert the latest state of the robot if it is available
            if self.latest_state is not None:
                msg = JointState()
                msg.header.stamp = rospy.Time.now()
                # Convert the HuboState to a series of joint states
                for joint_name in self.latest_state.keys():
                    # Determine if the joint is FREE or DEPENDENT
                    if joint_name in self.free_joints.keys():
                        msg.name.append(joint_name)
                        msg.position.append(self.latest_state[joint_name])
                    else:
                        self.warn_user(
                            "Joint " + joint_name +
                            " in update message not found in the URDF")
                # Check for joints in the URDF that are not in the HuboState
                for joint_name in self.free_joints:
                    if joint_name not in self.latest_state.keys():
                        self.warn_user(
                            "Joint " + joint_name +
                            " in the URDF not in the update message")
                        msg.name.append(joint_name)
                        msg.position.append(
                            self.free_joints[joint_name]['zero'])
                self.human_pub.publish(msg)
            else:
                rospy.logdebug("No valid message received from the Human yet")
                msg = JointState()
                msg.header.stamp = rospy.Time.now()
                for joint_name in self.free_joints:
                    msg.name.append(joint_name)
                    msg.position.append(self.free_joints[joint_name]['zero'])
                self.human_pub.publish(msg)
            # Spin
            r.sleep()

    def warn_user(self, warning_string):
        try:
            self.warnings[warning_string] += 1
        except:
            self.warnings[warning_string] = 1
            rospy.logwarn(
                warning_string + " - This message will only print once")


if __name__ == '__main__':
    rospy.init_node('human_joint_state_publisher')
    description_file = rospy.get_param("robot_description")
    publish_rate = rospy.get_param("~rate", 20.0)
    jsp = JointStatePublisher(description_file)
    jsp.loop(publish_rate)
