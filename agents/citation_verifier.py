"""
CitationVerifierAgent — checks every differential has at least one
exact-quote citation; flags gaps.
"""
from __future__ import annotations

from typing import List

import structlog

from api.models import CitationSnippet, Differential, GroundednessNote

log = structlog.get_logger()


class CitationVerifierAgent:
    async def verify(
        self,
        differentials: List[Differential],
        citations: List[CitationSnippet],
    ) -> GroundednessNote:
        """
        For each differential, check:
        1. It references at least one snippet_id.
        2. That snippet_id exists in citations.
        3. The cited snippet has a non-empty quote.
        """
        citation_index = {c.id: c for c in citations}
        gaps: List[str] = []
        verified_count = 0

        for diff in differentials:
            if not diff.support:
                gaps.append(
                    f'"{diff.dx}" has no citation support.'
                )
                continue

            has_valid = False
            for ref in diff.support:
                sid = ref.get("snippet_id", "")
                if sid not in citation_index:
                    gaps.append(
                        f'"{diff.dx}" references unknown snippet {sid}.'
                    )
                    continue
                snippet = citation_index[sid]
                if not snippet.quote or len(snippet.quote.strip()) < 10:
                    gaps.append(
                        f'Snippet {sid} cited by "{diff.dx}" has no quote.'
                    )
                    continue
                has_valid = True

            if has_valid:
                verified_count += 1

        all_verified = len(gaps) == 0
        note = (
            f"{verified_count}/{len(differentials)} differentials fully grounded."
            if not all_verified
            else "All differentials are grounded in retrieved evidence."
        )

        if gaps:
            note += f" Gaps: {'; '.join(gaps[:3])}"
            if len(gaps) > 3:
                note += f" ... (+{len(gaps)-3} more)"

        log.info("citation_verification",
                 verified=all_verified, gaps=len(gaps),
                 differentials=len(differentials))

        return GroundednessNote(
            verified=all_verified,
            gaps=gaps,
            note=note,
        )
