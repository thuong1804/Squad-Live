"""Provider-independent BA output: validated before entering any review gate."""

from dataclasses import dataclass
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=2000)]
Short = Annotated[str, Field(min_length=1, max_length=200)]


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class UserStory(Structured):
    id: Short
    role: Short
    goal: Text
    benefit: Text


class AcceptanceCriterion(Structured):
    id: Short
    story_id: Short
    given: Text
    when: Text
    then: Text


class RequirementSpecification(Structured):
    title: Short
    summary: Text
    user_stories: list[UserStory] = Field(min_length=1, max_length=12)
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=1, max_length=30)
    edge_cases: list[Text] = Field(max_length=15)
    non_functional_requirements: list[Text] = Field(max_length=15)
    open_questions: list[Text] = Field(max_length=15)
    assumptions: list[Text] = Field(max_length=15)

    @model_validator(mode="after")
    def coherent(self):
        stories = [story.id for story in self.user_stories]
        criteria = [criterion.id for criterion in self.acceptance_criteria]
        if len(stories) != len(set(stories)) or len(criteria) != len(set(criteria)):
            raise ValueError("Duplicate story or criterion ID")
        if any(criterion.story_id not in stories for criterion in self.acceptance_criteria):
            raise ValueError("Acceptance criterion references an unknown story")
        if len(self.model_dump_json()) > 24000:
            raise ValueError("Specification exceeds output budget")
        return self


@dataclass(frozen=True)
class Generation:
    specification: BaseModel
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = True):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class LLMProvider(Protocol):
    def generate(self, context: str, model: str) -> Generation: ...
