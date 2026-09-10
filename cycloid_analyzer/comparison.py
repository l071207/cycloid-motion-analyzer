from __future__ import annotations

from math import hypot, sqrt


Point = tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def path_length(points: list[Point]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(points[index - 1], points[index]) for index in range(1, len(points)))


def resample_path(points: list[Point], sample_count: int = 120) -> list[Point]:
    if not points:
        return []
    if len(points) == 1:
        return points * sample_count

    total_length = path_length(points)
    if total_length == 0:
        return [points[0]] * sample_count

    segment_lengths = [0.0]
    for index in range(1, len(points)):
        segment_lengths.append(segment_lengths[-1] + distance(points[index - 1], points[index]))

    result: list[Point] = []
    for target_index in range(sample_count):
        target_distance = (target_index / (sample_count - 1)) * total_length
        segment_index = 1
        while segment_index < len(segment_lengths) and segment_lengths[segment_index] < target_distance:
            segment_index += 1
        if segment_index >= len(points):
            result.append(points[-1])
            continue

        start_point = points[segment_index - 1]
        end_point = points[segment_index]
        start_length = segment_lengths[segment_index - 1]
        end_length = segment_lengths[segment_index]
        span = max(end_length - start_length, 1e-9)
        ratio = (target_distance - start_length) / span
        result.append(
            (
                start_point[0] + ((end_point[0] - start_point[0]) * ratio),
                start_point[1] + ((end_point[1] - start_point[1]) * ratio),
            )
        )
    return result


def compare_paths(reference: list[Point], candidate: list[Point], sample_count: int = 120) -> dict[str, float]:
    if len(reference) < 2 or len(candidate) < 2:
        return {
            "average_distance": 0.0,
            "rmse": 0.0,
            "max_distance": 0.0,
            "path_length_ratio": 0.0,
            "similarity_score": 0.0,
        }

    ref = resample_path(reference, sample_count)
    cand = resample_path(candidate, sample_count)
    distances = [distance(a, b) for a, b in zip(ref, cand, strict=True)]
    average_distance = sum(distances) / len(distances)
    rmse = sqrt(sum(value * value for value in distances) / len(distances))
    max_distance = max(distances)
    ref_length = path_length(reference)
    cand_length = path_length(candidate)
    path_length_ratio = cand_length / ref_length if ref_length else 0.0
    similarity_score = 1.0 / (1.0 + average_distance)
    return {
        "average_distance": average_distance,
        "rmse": rmse,
        "max_distance": max_distance,
        "path_length_ratio": path_length_ratio,
        "similarity_score": similarity_score,
    }

