"""Fail closed on incomplete or unsafe ROS/Gazebo bringup campaign evidence."""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from embodied.ros_campaign import verify_campaign  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--promote-local", action="store_true")
    parser.add_argument("--replace-promoted", action="store_true")
    args = parser.parse_args()
    if args.replace_promoted and not args.promote_local:
        parser.error("--replace-promoted requires --promote-local")
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    profile_hash = hashlib.sha256(
        (ROOT / "configs" / "robotics-profile.lock").read_bytes()
    ).hexdigest()
    summary = verify_campaign(report, expected_profile_sha256=profile_hash)
    if args.promote_local:
        target_dir = (ROOT / "reports" / "local" / "ros-bringup-campaign").resolve()
        if args.report.resolve().parent != target_dir:
            raise ValueError("only a local campaign report may be promoted")
        target = target_dir / "final.json"
        if target.exists() and target.read_bytes() != args.report.read_bytes():
            if not args.replace_promoted:
                raise FileExistsError(
                    "a different final ROS campaign is already promoted; "
                    "use --replace-promoted to preserve and supersede it"
                )
            archived_hash = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
            archived = target_dir / f"archive-{archived_hash}.json"
            if not archived.exists():
                shutil.copyfile(target, archived)
            shutil.copyfile(args.report, target)
        elif not target.exists():
            shutil.copyfile(args.report, target)
        summary["promoted_report"] = str(target.relative_to(ROOT))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
