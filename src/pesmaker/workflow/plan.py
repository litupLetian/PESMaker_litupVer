from __future__ import annotations

from dataclasses import dataclass

from pesmaker.config.schema import PESMakerConfig


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    detail: str


@dataclass(frozen=True)
class WorkflowPlan:
    project: str
    steps: tuple[WorkflowStep, ...]

    def to_text(self) -> str:
        lines = [f"PESMaker workflow plan for '{self.project}':"]
        for index, step in enumerate(self.steps, start=1):
            lines.append(f"{index}. {step.name}: {step.detail}")
        return "\n".join(lines)


def build_plan(config: PESMakerConfig) -> WorkflowPlan:
    steps = (
        WorkflowStep(
            "load structures",
            f"{len(config.structures)} input structure(s)",
        ),
        WorkflowStep(
            "generate candidates",
            f"supercell={config.generation.supercell}, "
            f"perturb={bool(config.generation.perturb)}",
        ),
        WorkflowStep(
            "sample configurations",
            f"engine={config.sampling.engine}",
        ),
        WorkflowStep(
            "label with DFT",
            f"engine={config.labeling.engine}",
        ),
        WorkflowStep(
            "assemble dataset",
            f"format={config.dataset.format}, split={config.dataset.split}",
        ),
        WorkflowStep(
            "train potential",
            f"model={config.training.engine}",
        ),
    )
    return WorkflowPlan(project=config.project, steps=steps)

