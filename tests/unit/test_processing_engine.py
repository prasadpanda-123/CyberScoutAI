"""
Unit tests for Processing Engine (Phase 4).
"""

import unittest

from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.processors.classifier import ClassifierProcessor
from src.processors.cleaner import CleanerProcessor
from src.processors.deduplicator import DeduplicatorProcessor
from src.processors.exceptions import QualityError, ValidationError
from src.processors.keyword_extractor import KeywordExtractorProcessor
from src.processors.metadata import MetadataExtractorProcessor
from src.processors.normalizer import NormalizerProcessor
from src.processors.pipeline import ProcessingPipeline
from src.processors.quality_checker import QualityCheckerProcessor
from src.processors.validator import ValidatorProcessor


class TestProcessingEngine(unittest.TestCase):
    def test_validator(self):
        validator = ValidatorProcessor()
        valid_item = Opportunity(
            title="SOC Analyst Intern",
            url="https://example.com/job/1",
            source_id="test",
        )
        res = validator.process(valid_item)
        self.assertIsNotNone(res)

        invalid_item = Opportunity(title="", url="invalid-url", source_id="test")
        with self.assertRaises(ValidationError):
            validator.process(invalid_item)

    def test_cleaner(self):
        cleaner = CleanerProcessor()
        dirty_item = Opportunity(
            title="<h1>SOC Analyst   Intern</h1>",
            url="https://example.com/job/1?utm_source=twitter&utm_medium=social",
            description="<p>Clean   text.</p>",
            source_id="test",
        )
        res = cleaner.process(dirty_item)
        self.assertEqual(res.title, "SOC Analyst Intern")
        self.assertEqual(res.url, "https://example.com/job/1")
        self.assertEqual(res.description, "Clean text.")

    def test_normalizer(self):
        normalizer = NormalizerProcessor()
        item = Opportunity(
            title="Remote DevSecOps Engineer",
            url="https://example.com/job/1",
            source_id="test",
            published_date="2026-08-01T12:00:00Z",
            provider="github",
        )
        res = normalizer.process(item)
        self.assertEqual(res.published_date, "2026-08-01")
        self.assertTrue(res.remote)

    def test_metadata_and_keyword_extractor(self):
        meta_proc = MetadataExtractorProcessor()
        kw_proc = KeywordExtractorProcessor()

        item = Opportunity(
            title="Software Intern at Google for Py and K8s",
            url="https://example.com/job/1",
            description="Free accredited course with certificate.",
            source_id="test",
        )
        res = meta_proc.process(item)
        self.assertEqual(res.company, "Google")
        self.assertTrue(res.certificate)
        self.assertFalse(res.paid)

        res_kw = kw_proc.process(res)
        self.assertIn("Python", res_kw.tags)
        self.assertIn("Kubernetes", res_kw.tags)

    def test_classifier(self):
        classifier = ClassifierProcessor()
        item = Opportunity(
            title="Cybersecurity Internship 2026",
            url="https://example.com/internship",
            source_id="test",
        )
        res = classifier.process(item)
        self.assertEqual(res.category, OpportunityCategory.INTERNSHIP.value)

    def test_deduplicator(self):
        dedup = DeduplicatorProcessor()
        item1 = Opportunity(title="Job 1", url="https://example.com/job", source_id="test")
        item2 = Opportunity(title="Job 1", url="https://example.com/job/", source_id="test")

        res1 = dedup.process(item1)
        self.assertIsNotNone(res1)
        res2 = dedup.process(item2)
        self.assertIsNone(res2)

    def test_quality_checker(self):
        quality = QualityCheckerProcessor()
        good_item = Opportunity(
            title="Cybersecurity Analyst Course",
            url="https://example.com/course",
            description="Detailed course description covering SOC operations.",
            provider="CISA",
            source_id="test",
        )
        res = quality.process(good_item)
        self.assertIsNotNone(res)
        self.assertGreaterEqual(res.score, 40)

        spam_item = Opportunity(
            title="Earn $1000 daily free crypto giveaway",
            url="https://spam.com",
            source_id="test",
        )
        with self.assertRaises(QualityError):
            quality.process(spam_item)

    def test_pipeline_execution(self):
        pipeline = ProcessingPipeline()
        items = [
            Opportunity(
                title="SOC Analyst Intern at Microsoft for Py",
                url="https://microsoft.com/careers/soc-intern?utm_source=rss",
                description="Remote internship with certificate.",
                source_id="test",
            ),
            Opportunity(
                title="Earn $1000 daily casino",
                url="https://spam.com",
                source_id="test",
            ),
        ]
        results = pipeline.process_batch(items)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company, "Microsoft")
        self.assertIn("Python", results[0].tags)
        self.assertEqual(results[0].category, OpportunityCategory.INTERNSHIP.value)


if __name__ == "__main__":
    unittest.main()
