import json
import os
import unittest

from data import fetch_metadata

class FetchMetadataTest(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(os.path.dirname(__file__), 'Algeria.json')) as file:
            self.algeria = json.load(file)

    def tearDown(self):
        pass

    def test_get_value(self):
        desc = fetch_metadata.get_value(self.algeria, '/common/topic/description')
        self.assertTrue(desc.startswith("Algeria, officially People's"))

    def test_trim_description(self):
        desc = fetch_metadata.get_value(self.algeria, '/common/topic/description')

        self.assertEqual("Algeria, officially People's Democratic Republic of Algeria, is a country in the Maghreb region of North Africa on the Mediterranean coast. Its capital and most populous city is Algiers.", fetch_metadata.trim_description(desc, 200))

    def test_extract_algeria(self):
        pop = self.algeria['property']['/location/statistical_region/population']
        md = {}
        fetch_metadata.extract_population(pop, md)
        self.assertEqual(12945462, md['population'])
        self.assertEqual("1968", md['population_date'])
        self.assertEqual("World Bank", md['population_source'])
        self.assertEqual("http://data.worldbank.org/indicator/SP.POP.TOTL", md['population_source_url'])


if __name__ == '__main__':
    unittest.main()
