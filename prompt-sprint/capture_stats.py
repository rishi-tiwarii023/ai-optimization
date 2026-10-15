import argparse

from dotenv import load_dotenv

from main import RESPONSES_DIR, ensure_responses_dir, load_json, save_json
from run_history import refresh_stats_snapshot


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Capture PromptSprint run stats snapshot")
    parser.add_argument("--output", default=RESPONSES_DIR)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    responses_dir = ensure_responses_dir(args.output)
    result = refresh_stats_snapshot(responses_dir, load_json, save_json)
    print(result["message"])
    if result["score_stats"]:
        stats = result["score_stats"]
        print(
            "Score stats: "
            f"count={stats['count']} mean={stats['mean']} median={stats['median']} "
            f"mode={stats['mode']} max={stats['max']} median_range={stats['median_range']} "
            f"p95={stats['p95']} std_dev={stats['std_dev']}"
        )


if __name__ == "__main__":
    main()
