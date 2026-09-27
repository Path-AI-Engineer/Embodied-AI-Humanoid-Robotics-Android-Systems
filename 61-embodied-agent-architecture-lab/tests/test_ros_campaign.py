"""A partial or unsafe campaign must never appear as verified live evidence."""

import unittest

from embodied.ros_campaign import verify_campaign


def campaign():
    return {
        "schema_version": "astra.ros-bringup-campaign.v1",
        "requested_runs": 12,
        "image_id": "sha256:" + "a" * 64,
        "robotics_profile_sha256": "b" * 64,
        "results": [
            {
                "run": index,
                "exit_code": 0,
                "wall_seconds": 100,
                "rosbag_verification": {
                    "arm_samples_within_limits": 100,
                    "estop_to_recovery_zero_motion": True,
                    "mission_event_sequence": "verified",
                    "policy_and_fault_lineage": True,
                    "topics": {"/astra/evidence/mission_events": 12},
                },
            }
            for index in range(1, 13)
        ],
    }


class RosCampaignTests(unittest.TestCase):
    def test_accepts_only_complete_safe_campaign(self) -> None:
        self.assertEqual(verify_campaign(campaign())["clean_bringups"], 12)
        with self.assertRaisesRegex(ValueError, "profile differs"):
            verify_campaign(campaign(), expected_profile_sha256="c" * 64)
        for mutation in (
            "missing_run",
            "failed_run",
            "moving_after_estop",
            "incomplete_events",
            "malformed_bag",
        ):
            with self.subTest(mutation=mutation):
                report = campaign()
                if mutation == "missing_run":
                    report["results"].pop()
                elif mutation == "failed_run":
                    report["results"][4]["exit_code"] = 30
                elif mutation == "moving_after_estop":
                    report["results"][4]["rosbag_verification"][
                        "estop_to_recovery_zero_motion"
                    ] = False
                elif mutation == "malformed_bag":
                    report["results"][4]["rosbag_verification"] = []
                else:
                    report["results"][4]["rosbag_verification"]["topics"][
                        "/astra/evidence/mission_events"
                    ] = 11
                with self.assertRaises(ValueError):
                    verify_campaign(report)


if __name__ == "__main__":
    unittest.main()
