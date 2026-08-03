"""
Shared type definitions and type aliases for CyberScout AI.
"""

from typing import Any, Dict, List, Union

JsonDict = Dict[str, Any]
OpportunityId = str
SourceId = str
RunId = str
ScoreBreakdown = Dict[str, Union[int, float, str]]
TagList = List[str]
