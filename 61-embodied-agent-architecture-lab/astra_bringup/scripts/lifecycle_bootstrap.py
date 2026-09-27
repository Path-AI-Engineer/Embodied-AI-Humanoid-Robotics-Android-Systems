"""Activate observation nodes once, in source-to-world order, at bringup."""

import sys
import time

import rclpy
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState, GetState


NODES = ("/lidar_perception", "/camera_perception", "/world_model")


def call(node, service_type, service_name, request, deadline):
    # A response can be lost even when the lifecycle service receives the
    # request. Drop that client and retry from a new DDS endpoint, while the
    # outer deadline remains bounded.
    attempt_deadline = min(deadline, time.monotonic() + 4.0)
    client = node.create_client(service_type, service_name)
    try:
        while not client.wait_for_service(timeout_sec=0.25):
            if time.monotonic() >= attempt_deadline:
                raise TimeoutError(f"lifecycle service unavailable: {service_name}")
        future = client.call_async(request)
        while not future.done():
            rclpy.spin_until_future_complete(node, future, timeout_sec=0.25)
            if time.monotonic() >= attempt_deadline:
                raise TimeoutError(f"lifecycle service timed out: {service_name}")
        response = future.result()
        if response is None:
            raise TimeoutError(
                f"lifecycle service returned no response: {service_name}"
            )
        return response
    finally:
        node.destroy_client(client)


def activate(node, name):
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            state = call(
                node, GetState, f"{name}/get_state", GetState.Request(), deadline
            ).current_state.label
        except TimeoutError as exc:
            node.get_logger().warning(f"lifecycle_bootstrap retry {name}: {exc}")
            continue
        if state == "active":
            node.get_logger().info(f"lifecycle_bootstrap {name}=active")
            return
        transition = ChangeState.Request()
        if state == "unconfigured":
            transition.transition.id = Transition.TRANSITION_CONFIGURE
        elif state == "inactive":
            transition.transition.id = Transition.TRANSITION_ACTIVATE
        elif state in {"configuring", "activating"}:
            time.sleep(0.1)
            continue
        else:
            raise RuntimeError(f"unexpected lifecycle state for {name}: {state}")
        try:
            response = call(
                node, ChangeState, f"{name}/change_state", transition, deadline
            )
        except TimeoutError as exc:
            node.get_logger().warning(f"lifecycle_bootstrap retry {name}: {exc}")
            continue
        if not response.success:
            raise RuntimeError(f"lifecycle transition rejected for {name}: {state}")
    raise TimeoutError(f"lifecycle activation timed out: {name}")


def main():
    rclpy.init()
    node = rclpy.create_node("lifecycle_bootstrap")
    try:
        for name in NODES:
            activate(node, name)
    except Exception as exc:
        node.get_logger().error(f"lifecycle_bootstrap failed: {exc}")
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
