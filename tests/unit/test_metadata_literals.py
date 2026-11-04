"""Render metadata macros without a database; untrusted names must remain SQL values."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import Environment

MACROS = Path(__file__).resolve().parents[2] / "dbt/include/tidbcloudlake/macros"


class MetadataLiteralTest(unittest.TestCase):
    def setUp(self):
        self.queries = []

        def statement(name, caller=None, **kwargs):
            self.queries.append(caller())
            return ""

        env = Environment(extensions=["jinja2.ext.do"])
        source = "\n".join((MACROS / path).read_text() for path in [
            "utils.sql", "adapters.sql", "adapters/relation.sql", "catalog.sql",
        ])
        self.macros = env.from_string(source).make_module({
            "statement": statement,
            "load_result": lambda name: SimpleNamespace(table=[]),
            "return": lambda value: value,
        })

    def test_metadata_names_remain_single_literals(self):
        # A backslash before a quote defeated quote-only escaping. The backslash-n
        # and Unicode also protect the existing value semantics for legal names.
        for name in ["orders", "O'Reilly", "\\' OR 1=1 --", "C:\\new\\file", "資料"]:
            with self.subTest(name=name):
                literal = "'" + name.replace("\\", "\\\\").replace("'", "''") + "'"
                relation = SimpleNamespace(identifier=name, schema=name)
                self.macros.tidbcloudlake__get_columns_in_relation(relation)
                self.assertIn("table = " + literal, self.queries[-1])
                self.assertIn("database = " + literal, self.queries[-1])
                self.macros.tidbcloudlake__list_relations_without_caching(relation)
                self.assertIn("database = " + literal, self.queries[-1])
                self.macros.tidbcloudlake__get_database(name)
                self.assertIn("name = " + literal, self.queries[-1])
                self.macros.tidbcloudlake__get_catalog(None, [name])
                self.assertEqual(2, self.queries[-1].count("in (" + literal + ")"))


if __name__ == "__main__":
    unittest.main()
