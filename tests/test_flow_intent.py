"""Flow intent classification coverage."""

import pytest

from akomagni.flow.intent import classify_message


@pytest.mark.parametrize(
    "message,skill",
    [
        ("génère un logo pour mon app", "image-pipeline"),
        ("je veux créer un nouveau jeu unity", "gds-brainstorm-game"),
        ("run qa e2e tests", "bmad-testarch-automate"),
        ("fais un pitch deck investisseurs", "presentation-deck"),
        ("innovation disruption blue ocean", "bmad-cis-innovation-strategy"),
        ("problème complexe root cause", "bmad-cis-problem-solving"),
        ("écris un post linkedin", "bmad-cis-storytelling"),
        ("design wireframe figma", "bmad-ux"),
        ("architecture infra scalable", "bmad-architecture"),
        ("écris le prd", "bmad-prd"),
        ("bonjour comment ça va", "chat"),
    ],
)
def test_classify_routes(message, skill):
    decision = classify_message(message)
    assert decision.skill == skill


def test_classify_greenfield_brainstorm():
    decision = classify_message("une idée pour une app", greenfield=True)
    assert decision.skill == "bmad-brainstorming"
    assert decision.greenfield is True


def test_classify_creative_brainstorm():
    decision = classify_message("brainstorm créatif wild", greenfield=True)
    assert decision.agent_id == "bmad-cis-agent-brainstorming-coach"
