from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data_loader import normalize_his_dataset


@dataclass(frozen=True)
class HospitalProfile:
    slug: str
    display_name: str
    days: int
    daily_admissions: int
    emergency_share: float
    icu_share: float
    pediatric_share: float
    avg_los_hours: float
    weekend_factor: float
    surge_probability: float


PROFILES = [
    HospitalProfile(
        slug="metro_general",
        display_name="Metro General Hospital",
        days=150,
        daily_admissions=132,
        emergency_share=0.29,
        icu_share=0.11,
        pediatric_share=0.08,
        avg_los_hours=44,
        weekend_factor=0.88,
        surge_probability=0.08,
    ),
    HospitalProfile(
        slug="community_care",
        display_name="Community Care Hospital",
        days=120,
        daily_admissions=74,
        emergency_share=0.22,
        icu_share=0.07,
        pediatric_share=0.05,
        avg_los_hours=34,
        weekend_factor=0.92,
        surge_probability=0.05,
    ),
    HospitalProfile(
        slug="pediatric_specialty",
        display_name="Pediatric Specialty Center",
        days=140,
        daily_admissions=96,
        emergency_share=0.24,
        icu_share=0.09,
        pediatric_share=0.36,
        avg_los_hours=38,
        weekend_factor=0.90,
        surge_probability=0.06,
    ),
]


def weighted_department(rng: random.Random, profile: HospitalProfile) -> tuple[str, str]:
    draw = rng.random()
    emergency_cutoff = profile.emergency_share
    icu_cutoff = emergency_cutoff + profile.icu_share
    pediatric_cutoff = icu_cutoff + profile.pediatric_share

    if draw < emergency_cutoff:
        return "Emergency Department", "Emergency"
    if draw < icu_cutoff:
        return "ICU", "Emergency" if rng.random() < 0.7 else "Transfer"
    if draw < pediatric_cutoff:
        return "Pediatric Ward", "Emergency" if rng.random() < 0.45 else "Scheduled"
    return "General Ward", "Scheduled" if rng.random() < 0.7 else "Observation"


def estimated_length_of_stay_hours(
    rng: random.Random,
    department: str,
    admission_type: str,
    profile: HospitalProfile,
) -> float:
    base = profile.avg_los_hours
    if department == "ICU":
        base *= 1.8
    elif department == "Emergency Department":
        base *= 0.25
    elif department == "Pediatric Ward":
        base *= 0.85

    if admission_type == "Scheduled":
        base *= 1.1
    elif admission_type == "Observation":
        base *= 0.65

    return max(6.0, rng.gauss(base, base * 0.28))


def hourly_pressure(hour: int) -> float:
    if 7 <= hour <= 10:
        return 1.22
    if 11 <= hour <= 16:
        return 1.12
    if 17 <= hour <= 21:
        return 1.18
    if 0 <= hour <= 4:
        return 0.56
    return 0.84


def build_event_rows(profile: HospitalProfile, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    start = datetime(2025, 1, 1, 0, 0)
    patient_counter = 100000 + (seed * 1000)
    rows: list[dict[str, str]] = []
    surge_hours_remaining = 0

    for day_offset in range(profile.days):
        current_day = start + timedelta(days=day_offset)
        weekend_multiplier = profile.weekend_factor if current_day.weekday() >= 5 else 1.0
        if rng.random() < profile.surge_probability:
            surge_hours_remaining = rng.randint(18, 48)

        for hour in range(24):
            timestamp = current_day + timedelta(hours=hour)
            multiplier = weekend_multiplier * hourly_pressure(hour)
            if surge_hours_remaining > 0:
                multiplier *= 1.28
                surge_hours_remaining -= 1

            expected = (profile.daily_admissions / 24.0) * multiplier
            admissions_this_hour = max(0, int(round(rng.gauss(expected, max(1.0, expected * 0.22)))))

            for _ in range(admissions_this_hour):
                department, admission_type = weighted_department(rng, profile)
                minute = rng.randint(0, 59)
                admission_time = timestamp + timedelta(minutes=minute)
                length_of_stay = estimated_length_of_stay_hours(rng, department, admission_type, profile)
                discharge_time = admission_time + timedelta(hours=length_of_stay)
                rows.append(
                    {
                        "patient_id": f"{profile.slug[:4].upper()}-{patient_counter}",
                        "admission_time": admission_time.isoformat(timespec="minutes"),
                        "discharge_time": discharge_time.isoformat(timespec="minutes"),
                        "department": department,
                        "admission_type": admission_type,
                    }
                )
                patient_counter += 1

    return rows


def write_profile(output_dir: Path, profile: HospitalProfile, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_event_rows(profile, seed)

    event_path = output_dir / f"{profile.slug}_his_events.csv"
    header = "patient_id,admission_time,discharge_time,department,admission_type"
    lines = [header] + [
        ",".join([
            row["patient_id"],
            row["admission_time"],
            row["discharge_time"],
            row["department"],
            row["admission_type"],
        ])
        for row in rows
    ]
    csv_text = "\n".join(lines)
    event_path.write_text(csv_text, encoding="utf-8")

    normalized_frame, metadata = normalize_his_dataset(csv_text, profile.display_name)
    aggregate_path = output_dir / f"{profile.slug}_hourly_occupancy.csv"
    normalized_frame.to_csv(aggregate_path, index=False)

    manifest = {
        "profile": profile.display_name,
        "event_dataset": event_path.name,
        "aggregate_dataset": aggregate_path.name,
        "rows": len(rows),
        "hourly_rows": int(len(normalized_frame)),
        "metadata": metadata,
    }
    (output_dir / f"{profile.slug}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Seeded {profile.display_name}: {len(rows)} encounters -> {len(normalized_frame)} hourly rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate multiple hospital-profile HIS seed datasets.")
    parser.add_argument(
        "--output-dir",
        default=str(Path("backend") / "data" / "seeds"),
        help="Directory where profile seed datasets will be written.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed for reproducible profile generation.",
    )
    args = parser.parse_args()

    root = Path(args.output_dir)
    for index, profile in enumerate(PROFILES):
        write_profile(root / profile.slug, profile, args.seed + index)


if __name__ == "__main__":
    main()
