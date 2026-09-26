#include <chrono>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <regex>
#include <string>
#include <thread>

#include "astra_interfaces/action/skill_invocation.hpp"
#include "astra_interfaces/msg/goal_request.hpp"
#include "astra_interfaces/msg/policy_decision.hpp"
#include "behaviortree_cpp/bt_factory.h"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_msgs/msg/string.hpp"

using namespace std::chrono_literals;
using Skill = astra_interfaces::action::SkillInvocation;
using GoalHandle = rclcpp_action::ClientGoalHandle<Skill>;

class MissionNode final : public rclcpp::Node {
 public:
  MissionNode() : Node("mission_executive") {
    events_ = create_publisher<std_msgs::msg::String>("/astra/evidence/mission_events", 16);
    goals_ = create_publisher<astra_interfaces::msg::GoalRequest>("/astra/goals/request", 4);
    goal_sub_ = create_subscription<astra_interfaces::msg::GoalRequest>(
        "/astra/goals/request", 4,
        [this](astra_interfaces::msg::GoalRequest::ConstSharedPtr goal) {
          static const std::regex mission_pattern("^mission-[a-z0-9-]{1,56}$");
          std::lock_guard<std::mutex> guard(lock_);
          if (running_ || finished_ || !std::regex_match(goal->mission_id, mission_pattern) ||
              goal->target_id != "object-00" || goal->station_id != "inspection-station" ||
              goal->requested_by != "local-operator" || goal->frame_id != "map" ||
              goal->clock_domain != "sim" || goal->schema_version != "astra.goal-request.v1") return;
          const double age = (now() - rclcpp::Time(goal->requested_at)).seconds();
          if (age < -0.05 || age > goal->ttl_seconds || goal->ttl_seconds <= 0 || goal->ttl_seconds > 1) return;
          pending_ = *goal;
        });
    policy_sub_ = create_subscription<astra_interfaces::msg::PolicyDecision>(
        "/astra/goals/decision", rclcpp::QoS(4).reliable().transient_local(),
        [this](astra_interfaces::msg::PolicyDecision::ConstSharedPtr decision) {
          std::lock_guard<std::mutex> guard(lock_);
          if (!pending_ || running_ || finished_ || decision->mission_id != pending_->mission_id) return;
          const double age = (now() - rclcpp::Time(decision->decided_at)).seconds();
          ready_ = decision->schema_version == "astra.policy-decision.v1" &&
                   decision->frame_id == "map" && decision->clock_domain == "sim" &&
                   decision->allowed && decision->result_code == "OK" && age >= -0.05 && age <= 1.0;
        });
    heartbeat_ = create_wall_timer(150ms, [this]() {
      astra_interfaces::msg::GoalRequest copy;
      {
        std::lock_guard<std::mutex> guard(lock_);
        if (!running_ || !pending_) return;
        copy = *pending_;
      }
      copy.requested_at = now();
      goals_->publish(copy);
    });
  }

  bool take_ready(std::string& mission, std::string& target) {
    std::lock_guard<std::mutex> guard(lock_);
    if (!ready_ || !pending_ || running_ || finished_) return false;
    running_ = true;
    mission = pending_->mission_id;
    target = pending_->target_id;
    return true;
  }

  void finish(const std::string& mission, const std::string& status) {
    {
      std::lock_guard<std::mutex> guard(lock_);
      running_ = false;
      finished_ = true;
    }
    event(mission, status);
  }

  void event(const std::string& mission, const std::string& status) {
    std_msgs::msg::String out;
    out.data = "{\"schema_version\":\"astra.mission-event.v1\",\"mission_id\":\"" +
               mission + "\",\"status\":\"" + status + "\"}";
    events_->publish(out);
  }

 private:
  std::mutex lock_;
  std::optional<astra_interfaces::msg::GoalRequest> pending_;
  bool ready_{false};
  bool running_{false};
  bool finished_{false};
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr events_;
  rclcpp::Publisher<astra_interfaces::msg::GoalRequest>::SharedPtr goals_;
  rclcpp::Subscription<astra_interfaces::msg::GoalRequest>::SharedPtr goal_sub_;
  rclcpp::Subscription<astra_interfaces::msg::PolicyDecision>::SharedPtr policy_sub_;
  rclcpp::TimerBase::SharedPtr heartbeat_;
};

class SkillStep final : public BT::StatefulActionNode {
 public:
  SkillStep(const std::string& name, const BT::NodeConfig& config,
            const std::shared_ptr<MissionNode>& node, const std::string& mission,
            const std::string& target)
      : BT::StatefulActionNode(name, config), node_(node), mission_(mission), target_(target),
        client_(rclcpp_action::create_client<Skill>(node, "/astra/skills/invoke")) {}

  static BT::PortsList providedPorts() {
    return {BT::InputPort<std::string>("skill"), BT::InputPort<double>("timeout")};
  }

  BT::NodeStatus onStart() override {
    const auto skill = getInput<std::string>("skill");
    const auto timeout = getInput<double>("timeout");
    if (!skill || !timeout || timeout.value() <= 0 || timeout.value() > 60 ||
        !client_->action_server_is_ready()) return BT::NodeStatus::FAILURE;
    Skill::Goal goal;
    goal.schema_version = "astra.skill-invocation.v1";
    goal.mission_id = mission_;
    goal.skill_name = skill.value();
    goal.target_id = target_;
    goal.frame_id = "map";
    goal.clock_domain = "sim";
    goal.requested_at = node_->now();
    goal.timeout_seconds = static_cast<float>(timeout.value());
    deadline_ = std::chrono::steady_clock::now() + std::chrono::milliseconds(
        static_cast<int>(timeout.value() * 1000) + 1000);
    accepted_ = client_->async_send_goal(goal);
    return BT::NodeStatus::RUNNING;
  }

  BT::NodeStatus onRunning() override {
    if (std::chrono::steady_clock::now() >= deadline_) {
      if (handle_) client_->async_cancel_goal(handle_);
      return BT::NodeStatus::FAILURE;
    }
    if (!handle_) {
      if (accepted_.wait_for(0s) != std::future_status::ready) return BT::NodeStatus::RUNNING;
      handle_ = accepted_.get();
      if (!handle_) return BT::NodeStatus::FAILURE;
      result_ = client_->async_get_result(handle_);
    }
    if (result_.wait_for(0s) != std::future_status::ready) return BT::NodeStatus::RUNNING;
    const auto wrapped = result_.get();
    const bool success = wrapped.code == rclcpp_action::ResultCode::SUCCEEDED &&
                         wrapped.result && wrapped.result->completed && wrapped.result->result_code == "OK";
    node_->event(mission_, success ? "SKILL_OK" : "SKILL_FAILED");
    return success ? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
  }

  void onHalted() override {
    if (handle_) client_->async_cancel_goal(handle_);
  }

 private:
  std::shared_ptr<MissionNode> node_;
  std::string mission_;
  std::string target_;
  rclcpp_action::Client<Skill>::SharedPtr client_;
  std::shared_future<GoalHandle::SharedPtr> accepted_;
  std::shared_future<GoalHandle::WrappedResult> result_;
  GoalHandle::SharedPtr handle_;
  std::chrono::steady_clock::time_point deadline_;
};

static void request_safe_stop(const std::shared_ptr<MissionNode>& node,
                              const std::string& mission, const std::string& target) {
  auto client = rclcpp_action::create_client<Skill>(node, "/astra/skills/invoke");
  if (!client->wait_for_action_server(2s)) return;
  Skill::Goal goal;
  goal.schema_version = "astra.skill-invocation.v1";
  goal.mission_id = mission;
  goal.skill_name = "safe_stop";
  goal.target_id = target;
  goal.frame_id = "map";
  goal.clock_domain = "sim";
  goal.requested_at = node->now();
  goal.timeout_seconds = 2.0f;
  auto accepted = client->async_send_goal(goal);
  if (accepted.wait_for(2s) != std::future_status::ready) return;
  auto handle = accepted.get();
  if (!handle) return;
  auto result = client->async_get_result(handle);
  result.wait_for(2s);
}

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<MissionNode>();
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spin([&executor]() { executor.spin(); });
  while (rclcpp::ok()) {
    std::string mission, target;
    if (!node->take_ready(mission, target)) {
      std::this_thread::sleep_for(50ms);
      continue;
    }
    node->event(mission, "RUNNING");
    BT::BehaviorTreeFactory factory;
    factory.registerBuilder<SkillStep>("Skill", [node, mission, target](const std::string& name,
        const BT::NodeConfig& config) {
      return std::make_unique<SkillStep>(name, config, node, mission, target);
    });
    const char* xml = R"(<root BTCPP_format="4"><BehaviorTree ID="AstraMission"><SequenceWithMemory>
      <Skill skill="observe_area" timeout="5"/><Skill skill="locate_entity" timeout="5"/>
      <Skill skill="wait_for_clearance" timeout="10"/><Skill skill="navigate_to" timeout="30"/>
      <Skill skill="align_base" timeout="8"/><Skill skill="point_at" timeout="10"/>
      <Skill skill="inspect_entity" timeout="5"/><Skill skill="speak_report" timeout="5"/>
      <Skill skill="return_home" timeout="30"/><Skill skill="safe_stop" timeout="2"/>
      </SequenceWithMemory></BehaviorTree></root>)";
    auto tree = factory.createTreeFromText(xml);
    BT::NodeStatus status = BT::NodeStatus::RUNNING;
    const auto mission_deadline = std::chrono::steady_clock::now() + 90s;
    while (rclcpp::ok() && status == BT::NodeStatus::RUNNING &&
           std::chrono::steady_clock::now() < mission_deadline) {
      status = tree.tickOnce();
      std::this_thread::sleep_for(50ms);
    }
    tree.haltTree();
    if (status != BT::NodeStatus::SUCCESS) request_safe_stop(node, mission, target);
    node->finish(mission, status == BT::NodeStatus::SUCCESS ? "SUCCEEDED" : "ABORTED_SAFE");
  }
  executor.cancel();
  spin.join();
  rclcpp::shutdown();
  return 0;
}
