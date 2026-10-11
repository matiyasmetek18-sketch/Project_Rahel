from __future__ import annotations

from job_assistant.model_benchmark import score_model


class FictionalModel:
    name = "fictional-structured-model"
    cost_per_1k = 0.01

    def extract_requirements(self, posting: str):
        lower = posting.lower()
        return tuple(
            item
            for item in ("cpr", "weekend availability", "transfer assistance", "reliable transportation", "companionship", "medication reminders")
            if item in lower
        )


def test_model_benchmark_is_reproducible_with_fictional_data():
    result = score_model(FictionalModel())
    assert result.model_name == "fictional-structured-model"
    assert 0 <= result.accuracy <= 1
    assert result.cost_per_1k == 0.01
