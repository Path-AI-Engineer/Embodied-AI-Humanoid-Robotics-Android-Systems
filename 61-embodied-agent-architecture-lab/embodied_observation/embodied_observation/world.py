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
        self.intake_counts = {}
        self.last_object_age_seconds = None
        self.entities = self.create_lifecycle_publisher(
            EntityState, "/astra/world/entities", 8
        )
        self.object_target = self.create_lifecycle_publisher(
            EntityState,
            "/astra/world/object_target",
            QoSProfile(depth=8, reliability=ReliabilityPolicy.RELIABLE),
        )
        self.deltas = self.create_lifecycle_publisher(
            WorldDelta, "/astra/world/delta", 8
        )
        percept_qos = QoSProfile(depth=8, reliability=ReliabilityPolicy.RELIABLE)
        self.camera_percepts = self.create_subscription(
            Percept, "/astra/perception/camera", self.on_percept, percept_qos
        )
        self.lidar_percepts = self.create_subscription(
            Percept, "/astra/perception/lidar", self.on_percept, percept_qos
        )
        self.timer = self.create_timer(0.1, self.evict_stale)

    def on_configure(self, state):
        self.facts.clear()
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        self.active = True
        self.get_logger().info("world_lifecycle activated")
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.active = False
        self.facts.clear()
        self.get_logger().info("world_lifecycle deactivated")
        return super().on_deactivate(state)

    def on_percept(self, percept):
        if not self.active:
            self.record_intake(percept.entity_id, "inactive")
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
            self.record_intake(percept.entity_id, "contract_rejected")
            return
        observed_ns = percept.observed_at.sec * 10**9 + percept.observed_at.nanosec
        now_ns = self.get_clock().now().nanoseconds
        age_seconds = (now_ns - observed_ns) / 10**9
        if percept.entity_id == "object-00":
            self.last_object_age_seconds = age_seconds
        if not -0.05 <= age_seconds <= percept.ttl_seconds:
            self.record_intake(percept.entity_id, "freshness_rejected")
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
        if entity.entity_id == "object-00":
            self.object_target.publish(entity)
        self.record_intake(percept.entity_id, "accepted")
        self.publish_delta([entity.entity_id], [], entity.frame_id, entity.provenance)

    def record_intake(self, entity_id, outcome):
        entity = entity_id if entity_id in PERCEPT_SOURCES else "other"
        key = f"{entity}:{outcome}"
        self.intake_counts[key] = self.intake_counts.get(key, 0) + 1
        total = sum(self.intake_counts.values())
        if total % 100 == 0:
            self.get_logger().info(
                "world_intake "
                f"total={total} counts={self.intake_counts} "
                f"last_object_age_seconds={self.last_object_age_seconds}"
            )

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
