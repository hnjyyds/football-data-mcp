from __future__ import annotations

from pydantic import ConfigDict

from football_data_mcp.api.schemas.common import LooseObjectResponse


class AIAnalysisLooseResponse(LooseObjectResponse):
    model_config = ConfigDict(extra="allow")


class AIMatchesWindowResponse(AIAnalysisLooseResponse):
    pass


class AIShortlistResponse(AIAnalysisLooseResponse):
    pass


class AIMatchAnalysisResponse(AIAnalysisLooseResponse):
    pass


class AIMatchOddsResponse(AIAnalysisLooseResponse):
    pass


class AIReviewSummaryResponse(AIAnalysisLooseResponse):
    pass


class AIReviewMatchResponse(AIAnalysisLooseResponse):
    pass


class AIOddsSourceStatusResponse(AIAnalysisLooseResponse):
    pass
