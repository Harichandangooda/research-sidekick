import unittest

from agents import AgentOutputSchema
from pydantic import ValidationError

from backend.services.discovery_service import DiscoveredPaper, SearchResults


class DiscoverySchemaTests(unittest.TestCase):
    def test_actual_agent_schema_has_no_unsupported_uri_format(self):
        schema = AgentOutputSchema(SearchResults).json_schema()
        url = schema["$defs"]["DiscoveredPaper"]["properties"]["url"]
        self.assertEqual(url["type"], "string")
        self.assertNotIn("format", url)

    def test_urls_are_still_validated_and_serialized_as_strings(self):
        fields = dict(title="Paper", authors="Author", year=2026, summary="Summary",
                      relevance=0.9, relevance_reason="Relevant")
        for url in ("https://example.com/paper.pdf", "http://example.com/paper"):
            paper = DiscoveredPaper(url=url, **fields)
            self.assertEqual(paper.model_dump(mode="json")["url"], url)
        for url in ("not a URL", "javascript:alert(1)", "ftp://example.com/paper"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                DiscoveredPaper(url=url, **fields)
