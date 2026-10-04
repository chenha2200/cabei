import unittest
from translation_guard import protect, restore, issues, cache_key, apply_revision

class GuardTests(unittest.TestCase):
    def test_glossary(self):
        masked, mapping = protect("Adquisición de Insecticidas y fungicidas")
        result = restore(masked, mapping)
        self.assertIn("殺蟲劑", result)
        self.assertIn("殺菌劑", result)

    def test_numbers_identifiers_urls(self):
        source = "BCIE ARG-2026-2280-34795-B USD 1,234.50 2026-10-05 https://example.com/123"
        masked, mapping = protect(source)
        result = restore(masked, mapping)
        self.assertEqual(result, source.replace("BCIE", "CABEI"))
        token = next(iter(mapping))
        self.assertIsNone(restore(masked.replace(token, ""), mapping))
        self.assertIsNone(restore(masked + token, mapping))

    def test_revisions_do_not_override_changed_source(self):
        revisions = {"1":{"originalTitle":"original","title":"人工修訂"}}
        item = {"process":"1","originalTitle":"changed","title":"新公告"}
        self.assertFalse(apply_revision(item, revisions))
        self.assertEqual(item["title"], "新公告")
        item["originalTitle"] = "original"
        self.assertTrue(apply_revision(item, revisions))
        self.assertEqual(item["title"], "人工修訂")

    def test_quality_and_cache(self):
        self.assertTrue(issues("fungicides"))
        self.assertTrue(issues("ZXQ1QXZ"))
        self.assertFalse(issues("殺菌劑採購"))
        self.assertNotEqual(cache_key("same","es","model"), cache_key("same","en","model"))

unittest.main()
