#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <memory>
#include <string>

#include "astra_interfaces/msg/control_intent.hpp"
#include "astra_interfaces/msg/fault_event.hpp"
#include "astra_interfaces/msg/safety_state.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "std_msgs/msg/bool.hpp"

using namespace std::chrono_literals;

class SafetyGateway final : public rclcpp::Node {
 public:
  SafetyGateway() : Node("safety_gateway"), started_wall_(std::chrono::steady_clock::now()), last_scan_wall_(started_wall_) {
    const auto sensor_qos = rclcpp::SensorDataQoS().keep_last(5);
    const auto state_qos = rclcpp::QoS(1).reliable().transient_local();
    command_pub_ = create_publisher<geometry_msgs::msg::Twist>("/astra/control/authorized_cmd_vel", 1);
    state_pub_ = create_publisher<astra_interfaces::msg::SafetyState>("/astra/safety/state", state_qos);
    fault_pub_ = create_publisher<astra_interfaces::msg::FaultEvent>("/astra/safety/faults", rclcpp::QoS(16).reliable());
    scan_sub_ = create_subscription<sensor_msgs::msg::LaserScan>(
        "/astra/sensors/scan", sensor_qos,
        [this](sensor_msgs::msg::LaserScan::ConstSharedPtr scan) { on_scan(*scan); });
    intent_sub_ = create_subscription<astra_interfaces::msg::ControlIntent>(
        "/astra/control/intent", rclcpp::QoS(5).reliable(),
        [this](astra_interfaces::msg::ControlIntent::ConstSharedPtr intent) { on_intent(*intent); });
    estop_sub_ = create_subscription<std_msgs::msg::Bool>(
        "/astra/safety/estop", rclcpp::QoS(1).reliable(),
        [this](std_msgs::msg::Bool::ConstSharedPtr msg) {
          if (msg->data) stop("EMERGENCY_STOP", "external_estop", true);
        });
    arm_sub_ = create_subscription<std_msgs::msg::Bool>(
        "/astra/safety/arm", rclcpp::QoS(1).reliable(),
        [this](std_msgs::msg::Bool::ConstSharedPtr msg) {
          if (msg->data && mode_ == "SAFE_IDLE" && scan_fresh()) {
            mode_ = "ACTIVE";
            reason_ = "operator_arm";
            last_intent_wall_ = std::chrono::steady_clock::now();
            publish_state();
          }
        });
    recovery_sub_ = create_subscription<std_msgs::msg::Bool>(
        "/astra/safety/recovery", rclcpp::QoS(1).reliable(),
        [this](std_msgs::msg::Bool::ConstSharedPtr msg) {
          if (msg->data && (mode_ == "EMERGENCY_STOP" || mode_ == "PROTECTIVE_STOP") && scan_fresh() && front_clearance_ >= 0.8f) {
            estop_latched_ = false;
            mode_ = "SAFE_IDLE";
            reason_ = "explicit_recovery_self_check";
            publish_zero();
            publish_state();
          }
        });
    watchdog_ = create_wall_timer(50ms, [this]() {
      if (!ready_ && std::chrono::steady_clock::now() - started_wall_ > 30s) {
        stop("PROTECTIVE_STOP", "sensor_startup_timeout", false);
      } else if (ready_ && !scan_fresh()) {
        if (mode_ != "EMERGENCY_STOP") stop("PROTECTIVE_STOP", "scan_heartbeat_lost", false);
      } else if (ready_ && mode_ == "INIT") {
        mode_ = "SAFE_IDLE";
        reason_ = "sensor_self_check_passed";
      }
      if (mode_ != "ACTIVE") publish_zero();
      else if (last_intent_wall_.time_since_epoch().count() == 0 ||
               std::chrono::steady_clock::now() - last_intent_wall_ > 250ms) {
        stop("PROTECTIVE_STOP", "intent_heartbeat_lost", false);
      }
      publish_state();
    });
    publish_zero();
  }

 private:
  bool scan_fresh() const {
    return ready_ && std::chrono::steady_clock::now() - last_scan_wall_ <= 750ms;
  }

  void on_scan(const sensor_msgs::msg::LaserScan &scan) {
    if (scan.header.frame_id != "astra/base_footprint/lidar_2d" || scan.angle_increment <= 0 ||
        scan.ranges.empty()) {
      if (ready_) stop("PROTECTIVE_STOP", "invalid_scan_frame_or_geometry", false);
      return;
    }
    const rclcpp::Time sample(scan.header.stamp);
    const auto age = (now() - sample).seconds();
    if (age < -0.05 || age > 0.35) {
      if (ready_) stop("PROTECTIVE_STOP", "invalid_scan_timestamp", false);
      return;
    }
    float clearance = std::numeric_limits<float>::infinity();
    for (size_t i = 0; i < scan.ranges.size(); ++i) {
      const float angle = scan.angle_min + static_cast<float>(i) * scan.angle_increment;
      const float range = scan.ranges[i];
      if (std::abs(angle) <= 0.65f && std::isfinite(range) && range >= scan.range_min && range <= scan.range_max) {
        clearance = std::min(clearance, range);
      }
    }
    if (!std::isfinite(clearance)) {
      if (ready_) stop("PROTECTIVE_STOP", "front_clearance_unknown", false);
      return;
    }
    const auto current_wall = std::chrono::steady_clock::now();
    stable_scan_count_ = have_scan_ && current_wall - last_scan_wall_ <= 750ms ? stable_scan_count_ + 1 : 1;
    ready_ = ready_ || stable_scan_count_ >= 3;
    front_clearance_ = clearance;
    have_scan_ = true;
    last_scan_wall_ = current_wall;
    if (mode_ == "ACTIVE" && front_clearance_ < 0.8f) {
      stop("PROTECTIVE_STOP", "obstacle_inside_protective_distance", false);
    }
  }

  void on_intent(const astra_interfaces::msg::ControlIntent &intent) {
    if (mode_ != "ACTIVE" || estop_latched_ || !scan_fresh()) {
      publish_zero();
      return;
    }
    const rclcpp::Time issued(intent.issued_at);
    const double age = (now() - issued).seconds();
    const bool valid = intent.schema_version == "astra.control-intent.v1" &&
                       intent.frame_id == "base_link" && intent.clock_domain == "sim" &&
                       !intent.mission_id.empty() && intent.ttl_seconds > 0 && intent.ttl_seconds <= 0.25f &&
                       age >= -0.05 && age <= intent.ttl_seconds &&
                       std::isfinite(intent.linear_meters_per_second) &&
                       std::isfinite(intent.angular_radians_per_second) &&
                       std::abs(intent.linear_meters_per_second) <= 0.35f &&
                       std::abs(intent.angular_radians_per_second) <= 0.8f &&
                       intent.arm_radians_per_second == 0.0f && front_clearance_ >= 0.8f;
    if (!valid) {
      stop("PROTECTIVE_STOP", "invalid_or_unsafe_control_intent", false);
      return;
    }
    geometry_msgs::msg::Twist command;
    command.linear.x = intent.linear_meters_per_second;
    command.angular.z = intent.angular_radians_per_second;
    command_pub_->publish(command);
    last_intent_wall_ = std::chrono::steady_clock::now();
  }

  void publish_zero() {
    command_pub_->publish(geometry_msgs::msg::Twist());
  }

  void stop(const std::string &mode, const std::string &reason, bool latch) {
    if (mode_ != mode || reason_ != reason) {
      astra_interfaces::msg::FaultEvent fault;
      fault.schema_version = "astra.fault-event.v1";
      fault.fault_id = "safety-" + std::to_string(++fault_sequence_);
      fault.frame_id = "base_link";
      fault.clock_domain = "sim";
      fault.detected_at = now();
      fault.severity = latch ? "EMERGENCY" : "PROTECTIVE";
      fault.result_code = latch ? "E_STOP_LATCHED" : "SAFETY_STOP";
      fault.reason = reason;
      fault_pub_->publish(fault);
    }
    mode_ = mode;
    reason_ = reason;
    estop_latched_ = estop_latched_ || latch;
    publish_zero();
    publish_state();
  }

  void publish_state() {
    astra_interfaces::msg::SafetyState state;
    state.schema_version = "astra.safety-state.v1";
    state.mode = mode_;
    state.frame_id = "base_link";
    state.clock_domain = "sim";
    state.observed_at = now();
    state.estop_latched = estop_latched_;
    state.sensor_age_seconds = have_scan_ ? std::chrono::duration<float>(std::chrono::steady_clock::now() - last_scan_wall_).count() : std::numeric_limits<float>::infinity();
    state.minimum_front_clearance_meters = front_clearance_;
    state.reason = reason_;
    state_pub_->publish(state);
  }

  std::string mode_ = "INIT";
  std::string reason_ = "waiting_for_sensor";
  bool estop_latched_ = false;
  bool have_scan_ = false;
  bool ready_ = false;
  unsigned int stable_scan_count_ = 0;
  unsigned long fault_sequence_ = 0;
  float front_clearance_ = std::numeric_limits<float>::infinity();
  std::chrono::steady_clock::time_point started_wall_;
  std::chrono::steady_clock::time_point last_scan_wall_;
  std::chrono::steady_clock::time_point last_intent_wall_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr command_pub_;
  rclcpp::Publisher<astra_interfaces::msg::SafetyState>::SharedPtr state_pub_;
  rclcpp::Publisher<astra_interfaces::msg::FaultEvent>::SharedPtr fault_pub_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<astra_interfaces::msg::ControlIntent>::SharedPtr intent_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr estop_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr arm_sub_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr recovery_sub_;
  rclcpp::TimerBase::SharedPtr watchdog_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<SafetyGateway>());
  rclcpp::shutdown();
  return 0;
}
