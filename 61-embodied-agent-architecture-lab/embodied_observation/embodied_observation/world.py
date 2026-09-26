"""Mission-local temporal facts with source provenance and stale eviction."""

import math

import rclpy
from astra_interfaces.msg import EntityState, Percept, WorldDelta
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy


PERCEPT_SOURCES = {
    "obstacle/front": (
        "astra/base_footprint/lidar_2d",
        "/astra/sensors/scan",
    ),
    "object-00": ("camera_optical_frame", "/astra/sensors/rgbd/image"),
}


class WorldModel(LifecycleNode):
    def __init__(self):
        super().__init__("world_model")
        self.active = False
        self.facts = {}
        self.entities = self.create_lifecycle_publisher(
            EntityState, "/astra/world/entities", 8
        )
        self.deltas = self.create_lifecycle_publisher(
            WorldDelta, "/astra/world/delta", 8
        )
        sensor_qos = QoSProfile(depth=8, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.percepts = self.create_subscription(
            Percept, "/astra/perception/percepts", self.on_percept, sensor_qos
        )
        self.timer = self.create_timer(0.1, self.evict_stale)

    def on_configure(self, state):
        self.facts.clear()
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        self.active = True
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.active = False
        self.facts.clear()
        return super().on_deactivate(state)

    def on_percept(self, percept):
        if not self.active:
            return
        if (
            percept.schema_version != "astra.percept.v1"
            or percept.clock_domain != "sim"
            or (percept.frame_id, percept.source_topic)
            != PERCEPT_SOURCES.get(percept.entity_id)
            or percept.result_code != "OK"
            or not 0.7 <= percept.confidence <= 1.0
            or not math.isfinite(percept.pose.pose.position.x)
            or not math.isfinite(percept.pose.pose.position.y)
            or not math.isfinite(percept.pose.pose.position.z)
            or not 0 < percept.ttl_seconds <= 0.25
        ):
            return
        observed_ns = percept.observed_at.sec * 10**9 + percept.observed_at.nanosec
        now_ns = self.get_clock().now().nanoseconds
        if not -0.05 <= (now_ns - observed_ns) / 10**9 <= percept.ttl_seconds:
            return
        # The red fiducial is fixed in this synthetic world. Percept intake
        # still requires a <=250 ms source sample, while the derived entity
        # uses the catalogued 500 ms world-fact lifetime to absorb one missed
        # RGB-D frame. Moving targets must not inherit this longer lifetime.
        fact_ttl = 0.5 if percept.entity_id == "object-00" else percept.ttl_seconds
        valid_ns = observed_ns + int(fact_ttl * 10**9)
        entity = EntityState()
        entity.schema_version = "astra.entity-state.v1"
        entity.entity_id = percept.entity_id
        entity.frame_id = percept.frame_id
        entity.clock_domain = "sim"
        entity.observed_at = percept.observed_at
        entity.valid_until.sec, entity.valid_until.nanosec = divmod(valid_ns, 10**9)
        entity.confidence = percept.confidence
        entity.pose = percept.pose
        entity.provenance = percept.source_topic
        self.facts[entity.entity_id] = entity
        self.entities.publish(entity)
        self.publish_delta([entity.entity_id], [], entity.frame_id, entity.provenance)

    def evict_stale(self):
        if not self.active:
            return
        now_ns = self.get_clock().now().nanoseconds
        expired = [
            name
            for name, entity in self.facts.items()
            if entity.valid_until.sec * 10**9 + entity.valid_until.nanosec < now_ns
        ]
        for name in expired:
            entity = self.facts.pop(name)
            self.publish_delta([name], [], entity.frame_id, entity.provenance)

    def publish_delta(self, changed, conflicts, frame_id, provenance):
        delta = WorldDelta()
        delta.schema_version = "astra.world-delta.v1"
        delta.frame_id = frame_id
        delta.clock_domain = "sim"
        delta.observed_at = self.get_clock().now().to_msg()
        delta.ttl_seconds = 0.5
        delta.changed_entity_ids = changed
        delta.unresolved_conflicts = conflicts
        delta.provenance = provenance
        self.deltas.publish(delta)


def main():
    rclpy.init()
    node = WorldModel()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
